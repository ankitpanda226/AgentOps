"""PR simulation safety, deterministic output, and API compatibility."""

from pathlib import Path
from unittest.mock import Mock

from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.schemas import AskRequest, AskResponse
from agents.graph import run_agent_workflow
from agents.pr_simulator_agent import PRSimulatorAgent, render_pr_simulation
from memory.memory_store import MemoryStore
from rag.vector_store import VectorStore


CONTEXT = [
    {"file_path": "app/api.py", "text": "def get_item(item_id): return items[item_id]"},
    {"file_path": "tests/test_api.py", "text": "def test_get_item(): pass"},
    {"file_path": "README.md", "text": "API usage"},
]


class EvidenceStore:
    def search(self, query, k=5):
        return CONTEXT[:k]


@pytest.mark.parametrize("fallback", [False, True])
def test_simulation_never_runs_tests_or_llm(monkeypatch, fallback):
    monkeypatch.setenv("AGENTOPS_DISABLE_LANGGRAPH", "1" if fallback else "0")
    forbidden = Mock(side_effect=AssertionError("Executable tool invoked"))
    monkeypatch.setattr("agents.test_agent.run_pytest", forbidden)
    llm = Mock()
    llm.generate = forbidden
    results = [
        run_agent_workflow(
            "Add an API endpoint and run pytest",
            repo_path="uploads/repos/example/repo",
            vector_store=EvidenceStore(),
            llm=llm,
            simulate_pr=True,
        )
        for _ in range(2)
    ]
    assert results[0] == results[1]
    result = results[0]
    forbidden.assert_not_called()
    assert result["test_result"] is None
    assert "run_pytest" not in result["tools_used"]
    assert "run_pytest" not in result["plan"]["needed_tools"]
    assert "simulate_pr" in result["tools_used"]
    assert "test_result" not in result["critique"]["missing_items"]
    assert "## Agentic PR Simulation" in result["final_answer"]
    assert "not ready" in result["final_answer"]
    simulation = result["pr_simulation"]
    assert simulation["merge_readiness_score"] == 70
    assert "not ready" in simulation["merge_readiness_reason"]
    assert {c["file_path"] for c in simulation["files_changed"]} == {
        c["file_path"] for c in CONTEXT
    }


def test_graph_and_fallback_simulation_match(monkeypatch):
    monkeypatch.setenv("AGENTOPS_DISABLE_LANGGRAPH", "0")
    graph = run_agent_workflow(
        "Add auth checks", vector_store=EvidenceStore(), simulate_pr=True
    )
    monkeypatch.setenv("AGENTOPS_DISABLE_LANGGRAPH", "1")
    fallback = run_agent_workflow(
        "Add auth checks", vector_store=EvidenceStore(), simulate_pr=True
    )
    assert graph == fallback


def test_missing_context_does_not_invent_files():
    simulation = PRSimulatorAgent().simulate_pr("Add auth", [], {})
    assert simulation["files_changed"] == []
    assert simulation["merge_readiness_score"] == 45
    assert "missing usable repository context" in simulation["merge_readiness_reason"]
    assert "No candidate files" in render_pr_simulation(simulation)
    assert any("authorization" in risk for risk in simulation["risk_review"])


def test_candidates_are_deduplicated_bounded_and_evidence_based():
    context = [
        CONTEXT[0],
        CONTEXT[0],
        {"file_path": "../escape.py", "text": "x"},
        {"file_path": "empty.py", "text": ""},
        {"text": "No path"},
    ]
    context += [{"file_path": f"source{i}.py", "text": "x" * 2000} for i in range(8)]
    simulation = PRSimulatorAgent().simulate_pr("Update code", context, {})
    changes = simulation["files_changed"]
    assert len(changes) == 6
    assert len({c["file_path"] for c in changes}) == 6
    assert all(c["file_path"] != "../escape.py" for c in changes)
    diffs = simulation["pseudo_diff"]
    assert len(diffs) == len(changes)
    assert all(len(diff["before"]) <= 260 for diff in diffs)
    assert "Retrieved excerpt" in diffs[0]["before"]
    assert "Proposed:" in diffs[0]["after"]
    assert "without an excerpt" in diffs[1]["before"]


@pytest.mark.parametrize(
    "phrase",
    ["without running tests", "skip tests", "do not run tests", "don't run tests"],
)
def test_explicit_test_negation_is_preserved(phrase, monkeypatch):
    forbidden = Mock(side_effect=AssertionError("Tests executed"))
    monkeypatch.setattr("agents.test_agent.run_pytest", forbidden)
    output = run_agent_workflow(f"Fix API; run pytest; {phrase}", simulate_pr=True)
    assert "explicitly deferred" in output["pr_simulation"]["test_plan"][0]
    assert output["test_result"] is None
    forbidden.assert_not_called()


def test_legacy_api_models_remain_valid():
    assert AskRequest(question="Explain code").simulate_pr is False
    old = run_agent_workflow("Explain code")
    old.pop("pr_simulation")
    assert AskResponse(task_id=None, **old).pr_simulation is None


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(app.state, "vector_store", VectorStore(use_chroma=False))
    monkeypatch.setattr(
        app.state, "memory_store", MemoryStore(str(tmp_path / "memory.db"))
    )
    return TestClient(app)


def test_api_simulates_uploaded_repo_without_writes_or_execution(
    client,
    tmp_path,
    monkeypatch,
):
    from io import BytesIO
    import zipfile

    monkeypatch.setattr("app.upload_utils.UPLOAD_ROOT", str(tmp_path / "uploads/repos"))
    archive = BytesIO()
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr("repo/api.py", CONTEXT[0]["text"])
    uploaded = client.post(
        "/upload-repo",
        files={"file": ("repo.zip", archive.getvalue(), "application/zip")},
    ).json()
    selector = {"repo_id": uploaded["repo_id"]}
    assert client.post("/index", json=selector).status_code == 200
    root = Path(uploaded["repo_path"])

    def snapshot():
        return {
            str(p.relative_to(root)): p.read_bytes()
            for p in root.rglob("*")
            if p.is_file()
        }

    before = snapshot()
    forbidden = Mock(side_effect=AssertionError("Side effect in simulation"))
    monkeypatch.setattr("subprocess.run", forbidden)
    monkeypatch.setattr("socket.socket.connect", forbidden)
    monkeypatch.setattr("agents.test_agent.run_pytest", forbidden)
    response = client.post(
        "/ask",
        json={
            "question": "Add API validation and run pytest",
            "simulate_pr": True,
            **selector,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["pr_simulation"]["files_changed"][0]["file_path"].endswith("api.py")
    assert body["test_result"] is None
    assert snapshot() == before
    forbidden.assert_not_called()
    normal = client.post("/ask", json={"question": "Explain API", **selector}).json()
    assert normal["pr_simulation"]["files_changed"]
    assert snapshot() == before
    forbidden.assert_not_called()


def test_api_refuses_unindexed_or_mismatched_repo(client, tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    (a / "a.py").write_text("alpha", encoding="utf-8")
    (b / "b.py").write_text("beta", encoding="utf-8")
    request = {"question": "Change code", "repo_path": str(a), "simulate_pr": True}
    assert client.post("/ask", json=request).status_code == 409
    assert client.post("/index", json={"repo_path": str(a)}).status_code == 200
    assert client.post("/index", json={"repo_path": str(b)}).status_code == 200
    assert client.post("/ask", json=request).status_code == 409
    request["repo_path"] = str(b)
    result = client.post("/ask", json=request).json()
    assert all(c["file_path"].startswith(str(b)) for c in result["context"])
    assert (
        result["pr_simulation"]["pseudo_diff"][0]["before"] == "Retrieved excerpt: beta"
    )


def test_failed_index_preserves_previous_snapshot(client, tmp_path, monkeypatch):
    (tmp_path / "a.py").write_text("alpha", encoding="utf-8")
    assert client.post("/index", json={"repo_path": str(tmp_path)}).status_code == 200
    previous = app.state.vector_store
    monkeypatch.setattr("app.main.index_repository", Mock(side_effect=RuntimeError))
    with pytest.raises(RuntimeError):
        client.post("/index", json={"repo_path": str(tmp_path)})
    assert app.state.vector_store is previous


EXPECTED_FIELDS = {
    "pr_title",
    "pr_summary",
    "files_changed",
    "pseudo_diff",
    "test_plan",
    "risk_review",
    "reviewer_questions",
    "merge_readiness_score",
    "merge_readiness_reason",
}


def test_pr_simulator_tool_request():
    priority_paths = [
        "pkg/tools/base.py",
        "pkg/tools/simple.py",
        "pkg/tools/convert.py",
        "pkg/tools/render.py",
        "pkg/agents/tool_calling_agent.py",
        "pkg/agents/agent.py",
    ]
    context = [{"file_path": "unrelated.py", "text": "unrelated"}]
    context.extend(
        {"file_path": path, "text": "tool implementation"} for path in priority_paths
    )
    context.append(context[1])
    plan = {
        "steps": ["Confirm tool compatibility"],
        "risks": ["Existing callbacks may depend on signatures"],
        "success_criteria": ["The new tool is registered"],
    }
    simulation = PRSimulatorAgent().simulate_pr(
        "Add tool calling integration", context, plan
    )
    assert set(simulation) == EXPECTED_FIELDS
    assert [item["file_path"] for item in simulation["files_changed"]] == priority_paths
    assert all(
        set(item) == {"file_path", "change_type", "reason"}
        for item in simulation["files_changed"]
    )
    assert all(
        set(item) == {"file_path", "before", "after", "notes"}
        for item in simulation["pseudo_diff"]
    )
    text = str(simulation).lower()
    for term in (
        "schema",
        "tool class",
        "register",
        "wire",
        "tests",
        "document",
        "confirm tool compatibility",
        "existing callbacks",
        "new tool is registered",
    ):
        assert term in text
    assert "base class" in simulation["pseudo_diff"][0]["after"]
    assert "rendering" in simulation["pseudo_diff"][3]["after"]


def test_pr_simulator_auth_request():
    context = [*CONTEXT, {"file_path": "app/middleware.py", "text": "auth middleware"}]
    simulation = PRSimulatorAgent().simulate_pr(
        "Add authentication middleware", context, {}
    )
    assert simulation["files_changed"][0]["file_path"] == "app/middleware.py"
    text = str(simulation).lower()
    for term in (
        "auth middleware",
        "request",
        "schemas",
        "protected",
        "unauthorized",
        "document",
        "authorization",
    ):
        assert term in text


@pytest.mark.parametrize(
    "question, terms",
    [
        (
            "Add an API endpoint",
            ("route", "schema", "service", "endpoint tests", "document"),
        ),
        (
            "Debug a failure",
            ("smallest", "regression", "failure handling", "validation"),
        ),
        ("Update docs", ("readme", "workflow docs", "examples", "acceptance criteria")),
    ],
)
def test_pr_simulator_request_specific_proposals(question, terms):
    simulation = PRSimulatorAgent().simulate_pr(question, CONTEXT, {})
    for term in terms:
        assert term in str(simulation).lower()
    types = {
        item["file_path"]: item["change_type"] for item in simulation["files_changed"]
    }
    assert types == {
        "app/api.py": "modify",
        "tests/test_api.py": "test",
        "README.md": "docs",
    }


def test_pr_simulator_empty_context_lowers_score():
    agent = PRSimulatorAgent()
    grounded = agent.simulate_pr("Add API validation", CONTEXT, {})
    empty = agent.simulate_pr("Add API validation", [], {})
    assert grounded["merge_readiness_score"] == 70
    assert empty["merge_readiness_score"] == 45
    assert "missing" in empty["merge_readiness_reason"]
    assert empty["files_changed"] == empty["pseudo_diff"] == []
    assert empty["test_plan"] and empty["reviewer_questions"]


def test_pr_simulator_failed_tests_lowers_score():
    simulation = PRSimulatorAgent().simulate_pr(
        "Fix a bug", CONTEXT, {}, {"success": False, "exit_code": 1}
    )
    assert simulation["merge_readiness_score"] == 55
    assert "-15" in simulation["merge_readiness_reason"]
    assert "failed" in simulation["test_plan"][0]


def test_pr_simulator_passed_tests_increases_score():
    simulation = PRSimulatorAgent().simulate_pr(
        "Fix a bug", CONTEXT, {}, {"success": True, "exit_code": 0}
    )
    assert simulation["merge_readiness_score"] == 80
    assert "+10" in simulation["merge_readiness_reason"]
    assert "not merge approval" in simulation["merge_readiness_reason"]
    assert "Earlier workflow tests passed" in simulation["test_plan"][0]


def test_uploaded_safety_skip_is_not_counted_as_failed_tests():
    simulation = PRSimulatorAgent().simulate_pr(
        "Fix a bug", CONTEXT, {}, {"success": False, "exit_code": -2}
    )
    assert simulation["merge_readiness_score"] == 60
    assert "-15" not in simulation["merge_readiness_reason"]
    assert "uploaded-repository safety" in simulation["merge_readiness_reason"]


@pytest.mark.parametrize("context_penalty", [0, 25])
@pytest.mark.parametrize("warnings_penalty", [0, 10])
@pytest.mark.parametrize(
    "test_result, adjustment",
    [
        (None, 0),
        ({"success": False, "exit_code": 1}, -15),
        ({"success": False, "exit_code": -2}, -10),
        ({"success": True, "exit_code": 0}, 10),
    ],
)
def test_score_adjustments_combine(
    context_penalty, warnings_penalty, test_result, adjustment
):
    simulation = PRSimulatorAgent().simulate_pr(
        "Change API",
        [] if context_penalty else CONTEXT,
        {},
        test_result,
        {"warnings": ["Review scope"] if warnings_penalty else []},
    )
    assert simulation["merge_readiness_score"] == max(
        0, min(100, 70 - context_penalty - warnings_penalty + adjustment)
    )
    if warnings_penalty:
        assert "Critic warning: Review scope" in simulation["risk_review"]


@pytest.mark.parametrize("fallback", [False, True])
def test_simulation_consumes_completed_tests_and_critique(monkeypatch, fallback):
    monkeypatch.setenv("AGENTOPS_DISABLE_LANGGRAPH", "1" if fallback else "0")
    monkeypatch.setattr(
        "agents.test_agent.run_pytest",
        Mock(
            return_value={
                "success": False,
                "exit_code": 1,
                "stdout": "failure",
                "stderr": "",
            }
        ),
    )
    monkeypatch.setattr(
        "agents.critic_agent.CriticAgent.critique_output",
        Mock(
            return_value={
                "passed": False,
                "warnings": ["Review missing coverage"],
                "missing_items": [],
            }
        ),
    )
    original = PRSimulatorAgent.simulate_pr
    calls = []

    def inspect_inputs(self, **kwargs):
        assert kwargs["plan"] and kwargs["context"]
        assert kwargs["test_result"]["exit_code"] == 1
        assert kwargs["critique"]["warnings"] == ["Review missing coverage"]
        calls.append(kwargs)
        return original(self, **kwargs)

    monkeypatch.setattr(PRSimulatorAgent, "simulate_pr", inspect_inputs)
    result = run_agent_workflow("Run pytest for the API", vector_store=EvidenceStore())
    assert len(calls) == 1
    assert result["issue_draft"]
    assert result["pr_simulation"]["merge_readiness_score"] == 45
    assert "Review missing coverage" in str(result["pr_simulation"])


def test_ask_endpoint_returns_pr_simulation(client):
    app.state.vector_store.add_documents(CONTEXT)
    response = client.post("/ask", json={"question": "Add an API endpoint"})
    assert response.status_code == 200
    result = response.json()
    assert set(result["pr_simulation"]) == EXPECTED_FIELDS
    assert result["pr_simulation"]["merge_readiness_score"] == 70
    assert result["plan"] and result["issue_draft"] and result["critique"]
    assert result["test_result"] is None


def test_simulator_preserves_input_evidence():
    from copy import deepcopy

    inputs = [
        "Update API",
        CONTEXT,
        {"steps": ["Inspect endpoints"]},
        {"success": True, "exit_code": 0},
        {"warnings": ["Review validation"]},
    ]
    before = deepcopy(inputs)
    result = PRSimulatorAgent().simulate_pr(*inputs)
    assert inputs == before
    assert result == PRSimulatorAgent().simulate_pr(*inputs)
