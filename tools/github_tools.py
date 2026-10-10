"""GitHub issue helpers with safe draft-first behavior."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

DEFAULT_LABELS = ["agent-generated"]


def create_issue_draft(
    title: str,
    body: str,
    labels: list[str] | None = None,
) -> dict:
    """Create a local GitHub issue draft without calling GitHub."""
    issue_labels = labels if labels is not None else DEFAULT_LABELS.copy()
    return {
        "title": title,
        "body": body,
        "labels": issue_labels,
        "ready_to_create": bool(title.strip() and body.strip()),
    }


def create_github_issue(
    owner: str,
    repo: str,
    title: str,
    body: str,
    token: str | None = None,
    labels: list[str] | None = None,
) -> dict:
    """Create a GitHub issue when an explicit token is provided.

    Without a token, this function never calls the network and returns a draft
    plus a warning.
    """
    issue_labels = labels if labels is not None else DEFAULT_LABELS.copy()
    if not token:
        draft = create_issue_draft(title=title, body=body, labels=issue_labels)
        return {
            **draft,
            "created": False,
            "warning": "GitHub token missing; returning draft only.",
        }

    payload = json.dumps(
        {
            "title": title,
            "body": body,
            "labels": issue_labels,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        url=f"https://api.github.com/repos/{owner}/{repo}/issues",
        data=payload,
        method="POST",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "agentops-copilot",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
        return {
            "created": True,
            "url": response_payload.get("html_url", ""),
            "number": response_payload.get("number"),
        }
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as error:
        return {
            "created": False,
            "error": str(error),
        }
    except json.JSONDecodeError as error:
        return {
            "created": False,
            "error": f"Invalid GitHub API response: {error}",
        }
