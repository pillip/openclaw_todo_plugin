"""Handler for the ``/todo project rename`` subcommand."""

from __future__ import annotations

import logging
import sqlite3

from openclaw_todo.event_logger import log_event
from openclaw_todo.parser import ParsedCommand
from openclaw_todo.project_resolver import AmbiguousProjectError, ProjectNotFoundError, resolve_project

logger = logging.getLogger(__name__)


def rename_handler(parsed: ParsedCommand, conn: sqlite3.Connection, context: dict) -> str:
    """Rename a project.

    Syntax: ``/todo project rename <old_name> <new_name>``

    Resolution uses Option A (sender private-first → shared).
    Private projects can only be renamed by their owner.
    """
    sender_id: str = context["sender_id"]

    # Extract tokens after "rename": [old_name, new_name, ?qualifier]
    tokens = parsed.title_tokens[1:] if len(parsed.title_tokens) > 1 else []
    if len(tokens) < 2:
        return "❌ Both old and new names are required. Usage: /todo project rename <old> <new> [shared|private]"

    old_name = tokens[0].strip()
    new_name = tokens[1].strip()

    # Optional visibility qualifier (3rd token)
    vis_qualifier: str | None = None
    if len(tokens) >= 3 and tokens[2].strip().lower() in ("shared", "private"):
        vis_qualifier = tokens[2].strip().lower()

    if not old_name or not new_name:
        return "❌ Both old and new names are required. Usage: /todo project rename <old> <new> [shared|private]"

    # Same-name noop
    if old_name == new_name:
        return f'ℹ️ Project "{old_name}" already has that name.'

    # Resolve old project using Option A
    try:
        project = resolve_project(conn, old_name, sender_id, visibility=vis_qualifier)
    except AmbiguousProjectError:
        return (
            f'❌ Ambiguous project name "{old_name}": both shared and private projects exist. '
            f'Append "shared" or "private" to disambiguate.'
        )
    except ProjectNotFoundError:
        return f'❌ Project "{old_name}" not found.'

    # Permission check: private projects can only be renamed by owner
    if project.visibility == "private" and project.owner_user_id != sender_id:
        # Hide existence of other users' private projects
        return f'❌ Project "{old_name}" not found.'

    # Attempt rename via UPDATE — rely on DB constraints for duplicate detection
    try:
        conn.execute(
            "UPDATE projects SET name = ?, updated_at = datetime('now') WHERE id = ?;",
            (new_name, project.id),
        )
    except sqlite3.IntegrityError:
        if project.visibility == "shared":
            return f'❌ Cannot rename: shared project "{new_name}" already exists.'
        else:
            return f'❌ Cannot rename: you already have a private project named "{new_name}".'

    log_event(
        conn,
        actor_user_id=sender_id,
        action="project.rename",
        payload={
            "project_id": project.id,
            "old_name": old_name,
            "new_name": new_name,
            "visibility": project.visibility,
        },
    )
    conn.commit()

    logger.info(
        "project rename: %s -> %s visibility=%s by %s",
        old_name,
        new_name,
        project.visibility,
        sender_id,
    )
    return f'✅ Renamed project "{old_name}" -> "{new_name}" ({project.visibility})'
