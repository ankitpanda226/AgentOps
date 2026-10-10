"""Markdown export of workflow evidence and the simulated PR proposal."""

import json

from agents.pr_simulator_agent import render_pr_simulation


def _details(value: object) -> str:
    """Render structured evidence without letting content close a code fence."""
    if isinstance(value, str):
        return value
    return "\n".join(
        "    " + line
        for line in json.dumps(value, indent=2, ensure_ascii=False).splitlines()
    )


def build_markdown_export(result: dict) -> str:
    """Export all workflow sections, including legacy responses without simulation."""
    final_answer = str(result.get("final_answer") or "No final answer available.")
    simulation = result.get("pr_simulation")
    simulation_markdown = render_pr_simulation(simulation) if simulation else ""
    # Graph reports already include the proposal. Place that exact section at the
    # end of the export once, preserving all other final-answer content verbatim.
    if simulation_markdown and final_answer.endswith(simulation_markdown):
        final_answer = final_answer[: -len(simulation_markdown)].rstrip()
    lines = [
        "# AgentOps Report Export",
        "",
        "## Final answer",
        "",
        final_answer,
        "",
        "## Plan",
        "",
        _details(result.get("plan") or {}),
        "",
        "## Retrieved context sources",
        "",
    ]
    for source in result.get("context") or []:
        lines.append(
            f"- `{source.get('file_path', 'unknown')}` "
            f"(chunk {source.get('chunk_id', 'unknown')})"
        )
    if not result.get("context"):
        lines.append("No repository context was retrieved.")
    issue = result.get("issue_draft") or {}
    lines.extend(
        [
            "",
            "## Issue draft",
            "",
            str(issue.get("title", "Untitled issue")),
            "",
            str(issue.get("body", "No issue body available.")),
            "",
            "**Acceptance criteria:**",
            "",
            *[f"- {item}" for item in issue.get("acceptance_criteria", [])],
            "",
            "## Test result",
            "",
        ]
    )
    test_result = result.get("test_result")
    lines.append(
        _details(test_result)
        if test_result is not None
        else "Tests were not run; no execution result is available."
    )
    if result.get("test_analysis") is not None:
        lines.extend(["", "## Test analysis", "", _details(result["test_analysis"])])
    lines.extend(["", "## Critique", "", _details(result.get("critique") or {})])
    if simulation_markdown:
        lines.extend(["", simulation_markdown])
    return "\n".join(lines) + "\n"
