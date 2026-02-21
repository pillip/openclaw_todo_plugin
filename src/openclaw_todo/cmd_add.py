"""Handler for the ``/todo add`` command."""

from __future__ import annotations

import logging
import sqlite3

from openclaw_todo.event_logger import log_event
from openclaw_todo.parser import DUE_CLEAR, ParsedCommand
from openclaw_todo.project_resolver import ProjectNotFoundError, resolve_project

logger = logging.getLogger(__name__)


def add_handler(parsed: ParsedCommand, conn: sqlite3.Connection, context: dict) -> str:
    """Create a new task.

    Resolves the target project (default ``Inbox``), applies defaults for
    section and assignees, validates the private-project assignee constraint,
    inserts the task + assignee rows, and logs an event.
    """
    sender_id: str = context["sender_id"]
    title = " ".join(parsed.title_tokens)

    if not title:
        return "Error: task title is required. Usage: !todo add <title> [options]"

    # --- Resolve project ---
    project_name = parsed.project or "Inbox"
    try:
        project = resolve_project(conn, project_name, sender_id)
    except ProjectNotFoundError:
        return f"Error: project {project_name!r} not found."

    # --- Defaults ---
    section = parsed.section or "backlog"
    due = parsed.due if parsed.due and parsed.due != DUE_CLEAR else None
    assignees = parsed.mentions if parsed.mentions else [sender_id]

    # --- Private project assignee validation (PRD 3.3) ---
    if project.visibility == "private":
        non_owner = [a for a in assignees if a != project.owner_user_id]
        if non_owner:
            formatted = ", ".join(f"<@{uid}>" for uid in non_owner)
            return (
                f"Warning: private project '{project.name}' belongs to "
                f"<@{project.owner_user_id}>. Cannot assign to {formatted}. "
                f"Task was NOT created."
            )

    # --- Insert task ---
    cursor = conn.execute(
        "INSERT INTO tasks (title, project_id, section, due, status, created_by) " "VALUES (?, ?, ?, ?, 'open', ?);",
        (title, project.id, section, due, sender_id),
    )
    task_id = cursor.lastrowid

    # --- Insert assignees ---
    for assignee in assignees:
        conn.execute(
            "INSERT INTO task_assignees (task_id, assignee_user_id) VALUES (?, ?);",
            (task_id, assignee),
        )

    # --- Log event ---
    log_event(
        conn,
        actor_user_id=sender_id,
        action="task.add",
        task_id=task_id,
        payload={
            "title": title,
            "project": project.name,
            "section": section,
            "due": due,
            "assignees": assignees,
        },
    )

    conn.commit()

    logger.info("Task #%d created in %s/%s by %s", task_id, project.name, section, sender_id)

    # --- Format response ---
    due_str = due if due else "-"
    assignee_str = ", ".join(f"<@{a}>" for a in assignees)
    return f"Added #{task_id} ({project.name}/{section}) " f"due:{due_str} assignees:{assignee_str} -- {title}"
