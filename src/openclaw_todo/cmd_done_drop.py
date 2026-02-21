"""Handlers for the ``/todo done`` and ``/todo drop`` commands."""

from __future__ import annotations

import logging
import sqlite3

from openclaw_todo.event_logger import log_event
from openclaw_todo.parser import ParsedCommand
from openclaw_todo.permissions import can_write_task

logger = logging.getLogger(__name__)


def _close_task(
    parsed: ParsedCommand,
    conn: sqlite3.Connection,
    context: dict,
    *,
    action: str,
    target_section: str,
    target_status: str,
) -> str:
    """Shared logic for ``done`` and ``drop`` commands.

    Sets section, status, and closed_at; validates permissions; logs event.
    """
    sender_id: str = context["sender_id"]

    # --- Validate task ID ---
    if not parsed.args:
        return f"Error: task ID required. Usage: todo: {action} <id>"

    try:
        task_id = int(parsed.args[0])
    except ValueError:
        return f"Error: invalid task ID: {parsed.args[0]!r}"

    # --- Check task exists ---
    row = conn.execute(
        "SELECT section, status FROM tasks WHERE id = ?;",
        (task_id,),
    ).fetchone()
    if row is None:
        return f"Error: task #{task_id} not found."

    current_section, current_status = row

    # --- Already closed? ---
    if current_status in ("done", "dropped"):
        return f"Task #{task_id} is already {current_status}."

    # --- Check permission ---
    if not can_write_task(conn, task_id, sender_id):
        return f"Error: permission denied for task #{task_id}."

    # --- Update task ---
    conn.execute(
        "UPDATE tasks SET section = ?, status = ?, "
        "updated_at = datetime('now'), closed_at = datetime('now') "
        "WHERE id = ?;",
        (target_section, target_status, task_id),
    )

    # --- Log event ---
    log_event(
        conn,
        actor_user_id=sender_id,
        action=f"task.{action}",
        task_id=task_id,
        payload={
            "old_section": current_section,
            "new_section": target_section,
            "old_status": current_status,
            "new_status": target_status,
        },
    )

    conn.commit()

    logger.info("Task #%d %s by %s", task_id, action, sender_id)

    return f"Task #{task_id} marked as {target_status}."


def done_handler(parsed: ParsedCommand, conn: sqlite3.Connection, context: dict) -> str:
    """Mark a task as done."""
    return _close_task(
        parsed,
        conn,
        context,
        action="done",
        target_section="done",
        target_status="done",
    )


def drop_handler(parsed: ParsedCommand, conn: sqlite3.Connection, context: dict) -> str:
    """Mark a task as dropped."""
    return _close_task(
        parsed,
        conn,
        context,
        action="drop",
        target_section="drop",
        target_status="dropped",
    )
