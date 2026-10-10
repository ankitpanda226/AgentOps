"""Tests for SQLite-backed persistent memory."""

from pathlib import Path

from memory.memory_store import MemoryStore


def test_create_task(tmp_path: Path) -> None:
    """create_task should insert and return a task id."""
    store = _store(tmp_path)

    task_id = store.create_task("Build RAG", plan="Index files")
    task = store.get_task(task_id)

    assert task is not None
    assert task["id"] == task_id
    assert task["user_request"] == "Build RAG"
    assert task["plan"] == "Index files"
    assert task["final_answer"] is None
    assert task["created_at"].endswith("+00:00")


def test_save_decision(tmp_path: Path) -> None:
    """save_decision should attach decisions to a task."""
    store = _store(tmp_path)
    task_id = store.create_task("Choose storage")

    store.save_decision(task_id, "Use SQLite", "Standard library and local-first")

    task = store.get_task(task_id)
    assert task is not None
    assert task["decisions"] == [
        {
            "id": 1,
            "task_id": task_id,
            "decision": "Use SQLite",
            "reason": "Standard library and local-first",
            "created_at": task["decisions"][0]["created_at"],
        }
    ]
    assert task["decisions"][0]["created_at"].endswith("+00:00")


def test_save_tool_call(tmp_path: Path) -> None:
    """save_tool_call should attach structured tool call history."""
    store = _store(tmp_path)
    task_id = store.create_task("Run tests")

    store.save_tool_call(task_id, "pytest", "tests", "1 passed", True)

    task = store.get_task(task_id)
    assert task is not None
    assert task["tool_calls"] == [
        {
            "id": 1,
            "task_id": task_id,
            "tool_name": "pytest",
            "tool_input": "tests",
            "tool_output": "1 passed",
            "success": True,
            "created_at": task["tool_calls"][0]["created_at"],
        }
    ]
    assert task["tool_calls"][0]["created_at"].endswith("+00:00")


def test_get_recent_tasks(tmp_path: Path) -> None:
    """get_recent_tasks should return newest tasks first with a limit."""
    store = _store(tmp_path)
    first_id = store.create_task("First")
    second_id = store.create_task("Second")
    third_id = store.create_task("Third")

    recent = store.get_recent_tasks(limit=2)

    assert [task["id"] for task in recent] == [third_id, second_id]
    assert first_id not in [task["id"] for task in recent]


def test_update_final_answer(tmp_path: Path) -> None:
    """update_final_answer should persist the final response text."""
    store = _store(tmp_path)
    task_id = store.create_task("Summarize")

    store.update_final_answer(task_id, "Done")

    task = store.get_task(task_id)
    assert task is not None
    assert task["final_answer"] == "Done"


def test_get_task_missing_returns_none(tmp_path: Path) -> None:
    """get_task should return None for missing task ids."""
    store = _store(tmp_path)

    assert store.get_task(999) is None


def _store(tmp_path: Path) -> MemoryStore:
    store = MemoryStore(str(tmp_path / "memory.db"))
    store.init_db()
    return store
