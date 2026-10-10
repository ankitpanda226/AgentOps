"""Rule-based output critic agent."""

from app.llm import BaseLLM
from agents.intent import should_run_tests


class CriticAgent:
    """Check deterministic agent outputs for obvious missing pieces."""

    def __init__(self, llm: BaseLLM | None = None) -> None:
        """Create a critic with an optional LLM for one extra note."""
        self.llm = llm

    def critique_output(self, user_request: str, output: dict) -> dict:
        """Return warnings and missing items for an orchestrated output."""
        normalized_request = user_request.lower()
        warnings: list[str] = []
        missing_items: list[str] = []

        if not output.get("plan"):
            missing_items.append("plan")

        is_code_request = any(
            term in normalized_request
            for term in ("file", "repo", "code", "implementation")
        )
        if is_code_request and not output.get("context"):
            missing_items.append("context")
            warnings.append("Code or repository request has no retrieved context.")

        is_test_request = should_run_tests(user_request)
        if is_test_request and not output.get("test_result"):
            missing_items.append("test_result")
            warnings.append("Test or bug request has no test result.")

        final_answer = str(output.get("final_answer", "")).strip()
        if not self._is_descriptive_final_answer(final_answer):
            warnings.append("Final answer may be too vague.")

        if output.get("unsupported_claims"):
            warnings.append("Output contains unsupported claims.")

        if self.llm is not None:
            warnings.append(
                self.llm.generate(
                    "Add one concise critique note for this agent output.",
                    f"Request: {user_request}\nOutput keys: {sorted(output.keys())}",
                )
            )

        return {
            "passed": not warnings and not missing_items,
            "warnings": warnings,
            "missing_items": missing_items,
        }

    def _is_descriptive_final_answer(self, final_answer: str) -> bool:
        required_report_sections = [
            "AgentOps Workflow Report",
            "Recommended Developer Workflow",
            "Testing and Validation Plan",
            "Final Next Steps",
        ]
        if all(section in final_answer for section in required_report_sections):
            return True

        words = final_answer.split()
        return len(words) >= 40 and (
            "Next steps" in final_answer or "Recommended next steps" in final_answer
        )
