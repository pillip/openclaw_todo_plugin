"""Handler for the ``/todo project delete`` subcommand."""

from __future__ import annotations

import logging
import sqlite3

from openclaw_todo.event_logger import log_event
from openclaw_todo.parser import ParsedCommand
from openclaw_todo.project_resolver import AmbiguousProjectError, ProjectNotFoundError, resolve_project

logger = logging.getLogger(__name__)


def delete_handler(parsed: ParsedCommand, conn: sqlite3.Connection, context: dict) -> str:
    """Delete a project if it has no remaining tasks.

    Syntax: ``/todo project delete <name>``
    """
    sender_id: str = context["sender_id"]

    # Extract project name and optional visibility qualifier from tokens after "delete"
    tokens = parsed.title_tokens[1:] if len(parsed.title_tokens) > 1 else []
    if not tokens:
        return "❌ Project name is required. Usage: /todo project delete <name> [shared|private]"

    project_name = tokens[0].strip()
    if not project_name:
        return "❌ Project name is required. Usage: /todo project delete <name> [shared|private]"

    # Optional visibility qualifier (2nd token)
    vis_qualifier: str | None = None
    if len(tokens) >= 2 and tokens[1].strip().lower() in ("shared", "private"):
        vis_qualifier = tokens[1].strip().lower()

    # Block deletion of Inbox (system project) — case-insensitive guard
    if project_name.lower() == "inbox":
        return '❌ Cannot delete the system project "Inbox".'

    # Resolve project (Option A: private-first)
    try:
        project = resolve_project(conn, project_name, sender_id, visibility=vis_qualifier)
    except AmbiguousProjectError:
        return (
            f'❌ Ambiguous project name "{project_name}": both shared and private projects exist. '
            f'Append "shared" or "private" to disambiguate.'
        )
    except ProjectNotFoundError:
        return f'❌ Project "{project_name}" not found.'

    # Permission: private projects can only be deleted by owner
    if project.visibility == "private" and project.owner_user_id != sender_id:
        return f'❌ Project "{project_name}" not found.'

    # Check for remaining tasks
    row = conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE project_id = ?;",
        (project.id,),
    ).fetchone()
    task_count = row[0]

    if task_count > 0:
        return (
            f'❌ Cannot delete: project "{project_name}" still has '
            f"{task_count} task(s). Remove or move them first."
        )

    # Delete the project
    conn.execute("DELETE FROM projects WHERE id = ?;", (project.id,))

    log_event(
        conn,
        actor_user_id=sender_id,
        action="project.delete",
        payload={
            "project_id": project.id,
            "name": project_name,
            "visibility": project.visibility,
        },
    )
    conn.commit()

    logger.info("project delete: %s visibility=%s by %s", project_name, project.visibility, sender_id)
    return f'✅ Deleted project "{project_name}" ({project.visibility})'
