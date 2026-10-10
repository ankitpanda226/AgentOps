"""Rule-based planning agent."""

from app.llm import BaseLLM
from agents.intent import has_test_negation, should_run_tests


class PlannerAgent:
    """Create deterministic task plans without requiring an LLM."""

    def __init__(self, llm: BaseLLM | None = None) -> None:
        """Create a planner with an optional LLM for goal wording."""
        self.llm = llm

    def create_plan(self, user_request: str) -> dict:
        """Return a structured plan for a user request."""
        normalized_request = user_request.lower()
        needed_tools = ["retriever"]
        run_tests = should_run_tests(user_request)

        if run_tests:
            needed_tools.append("run_pytest")
        if any(
            term in normalized_request
            for term in ("file", "repo", "code", "implementation")
        ):
            needed_tools.extend(["read_file", "search_repo"])
        if any(term in normalized_request for term in ("issue", "github", "ticket")):
            needed_tools.append("create_issue_draft")

        steps = [
            "Analyze the request and identify the desired outcome.",
            "Retrieve relevant context from the repository and documentation.",
            "Inspect files if the request depends on specific implementation details.",
            self._test_step(user_request, run_tests),
            "Create a grounded final answer with clear next steps.",
        ]

        return {
            "goal": self._goal_text(user_request),
            "steps": steps,
            "needed_tools": list(dict.fromkeys(needed_tools)),
            "risks": [
                "Hallucination from insufficient evidence.",
                "Missing context from relevant files or documentation.",
                "Unsafe file access outside the intended workspace.",
            ],
            "success_criteria": [
                "Answer is grounded in retrieved context or inspected files.",
                "Relevant files and sources are identified when applicable.",
                "Clear next steps are provided.",
            ],
        }

    def _goal_text(self, user_request: str) -> str:
        if self.llm is None:
            return self._summarize_goal(user_request)
        return self.llm.generate(
            "Improve the goal wording for a developer workflow plan.",
            f"Summarize this request as one concise goal: {user_request}",
        )

    def _summarize_goal(self, user_request: str) -> str:
        cleaned = " ".join(user_request.split())
        if len(cleaned) <= 120:
            return cleaned
        return cleaned[:117].rstrip() + "..."

    def _test_step(self, user_request: str, run_tests: bool) -> str:
        if has_test_negation(user_request):
            return "Do not run tests; document targeted validation to run later."
        if run_tests:
            return "Run the requested tests and capture structured results."
        return "Recommend relevant validation without executing tests."
