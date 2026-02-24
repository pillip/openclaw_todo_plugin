"""Handler for the ``/todo list`` command."""

from __future__ import annotations

import logging
import sqlite3

from openclaw_todo.parser import ParsedCommand
from openclaw_todo.project_resolver import ProjectNotFoundError, resolve_project
from openclaw_todo.scope_builder import build_scope_conditions, format_assignees

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

    # Extract scope, limit, and status from tokens
    remaining_tokens: list[str] = []
    status_token: str | None = None
    for tok in tokens:
        low = tok.lower()
        if low in ("mine", "all"):
            scope = low
        elif low in ("open", "done", "drop"):
            status_token = low
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

    # Status filter: title_token > /s section > default "open"
    status_filter = "open"
    if status_token:
        status_filter = "dropped" if status_token == "drop" else status_token
        section_filter = parsed.section if parsed.section not in ("done", "drop") else None
    elif parsed.section in ("done", "drop"):
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
    scope_conds, scope_params = build_scope_conditions(scope, sender_id, scope_user)
    conditions.extend(scope_conds)
    params.extend(scope_params)

    where_clause = " AND ".join(conditions)

    # --- Count total matching rows ---
    count_query = (
        "SELECT COUNT(*) "
        "FROM tasks t "
        "JOIN projects p ON t.project_id = p.id "
        f"WHERE {where_clause}"
    )
    total_count = conn.execute(count_query, params).fetchone()[0]

    # --- Fetch limited rows ---
    query = (
        "SELECT t.id, t.title, t.section, t.due, p.name AS project_name "
        "FROM tasks t "
        "JOIN projects p ON t.project_id = p.id "
        f"WHERE {where_clause} "
        "ORDER BY (CASE WHEN t.due IS NOT NULL THEN 0 ELSE 1 END), t.due ASC, t.id DESC "
        "LIMIT ?"
    )
    fetch_params = list(params) + [limit]

    rows = conn.execute(query, fetch_params).fetchall()

    logger.info(
        "list: scope=%s project=%s returned %d rows",
        scope,
        parsed.project,
        len(rows),
    )

    # --- Build header ---
    project_label = f" /p {parsed.project}" if parsed.project else ""
    section_label = f" /s {parsed.section}" if section_filter else ""
    header = f"📋 TODO List ({scope} / {status_filter}){project_label}{section_label} — {total_count} tasks"

    if total_count == 0:
        return f"{header}\n\nNo tasks found."

    # --- Format output ---
    lines: list[str] = [header, ""]
    for row in rows:
        task_id, title, section, due, project_name = row
        due_str = due if due else "-"
        assignee_str = format_assignees(conn, task_id)
        lines.append(f"#{task_id}  due:{due_str}  ({project_name}/{section})  {assignee_str}  {title}")

    # --- Footer ---
    displayed = len(rows)
    lines.append("")
    lines.append(f"Showing {displayed} of {total_count}. Use limit:N to see more.")

    return "\n".join(lines)
