"""Project resolver: resolve project name to a project row (Option A — private first)."""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class ProjectNotFoundError(Exception):
    """Raised when a project cannot be resolved."""


class AmbiguousProjectError(Exception):
    """Raised when both shared and private projects exist with the same name."""


@dataclass
class Project:
    """Represents a resolved project row."""

    id: int
    name: str
    visibility: str  # 'shared' | 'private'
    owner_user_id: str | None


def resolve_project(
    conn: sqlite3.Connection,
    name: str,
    sender_id: str,
    visibility: str | None = None,
) -> Project:
    """Resolve a project name following PRD 3.2 Option A.

    Resolution order (when *visibility* is ``None``):
    1. If both private (owned by sender) and shared exist → raise
       :class:`AmbiguousProjectError`
    2. Sender's private project with that name (private-first)
    3. Shared project with that name
    4. If name is ``Inbox``, auto-create as shared
    5. Otherwise raise :class:`ProjectNotFoundError`

    When *visibility* is ``'shared'`` or ``'private'``, only that type is
    queried (no ambiguity check).
    """
    if visibility == "private":
        row = conn.execute(
            "SELECT id, name, visibility, owner_user_id FROM projects "
            "WHERE name = ? AND visibility = 'private' AND owner_user_id = ?;",
            (name, sender_id),
        ).fetchone()
        if row:
            return Project(id=row[0], name=row[1], visibility=row[2], owner_user_id=row[3])
        raise ProjectNotFoundError(f"Project not found: {name!r}")

    if visibility == "shared":
        row = conn.execute(
            "SELECT id, name, visibility, owner_user_id FROM projects "
            "WHERE name = ? AND visibility = 'shared';",
            (name,),
        ).fetchone()
        if row:
            return Project(id=row[0], name=row[1], visibility=row[2], owner_user_id=row[3])
        # Auto-create Inbox as shared
        if name == "Inbox":
            conn.execute(
                "INSERT OR IGNORE INTO projects (name, visibility, owner_user_id) "
                "VALUES ('Inbox', 'shared', NULL);",
            )
            conn.commit()
            row = conn.execute(
                "SELECT id, name, visibility, owner_user_id FROM projects "
                "WHERE name = 'Inbox' AND visibility = 'shared';",
            ).fetchone()
            return Project(id=row[0], name=row[1], visibility=row[2], owner_user_id=row[3])
        raise ProjectNotFoundError(f"Project not found: {name!r}")

    # --- No explicit visibility: detect ambiguity ---
    # 1) Private project of sender
    private_row = conn.execute(
        "SELECT id, name, visibility, owner_user_id FROM projects "
        "WHERE name = ? AND visibility = 'private' AND owner_user_id = ?;",
        (name, sender_id),
    ).fetchone()

    # 2) Shared project
    shared_row = conn.execute(
        "SELECT id, name, visibility, owner_user_id FROM projects "
        "WHERE name = ? AND visibility = 'shared';",
        (name,),
    ).fetchone()

    # Both exist → ambiguous
    if private_row and shared_row:
        raise AmbiguousProjectError(
            f'Ambiguous project name "{name}": both shared and private projects exist. '
            f'Append "shared" or "private" to disambiguate.'
        )

    if private_row:
        project = Project(
            id=private_row[0], name=private_row[1],
            visibility=private_row[2], owner_user_id=private_row[3],
        )
        logger.debug(
            "Resolved project '%s' -> id=%d vis=%s (private match)",
            name, project.id, project.visibility,
        )
        return project

    if shared_row:
        project = Project(
            id=shared_row[0], name=shared_row[1],
            visibility=shared_row[2], owner_user_id=shared_row[3],
        )
        logger.debug(
            "Resolved project '%s' -> id=%d vis=%s (shared match)",
            name, project.id, project.visibility,
        )
        return project

    # 3) Auto-create Inbox as shared
    if name == "Inbox":
        conn.execute(
            "INSERT OR IGNORE INTO projects (name, visibility, owner_user_id) "
            "VALUES ('Inbox', 'shared', NULL);",
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, name, visibility, owner_user_id FROM projects "
            "WHERE name = 'Inbox' AND visibility = 'shared';",
        ).fetchone()
        project = Project(id=row[0], name=row[1], visibility=row[2], owner_user_id=row[3])
        logger.debug(
            "Resolved project '%s' -> id=%d vis=%s (auto-created)",
            name, project.id, project.visibility,
        )
        return project

    # 4) Not found
    raise ProjectNotFoundError(f"Project not found: {name!r}")
