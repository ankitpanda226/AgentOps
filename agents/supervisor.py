"""Rule-based supervisor agent orchestration."""

from app.llm import BaseLLM
from agents.graph import run_agent_workflow


class SupervisorAgent:
    """Coordinate rule-based specialist agents for a user request."""

    def __init__(
        self,
        vector_store=None,
        memory_store=None,
        llm: BaseLLM | None = None,
    ) -> None:
        """Create a supervisor with optional retrieval and memory backends."""
        self.vector_store = vector_store
        self.memory_store = memory_store
        self.llm = llm

    def handle_request(
        self, user_request: str, repo_path: str | None = None, simulate_pr: bool = False
    ) -> dict:
        """Plan, retrieve, draft, optionally test, critique, and persist a task."""
        task_id = self._create_memory_task(user_request)
        output = run_agent_workflow(
            user_request=user_request,
            repo_path=repo_path,
            vector_store=self.vector_store,
            llm=self.llm,
            simulate_pr=simulate_pr,
        )

        if task_id is not None:
            self._save_decision(
                task_id,
                "Created rule-based plan",
                "PlannerAgent produced deterministic steps and tool needs.",
            )
            if "retriever" in output["tools_used"]:
                self._save_tool_call(
                    task_id,
                    "retriever",
                    user_request,
                    f"Retrieved {len(output['context'])} context chunks.",
                    True,
                )
            if output["test_result"] is not None:
                self._save_tool_call(
                    task_id,
                    "run_pytest",
                    repo_path or "tests",
                    output["test_result"].get("stdout", ""),
                    bool(output["test_result"].get("success")),
                )
            self.memory_store.update_final_answer(task_id, output["final_answer"] or "")

        return {
            "task_id": task_id,
            "plan": output["plan"],
            "context": output["context"],
            "issue_draft": output["issue_draft"],
            "test_result": output["test_result"],
            "critique": output["critique"],
            "final_answer": output["final_answer"],
            "pr_simulation": output["pr_simulation"],
        }

    def _create_memory_task(self, user_request: str) -> int | None:
        if self.memory_store is None:
            return None
        self.memory_store.init_db()
        return self.memory_store.create_task(user_request)

    def _save_decision(self, task_id: int, decision: str, reason: str) -> None:
        if self.memory_store is not None:
            self.memory_store.save_decision(task_id, decision, reason)

    def _save_tool_call(
        self,
        task_id: int,
        tool_name: str,
        tool_input: str,
        tool_output: str,
        success: bool,
    ) -> None:
        if self.memory_store is not None:
            self.memory_store.save_tool_call(
                task_id, tool_name, tool_input, tool_output, success
            )
