"""Handler for the ``/todo board`` command."""

from __future__ import annotations

import logging
import sqlite3
from collections import OrderedDict

from openclaw_todo.parser import ParsedCommand
from openclaw_todo.project_resolver import ProjectNotFoundError, resolve_project
from openclaw_todo.scope_builder import build_scope_conditions, format_assignees

logger = logging.getLogger(__name__)

DEFAULT_LIMIT_PER_SECTION = 10

SECTION_ORDER = ("backlog", "doing", "waiting", "done", "drop")


def board_handler(parsed: ParsedCommand, conn: sqlite3.Connection, context: dict) -> str:
    """Display tasks grouped by section in kanban board format."""
    sender_id: str = context["sender_id"]

    # --- Parse scope / limitPerSection from title_tokens ---
    scope = "mine"
    scope_user: str | None = None
    limit_per_section = DEFAULT_LIMIT_PER_SECTION

    tokens = list(parsed.title_tokens)

    status_token: str | None = None
    for tok in tokens:
        low = tok.lower()
        if low in ("mine", "all"):
            scope = low
        elif low in ("open", "done", "drop"):
            status_token = low
        elif low.startswith("limitpersection:"):
            try:
                limit_per_section = int(low.split(":", 1)[1])
                if limit_per_section < 1:
                    return f'❌ Invalid limitPerSection value "{tok}". Must be a positive integer.'
            except ValueError:
                return f'❌ Invalid limitPerSection value "{tok}". Must be a positive integer.'

    if parsed.mentions:
        scope = "user"
        scope_user = parsed.mentions[0]

    # --- Build query (same filtering as list) ---
    conditions: list[str] = []
    params: list[str | int] = []

    # Status filter: title_token > /s section > default "open"
    status_filter = "open"
    if status_token:
        status_filter = "dropped" if status_token == "drop" else status_token
    elif parsed.section in ("done", "drop"):
        status_filter = "done" if parsed.section == "done" else "dropped"

    conditions.append("t.status = ?")
    params.append(status_filter)

    # Project filter
    if parsed.project:
        try:
            project = resolve_project(conn, parsed.project, sender_id)
        except ProjectNotFoundError:
            return f'❌ Project "{parsed.project}" not found.'
        conditions.append("t.project_id = ?")
        params.append(project.id)

    # Scope filter
    scope_conds, scope_params = build_scope_conditions(scope, sender_id, scope_user)
    conditions.extend(scope_conds)
    params.extend(scope_params)

    where_clause = " AND ".join(conditions)

    query = (
        "SELECT t.id, t.title, t.section, t.due "
        "FROM tasks t "
        "JOIN projects p ON t.project_id = p.id "
        f"WHERE {where_clause} "
        "ORDER BY (CASE WHEN t.due IS NOT NULL THEN 0 ELSE 1 END), t.due ASC, t.id DESC"
    )

    rows = conn.execute(query, params).fetchall()

    # --- Group by section ---
    section_tasks: OrderedDict[str, list] = OrderedDict()
    for s in SECTION_ORDER:
        section_tasks[s] = []

    for row in rows:
        task_id, title, section, due = row
        if section in section_tasks:
            section_tasks[section].append((task_id, title, due))

    logger.info(
        "board: scope=%s project=%s sections=%s",
        scope,
        parsed.project,
        {s: len(tasks) for s, tasks in section_tasks.items()},
    )

    # --- Format output ---
    project_label = f" /p {parsed.project}" if parsed.project else ""
    header = f"📊 Board ({scope} / {status_filter}){project_label}"

    lines: list[str] = [header, ""]

    for section, tasks in section_tasks.items():
        lines.append(f"— {section.upper()} ({len(tasks)}) —")
        if not tasks:
            lines.append("(empty)")
        else:
            displayed = tasks[:limit_per_section]
            for task_id, title, due in displayed:
                due_str = due if due else "-"
                assignee_str = format_assignees(conn, task_id)
                lines.append(f"  #{task_id}  due:{due_str}  {assignee_str}  {title}")
            overflow = len(tasks) - limit_per_section
            if overflow > 0:
                lines.append(f"  ... and {overflow} more")
        lines.append("")

    return "\n".join(lines).rstrip()
