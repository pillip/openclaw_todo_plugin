"""Project resolver: resolve project name to a project row (Option A — private first)."""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class ProjectNotFoundError(Exception):
    """Raised when a project cannot be resolved."""


@dataclass
class Project:
    """Represents a resolved project row."""

    id: int
    name: str
    visibility: str  # 'shared' | 'private'
    owner_user_id: str | None


def resolve_project(conn: sqlite3.Connection, name: str, sender_id: str) -> Project:
    """Resolve a project name following PRD 3.2 Option A.

    Resolution order:
    1. Sender's private project with that name (private-first)
    2. Shared project with that name
    3. If name is ``Inbox``, auto-create as shared
    4. Otherwise raise :class:`ProjectNotFoundError`
    """
    # 1) Private project of sender
    row = conn.execute(
        "SELECT id, name, visibility, owner_user_id FROM projects "
        "WHERE name = ? AND visibility = 'private' AND owner_user_id = ?;",
        (name, sender_id),
    ).fetchone()
    if row:
        project = Project(id=row[0], name=row[1], visibility=row[2], owner_user_id=row[3])
        logger.debug(
            "Resolved project '%s' -> id=%d vis=%s (private match)",
            name,
            project.id,
            project.visibility,
        )
        return project

    # 2) Shared project
    row = conn.execute(
        "SELECT id, name, visibility, owner_user_id FROM projects " "WHERE name = ? AND visibility = 'shared';",
        (name,),
    ).fetchone()
    if row:
        project = Project(id=row[0], name=row[1], visibility=row[2], owner_user_id=row[3])
        logger.debug(
            "Resolved project '%s' -> id=%d vis=%s (shared match)",
            name,
            project.id,
            project.visibility,
        )
        return project

    # 3) Auto-create Inbox as shared
    if name == "Inbox":
        conn.execute(
            "INSERT OR IGNORE INTO projects (name, visibility, owner_user_id) " "VALUES ('Inbox', 'shared', NULL);",
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, name, visibility, owner_user_id FROM projects "
            "WHERE name = 'Inbox' AND visibility = 'shared';",
        ).fetchone()
        project = Project(id=row[0], name=row[1], visibility=row[2], owner_user_id=row[3])
        logger.debug(
            "Resolved project '%s' -> id=%d vis=%s (auto-created)",
            name,
            project.id,
            project.visibility,
        )
        return project

    # 4) Not found
    raise ProjectNotFoundError(f"Project not found: {name!r}")
