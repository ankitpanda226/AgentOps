"""LangGraph-compatible orchestration for rule-based agents."""

from __future__ import annotations

import os
import warnings
from typing import TypedDict

from app.llm import BaseLLM
from agents.critic_agent import CriticAgent
from agents.docs_agent import DocsAgent
from agents.intent import should_run_tests
from agents.planner_agent import PlannerAgent
from agents.pr_simulator_agent import PRSimulatorAgent, render_pr_simulation
from agents.rag_agent import RAGAgent
from agents.test_agent import TestAgent
from agents.workflow_report_agent import WorkflowReportAgent

warnings.filterwarnings(
    "ignore",
    message="The default value of `allowed_objects`.*",
    module=r"langgraph\.cache\.base.*",
)


class AgentGraphState(TypedDict):
    """State passed between agent workflow nodes."""

    user_request: str
    simulate_pr: bool
    pr_simulation: dict | None
    repo_path: str | None
    plan: dict | None
    context: list[dict]
    issue_draft: dict | None
    test_result: dict | None
    critique: dict | None
    final_answer: str | None
    tools_used: list[str]


def build_agent_graph(
    planner_agent,
    rag_agent,
    docs_agent,
    test_agent,
    critic_agent,
):
    """Build a LangGraph workflow, or a deterministic fallback if unavailable."""
    nodes = _AgentGraphNodes(
        planner_agent=planner_agent,
        rag_agent=rag_agent,
        docs_agent=docs_agent,
        test_agent=test_agent,
        critic_agent=critic_agent,
    )
    if os.getenv("AGENTOPS_DISABLE_LANGGRAPH") == "1":
        return _FallbackAgentGraph(nodes)

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from langgraph.graph import END, StateGraph

            graph = StateGraph(AgentGraphState)
            graph.add_node("plan_node", nodes.plan_node)
            graph.add_node("retrieve_context_node", nodes.retrieve_context_node)
            graph.add_node("generate_issue_node", nodes.generate_issue_node)
            graph.add_node("optional_test_node", nodes.optional_test_node)
            graph.add_node("simulate_pr_node", nodes.simulate_pr_node)
            graph.add_node("critique_node", nodes.critique_node)
            graph.add_node("finalize_node", nodes.finalize_node)

            graph.set_entry_point("plan_node")
            graph.add_conditional_edges(
                "plan_node",
                nodes.route_after_plan,
                {
                    "retrieve_context_node": "retrieve_context_node",
                    "generate_issue_node": "generate_issue_node",
                },
            )
            graph.add_edge("retrieve_context_node", "generate_issue_node")
            graph.add_conditional_edges(
                "generate_issue_node",
                nodes.route_after_issue,
                {
                    "optional_test_node": "optional_test_node",
                    "critique_node": "critique_node",
                },
            )
            graph.add_edge("optional_test_node", "critique_node")
            graph.add_edge("critique_node", "simulate_pr_node")
            graph.add_edge("simulate_pr_node", "finalize_node")
            graph.add_edge("finalize_node", END)
            return graph.compile()
    except Exception:
        return _FallbackAgentGraph(nodes)


def run_agent_workflow(
    user_request: str,
    repo_path: str | None = None,
    vector_store=None,
    llm: BaseLLM | None = None,
    simulate_pr: bool = False,
) -> dict:
    """Run the agent workflow and return the final structured state."""
    # A simulation must remain local even when a caller supplies a live LLM.
    if simulate_pr:
        llm = None
    planner_agent = PlannerAgent(llm=llm)
    rag_agent = RAGAgent(vector_store) if vector_store is not None else None
    docs_agent = DocsAgent(llm=llm)
    test_agent = TestAgent()
    critic_agent = CriticAgent(llm=llm)
    graph = build_agent_graph(
        planner_agent=planner_agent,
        rag_agent=rag_agent,
        docs_agent=docs_agent,
        test_agent=test_agent,
        critic_agent=critic_agent,
    )

    initial_state: AgentGraphState = {
        "user_request": user_request,
        "simulate_pr": simulate_pr,
        "pr_simulation": None,
        "repo_path": repo_path,
        "plan": None,
        "context": [],
        "issue_draft": None,
        "test_result": None,
        "critique": None,
        "final_answer": None,
        "tools_used": [],
    }
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return dict(graph.invoke(initial_state))


class _AgentGraphNodes:
    """Shared node implementations for LangGraph and fallback execution."""

    def __init__(
        self,
        planner_agent,
        rag_agent,
        docs_agent,
        test_agent,
        critic_agent,
    ) -> None:
        self.planner_agent = planner_agent
        self.rag_agent = rag_agent
        self.docs_agent = docs_agent
        self.test_agent = test_agent
        self.critic_agent = critic_agent

    def plan_node(self, state: AgentGraphState) -> AgentGraphState:
        """Create a structured plan."""
        updated = self._copy_state(state)
        updated["plan"] = self.planner_agent.create_plan(self._planning_request(state))
        if state.get("simulate_pr"):
            updated["plan"]["goal"] = " ".join(state["user_request"].split())[:120]
        return updated

    def retrieve_context_node(self, state: AgentGraphState) -> AgentGraphState:
        """Retrieve repository context if a RAG agent exists."""
        updated = self._copy_state(state)
        if self.rag_agent is None:
            return updated

        result = self.rag_agent.answer_with_context(state["user_request"])
        updated["context"] = result["context"]
        updated["tools_used"] = [*updated["tools_used"], "retriever"]
        return updated

    def generate_issue_node(self, state: AgentGraphState) -> AgentGraphState:
        """Generate a deterministic issue draft."""
        updated = self._copy_state(state)
        updated["issue_draft"] = self.docs_agent.generate_issue_draft(
            self._planning_request(state),
            state["plan"] or {},
            state["context"],
        )
        updated["tools_used"] = [*updated["tools_used"], "create_issue_draft"]
        return updated

    def optional_test_node(self, state: AgentGraphState) -> AgentGraphState:
        """Run tests only for test-like requests."""
        updated = self._copy_state(state)
        test_path = state["repo_path"] or "tests"
        updated["test_result"] = self.test_agent.run_tests(test_path)
        updated["tools_used"] = [*updated["tools_used"], "run_pytest"]
        return updated

    def simulate_pr_node(self, state: AgentGraphState) -> AgentGraphState:
        """Produce a pure proposal without invoking executable tools."""
        updated = self._copy_state(state)
        updated["pr_simulation"] = PRSimulatorAgent().simulate_pr(
            user_request=state["user_request"],
            context=state["context"],
            plan=state["plan"] or {},
            test_result=state["test_result"],
            critique=state["critique"],
        )
        updated["tools_used"] = [*updated["tools_used"], "simulate_pr"]
        return updated

    @staticmethod
    def _planning_request(state: AgentGraphState) -> str:
        if state.get("simulate_pr"):
            return state["user_request"] + " (simulation only, without running tests)"
        return state["user_request"]

    def critique_node(self, state: AgentGraphState) -> AgentGraphState:
        """Critique the current workflow output."""
        updated = self._copy_state(state)
        provisional_final_answer = state["final_answer"] or _build_final_answer(
            state, critique=None
        )
        updated["critique"] = self.critic_agent.critique_output(
            self._planning_request(state),
            {
                "plan": state["plan"],
                "context": state["context"],
                "issue_draft": state["issue_draft"],
                "test_result": state["test_result"],
                "final_answer": provisional_final_answer,
            },
        )
        return updated

    def finalize_node(self, state: AgentGraphState) -> AgentGraphState:
        """Create the final deterministic answer."""
        updated = self._copy_state(state)
        updated["final_answer"] = _build_final_answer(state, critique=state["critique"])
        return updated

    def route_after_plan(self, state: AgentGraphState) -> str:
        """Route to retrieval when a RAG agent is available."""
        if self.rag_agent is not None:
            return "retrieve_context_node"
        return "generate_issue_node"

    def route_after_issue(self, state: AgentGraphState) -> str:
        """Route to tests only for bug/test/failure requests."""
        if not state.get("simulate_pr") and should_run_tests(state["user_request"]):
            return "optional_test_node"
        return "critique_node"

    def _copy_state(self, state: AgentGraphState) -> AgentGraphState:
        return {
            "user_request": state["user_request"],
            "simulate_pr": state.get("simulate_pr", False),
            "pr_simulation": state.get("pr_simulation"),
            "repo_path": state["repo_path"],
            "plan": state["plan"],
            "context": list(state["context"]),
            "issue_draft": state["issue_draft"],
            "test_result": state["test_result"],
            "critique": state["critique"],
            "final_answer": state["final_answer"],
            "tools_used": list(state["tools_used"]),
        }


class _FallbackAgentGraph:
    """Plain Python graph runner used when LangGraph is unavailable."""

    def __init__(self, nodes: _AgentGraphNodes) -> None:
        self.nodes = nodes

    def invoke(self, state: AgentGraphState) -> AgentGraphState:
        """Run the workflow in the same order as the LangGraph graph."""
        state = self.nodes.plan_node(state)
        if self.nodes.route_after_plan(state) == "retrieve_context_node":
            state = self.nodes.retrieve_context_node(state)
        state = self.nodes.generate_issue_node(state)
        if self.nodes.route_after_issue(state) == "optional_test_node":
            state = self.nodes.optional_test_node(state)
        state = self.nodes.critique_node(state)
        state = self.nodes.simulate_pr_node(state)
        state = self.nodes.finalize_node(state)
        return state


def _build_final_answer(state: AgentGraphState, critique: dict | None) -> str:
    report = WorkflowReportAgent().generate_report(
        user_request=_AgentGraphNodes._planning_request(state),
        plan=state["plan"] or {},
        context=state["context"],
        issue_draft=state["issue_draft"] or {},
        test_result=state["test_result"],
        critique=critique,
    )

    if state.get("pr_simulation"):
        report += "\n\n" + render_pr_simulation(state["pr_simulation"])
    return report
