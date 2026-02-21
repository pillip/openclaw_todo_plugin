"""Handler for the ``/todo edit`` command."""

from __future__ import annotations

import json
import logging
import sqlite3

from openclaw_todo.parser import DUE_CLEAR, ParsedCommand
from openclaw_todo.permissions import can_write_task, validate_private_assignees
from openclaw_todo.project_resolver import ProjectNotFoundError, resolve_project

logger = logging.getLogger(__name__)


def edit_handler(parsed: ParsedCommand, conn: sqlite3.Connection, context: dict) -> str:
    """Edit a task's title, assignees, project, section, or due date."""
    sender_id: str = context["sender_id"]

    # --- Validate task ID ---
    if not parsed.args:
        return "Error: task ID required. Usage: /todo edit <id> [title] [options]"

    try:
        task_id = int(parsed.args[0])
    except ValueError:
        return f"Error: invalid task ID: {parsed.args[0]!r}"

    # --- Check task exists ---
    row = conn.execute(
        "SELECT title, project_id, section, due, created_by FROM tasks WHERE id = ?;",
        (task_id,),
    ).fetchone()
    if row is None:
        return f"Error: task #{task_id} not found."

    old_title, old_project_id, old_section, old_due, created_by = row

    # --- Check permission ---
    if not can_write_task(conn, task_id, sender_id):
        return f"Error: permission denied for task #{task_id}."

    # --- Collect changes ---
    changes: dict[str, tuple] = {}  # field -> (old, new)
    update_fields: list[str] = []
    update_params: list = []

    # Title: update if title_tokens present
    if parsed.title_tokens:
        new_title = " ".join(parsed.title_tokens)
        if new_title != old_title:
            changes["title"] = (old_title, new_title)
            update_fields.append("title = ?")
            update_params.append(new_title)

    # Section
    if parsed.section and parsed.section != old_section:
        changes["section"] = (old_section, parsed.section)
        update_fields.append("section = ?")
        update_params.append(parsed.section)

    # Due date
    if parsed.due is not None:
        if parsed.due == DUE_CLEAR:
            new_due = None
        else:
            new_due = parsed.due
        if new_due != old_due:
            changes["due"] = (old_due, new_due)
            update_fields.append("due = ?")
            update_params.append(new_due)

    # Project
    new_project_id = old_project_id
    if parsed.project:
        try:
            project = resolve_project(conn, parsed.project, sender_id)
        except ProjectNotFoundError:
            return f"Error: project {parsed.project!r} not found."
        if project.id != old_project_id:
            # Get old project name for the change log
            old_proj_name = conn.execute(
                "SELECT name FROM projects WHERE id = ?", (old_project_id,)
            ).fetchone()[0]
            changes["project"] = (old_proj_name, project.name)
            update_fields.append("project_id = ?")
            update_params.append(project.id)
            new_project_id = project.id

    # Assignees (full replace if mentions present)
    if parsed.mentions:
        old_assignees = [
            r[0] for r in conn.execute(
                "SELECT assignee_user_id FROM task_assignees WHERE task_id = ? ORDER BY assignee_user_id",
                (task_id,),
            ).fetchall()
        ]
        new_assignees = sorted(set(parsed.mentions))
        if old_assignees != new_assignees:
            # Validate private project constraint on target project
            proj_row = conn.execute(
                "SELECT visibility, owner_user_id FROM projects WHERE id = ?",
                (new_project_id,),
            ).fetchone()
            warning = validate_private_assignees(
                proj_row[0], new_assignees, proj_row[1]
            )
            if warning:
                return f"Error: {warning}"

            changes["assignees"] = (old_assignees, new_assignees)

    # --- No changes? ---
    if not changes:
        return f"No changes for task #{task_id}."

    # --- Apply updates ---
    if update_fields:
        update_fields.append("updated_at = datetime('now')")
        sql = f"UPDATE tasks SET {', '.join(update_fields)} WHERE id = ?;"
        update_params.append(task_id)
        conn.execute(sql, update_params)

    # Apply assignee replacement
    if "assignees" in changes:
        conn.execute("DELETE FROM task_assignees WHERE task_id = ?;", (task_id,))
        for assignee in changes["assignees"][1]:
            conn.execute(
                "INSERT INTO task_assignees (task_id, assignee_user_id) VALUES (?, ?);",
                (task_id, assignee),
            )

    # --- Log event ---
    payload = json.dumps({
        k: {"old": v[0], "new": v[1]} for k, v in changes.items()
    })
    conn.execute(
        "INSERT INTO events (actor_user_id, action, task_id, payload) "
        "VALUES (?, 'task.edit', ?, ?);",
        (sender_id, task_id, payload),
    )

    conn.commit()

    changed_fields = ", ".join(changes.keys())
    logger.info("Task #%d edited by %s: fields=%s", task_id, sender_id, changed_fields)

    return f"Edited #{task_id}: updated {changed_fields}."
