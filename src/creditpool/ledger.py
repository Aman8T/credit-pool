from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from creditpool.models import TaskState, Termination

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY,
  prompt TEXT NOT NULL,
  acceptance TEXT,
  repo_root TEXT NOT NULL,
  base_commit TEXT NOT NULL,
  branch TEXT NOT NULL,
  worktree_path TEXT NOT NULL,
  state TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  error TEXT
);
CREATE TABLE IF NOT EXISTS attempts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id TEXT NOT NULL,
  n INTEGER NOT NULL,
  agent_id TEXT NOT NULL,
  started_at TEXT NOT NULL,
  ended_at TEXT,
  exit_code INTEGER,
  termination TEXT,
  stdout_path TEXT,
  stderr_path TEXT,
  native_session_id TEXT,
  duration_ms INTEGER,
  FOREIGN KEY(task_id) REFERENCES tasks(id)
);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  attempt_id INTEGER NOT NULL,
  seq INTEGER NOT NULL,
  payload TEXT NOT NULL,
  FOREIGN KEY(attempt_id) REFERENCES attempts(id)
);
CREATE TABLE IF NOT EXISTS handoffs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id TEXT NOT NULL,
  from_attempt_id INTEGER NOT NULL,
  path TEXT NOT NULL,
  payload TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS verifications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id TEXT NOT NULL,
  attempt_id INTEGER,
  command TEXT NOT NULL,
  exit_code INTEGER,
  log_path TEXT,
  created_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class TaskRow:
    id: str
    prompt: str
    acceptance: str | None
    repo_root: str
    base_commit: str
    branch: str
    worktree_path: str
    state: str
    created_at: str
    updated_at: str
    error: str | None


@dataclass
class AttemptRow:
    id: int
    task_id: str
    n: int
    agent_id: str
    started_at: str
    ended_at: str | None
    exit_code: int | None
    termination: str | None
    stdout_path: str | None
    stderr_path: str | None
    native_session_id: str | None
    duration_ms: int | None


class Ledger:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def insert_task(
        self,
        *,
        task_id: str,
        prompt: str,
        acceptance: str | None,
        repo_root: str,
        base_commit: str,
        branch: str,
        worktree_path: str,
    ) -> TaskRow:
        now = _now()
        self._conn.execute(
            """
            INSERT INTO tasks (id, prompt, acceptance, repo_root, base_commit, branch,
                               worktree_path, state, created_at, updated_at, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
            """,
            (
                task_id,
                prompt,
                acceptance,
                repo_root,
                base_commit,
                branch,
                worktree_path,
                TaskState.pending.value,
                now,
                now,
            ),
        )
        self._conn.commit()
        row = self.get_task(task_id)
        assert row is not None
        return row

    def set_state(self, task_id: str, state: TaskState, error: str | None = None) -> None:
        self._conn.execute(
            "UPDATE tasks SET state = ?, error = ?, updated_at = ? WHERE id = ?",
            (state.value, error, _now(), task_id),
        )
        self._conn.commit()

    def get_task(self, task_id: str) -> TaskRow | None:
        cur = self._conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cur.fetchone()
        return _task(row) if row else None

    def list_tasks(self) -> list[TaskRow]:
        cur = self._conn.execute("SELECT * FROM tasks ORDER BY created_at DESC")
        return [_task(row) for row in cur.fetchall()]

    def latest_task(self) -> TaskRow | None:
        cur = self._conn.execute("SELECT * FROM tasks ORDER BY created_at DESC LIMIT 1")
        row = cur.fetchone()
        return _task(row) if row else None

    def start_attempt(self, task_id: str, agent_id: str) -> AttemptRow:
        cur = self._conn.execute(
            "SELECT COALESCE(MAX(n), 0) FROM attempts WHERE task_id = ?", (task_id,)
        )
        n = int(cur.fetchone()[0]) + 1
        cur = self._conn.execute(
            """
            INSERT INTO attempts (task_id, n, agent_id, started_at)
            VALUES (?, ?, ?, ?)
            """,
            (task_id, n, agent_id, _now()),
        )
        self._conn.commit()
        return self.get_attempt(int(cur.lastrowid))  # type: ignore[arg-type]

    def finish_attempt(
        self,
        attempt_id: int,
        *,
        exit_code: int | None,
        termination: Termination,
        stdout_path: str,
        stderr_path: str,
        native_session_id: str | None,
        duration_ms: int,
        events: Iterable[dict[str, Any]],
    ) -> None:
        self._conn.execute(
            """
            UPDATE attempts SET ended_at = ?, exit_code = ?, termination = ?,
              stdout_path = ?, stderr_path = ?, native_session_id = ?, duration_ms = ?
            WHERE id = ?
            """,
            (
                _now(),
                exit_code,
                termination.value,
                stdout_path,
                stderr_path,
                native_session_id,
                duration_ms,
                attempt_id,
            ),
        )
        for seq, payload in enumerate(events):
            self._conn.execute(
                "INSERT INTO events (attempt_id, seq, payload) VALUES (?, ?, ?)",
                (attempt_id, seq, json.dumps(payload, default=str)),
            )
        self._conn.commit()

    def get_attempt(self, attempt_id: int) -> AttemptRow:
        cur = self._conn.execute("SELECT * FROM attempts WHERE id = ?", (attempt_id,))
        row = cur.fetchone()
        if row is None:
            raise KeyError(attempt_id)
        return _attempt(row)

    def attempts_for(self, task_id: str) -> list[AttemptRow]:
        cur = self._conn.execute(
            "SELECT * FROM attempts WHERE task_id = ? ORDER BY n ASC", (task_id,)
        )
        return [_attempt(row) for row in cur.fetchall()]

    def insert_handoff(
        self, *, task_id: str, from_attempt_id: int, path: str, payload: dict[str, Any]
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO handoffs (task_id, from_attempt_id, path, payload, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (task_id, from_attempt_id, path, json.dumps(payload, default=str), _now()),
        )
        self._conn.commit()

    def handoffs_for(self, task_id: str) -> list[dict[str, Any]]:
        cur = self._conn.execute(
            "SELECT * FROM handoffs WHERE task_id = ? ORDER BY id ASC", (task_id,)
        )
        return [dict(row) for row in cur.fetchall()]

    def insert_verification(
        self,
        *,
        task_id: str,
        attempt_id: int | None,
        command: list[str],
        exit_code: int,
        log_path: str,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO verifications (task_id, attempt_id, command, exit_code, log_path, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (task_id, attempt_id, json.dumps(command), exit_code, log_path, _now()),
        )
        self._conn.commit()

    def verifications_for(self, task_id: str) -> list[dict[str, Any]]:
        cur = self._conn.execute(
            "SELECT * FROM verifications WHERE task_id = ? ORDER BY id ASC", (task_id,)
        )
        return [dict(row) for row in cur.fetchall()]


def _task(row: sqlite3.Row) -> TaskRow:
    return TaskRow(
        id=row["id"],
        prompt=row["prompt"],
        acceptance=row["acceptance"],
        repo_root=row["repo_root"],
        base_commit=row["base_commit"],
        branch=row["branch"],
        worktree_path=row["worktree_path"],
        state=row["state"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        error=row["error"],
    )


def _attempt(row: sqlite3.Row) -> AttemptRow:
    return AttemptRow(
        id=row["id"],
        task_id=row["task_id"],
        n=row["n"],
        agent_id=row["agent_id"],
        started_at=row["started_at"],
        ended_at=row["ended_at"],
        exit_code=row["exit_code"],
        termination=row["termination"],
        stdout_path=row["stdout_path"],
        stderr_path=row["stderr_path"],
        native_session_id=row["native_session_id"],
        duration_ms=row["duration_ms"],
    )
