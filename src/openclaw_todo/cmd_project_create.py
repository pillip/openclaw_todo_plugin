"""Handler for the ``/todo project create`` subcommand."""

from __future__ import annotations

import logging
import sqlite3

from openclaw_todo.event_logger import log_event
from openclaw_todo.parser import ParsedCommand

logger = logging.getLogger(__name__)

_VALID_VISIBILITY = frozenset({"shared", "private"})


def create_handler(parsed: ParsedCommand, conn: sqlite3.Connection, context: dict) -> str:
    """Create a project with explicit visibility.

    Syntax: ``/todo project create <name> [shared|private]``
    Default visibility is ``shared``.
    """
    sender_id: str = context["sender_id"]

    # Extract tokens after "create"
    tokens = parsed.title_tokens[1:] if len(parsed.title_tokens) > 1 else []
    if not tokens:
        return "❌ Project name is required. Usage: /todo project create <name> [shared|private]"

    project_name = tokens[0].strip()
    if not project_name:
        return "❌ Project name is required. Usage: /todo project create <name> [shared|private]"

    # Parse optional visibility (default: shared)
    visibility = "shared"
    if len(tokens) >= 2:
        vis_input = tokens[1].lower()
        if vis_input not in _VALID_VISIBILITY:
            return f'❌ Invalid visibility "{tokens[1]}". Must be shared or private.'
        visibility = vis_input

    if visibility == "shared":
        return _create_shared(conn, project_name, sender_id)
    else:
        return _create_private(conn, project_name, sender_id)


def _create_shared(conn: sqlite3.Connection, name: str, sender_id: str) -> str:
    """Insert a shared project (owner_user_id=NULL)."""
    try:
        cursor = conn.execute(
            "INSERT INTO projects (name, visibility, owner_user_id) VALUES (?, 'shared', NULL);",
            (name,),
        )
    except sqlite3.IntegrityError:
        return f'❌ Cannot create: shared project "{name}" already exists.'

    project_id = cursor.lastrowid
    log_event(
        conn,
        actor_user_id=sender_id,
        action="project.create",
        payload={"project_id": project_id, "name": name, "visibility": "shared"},
    )
    conn.commit()

    logger.info("project create: %s visibility=shared by %s", name, sender_id)
    return f'✅ Created project "{name}" (shared)'


def _create_private(conn: sqlite3.Connection, name: str, sender_id: str) -> str:
    """Insert a private project (owner_user_id=sender)."""
    try:
        cursor = conn.execute(
            "INSERT INTO projects (name, visibility, owner_user_id) VALUES (?, 'private', ?);",
            (name, sender_id),
        )
    except sqlite3.IntegrityError:
        return f'❌ Cannot create: you already have a private project named "{name}".'

    project_id = cursor.lastrowid
    log_event(
        conn,
        actor_user_id=sender_id,
        action="project.create",
        payload={"project_id": project_id, "name": name, "visibility": "private"},
    )
    conn.commit()

    logger.info("project create: %s visibility=private by %s", name, sender_id)
    return f'✅ Created project "{name}" (private, owner:<@{sender_id}>)'
