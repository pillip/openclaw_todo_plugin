"""Handler for the ``/todo project set-shared`` subcommand."""

from __future__ import annotations

import logging
import sqlite3

from openclaw_todo.event_logger import log_event
from openclaw_todo.parser import ParsedCommand

logger = logging.getLogger(__name__)


def set_shared_handler(parsed: ParsedCommand, conn: sqlite3.Connection, context: dict) -> str:
    """Set a project to shared (or create a new shared project).

    Resolution flow:
    1. If a shared project with that name already exists -> noop.
    2. If the sender owns a private project with that name -> convert to shared.
    3. If neither exists -> create a new shared project.
    """
    sender_id: str = context["sender_id"]

    # Extract project name from title_tokens (tokens after "set-shared")
    name_tokens = parsed.title_tokens[1:] if len(parsed.title_tokens) > 1 else []
    if not name_tokens:
        return "Error: project name required. Usage: !todo project set-shared <name>"
    project_name = name_tokens[0]

    # Step 1: Check if a shared project with this name already exists
    row = conn.execute(
        "SELECT id FROM projects " "WHERE name = ? AND visibility = 'shared';",
        (project_name,),
    ).fetchone()
    if row is not None:
        logger.info("project set-shared: %s result=already_shared", project_name)
        return f"Project '{project_name}' is already shared."

    # Step 2: Check if sender has a private project with this name
    private_row = conn.execute(
        "SELECT id FROM projects " "WHERE name = ? AND visibility = 'private' AND owner_user_id = ?;",
        (project_name, sender_id),
    ).fetchone()

    if private_row is not None:
        project_id = private_row[0]
        return _convert_private_to_shared(conn, project_id, project_name, sender_id)

    # Step 3: Neither exists -> create new shared project
    try:
        cursor = conn.execute(
            "INSERT INTO projects (name, visibility, owner_user_id) " "VALUES (?, 'shared', NULL);",
            (project_name,),
        )
    except sqlite3.IntegrityError:
        # Concurrent request already created the shared project (TOCTOU).
        return f"Project '{project_name}' is already shared."
    new_id = cursor.lastrowid

    log_event(
        conn,
        actor_user_id=sender_id,
        action="project.create_shared",
        payload={"project_id": new_id, "name": project_name},
    )
    conn.commit()

    logger.info("project set-shared: %s result=created by %s", project_name, sender_id)
    return f"Created shared project '{project_name}'."


def _convert_private_to_shared(
    conn: sqlite3.Connection,
    project_id: int,
    project_name: str,
    sender_id: str,
) -> str:
    """Convert a private project to shared."""
    try:
        conn.execute(
            "UPDATE projects SET visibility = 'shared', owner_user_id = NULL, "
            "updated_at = datetime('now') WHERE id = ?;",
            (project_id,),
        )
    except sqlite3.IntegrityError:
        # A shared project with this name was created concurrently (TOCTOU).
        return f"Project '{project_name}' is already shared."

    log_event(
        conn,
        actor_user_id=sender_id,
        action="project.set_shared",
        payload={
            "project_id": project_id,
            "name": project_name,
            "old_visibility": "private",
        },
    )
    conn.commit()

    logger.info("project set-shared: %s result=converted by %s", project_name, sender_id)
    return f"Project '{project_name}' is now shared."
