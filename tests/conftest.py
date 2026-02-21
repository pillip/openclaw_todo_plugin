"""Shared fixtures for the openclaw_todo test suite."""

from __future__ import annotations

import pytest

from openclaw_todo.db import get_connection
from openclaw_todo.migrations import _migrations, migrate


@pytest.fixture(autouse=True)
def _load_v1():
    """Ensure V1 migration is registered."""
    saved = _migrations.copy()
    _migrations.clear()
    from openclaw_todo.schema_v1 import migrate_v1

    if migrate_v1 not in _migrations:
        _migrations.append(migrate_v1)
    yield
    _migrations.clear()
    _migrations.extend(saved)


@pytest.fixture()
def conn(tmp_path):
    """Return a migrated V1 connection."""
    c = get_connection(tmp_path / "test.sqlite3")
    migrate(c)
    yield c
    c.close()


def seed_task(
    conn,
    *,
    project_name="Inbox",
    visibility="shared",
    owner=None,
    title="Test task",
    section="backlog",
    created_by="U001",
    assignees=None,
    due=None,
):
    """Insert a task with associated project and assignees. Returns task_id."""
    row = conn.execute("SELECT id FROM projects WHERE name = ?", (project_name,)).fetchone()
    if row:
        project_id = row[0]
    else:
        conn.execute(
            "INSERT INTO projects (name, visibility, owner_user_id) VALUES (?, ?, ?);",
            (project_name, visibility, owner),
        )
        project_id = conn.execute("SELECT id FROM projects WHERE name = ?", (project_name,)).fetchone()[0]

    cursor = conn.execute(
        "INSERT INTO tasks (title, project_id, section, status, created_by, due) " "VALUES (?, ?, ?, 'open', ?, ?);",
        (title, project_id, section, created_by, due),
    )
    task_id = cursor.lastrowid

    for assignee in assignees or [created_by]:
        conn.execute(
            "INSERT INTO task_assignees (task_id, assignee_user_id) VALUES (?, ?);",
            (task_id, assignee),
        )
    conn.commit()
    return task_id
