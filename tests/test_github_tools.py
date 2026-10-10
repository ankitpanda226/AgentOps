"""Tests for safe GitHub issue helpers."""

from tools.github_tools import create_github_issue, create_issue_draft


def test_create_issue_draft_defaults_label() -> None:
    """Issue drafts should default to an agent-generated label."""
    draft = create_issue_draft("Improve docs", "Add workflow examples.")

    assert draft == {
        "title": "Improve docs",
        "body": "Add workflow examples.",
        "labels": ["agent-generated"],
        "ready_to_create": True,
    }


def test_create_issue_draft_requires_title_and_body() -> None:
    """Issue drafts should only be ready when title and body are non-empty."""
    missing_title = create_issue_draft("", "Body")
    missing_body = create_issue_draft("Title", " ")

    assert missing_title["ready_to_create"] is False
    assert missing_body["ready_to_create"] is False


def test_create_github_issue_without_token_returns_draft_warning() -> None:
    """Without a token, create_github_issue should not call GitHub."""
    result = create_github_issue(
        owner="octocat",
        repo="hello-world",
        title="Draft issue",
        body="Issue body",
    )

    assert result == {
        "title": "Draft issue",
        "body": "Issue body",
        "labels": ["agent-generated"],
        "ready_to_create": True,
        "created": False,
        "warning": "GitHub token missing; returning draft only.",
    }
