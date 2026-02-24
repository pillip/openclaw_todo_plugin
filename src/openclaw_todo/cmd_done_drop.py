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
    emoji: str,
    verb: str,
) -> str:
    """Shared logic for ``done`` and ``drop`` commands.

    Sets section, status, and closed_at; validates permissions; logs event.
    """
    sender_id: str = context["sender_id"]

    # --- Validate task ID ---
    if not parsed.args:
        return f"❌ Task ID is required. Usage: todo: {action} <id>"

    try:
        task_id = int(parsed.args[0])
    except ValueError:
        return f'❌ Invalid task ID "{parsed.args[0]}". Must be a number.'

    # --- Check task exists ---
    row = conn.execute(
        "SELECT t.title, t.section, t.status, p.name "
        "FROM tasks t JOIN projects p ON t.project_id = p.id "
        "WHERE t.id = ?;",
        (task_id,),
    ).fetchone()
    if row is None:
        return f"❌ Task #{task_id} not found."

    title, current_section, current_status, project_name = row

    # --- Already closed? ---
    if current_status in ("done", "dropped"):
        return f"ℹ️ Task #{task_id} is already {current_status}."

    # --- Check permission ---
    if not can_write_task(conn, task_id, sender_id):
        return f"❌ You don't have permission to modify task #{task_id}."

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

    return f"{emoji} {verb} #{task_id} ({project_name}) — {title}"


def done_handler(parsed: ParsedCommand, conn: sqlite3.Connection, context: dict) -> str:
    """Mark a task as done."""
    return _close_task(
        parsed,
        conn,
        context,
        action="done",
        target_section="done",
        target_status="done",
        emoji="✅",
        verb="Done",
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
        emoji="🗑️",
        verb="Dropped",
    )
