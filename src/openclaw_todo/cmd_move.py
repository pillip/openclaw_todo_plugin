"""Handler for the ``/todo move`` command."""

from __future__ import annotations

import logging
import sqlite3

from openclaw_todo.event_logger import log_event
from openclaw_todo.parser import ParsedCommand
from openclaw_todo.permissions import can_write_task

logger = logging.getLogger(__name__)


def move_handler(parsed: ParsedCommand, conn: sqlite3.Connection, context: dict) -> str:
    """Move a task to a different section.

    Validates section enum, checks permissions (private: owner only;
    shared: assignee or created_by), updates task section and updated_at,
    and logs an event.
    """
    sender_id: str = context["sender_id"]

    # --- Validate task ID ---
    if not parsed.args:
        return "Error: task ID required. Usage: todo: move <id> /s <section>"

    try:
        task_id = int(parsed.args[0])
    except ValueError:
        return f"Error: invalid task ID: {parsed.args[0]!r}"

    # --- Validate target section ---
    target_section = parsed.section
    if not target_section:
        return "Error: target section required. Usage: todo: move <id> /s <section>"

    # --- Check task exists ---
    row = conn.execute(
        "SELECT title, section, project_id FROM tasks WHERE id = ?;",
        (task_id,),
    ).fetchone()
    if row is None:
        return f"Error: task #{task_id} not found."

    _, current_section, _ = row

    if current_section == target_section:
        return f"Task #{task_id} is already in section '{target_section}'."

    # --- Check permission ---
    if not can_write_task(conn, task_id, sender_id):
        return f"Error: permission denied for task #{task_id}."

    # --- Update task ---
    conn.execute(
        "UPDATE tasks SET section = ?, updated_at = datetime('now') WHERE id = ?;",
        (target_section, task_id),
    )

    # --- Log event ---
    log_event(
        conn,
        actor_user_id=sender_id,
        action="task.move",
        task_id=task_id,
        payload={
            "old_section": current_section,
            "new_section": target_section,
        },
    )

    conn.commit()

    logger.info("Task #%d moved to %s by %s", task_id, target_section, sender_id)

    return f"Moved #{task_id} from {current_section} → {target_section}"
