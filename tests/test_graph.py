"""Tests for LangGraph-compatible agent orchestration."""

from pathlib import Path

from agents.graph import run_agent_workflow
from agents.supervisor import SupervisorAgent
from memory.memory_store import MemoryStore


class FakeVectorStore:
    """Deterministic vector store for workflow tests."""

    def search(self, query: str, k: int = 5) -> list[dict]:
        """Return fixed context for a query."""
        return [
            {
                "file_path": "rag/retriever.py",
                "chunk_id": 0,
                "text": f"retrieved context for {query}",
                "score": 1.0,
            }
        ][:k]


def test_run_agent_workflow_returns_plan() -> None:
    """The graph workflow should produce a structured plan."""
    result = run_agent_workflow("Explain the project")

    assert result["plan"] is not None
    assert result["plan"]["goal"] == "Explain the project"
    assert result["issue_draft"] is not None
    assert result["final_answer"]


def test_run_agent_workflow_runs_tests_for_explicit_test_request(
    tmp_path: Path,
) -> None:
    """The graph workflow should run tests only for explicit test requests."""
    test_file = tmp_path / "test_bug.py"
    test_file.write_text("def test_bug_path():\n    assert True\n", encoding="utf-8")

    result = run_agent_workflow("Run pytest for this bug", repo_path=str(test_file))

    assert result["test_result"] is not None
    assert result["test_result"]["success"] is True
    assert "run_pytest" in result["tools_used"]


def test_graph_skips_tests_when_negated() -> None:
    """The graph workflow should honor explicit requests not to run tests."""
    result = run_agent_workflow(
        "Explain how you would investigate a bug in tool execution without running tests"
    )

    assert result["test_result"] is None
    assert "run_pytest" not in result["tools_used"]
    assert "Tests were intentionally not run" in result["final_answer"]


def test_run_agent_workflow_skips_tests_for_general_request() -> None:
    """The graph workflow should skip tests for general requests."""
    result = run_agent_workflow("Draft implementation notes")

    assert result["test_result"] is None
    assert "run_pytest" not in result["tools_used"]


def test_uploaded_repo_does_not_run_full_pytest_by_default() -> None:
    """Uploaded repositories should not trigger broad automatic pytest runs."""
    result = run_agent_workflow(
        "Run pytest for this uploaded repository",
        repo_path="uploads/repos/example/repo",
    )

    assert result["test_result"] is not None
    assert result["test_result"]["success"] is False
    assert result["test_result"]["exit_code"] == -2
    assert (
        result["test_result"]["stderr"]
        == "Tests were not run automatically for uploaded repositories. Provide a targeted test path to avoid large unsafe test runs."
    )
    assert "run_pytest" in result["tools_used"]


def test_run_agent_workflow_retrieves_context_with_fake_vector_store() -> None:
    """The graph workflow should retrieve context when a vector store exists."""
    result = run_agent_workflow(
        "Explain retriever code",
        vector_store=FakeVectorStore(),
    )

    assert result["context"][0]["file_path"] == "rag/retriever.py"
    assert "retriever" in result["tools_used"]


def test_supervisor_still_handles_request_after_graph_refactor(tmp_path: Path) -> None:
    """SupervisorAgent should keep its public interface after graph refactor."""
    memory_store = MemoryStore(str(tmp_path / "supervisor_memory.db"))
    supervisor = SupervisorAgent(
        vector_store=FakeVectorStore(),
        memory_store=memory_store,
    )

    result = supervisor.handle_request("Create a GitHub issue for repo docs")

    assert result["task_id"] == 1
    assert result["plan"]["goal"] == "Create a GitHub issue for repo docs"
    assert result["context"][0]["file_path"] == "rag/retriever.py"
    assert result["test_result"] is None
    assert result["final_answer"]

    task = memory_store.get_task(result["task_id"])
    assert task is not None
    assert task["final_answer"] == result["final_answer"]


def test_graph_final_answer_is_workflow_report() -> None:
    """Graph workflow should return the Markdown workflow report."""
    result = run_agent_workflow(
        "Explain API endpoint implementation",
        vector_store=FakeVectorStore(),
    )

    assert result["final_answer"].startswith("# AgentOps Workflow Report")
    assert "## 3. Recommended Developer Workflow" in result["final_answer"]
    assert "## 5. Testing and Validation Plan" in result["final_answer"]
    assert "## 8. Final Next Steps" in result["final_answer"]
