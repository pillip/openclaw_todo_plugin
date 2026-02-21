"""Handler for the ``/todo project set-private`` subcommand."""

from __future__ import annotations

import logging
import sqlite3

from openclaw_todo.event_logger import log_event
from openclaw_todo.parser import ParsedCommand

logger = logging.getLogger(__name__)

_MAX_VIOLATIONS = 10


def set_private_handler(parsed: ParsedCommand, conn: sqlite3.Connection, context: dict) -> str:
    """Set a project to private for the sender.

    Resolution flow:
    1. If sender already has a private project with that name → noop.
    2. If a shared project with that name exists → attempt conversion
       (reject if any task has a non-owner assignee).
    3. If neither exists → create a new private project.
    """
    sender_id: str = context["sender_id"]

    # Extract project name from title_tokens (tokens after "set-private")
    name_tokens = parsed.title_tokens[1:] if len(parsed.title_tokens) > 1 else []
    if not name_tokens:
        return "Error: project name required. Usage: todo: project set-private <name>"
    project_name = name_tokens[0]

    # Step 1: Check if sender already has a private project with this name
    row = conn.execute(
        "SELECT id FROM projects " "WHERE name = ? AND visibility = 'private' AND owner_user_id = ?;",
        (project_name, sender_id),
    ).fetchone()
    if row is not None:
        logger.info("project set-private: %s result=already_private by %s", project_name, sender_id)
        return f"Project '{project_name}' is already private for you."

    # Step 2: Check if a shared project with this name exists
    shared_row = conn.execute(
        "SELECT id FROM projects " "WHERE name = ? AND visibility = 'shared';",
        (project_name,),
    ).fetchone()

    if shared_row is not None:
        project_id = shared_row[0]
        return _convert_shared_to_private(conn, project_id, project_name, sender_id)

    # Step 3: Neither exists → create new private project
    cursor = conn.execute(
        "INSERT INTO projects (name, visibility, owner_user_id) " "VALUES (?, 'private', ?);",
        (project_name, sender_id),
    )
    new_id = cursor.lastrowid

    log_event(
        conn,
        actor_user_id=sender_id,
        action="project.create_private",
        payload={"project_id": new_id, "name": project_name},
    )
    conn.commit()

    logger.info("project set-private: %s result=created by %s", project_name, sender_id)
    return f"Created private project '{project_name}'."


def _convert_shared_to_private(
    conn: sqlite3.Connection,
    project_id: int,
    project_name: str,
    sender_id: str,
) -> str:
    """Attempt to convert a shared project to private.

    Scans all tasks in the project. If any task has a non-owner assignee,
    the conversion is rejected with a list of violating tasks.
    """
    # Find tasks with non-owner assignees
    violations = conn.execute(
        "SELECT t.id, ta.assignee_user_id "
        "FROM tasks t "
        "JOIN task_assignees ta ON ta.task_id = t.id "
        "WHERE t.project_id = ? AND ta.assignee_user_id != ?;",
        (project_id, sender_id),
    ).fetchall()

    if violations:
        # Group by task ID
        task_ids: list[int] = []
        assignees: set[str] = set()
        for task_id, assignee in violations:
            if task_id not in task_ids:
                task_ids.append(task_id)
            assignees.add(assignee)

        # Truncate to max violations
        shown_tasks = task_ids[:_MAX_VIOLATIONS]
        shown_assignees = sorted(assignees)[:_MAX_VIOLATIONS]

        task_list = ", ".join(f"#{tid}" for tid in shown_tasks)
        assignee_list = ", ".join(shown_assignees)

        suffix = ""
        if len(task_ids) > _MAX_VIOLATIONS:
            suffix += f" (+{len(task_ids) - _MAX_VIOLATIONS} more tasks)"
        if len(assignees) > _MAX_VIOLATIONS:
            suffix += f" (+{len(assignees) - _MAX_VIOLATIONS} more assignees)"

        logger.info(
            "project set-private: %s result=rejected by %s (%d violations)",
            project_name,
            sender_id,
            len(violations),
        )
        return (
            f"Cannot make '{project_name}' private: "
            f"tasks [{task_list}] have non-owner assignees [{assignee_list}].{suffix}"
        )

    # All clear — convert
    conn.execute(
        "UPDATE projects SET visibility = 'private', owner_user_id = ?, " "updated_at = datetime('now') WHERE id = ?;",
        (sender_id, project_id),
    )

    log_event(
        conn,
        actor_user_id=sender_id,
        action="project.set_private",
        payload={
            "project_id": project_id,
            "name": project_name,
            "old_visibility": "shared",
        },
    )
    conn.commit()

    logger.info("project set-private: %s result=converted by %s", project_name, sender_id)
    return f"Project '{project_name}' is now private."
