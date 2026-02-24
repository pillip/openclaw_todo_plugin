"""Handler for the ``/todo add`` command."""

from __future__ import annotations

import logging
import sqlite3

from openclaw_todo.event_logger import log_event
from openclaw_todo.parser import DUE_CLEAR, ParsedCommand
from openclaw_todo.project_resolver import Project, ProjectNotFoundError, resolve_project

logger = logging.getLogger(__name__)


def add_handler(parsed: ParsedCommand, conn: sqlite3.Connection, context: dict) -> str:
    """Create a new task.

    Resolves the target project (default ``Inbox``), applies defaults for
    section and assignees, validates the private-project assignee constraint,
    inserts the task + assignee rows, and logs an event.
    """
    sender_id: str = context["sender_id"]
    title = " ".join(parsed.title_tokens)

    if not title:
        return "❌ Title is required. Usage: todo: add <title> [options]"

    # --- Resolve project (auto-create as shared if not found) ---
    project_name = parsed.project or "Inbox"
    project_auto_created = False
    try:
        project = resolve_project(conn, project_name, sender_id)
    except ProjectNotFoundError:
        # Validate project name before auto-creating
        stripped = project_name.strip()
        if not stripped or len(stripped) > 128:
            return "❌ Project name must be 1-128 characters."
        if not all(c.isalnum() or c in " _-" for c in stripped):
            return "❌ Project name may only contain letters, digits, spaces, hyphens, and underscores."

        try:
            conn.execute(
                "INSERT INTO projects (name, visibility, owner_user_id) VALUES (?, 'shared', NULL);",
                (stripped,),
            )
        except sqlite3.IntegrityError:
            # Race condition: another concurrent request already created it
            logger.debug("Concurrent auto-create for project '%s'; falling back to SELECT", stripped)

        row = conn.execute(
            "SELECT id, name, visibility, owner_user_id FROM projects WHERE name = ? AND visibility = 'shared';",
            (stripped,),
        ).fetchone()
        project = Project(id=row[0], name=row[1], visibility=row[2], owner_user_id=row[3])
        project_auto_created = True
        logger.info("Auto-created shared project '%s' for add command", project_name)

    # --- Defaults ---
    section = parsed.section or "backlog"
    due = parsed.due if parsed.due and parsed.due != DUE_CLEAR else None
    assignees = parsed.mentions if parsed.mentions else [sender_id]

    # --- Private project assignee validation (PRD 3.3) ---
    if project.visibility == "private":
        non_owner = [a for a in assignees if a != project.owner_user_id]
        if non_owner:
            formatted = ", ".join(f"<@{uid}>" for uid in non_owner)
            return (
                f'⚠️ Private 프로젝트("{project.name}")는 owner만 볼 수 있어요. '
                f"다른 담당자({formatted})를 지정할 수 없습니다.\n"
                f"(요청이 적용되지 않았습니다.)"
            )

    # --- Insert task ---
    cursor = conn.execute(
        "INSERT INTO tasks (title, project_id, section, due, status, created_by) " "VALUES (?, ?, ?, ?, 'open', ?);",
        (title, project.id, section, due, sender_id),
    )
    task_id = cursor.lastrowid

    # --- Insert assignees ---
    for assignee in assignees:
        conn.execute(
            "INSERT INTO task_assignees (task_id, assignee_user_id) VALUES (?, ?);",
            (task_id, assignee),
        )

    # --- Log events ---
    if project_auto_created:
        log_event(
            conn,
            actor_user_id=sender_id,
            action="project.auto_create",
            task_id=None,
            payload={"project": project.name, "visibility": "shared"},
        )

    log_event(
        conn,
        actor_user_id=sender_id,
        action="task.add",
        task_id=task_id,
        payload={
            "title": title,
            "project": project.name,
            "section": section,
            "due": due,
            "assignees": assignees,
        },
    )

    conn.commit()

    logger.info("Task #%d created in %s/%s by %s", task_id, project.name, section, sender_id)

    # --- Format response ---
    due_str = due if due else "-"
    assignee_str = ", ".join(f"<@{a}>" for a in assignees)
    response = f"✅ Added #{task_id} ({project.name}/{section}) due:{due_str} assignees:{assignee_str} — {title}"
    if project_auto_created:
        response = f'{response}\nℹ️ Project "{project.name}" was created (shared).'
    return response
