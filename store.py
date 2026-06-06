import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent / "life_agent.db"

_STATUS_OPEN = "open"
_STATUS_DONE = "done"
_STATUS_DROPPED = "dropped"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT    NOT NULL,
                notes       TEXT,
                due_date    TEXT,
                status      TEXT    NOT NULL DEFAULT 'open'
                                CHECK(status IN ('open', 'done', 'dropped')),
                created_at  TEXT    NOT NULL,
                completed_at TEXT
            )
        """)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def add_task(
    title: str,
    notes: Optional[str] = None,
    due_date: Optional[str] = None,
) -> int:
    """Insert a new open task. Returns the new task id."""
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO tasks (title, notes, due_date, status, created_at)
            VALUES (?, ?, ?, 'open', ?)
            """,
            (title, notes, due_date, _now()),
        )
        return cursor.lastrowid


def list_open() -> list[sqlite3.Row]:
    """Return all tasks with status='open', ordered by due_date nulls last."""
    with _connect() as conn:
        return conn.execute(
            """
            SELECT * FROM tasks
            WHERE status = 'open'
            ORDER BY due_date IS NULL, due_date ASC, created_at ASC
            """
        ).fetchall()


def mark_done(task_id: int) -> bool:
    """Mark a task as done. Returns True if a row was updated."""
    with _connect() as conn:
        cursor = conn.execute(
            """
            UPDATE tasks
               SET status = 'done', completed_at = ?
             WHERE id = ? AND status = 'open'
            """,
            (_now(), task_id),
        )
        return cursor.rowcount > 0


def drop_task(task_id: int) -> bool:
    """Mark a task as dropped. Returns True if a row was updated."""
    with _connect() as conn:
        cursor = conn.execute(
            """
            UPDATE tasks
               SET status = 'dropped', completed_at = ?
             WHERE id = ? AND status = 'open'
            """,
            (_now(), task_id),
        )
        return cursor.rowcount > 0


def get_overdue() -> list[sqlite3.Row]:
    """Return open tasks whose due_date is strictly before today (UTC date)."""
    today = datetime.now(timezone.utc).date().isoformat()
    with _connect() as conn:
        return conn.execute(
            """
            SELECT * FROM tasks
            WHERE status = 'open'
              AND due_date IS NOT NULL
              AND due_date < ?
            ORDER BY due_date ASC
            """,
            (today,),
        ).fetchall()


def get_task(task_id: int) -> Optional[sqlite3.Row]:
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
