"""SQLite-backed persistent memory for tasks, decisions, and tool calls."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class MemoryStore:
    """Persist previous tasks and workflow decisions in SQLite."""

    def __init__(self, db_path: str = "agentops_memory.db") -> None:
        """Create a memory store for a SQLite database path."""
        self.db_path = db_path

    def init_db(self) -> None:
        """Initialize database tables from ``schema.sql``."""
        schema_path = Path(__file__).with_name("schema.sql")
        schema = schema_path.read_text(encoding="utf-8")

        with self._connect() as connection:
            connection.executescript(schema)

    def create_task(self, user_request: str, plan: str | None = None) -> int:
        """Create a task memory record and return its id."""
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO tasks (user_request, plan, final_answer, created_at)
                VALUES (?, ?, NULL, ?)
                """,
                (user_request, plan, self._utc_now()),
            )
            return int(cursor.lastrowid)

    def save_decision(self, task_id: int, decision: str, reason: str) -> None:
        """Persist a decision made while handling a task."""
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO decisions (task_id, decision, reason, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (task_id, decision, reason, self._utc_now()),
            )

    def save_tool_call(
        self,
        task_id: int,
        tool_name: str,
        tool_input: str,
        tool_output: str,
        success: bool,
    ) -> None:
        """Persist a tool invocation and its result."""
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO tool_calls (
                    task_id, tool_name, tool_input, tool_output, success, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    tool_name,
                    tool_input,
                    tool_output,
                    int(success),
                    self._utc_now(),
                ),
            )

    def get_recent_tasks(self, limit: int = 5) -> list[dict]:
        """Return recent task records ordered newest first."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, user_request, plan, final_answer, created_at
                FROM tasks
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def update_final_answer(self, task_id: int, final_answer: str) -> None:
        """Update the final answer for a task."""
        with self._connect() as connection:
            connection.execute(
                "UPDATE tasks SET final_answer = ? WHERE id = ?",
                (final_answer, task_id),
            )

    def get_task(self, task_id: int) -> dict | None:
        """Return one task with related decisions and tool calls."""
        with self._connect() as connection:
            task_row = connection.execute(
                """
                SELECT id, user_request, plan, final_answer, created_at
                FROM tasks
                WHERE id = ?
                """,
                (task_id,),
            ).fetchone()

            if task_row is None:
                return None

            decisions = connection.execute(
                """
                SELECT id, task_id, decision, reason, created_at
                FROM decisions
                WHERE task_id = ?
                ORDER BY id ASC
                """,
                (task_id,),
            ).fetchall()
            tool_calls = connection.execute(
                """
                SELECT id, task_id, tool_name, tool_input, tool_output, success, created_at
                FROM tool_calls
                WHERE task_id = ?
                ORDER BY id ASC
                """,
                (task_id,),
            ).fetchall()

        task = self._row_to_dict(task_row)
        task["decisions"] = [self._row_to_dict(row) for row in decisions]
        task["tool_calls"] = [
            self._convert_tool_call(self._row_to_dict(row)) for row in tool_calls
        ]
        return task

    def _connect(self) -> sqlite3.Connection:
        parent = Path(self.db_path).expanduser().parent
        parent.mkdir(parents=True, exist_ok=True)

        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return dict(row)

    def _convert_tool_call(self, tool_call: dict[str, Any]) -> dict[str, Any]:
        tool_call["success"] = bool(tool_call["success"])
        return tool_call

    def _utc_now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
