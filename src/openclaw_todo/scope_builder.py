"""Shared helpers for building scope-based query conditions."""

from __future__ import annotations

import sqlite3


def build_scope_conditions(
    scope: str,
    sender_id: str,
    scope_user: str | None = None,
) -> tuple[list[str], list[str | int]]:
    """Return SQL WHERE fragments and params for scope filtering.

    Parameters
    ----------
    scope:
        One of ``"mine"``, ``"all"``, or ``"user"``.
    sender_id:
        The current user's Slack ID (used for visibility checks).
    scope_user:
        Target user ID when *scope* is ``"user"``.

    Returns
    -------
    tuple[list[str], list[str | int]]
        ``(conditions, params)`` to be AND-joined into a WHERE clause.
        Assumes the query aliases ``tasks`` as ``t`` and ``projects`` as ``p``.
    """
    conditions: list[str] = []
    params: list[str | int] = []

    if scope == "mine":
        conditions.append("t.id IN (SELECT task_id FROM task_assignees WHERE assignee_user_id = ?)")
        params.append(sender_id)
        conditions.append("(p.visibility = 'shared' OR p.owner_user_id = ?)")
        params.append(sender_id)
    elif scope == "all":
        conditions.append("(p.visibility = 'shared' OR p.owner_user_id = ?)")
        params.append(sender_id)
    elif scope == "user" and scope_user:
        conditions.append("t.id IN (SELECT task_id FROM task_assignees WHERE assignee_user_id = ?)")
        params.append(scope_user)
        conditions.append("(p.visibility = 'shared' OR p.owner_user_id = ?)")
        params.append(sender_id)

    return conditions, params


def format_assignees(conn: sqlite3.Connection, task_id: int) -> str:
    """Return a comma-separated ``<@UID>`` string for *task_id*'s assignees."""
    rows = conn.execute(
        "SELECT assignee_user_id FROM task_assignees WHERE task_id = ?",
        (task_id,),
    ).fetchall()
    return ", ".join(f"<@{r[0]}>" for r in rows)
