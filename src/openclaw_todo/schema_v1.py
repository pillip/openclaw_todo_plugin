"""V1 schema migration: projects, tasks, task_assignees, events tables."""

from __future__ import annotations

import logging
import sqlite3

from openclaw_todo.migrations import register

logger = logging.getLogger(__name__)


@register
def migrate_v1(conn: sqlite3.Connection) -> None:
    """Create the four core tables and seed the Inbox project."""

    conn.execute("""
        CREATE TABLE projects (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT NOT NULL,
            visibility      TEXT NOT NULL CHECK (visibility IN ('shared', 'private')),
            owner_user_id   TEXT NULL,
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)

    conn.execute("""
        CREATE UNIQUE INDEX ux_projects_shared_name
        ON projects(name) WHERE visibility = 'shared';
    """)

    conn.execute("""
        CREATE UNIQUE INDEX ux_projects_private_owner_name
        ON projects(owner_user_id, name) WHERE visibility = 'private';
    """)

    conn.execute("""
        CREATE TABLE tasks (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            title           TEXT NOT NULL,
            project_id      INTEGER NOT NULL REFERENCES projects(id),
            section         TEXT NOT NULL CHECK (section IN ('backlog', 'doing', 'waiting', 'done', 'drop')),
            due             TEXT NULL,
            status          TEXT NOT NULL CHECK (status IN ('open', 'done', 'dropped')),
            created_by      TEXT NOT NULL,
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
            closed_at       TEXT NULL
        );
    """)

    conn.execute("""
        CREATE TABLE task_assignees (
            task_id             INTEGER NOT NULL REFERENCES tasks(id),
            assignee_user_id    TEXT NOT NULL,
            PRIMARY KEY (task_id, assignee_user_id)
        );
    """)

    conn.execute("""
        CREATE INDEX ix_task_assignees_user
        ON task_assignees(assignee_user_id, task_id);
    """)

    conn.execute("""
        CREATE TABLE events (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            ts              TEXT NOT NULL DEFAULT (datetime('now')),
            actor_user_id   TEXT,
            action          TEXT,
            task_id         INTEGER NULL,
            payload         TEXT
        );
    """)

    # Seed shared Inbox project
    conn.execute("""
        INSERT OR IGNORE INTO projects (name, visibility, owner_user_id)
        VALUES ('Inbox', 'shared', NULL);
    """)

    logger.info("V1 schema created: projects, tasks, task_assignees, events + Inbox seeded")
