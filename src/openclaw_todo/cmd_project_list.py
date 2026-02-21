"""Handler for the ``/todo project list`` subcommand."""

from __future__ import annotations

import logging
import sqlite3

from openclaw_todo.parser import ParsedCommand

logger = logging.getLogger(__name__)


def project_list_handler(
    parsed: ParsedCommand, conn: sqlite3.Connection, context: dict
) -> str:
    """List all shared projects and the sender's private projects with task counts."""
    sender_id: str = context["sender_id"]

    rows = conn.execute(
        "SELECT p.id, p.name, p.visibility, p.owner_user_id, "
        "       COUNT(t.id) AS task_count "
        "FROM projects p "
        "LEFT JOIN tasks t ON t.project_id = p.id "
        "WHERE p.visibility = 'shared' "
        "   OR (p.visibility = 'private' AND p.owner_user_id = ?) "
        "GROUP BY p.id "
        "ORDER BY p.visibility, p.name;",
        (sender_id,),
    ).fetchall()

    if not rows:
        return "No projects found."

    shared_lines: list[str] = []
    private_lines: list[str] = []

    for row in rows:
        _pid, name, visibility, _owner, task_count = row
        line = f"  {name} ({task_count} tasks)"
        if visibility == "shared":
            shared_lines.append(line)
        else:
            private_lines.append(line)

    parts: list[str] = []
    if shared_lines:
        parts.append("Shared:")
        parts.extend(shared_lines)
    if private_lines:
        parts.append("Private:")
        parts.extend(private_lines)

    shared_count = len(shared_lines)
    private_count = len(private_lines)
    logger.info(
        "project list: %d shared, %d private for %s",
        shared_count, private_count, sender_id,
    )

    return "\n".join(parts)
