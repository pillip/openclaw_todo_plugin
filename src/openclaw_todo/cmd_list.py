"""Handler for the ``/todo list`` command."""

from __future__ import annotations

import logging
import sqlite3

from openclaw_todo.parser import ParsedCommand
from openclaw_todo.project_resolver import ProjectNotFoundError, resolve_project

logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 30


def list_handler(parsed: ParsedCommand, conn: sqlite3.Connection, context: dict) -> str:
    """Query and display tasks with filtering, sorting, and scope support.

    Scope resolution:
    - ``mine`` (default): tasks where sender is an assignee
    - ``all``: shared projects + sender's private (excludes others' private)
    - ``<@UXXXX>``: tasks assigned to a specific user (same visibility rules)

    Sorting: due NOT NULL first, due ASC, id DESC.
    """
    sender_id: str = context["sender_id"]

    # --- Parse scope from title_tokens ---
    scope = "mine"
    scope_user: str | None = None
    limit = DEFAULT_LIMIT

    tokens = list(parsed.title_tokens)

    # Extract scope and limit from tokens
    remaining_tokens: list[str] = []
    for tok in tokens:
        low = tok.lower()
        if low in ("mine", "all"):
            scope = low
        elif low.startswith("limit:"):
            try:
                limit = int(low.split(":", 1)[1])
                if limit < 1:
                    return f"Error: limit must be a positive integer, got: {tok!r}"
            except ValueError:
                return f"Error: invalid limit value: {tok!r}"
        else:
            remaining_tokens.append(tok)

    # If mentions present in parsed, treat first as scope target
    if parsed.mentions:
        scope = "user"
        scope_user = parsed.mentions[0]

    # --- Build query ---
    conditions: list[str] = []
    params: list[str | int] = []

    # Status filter (default: open)
    status_filter = "open"
    if parsed.section in ("done", "drop"):
        status_filter = "done" if parsed.section == "done" else "dropped"
        # Don't also filter by section since we're using status
        section_filter = None
    else:
        section_filter = parsed.section

    conditions.append("t.status = ?")
    params.append(status_filter)

    # Section filter
    if section_filter:
        conditions.append("t.section = ?")
        params.append(section_filter)

    # Project filter
    if parsed.project:
        try:
            project = resolve_project(conn, parsed.project, sender_id)
        except ProjectNotFoundError:
            return f"Error: project {parsed.project!r} not found."
        conditions.append("t.project_id = ?")
        params.append(project.id)

    # Scope filter
    if scope == "mine":
        conditions.append(
            "t.id IN (SELECT task_id FROM task_assignees WHERE assignee_user_id = ?)"
        )
        params.append(sender_id)
        # Also exclude others' private projects
        conditions.append(
            "(p.visibility = 'shared' OR p.owner_user_id = ?)"
        )
        params.append(sender_id)
    elif scope == "all":
        conditions.append(
            "(p.visibility = 'shared' OR p.owner_user_id = ?)"
        )
        params.append(sender_id)
    elif scope == "user" and scope_user:
        conditions.append(
            "t.id IN (SELECT task_id FROM task_assignees WHERE assignee_user_id = ?)"
        )
        params.append(scope_user)
        # Still enforce visibility
        conditions.append(
            "(p.visibility = 'shared' OR p.owner_user_id = ?)"
        )
        params.append(sender_id)

    where_clause = " AND ".join(conditions)

    query = (
        "SELECT t.id, t.title, t.section, t.due, p.name AS project_name "
        "FROM tasks t "
        "JOIN projects p ON t.project_id = p.id "
        f"WHERE {where_clause} "
        "ORDER BY (CASE WHEN t.due IS NOT NULL THEN 0 ELSE 1 END), t.due ASC, t.id DESC "
        "LIMIT ?"
    )
    params.append(limit)

    rows = conn.execute(query, params).fetchall()

    logger.info(
        "list: scope=%s project=%s returned %d rows",
        scope, parsed.project, len(rows),
    )

    if not rows:
        return "No tasks found."

    # --- Format output ---
    lines: list[str] = []
    for row in rows:
        task_id, title, section, due, project_name = row
        due_str = due if due else "-"
        # Get assignees for this task
        assignee_rows = conn.execute(
            "SELECT assignee_user_id FROM task_assignees WHERE task_id = ?",
            (task_id,),
        ).fetchall()
        assignee_str = ", ".join(f"<@{a[0]}>" for a in assignee_rows)
        lines.append(
            f"#{task_id} ({project_name}/{section}) due:{due_str} "
            f"assignees:{assignee_str} -- {title}"
        )

    return "\n".join(lines)
