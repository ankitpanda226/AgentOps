"""Tests for deterministic rule-based agents."""

from pathlib import Path

from agents.code_agent import CodeAgent
from agents.critic_agent import CriticAgent
from agents.docs_agent import DocsAgent
from agents.intent import should_run_tests
from agents.planner_agent import PlannerAgent
from agents.rag_agent import RAGAgent
from agents.supervisor import SupervisorAgent
from agents.workflow_report_agent import WorkflowReportAgent
from app.llm import MockLLM
from memory.memory_store import MemoryStore


class FakeVectorStore:
    """Small deterministic vector store for agent tests."""

    def search(self, query: str, k: int = 5) -> list[dict]:
        """Return fixed context."""
        return [
            {
                "file_path": "app/main.py",
                "chunk_id": 0,
                "text": f"context for {query}",
                "score": 1.0,
            }
        ][:k]


def test_planner_agent_creates_structured_plan() -> None:
    """PlannerAgent should return the expected plan shape."""
    plan = PlannerAgent().create_plan("Implement repository search")

    assert plan["goal"] == "Implement repository search"
    assert "retriever" in plan["needed_tools"]
    assert len(plan["steps"]) >= 5
    assert plan["risks"]
    assert plan["success_criteria"]


def test_planner_infers_test_tool() -> None:
    """PlannerAgent should include pytest tooling for test-like requests."""
    plan = PlannerAgent().create_plan("Fix this pytest failure")

    assert "run_pytest" in plan["needed_tools"]


def test_should_run_tests_false_for_without_running_tests() -> None:
    """Test intent should respect explicit negation."""
    assert (
        should_run_tests(
            "Explain how you would investigate a bug in tool execution without running tests"
        )
        is False
    )


def test_should_run_tests_false_for_do_not_run_tests() -> None:
    """Test intent should respect do-not-run phrasing."""
    assert should_run_tests("Plan the fix, but do not run tests") is False


def test_should_run_tests_true_for_run_pytest() -> None:
    """Test intent should trigger only for explicit test execution requests."""
    assert should_run_tests("Run pytest for the failing behavior") is True


def test_planner_does_not_include_pytest_when_negated() -> None:
    """PlannerAgent should not include pytest when test execution is negated."""
    plan = PlannerAgent().create_plan(
        "Explain how you would investigate a bug without running tests"
    )

    assert "run_pytest" not in plan["needed_tools"]


def test_rag_agent_returns_context() -> None:
    """RAGAgent should return context and sources."""
    result = RAGAgent(FakeVectorStore()).answer_with_context("health endpoint")

    assert result["answer"] == "Retrieved 1 relevant context chunks for: health endpoint"
    assert result["context"][0]["file_path"] == "app/main.py"
    assert result["sources"] == ["app/main.py"]


def test_code_agent_handles_missing_file(tmp_path: Path) -> None:
    """CodeAgent should report per-file failures without raising."""
    missing = tmp_path / "missing.py"

    result = CodeAgent().inspect_files([str(missing)])

    assert result["files"][0]["path"] == str(missing)
    assert result["files"][0]["success"] is False
    assert result["files"][0]["content"] == ""
    assert result["files"][0]["error"]


def test_docs_agent_generates_issue_draft() -> None:
    """DocsAgent should include request, plan, context sources, and criteria."""
    plan = PlannerAgent().create_plan("Add memory tests")
    context = [{"file_path": "memory/memory_store.py", "text": "MemoryStore"}]

    draft = DocsAgent().generate_issue_draft("Add memory tests", plan, context)

    assert draft["title"] == "Add memory tests"
    assert "## Request Summary" in draft["body"]
    assert "memory/memory_store.py" in draft["body"]
    assert draft["acceptance_criteria"] == plan["success_criteria"]


def test_critic_warns_when_context_missing_for_code_request() -> None:
    """CriticAgent should warn when a code request lacks context."""
    critique = CriticAgent().critique_output(
        "Inspect the implementation code",
        {
            "plan": {"steps": ["Retrieve context"]},
            "context": [],
            "final_answer": "This answer is long enough to avoid vague warning.",
        },
    )

    assert critique["passed"] is False
    assert "context" in critique["missing_items"]


def test_supervisor_handles_request_with_memory(tmp_path: Path) -> None:
    """SupervisorAgent should orchestrate agents and persist task memory."""
    memory_store = MemoryStore(str(tmp_path / "agent_memory.db"))
    supervisor = SupervisorAgent(
        vector_store=FakeVectorStore(),
        memory_store=memory_store,
    )

    result = supervisor.handle_request("Create a GitHub issue for code cleanup")

    assert result["task_id"] == 1
    assert result["plan"]["goal"] == "Create a GitHub issue for code cleanup"
    assert result["context"][0]["file_path"] == "app/main.py"
    assert result["issue_draft"]["title"] == "Create a GitHub issue for code cleanup"
    assert result["test_result"] is None
    assert result["final_answer"]

    task = memory_store.get_task(result["task_id"])
    assert task is not None
    assert task["final_answer"] == result["final_answer"]
    assert task["decisions"][0]["decision"] == "Created rule-based plan"
    assert task["tool_calls"][0]["tool_name"] == "retriever"


def test_planner_accepts_mock_llm() -> None:
    """PlannerAgent should accept an optional LLM for goal wording."""
    plan = PlannerAgent(llm=MockLLM()).create_plan("Add API docs")

    assert plan["goal"] == (
        "MockLLM response: Summarize this request as one concise goal: Add API docs"
    )
    assert "retriever" in plan["needed_tools"]


def test_docs_agent_accepts_mock_llm() -> None:
    """DocsAgent should accept an optional LLM for issue body wording."""
    plan = PlannerAgent().create_plan("Add docs")

    draft = DocsAgent(llm=MockLLM()).generate_issue_draft("Add docs", plan, [])

    assert draft["title"] == "Add docs"
    assert "## LLM Draft Note" in draft["body"]
    assert "MockLLM response:" in draft["body"]
    assert draft["acceptance_criteria"] == plan["success_criteria"]


def test_critic_agent_accepts_mock_llm() -> None:
    """CriticAgent should accept an optional LLM critique note."""
    critique = CriticAgent(llm=MockLLM()).critique_output(
        "Summarize project",
        {
            "plan": {"steps": ["Answer"]},
            "context": [],
            "final_answer": "This is a sufficiently clear final answer.",
        },
    )

    assert critique["passed"] is False
    assert any("MockLLM response:" in warning for warning in critique["warnings"])


def test_supervisor_accepts_mock_llm(tmp_path: Path) -> None:
    """SupervisorAgent should pass the optional LLM to relevant agents."""
    memory_store = MemoryStore(str(tmp_path / "llm_memory.db"))
    supervisor = SupervisorAgent(
        vector_store=FakeVectorStore(),
        memory_store=memory_store,
        llm=MockLLM(),
    )

    result = supervisor.handle_request("Create implementation plan")

    assert result["task_id"] == 1
    assert result["plan"]["goal"].startswith("MockLLM response:")
    assert "MockLLM response:" in result["issue_draft"]["body"]
    assert any(
        "MockLLM response:" in warning for warning in result["critique"]["warnings"]
    )


def test_supervisor_final_answer_has_next_steps(tmp_path: Path) -> None:
    """SupervisorAgent final answers should be descriptive and actionable."""
    memory_store = MemoryStore(str(tmp_path / "final_answer_memory.db"))
    supervisor = SupervisorAgent(
        vector_store=FakeVectorStore(),
        memory_store=memory_store,
    )

    result = supervisor.handle_request("Explain the API endpoint implementation")

    assert "# AgentOps Workflow Report" in result["final_answer"]
    assert "## 3. Recommended Developer Workflow" in result["final_answer"]
    assert "## 5. Testing and Validation Plan" in result["final_answer"]
    assert "app/main.py" in result["final_answer"]
    assert "## 8. Final Next Steps" in result["final_answer"]


def test_critic_does_not_warn_for_descriptive_final_answer() -> None:
    """CriticAgent should accept detailed final answers with next steps."""
    final_answer = (
        "Goal: explain the API implementation clearly. Tools selected: retriever "
        "and create_issue_draft. Retrieved two context chunks from app/main.py and "
        "agents/graph.py. Test status: tests were not run because they were not "
        "required. Issue draft title: Explain the API. Critique status: pending. "
        "Recommended next steps: review the source files, confirm the plan, run "
        "targeted tests, and use the issue draft as the checklist."
    )

    critique = CriticAgent().critique_output(
        "Explain the API implementation code",
        {
            "plan": {"steps": ["Retrieve context"]},
            "context": [{"file_path": "app/main.py"}],
            "final_answer": final_answer,
        },
    )

    assert "Final answer may be too vague." not in critique["warnings"]


def test_workflow_report_contains_required_sections() -> None:
    """WorkflowReportAgent should generate the required Markdown sections."""
    report = WorkflowReportAgent().generate_report(
        user_request="Add API endpoint",
        plan=PlannerAgent().create_plan("Add API endpoint"),
        context=[],
        issue_draft=DocsAgent().generate_issue_draft(
            "Add API endpoint",
            PlannerAgent().create_plan("Add API endpoint"),
            [],
        ),
    )

    for section in [
        "# AgentOps Workflow Report",
        "## 1. Request Summary",
        "## 2. What I Found in the Repository",
        "## 3. Recommended Developer Workflow",
        "## 4. Step-by-Step Implementation Plan",
        "## 5. Testing and Validation Plan",
        "## 6. Risks and Safety Checks",
        "## 7. GitHub Issue Draft",
        "## 8. Final Next Steps",
    ]:
        assert section in report


def test_workflow_report_mentions_relevant_files() -> None:
    """Workflow reports should mention retrieved file paths and chunk ids."""
    report = WorkflowReportAgent().generate_report(
        user_request="Explain retrieval code",
        plan=PlannerAgent().create_plan("Explain retrieval code"),
        context=[
            {
                "file_path": "rag/retriever.py",
                "chunk_id": 3,
                "text": "retrieve_context calls vector_store.search",
            }
        ],
        issue_draft={"title": "Explain retrieval code", "body": "", "acceptance_criteria": []},
    )

    assert "rag/retriever.py" in report
    assert "chunk `3`" in report
    assert "retrieval or indexing" in report


def test_workflow_report_auth_request_has_auth_specific_steps() -> None:
    """Auth requests should include auth-specific implementation guidance."""
    report = WorkflowReportAgent().generate_report(
        user_request="Add authentication to the API endpoint",
        plan=PlannerAgent().create_plan("Add authentication to the API endpoint"),
        context=[],
        issue_draft={"title": "Add auth", "body": "", "acceptance_criteria": []},
    )

    assert "auth middleware" in report
    assert "request validation" in report
    assert "user, session, and token handling" in report


def test_workflow_report_tool_request_has_tool_specific_steps() -> None:
    """Tool requests should include tool integration guidance."""
    report = WorkflowReportAgent().generate_report(
        user_request="Add tool calling support for a new repo search tool",
        plan=PlannerAgent().create_plan(
            "Add tool calling support for a new repo search tool"
        ),
        context=[],
        issue_draft={"title": "Add tool", "body": "", "acceptance_criteria": []},
    )

    assert "tool base class/interface" in report
    assert "structured input schema" in report
    assert "Register the tool" in report


def test_workflow_report_without_tests_removes_pytest_recommendations() -> None:
    """Workflow reports should remove pytest commands when tests are negated."""
    report = WorkflowReportAgent().generate_report(
        user_request="Investigate a bug in tool execution without running tests",
        plan=PlannerAgent().create_plan(
            "Investigate a bug in tool execution without running tests"
        ),
        context=[],
        issue_draft={
            "title": "Investigate tool execution",
            "body": "",
            "acceptance_criteria": [],
        },
    )

    assert "Add or update tests that prove the behavior works." not in report
    assert "Run validation with pytest" not in report
    assert "Add targeted tests and run `python -m pytest`" not in report
    assert "Run tests before committing or opening a PR." not in report
    assert "read the test output before patching" not in report
    assert "rerun tests" not in report
    assert "Tests were intentionally not run" in report


def test_workflow_report_without_tests_mentions_manual_review() -> None:
    """Workflow reports should recommend manual investigation when tests are skipped."""
    report = WorkflowReportAgent().generate_report(
        user_request="Explain how to investigate a bug in tool execution without running tests",
        plan=PlannerAgent().create_plan(
            "Explain how to investigate a bug in tool execution without running tests"
        ),
        context=[],
        issue_draft={
            "title": "Investigate tool execution",
            "body": "",
            "acceptance_criteria": [],
        },
    )

    assert "Review the relevant code paths manually." in report
    assert "Trace tool input parsing, tool execution, callbacks, and error handling." in report
    assert "Document which targeted tests should be run later, but do not execute them now." in report
    assert "Review the investigation plan manually." in report
    assert "List targeted tests to run later if test execution becomes allowed." in report


def test_issue_draft_or_report_mentions_tests_intentionally_skipped() -> None:
    """Issue drafts and reports should record intentional test skipping."""
    request = "Investigate a bug in tool execution without running tests"
    plan = PlannerAgent().create_plan(request)
    draft = DocsAgent().generate_issue_draft(request, plan, [])
    report = WorkflowReportAgent().generate_report(
        user_request=request,
        plan=plan,
        context=[],
        issue_draft=draft,
    )

    assert "Tests were intentionally not run" in draft["body"]
    assert "Tests were intentionally not run" in report


def test_supervisor_final_answer_is_workflow_report(tmp_path: Path) -> None:
    """SupervisorAgent should return the workflow report as final_answer."""
    memory_store = MemoryStore(str(tmp_path / "workflow_report_memory.db"))
    supervisor = SupervisorAgent(
        vector_store=FakeVectorStore(),
        memory_store=memory_store,
    )

    result = supervisor.handle_request("Create implementation plan")

    assert result["final_answer"].startswith("# AgentOps Workflow Report")
    assert "## 8. Final Next Steps" in result["final_answer"]


def test_supervisor_skips_tests_when_negated(tmp_path: Path) -> None:
    """SupervisorAgent should not run tests when request explicitly negates them."""
    memory_store = MemoryStore(str(tmp_path / "negated_tests_memory.db"))
    supervisor = SupervisorAgent(
        vector_store=FakeVectorStore(),
        memory_store=memory_store,
    )

    result = supervisor.handle_request(
        "Explain how you would investigate a bug in tool execution without running tests"
    )

    assert result["test_result"] is None
    assert "Tests were intentionally not run" in result["final_answer"]


def test_critic_passes_workflow_report() -> None:
    """CriticAgent should not flag a complete workflow report as vague."""
    report = WorkflowReportAgent().generate_report(
        user_request="Explain API code",
        plan=PlannerAgent().create_plan("Explain API code"),
        context=[{"file_path": "app/main.py", "chunk_id": 0, "text": "FastAPI route"}],
        issue_draft={"title": "Explain API code", "body": "Body", "acceptance_criteria": []},
    )

    critique = CriticAgent().critique_output(
        "Explain API code",
        {
            "plan": {"steps": ["Retrieve context"]},
            "context": [{"file_path": "app/main.py"}],
            "final_answer": report,
        },
    )

    assert "Final answer may be too vague." not in critique["warnings"]
