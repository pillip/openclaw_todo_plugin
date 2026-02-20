"""Permission helpers for the OpenClaw TODO plugin."""

from __future__ import annotations

import logging
import sqlite3

logger = logging.getLogger(__name__)


def can_write_task(conn: sqlite3.Connection, task_id: int, sender_id: str) -> bool:
    """Check whether *sender_id* is allowed to modify the task.

    Rules:
    - Private project: only the project owner can write.
    - Shared project: only an assignee or the task creator can write.
    """
    row = conn.execute(
        """
        SELECT t.created_by, p.visibility, p.owner_user_id
        FROM tasks t
        JOIN projects p ON p.id = t.project_id
        WHERE t.id = ?;
        """,
        (task_id,),
    ).fetchone()

    if row is None:
        logger.debug("Permission check: task=%d not found", task_id)
        return False

    created_by, visibility, owner_user_id = row

    if visibility == "private":
        result = sender_id == owner_user_id
        logger.debug(
            "Permission check: task=%d sender=%s result=%s (private, owner=%s)",
            task_id, sender_id, result, owner_user_id,
        )
        return result

    # Shared project: check assignee or creator
    if sender_id == created_by:
        logger.debug(
            "Permission check: task=%d sender=%s result=True (creator)",
            task_id, sender_id,
        )
        return True

    assignee_row = conn.execute(
        "SELECT 1 FROM task_assignees WHERE task_id = ? AND assignee_user_id = ?;",
        (task_id, sender_id),
    ).fetchone()

    result = assignee_row is not None
    logger.debug(
        "Permission check: task=%d sender=%s result=%s (shared, assignee check)",
        task_id, sender_id, result,
    )
    return result


def validate_private_assignees(
    visibility: str,
    assignees: list[str],
    owner_id: str | None,
) -> str | None:
    """Return a warning if non-owner assignees exist on a private project.

    Returns ``None`` for shared projects or when all assignees are the owner.
    """
    if visibility != "private":
        return None

    non_owner = [a for a in assignees if a != owner_id]
    if not non_owner:
        return None

    return (
        f"Private project cannot have non-owner assignees: {', '.join(non_owner)}"
    )
