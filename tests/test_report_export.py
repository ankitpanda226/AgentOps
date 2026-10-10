"""Complete Markdown exports with optional legacy fields and source evidence."""

from app.report_export import build_markdown_export
from agents.graph import run_agent_workflow
from agents.pr_simulator_agent import PRSimulatorAgent


def test_markdown_export_contains_pr_simulation():
    simulation = PRSimulatorAgent().simulate_pr(
        "Add auth middleware", [{"file_path": "app/auth.py", "text": "auth"}], {}
    )
    result = {
        "final_answer": "Existing workflow report",
        "plan": {"goal": "Protect routes"},
        "context": [{"file_path": "app/auth.py", "chunk_id": 3}],
        "issue_draft": {
            "title": "Auth issue",
            "body": "Enforce auth",
            "acceptance_criteria": ["Reject invalid credentials"],
        },
        "test_result": {"success": False, "exit_code": -2},
        "test_analysis": "Run targeted validation later",
        "critique": {"warnings": ["Review credentials"]},
        "pr_simulation": simulation,
    }
    markdown = build_markdown_export(result)
    for expected in (
        "Existing workflow report",
        "Protect routes",
        "app/auth.py",
        "chunk 3",
        "Auth issue",
        "Enforce auth",
        "Reject invalid credentials",
        '"exit_code": -2',
        "Run targeted validation later",
        "Review credentials",
        "Agentic PR Simulation",
        simulation["pr_title"],
        simulation["pr_summary"],
        "Merge readiness: 70/100",
        simulation["merge_readiness_reason"],
        "Files changed",
        "Pseudo-diff",
        "Before",
        "After",
        "Test plan",
        "Risk review",
        "Reviewer questions",
    ):
        assert expected in markdown


def test_export_does_not_duplicate_proposal_in_final_answer():
    result = run_agent_workflow("Add auth middleware", simulate_pr=True)
    markdown = build_markdown_export(result)
    assert markdown.count("## Agentic PR Simulation") == 1
    assert markdown.index("## Critique") < markdown.index("## Agentic PR Simulation")
    assert "AgentOps Workflow Report" in markdown


def test_export_supports_legacy_response_and_no_test_result():
    markdown = build_markdown_export({"final_answer": "Legacy answer"})
    assert "Legacy answer" in markdown
    assert "Tests were not run" in markdown
    assert "No repository context" in markdown
    assert "Agentic PR Simulation" not in markdown
