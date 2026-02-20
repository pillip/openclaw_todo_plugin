"""Tests for the permissions helper module."""

from __future__ import annotations

import pytest

from openclaw_todo.db import get_connection
from openclaw_todo.migrations import migrate
from openclaw_todo.permissions import can_write_task, validate_private_assignees

import openclaw_todo.schema_v1  # noqa: F401 — register V1 migration


@pytest.fixture()
def conn(tmp_path):
    """Return a migrated in-memory-like SQLite connection."""
    db_path = tmp_path / "test.db"
    c = get_connection(db_path)
    migrate(c)
    return c


def _create_project(conn, name, visibility, owner_user_id=None):
    conn.execute(
        "INSERT INTO projects (name, visibility, owner_user_id) VALUES (?, ?, ?);",
        (name, visibility, owner_user_id),
    )
    conn.commit()
    return conn.execute(
        "SELECT id FROM projects WHERE name = ? AND visibility = ? "
        "AND (owner_user_id = ? OR (owner_user_id IS NULL AND ? IS NULL));",
        (name, visibility, owner_user_id, owner_user_id),
    ).fetchone()[0]


def _create_task(conn, project_id, title, created_by):
    conn.execute(
        "INSERT INTO tasks (title, project_id, section, status, created_by) "
        "VALUES (?, ?, 'backlog', 'open', ?);",
        (title, project_id, created_by),
    )
    conn.commit()
    return conn.execute("SELECT last_insert_rowid();").fetchone()[0]


def _assign(conn, task_id, user_id):
    conn.execute(
        "INSERT INTO task_assignees (task_id, assignee_user_id) VALUES (?, ?);",
        (task_id, user_id),
    )
    conn.commit()


class TestCanWriteTask:
    def test_private_owner_can_write(self, conn):
        pid = _create_project(conn, "MyPrivate", "private", "U_OWNER")
        tid = _create_task(conn, pid, "task1", "U_OWNER")
        assert can_write_task(conn, tid, "U_OWNER") is True

    def test_private_non_owner_rejected(self, conn):
        pid = _create_project(conn, "MyPrivate", "private", "U_OWNER")
        tid = _create_task(conn, pid, "task1", "U_OWNER")
        assert can_write_task(conn, tid, "U_OTHER") is False

    def test_shared_assignee_can_write(self, conn):
        pid = _create_project(conn, "TeamProject", "shared")
        tid = _create_task(conn, pid, "task1", "U_CREATOR")
        _assign(conn, tid, "U_ASSIGNEE")
        assert can_write_task(conn, tid, "U_ASSIGNEE") is True

    def test_shared_creator_can_write(self, conn):
        pid = _create_project(conn, "TeamProject", "shared")
        tid = _create_task(conn, pid, "task1", "U_CREATOR")
        assert can_write_task(conn, tid, "U_CREATOR") is True

    def test_shared_creator_and_assignee_can_write(self, conn):
        pid = _create_project(conn, "TeamProject2", "shared")
        tid = _create_task(conn, pid, "task1", "U_BOTH")
        _assign(conn, tid, "U_BOTH")
        assert can_write_task(conn, tid, "U_BOTH") is True

    def test_shared_unrelated_rejected(self, conn):
        pid = _create_project(conn, "TeamProject", "shared")
        tid = _create_task(conn, pid, "task1", "U_CREATOR")
        assert can_write_task(conn, tid, "U_STRANGER") is False

    def test_nonexistent_task(self, conn):
        assert can_write_task(conn, 99999, "U_ANY") is False


class TestValidatePrivateAssignees:
    def test_validate_private_assignees_warning(self):
        result = validate_private_assignees("private", ["U_OWNER", "U_OTHER"], "U_OWNER")
        assert result is not None
        assert "U_OTHER" in result

    def test_private_all_owner_ok(self):
        result = validate_private_assignees("private", ["U_OWNER"], "U_OWNER")
        assert result is None

    def test_shared_always_ok(self):
        result = validate_private_assignees("shared", ["U_A", "U_B"], "U_A")
        assert result is None

    def test_private_empty_assignees_ok(self):
        result = validate_private_assignees("private", [], "U_OWNER")
        assert result is None
