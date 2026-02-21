"""Tests for V1 schema migration: tables, indexes, and Inbox seed."""

import sqlite3

import pytest

from openclaw_todo.migrations import get_version


def test_v1_tables_exist(conn):
    """All four tables should be created by V1 migration."""
    tables = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table';"
        ).fetchall()
    }
    assert "projects" in tables
    assert "tasks" in tables
    assert "task_assignees" in tables
    assert "events" in tables


def test_v1_schema_version(conn):
    """Schema version should be 1 after V1 migration."""
    assert get_version(conn) == 1


def test_v1_inbox_created(conn):
    """Shared Inbox project should be auto-created."""
    row = conn.execute(
        "SELECT name, visibility, owner_user_id FROM projects WHERE name = 'Inbox';"
    ).fetchone()
    assert row is not None
    assert row[0] == "Inbox"
    assert row[1] == "shared"
    assert row[2] is None


def test_v1_shared_unique_index_enforced(conn):
    """Inserting duplicate shared project name should raise IntegrityError."""
    conn.execute(
        "INSERT INTO projects (name, visibility) VALUES ('TestProj', 'shared');"
    )
    conn.commit()

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO projects (name, visibility) VALUES ('TestProj', 'shared');"
        )
    conn.rollback()


def test_v1_private_unique_index_enforced(conn):
    """Same owner cannot have two private projects with same name."""
    conn.execute(
        "INSERT INTO projects (name, visibility, owner_user_id) VALUES ('MyProj', 'private', 'U1');"
    )
    conn.commit()

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO projects (name, visibility, owner_user_id) VALUES ('MyProj', 'private', 'U1');"
        )
    conn.rollback()

    # Different owner should succeed
    conn.execute(
        "INSERT INTO projects (name, visibility, owner_user_id) VALUES ('MyProj', 'private', 'U2');"
    )
    conn.commit()


def test_v1_section_check_constraint(conn):
    """Invalid section value should raise IntegrityError."""
    conn.execute(
        "INSERT INTO projects (name, visibility) VALUES ('P1', 'shared');"
    )
    conn.commit()
    project_id = conn.execute("SELECT id FROM projects WHERE name='P1';").fetchone()[0]

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO tasks (title, project_id, section, status, created_by) "
            "VALUES ('t', ?, 'invalid_section', 'open', 'U1');",
            (project_id,),
        )
    conn.rollback()


def test_v1_status_check_constraint(conn):
    """Invalid status value should raise IntegrityError."""
    conn.execute(
        "INSERT INTO projects (name, visibility) VALUES ('P2', 'shared');"
    )
    conn.commit()
    project_id = conn.execute("SELECT id FROM projects WHERE name='P2';").fetchone()[0]

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO tasks (title, project_id, section, status, created_by) "
            "VALUES ('t', ?, 'backlog', 'invalid_status', 'U1');",
            (project_id,),
        )
    conn.rollback()
