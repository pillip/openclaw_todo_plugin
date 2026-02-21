"""Tests for the /todo project list subcommand handler."""

from __future__ import annotations

import pytest

from openclaw_todo.cmd_project_list import project_list_handler
from openclaw_todo.db import get_connection
from openclaw_todo.migrations import _migrations, migrate
from openclaw_todo.parser import ParsedCommand


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


def _make_parsed() -> ParsedCommand:
    return ParsedCommand(
        command="project",
        args=[],
        project=None,
        section=None,
        due=None,
        mentions=[],
        title_tokens=["list"],
    )


def _seed_projects(conn):
    """Seed test projects: Inbox (shared, from V1), Backend (shared), Secret (private U002)."""
    conn.execute(
        "INSERT INTO projects (name, visibility) VALUES ('Backend', 'shared');"
    )
    conn.execute(
        "INSERT INTO projects (name, visibility, owner_user_id) "
        "VALUES ('MyStuff', 'private', 'U001');"
    )
    conn.execute(
        "INSERT INTO projects (name, visibility, owner_user_id) "
        "VALUES ('Secret', 'private', 'U002');"
    )

    # Add tasks: 2 in Inbox, 1 in Backend, 1 in MyStuff, 1 in Secret
    inbox_id = conn.execute("SELECT id FROM projects WHERE name = 'Inbox'").fetchone()[0]
    backend_id = conn.execute("SELECT id FROM projects WHERE name = 'Backend'").fetchone()[0]
    mystuff_id = conn.execute("SELECT id FROM projects WHERE name = 'MyStuff'").fetchone()[0]
    secret_id = conn.execute("SELECT id FROM projects WHERE name = 'Secret'").fetchone()[0]

    for pid, count in [(inbox_id, 2), (backend_id, 1), (mystuff_id, 1), (secret_id, 1)]:
        for i in range(count):
            conn.execute(
                "INSERT INTO tasks (title, project_id, section, status, created_by) "
                "VALUES (?, ?, 'backlog', 'open', 'U001');",
                (f"task-{pid}-{i}", pid),
            )
    conn.commit()


class TestProjectListShowsShared:
    """Shared projects are listed regardless of sender."""

    def test_project_list_shows_shared(self, conn):
        _seed_projects(conn)
        parsed = _make_parsed()
        ctx = {"sender_id": "U001"}

        result = project_list_handler(parsed, conn, ctx)

        assert "Shared:" in result
        assert "Inbox" in result
        assert "Backend" in result

    def test_shared_projects_show_task_count(self, conn):
        _seed_projects(conn)
        parsed = _make_parsed()
        ctx = {"sender_id": "U001"}

        result = project_list_handler(parsed, conn, ctx)

        # Inbox has 2 tasks, Backend has 1
        assert "Inbox (2 tasks)" in result
        assert "Backend (1 tasks)" in result


class TestProjectListShowsOwnPrivate:
    """Sender's private projects are listed."""

    def test_project_list_shows_own_private(self, conn):
        _seed_projects(conn)
        parsed = _make_parsed()
        ctx = {"sender_id": "U001"}

        result = project_list_handler(parsed, conn, ctx)

        assert "Private:" in result
        assert "MyStuff" in result


class TestProjectListHidesOthersPrivate:
    """Other users' private projects are NOT shown."""

    def test_project_list_hides_others_private(self, conn):
        _seed_projects(conn)
        parsed = _make_parsed()
        ctx = {"sender_id": "U001"}

        result = project_list_handler(parsed, conn, ctx)

        assert "Secret" not in result

    def test_other_user_sees_own_private(self, conn):
        _seed_projects(conn)
        parsed = _make_parsed()
        ctx = {"sender_id": "U002"}

        result = project_list_handler(parsed, conn, ctx)

        assert "Secret" in result
        assert "MyStuff" not in result


class TestProjectListEmpty:
    """Edge case: no projects at all (only Inbox from V1 seed)."""

    def test_default_inbox_shown(self, conn):
        parsed = _make_parsed()
        ctx = {"sender_id": "U001"}

        result = project_list_handler(parsed, conn, ctx)

        # Inbox is always seeded by V1 migration
        assert "Inbox" in result
        assert "Inbox (0 tasks)" in result
