"""Run deterministic evaluation tasks for AgentOps Copilot."""

from __future__ import annotations

import json
import os
import sys
import warnings
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

warnings.simplefilter("ignore")
os.environ["AGENTOPS_DISABLE_LANGGRAPH"] = "1"

from agents.graph import run_agent_workflow
from evals.metrics import (
    aggregate_score,
    keyword_coverage,
    required_fields_score,
    tool_coverage,
)

TASKS_PATH = Path(__file__).with_name("tasks.jsonl")
RESULTS_PATH = Path(__file__).with_name("results.json")


class EvalVectorStore:
    """Deterministic vector store used by offline evaluations."""

    def search(self, query: str, k: int = 5) -> list[dict]:
        """Return stable context for a query."""
        return [
            {
                "file_path": "app/main.py",
                "chunk_id": 0,
                "text": f"FastAPI API planning context for {query}",
                "score": 1.0,
            },
            {
                "file_path": "rag/indexer.py",
                "chunk_id": 0,
                "text": "RAG indexing retrieves repository files and chunks.",
                "score": 0.9,
            },
            {
                "file_path": "memory/memory_store.py",
                "chunk_id": 0,
                "text": "Memory stores tasks, decisions, and tool calls.",
                "score": 0.8,
            },
        ][:k]


def load_tasks(path: Path = TASKS_PATH) -> list[dict]:
    """Load JSONL evaluation tasks."""
    tasks: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            tasks.append(json.loads(line))
    return tasks


def run_evaluations(tasks: list[dict] | None = None) -> list[dict]:
    """Run all evaluation tasks and return structured results."""
    eval_tasks = tasks if tasks is not None else load_tasks()
    vector_store = EvalVectorStore()
    results: list[dict] = []

    for task in eval_tasks:
        output = run_agent_workflow(
            user_request=task["user_request"],
            repo_path=None,
            vector_store=vector_store,
            llm=None,
        )
        output_text = json.dumps(output, sort_keys=True)
        scores = {
            "keyword_coverage": keyword_coverage(
                output_text, task.get("expected_keywords", [])
            ),
            "required_fields_score": required_fields_score(
                output, task.get("expected_output_fields", [])
            ),
            "tool_coverage": tool_coverage(
                output.get("tools_used", []), task.get("expected_tools", [])
            ),
        }
        scores["aggregate_score"] = aggregate_score(scores)
        results.append(
            {
                "id": task["id"],
                "user_request": task["user_request"],
                "scores": scores,
                "output": output,
            }
        )

    return results


def save_results(results: list[dict], path: Path = RESULTS_PATH) -> None:
    """Save evaluation results as JSON."""
    path.write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")


def print_summary(results: list[dict]) -> None:
    """Print a readable summary table."""
    print("Task ID  Aggregate")
    print("-------  ---------")
    for result in results:
        aggregate = result["scores"]["aggregate_score"]
        print(f"{result['id']:<7}  {aggregate:.2f}")


def main() -> None:
    """Run the evaluation suite from the command line."""
    results = run_evaluations()
    save_results(results)
    print_summary(results)


if __name__ == "__main__":
    main()
