"""Handler for the ``/todo project rename`` subcommand."""

from __future__ import annotations

import logging
import sqlite3

from openclaw_todo.event_logger import log_event
from openclaw_todo.parser import ParsedCommand
from openclaw_todo.project_resolver import ProjectNotFoundError, resolve_project

logger = logging.getLogger(__name__)


def rename_handler(parsed: ParsedCommand, conn: sqlite3.Connection, context: dict) -> str:
    """Rename a project.

    Syntax: ``/todo project rename <old_name> <new_name>``

    Resolution uses Option A (sender private-first → shared).
    Private projects can only be renamed by their owner.
    """
    sender_id: str = context["sender_id"]

    # Extract tokens after "rename": [old_name, new_name]
    tokens = parsed.title_tokens[1:] if len(parsed.title_tokens) > 1 else []
    if len(tokens) < 2:
        return "❌ Both old and new names are required. Usage: /todo project rename <old> <new>"

    old_name = tokens[0].strip()
    new_name = tokens[1].strip()

    if not old_name or not new_name:
        return "❌ Both old and new names are required. Usage: /todo project rename <old> <new>"

    # Same-name noop
    if old_name == new_name:
        return f'ℹ️ Project "{old_name}" already has that name.'

    # Resolve old project using Option A
    try:
        project = resolve_project(conn, old_name, sender_id)
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
