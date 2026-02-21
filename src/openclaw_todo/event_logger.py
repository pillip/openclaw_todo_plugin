"""Centralised event logging helper."""

from __future__ import annotations

import json
import sqlite3


def log_event(
    conn: sqlite3.Connection,
    *,
    actor_user_id: str,
    action: str,
    payload: dict,
    task_id: int | None = None,
) -> None:
    """Insert a row into the ``events`` table.

    Parameters
    ----------
    conn:
        Active SQLite connection (caller is responsible for committing).
    actor_user_id:
        Slack user ID of the person who triggered the action.
    action:
        Dot-separated event name, e.g. ``task.add``, ``project.set_private``.
    payload:
        Arbitrary dict serialised as JSON into the ``payload`` column.
    task_id:
        Optional task reference.  ``None`` for project-level events.
    """
    conn.execute(
        "INSERT INTO events (actor_user_id, action, task_id, payload) "
        "VALUES (?, ?, ?, ?);",
        (actor_user_id, action, task_id, json.dumps(payload)),
    )
