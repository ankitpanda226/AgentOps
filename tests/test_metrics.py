"""Tests for evaluation metrics."""

from evals.metrics import (
    aggregate_score,
    keyword_coverage,
    required_fields_score,
    tool_coverage,
)


def test_keyword_coverage_full_match() -> None:
    """keyword_coverage should return 1.0 when all keywords match."""
    score = keyword_coverage("The plan uses RAG context.", ["plan", "rag"])

    assert score == 1.0


def test_keyword_coverage_partial_match() -> None:
    """keyword_coverage should score partial keyword matches."""
    score = keyword_coverage("The plan uses context.", ["plan", "rag"])

    assert score == 0.5


def test_required_fields_score_supports_nested_paths() -> None:
    """required_fields_score should support nested dot paths and list indexes."""
    output = {
        "plan": {"steps": ["inspect"]},
        "issue_draft": {"body": "details"},
        "context": [{"file_path": "app/main.py"}],
    }

    score = required_fields_score(
        output,
        ["plan.steps", "issue_draft.body", "context.0.file_path", "missing.path"],
    )

    assert score == 0.75


def test_tool_coverage_case_insensitive() -> None:
    """tool_coverage should compare tool names case-insensitively."""
    score = tool_coverage(["Retriever", "RUN_PYTEST"], ["retriever", "run_pytest"])

    assert score == 1.0


def test_aggregate_score_averages_metrics() -> None:
    """aggregate_score should average numeric metric values."""
    score = aggregate_score({"a": 1.0, "b": 0.5, "label": "ignored"})

    assert score == 0.75
