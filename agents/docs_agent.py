"""Rule-based documentation and issue drafting agent."""

from app.llm import BaseLLM
from agents.intent import has_test_negation


class DocsAgent:
    """Generate deterministic issue drafts from request, plan, and context."""

    def __init__(self, llm: BaseLLM | None = None) -> None:
        """Create a docs agent with an optional LLM for body wording."""
        self.llm = llm

    def generate_issue_draft(
        self, user_request: str, plan: dict, context: list[dict]
    ) -> dict:
        """Create a structured GitHub issue draft."""
        title = self._title_from_request(user_request)
        steps = plan.get("steps", [])
        risks = plan.get("risks", [])
        sources = [
            str(item["file_path"])
            for item in context
            if item.get("file_path") is not None
        ]

        body = "\n".join(
            [
                "## Request Summary",
                user_request,
                "",
                "## Plan",
                *[f"- {step}" for step in steps],
                "",
                "## Relevant Context Sources",
                *([f"- {source}" for source in list(dict.fromkeys(sources))] or ["- None retrieved"]),
                "",
                "## Risks",
                *[f"- {risk}" for risk in risks],
            ]
        )
        if has_test_negation(user_request):
            body = (
                f"{body}\n\n"
                "## Test Execution Note\n"
                "Tests were intentionally not run because the request asked not to run them."
            )
        if self.llm is not None:
            improved_body = self.llm.generate(
                "Improve the wording of a GitHub issue body.",
                body,
            )
            body = f"{body}\n\n## LLM Draft Note\n{improved_body}"

        return {
            "title": title,
            "body": body,
            "acceptance_criteria": plan.get("success_criteria", []),
        }

    def _title_from_request(self, user_request: str) -> str:
        cleaned = " ".join(user_request.split())
        if not cleaned:
            return "AgentOps Copilot task"
        if len(cleaned) <= 80:
            return cleaned
        return cleaned[:77].rstrip() + "..."
