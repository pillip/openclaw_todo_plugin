"""Tests for the /todo add command handler."""

from __future__ import annotations

import json

import pytest

from openclaw_todo.cmd_add import add_handler
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


def _make_parsed(
    *,
    title_tokens: list[str] | None = None,
    project: str | None = None,
    section: str | None = None,
    due: str | None = None,
    mentions: list[str] | None = None,
) -> ParsedCommand:
    """Helper to build a ParsedCommand for the add command."""
    return ParsedCommand(
        command="add",
        args=[],
        project=project,
        section=section,
        due=due,
        mentions=mentions or [],
        title_tokens=title_tokens or [],
    )


class TestAddDefaultInbox:
    """Task added to Inbox with defaults when no project/section specified."""

    def test_add_default_inbox(self, conn):
        parsed = _make_parsed(title_tokens=["Buy", "groceries"])
        ctx = {"sender_id": "U001"}

        result = add_handler(parsed, conn, ctx)

        assert "Added #" in result
        assert "(Inbox/backlog)" in result
        assert "due:-" in result
        assert "<@U001>" in result
        assert "Buy groceries" in result

        # Verify DB row
        row = conn.execute("SELECT title, section, status, due, created_by FROM tasks WHERE id = 1").fetchone()
        assert row == ("Buy groceries", "backlog", "open", None, "U001")

        # Verify assignee
        assignees = conn.execute("SELECT assignee_user_id FROM task_assignees WHERE task_id = 1").fetchall()
        assert assignees == [("U001",)]


class TestAddWithProjectSectionDue:
    """Task created with explicit project, section, and due."""

    def test_add_with_project_section_due(self, conn):
        # Create a shared project
        conn.execute("INSERT INTO projects (name, visibility) VALUES ('Backend', 'shared');")
        conn.commit()

        parsed = _make_parsed(
            title_tokens=["Fix", "login", "bug"],
            project="Backend",
            section="doing",
            due="2026-03-15",
        )
        ctx = {"sender_id": "U001"}

        result = add_handler(parsed, conn, ctx)

        assert "(Backend/doing)" in result
        assert "due:2026-03-15" in result
        assert "Fix login bug" in result

        row = conn.execute("SELECT section, due, project_id FROM tasks WHERE id = 1").fetchone()
        assert row[0] == "doing"
        assert row[1] == "2026-03-15"

        # project_id should be the Backend project (id=2, after Inbox=1)
        proj_row = conn.execute("SELECT id FROM projects WHERE name = 'Backend'").fetchone()
        assert row[2] == proj_row[0]


class TestAddPrivateRejectsOtherAssignee:
    """Private project + non-owner assignee is rejected."""

    def test_add_private_rejects_other_assignee(self, conn):
        conn.execute(
            "INSERT INTO projects (name, visibility, owner_user_id) "
            "VALUES ('MyPrivate', 'private', 'U001');"
        )
        conn.commit()

        parsed = _make_parsed(
            title_tokens=["Secret", "task"],
            project="MyPrivate",
            mentions=["U002"],
        )
        ctx = {"sender_id": "U001"}

        result = add_handler(parsed, conn, ctx)

        assert "Warning" in result
        assert "NOT created" in result
        assert "<@U002>" in result

        # Verify no task was inserted
        count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        assert count == 0

    def test_add_private_allows_owner_assignee(self, conn):
        conn.execute(
            "INSERT INTO projects (name, visibility, owner_user_id) "
            "VALUES ('MyPrivate', 'private', 'U001');"
        )
        conn.commit()

        parsed = _make_parsed(
            title_tokens=["Owner", "task"],
            project="MyPrivate",
            mentions=["U001"],
        )
        ctx = {"sender_id": "U001"}

        result = add_handler(parsed, conn, ctx)

        assert "Added #" in result
        assert "(MyPrivate/backlog)" in result


class TestAddAssigneeDefaultsToSender:
    """When no mentions are provided, assignee defaults to sender."""

    def test_add_assignee_defaults_to_sender(self, conn):
        parsed = _make_parsed(title_tokens=["Some", "task"])
        ctx = {"sender_id": "USENDER"}

        result = add_handler(parsed, conn, ctx)

        assert "<@USENDER>" in result

        assignees = conn.execute(
            "SELECT assignee_user_id FROM task_assignees WHERE task_id = 1"
        ).fetchall()
        assert assignees == [("USENDER",)]


class TestAddMultipleAssignees:
    """Multiple mentions create multiple task_assignee rows."""

    def test_add_multiple_assignees(self, conn):
        parsed = _make_parsed(
            title_tokens=["Review", "PR"],
            mentions=["UBOB", "UCAROL"],
        )
        ctx = {"sender_id": "U001"}

        result = add_handler(parsed, conn, ctx)

        assert "<@UBOB>" in result
        assert "<@UCAROL>" in result

        assignees = conn.execute(
            "SELECT assignee_user_id FROM task_assignees WHERE task_id = 1 ORDER BY assignee_user_id"
        ).fetchall()
        assert assignees == [("UBOB",), ("UCAROL",)]


class TestAddEventLogging:
    """Event is logged to the events table."""

    def test_event_logged(self, conn):
        parsed = _make_parsed(title_tokens=["Task", "one"])
        ctx = {"sender_id": "U001"}

        add_handler(parsed, conn, ctx)

        event = conn.execute(
            "SELECT actor_user_id, action, task_id, payload FROM events WHERE action = 'task.add'"
        ).fetchone()
        assert event is not None
        assert event[0] == "U001"
        assert event[1] == "task.add"
        assert event[2] == 1

        payload = json.loads(event[3])
        assert payload["title"] == "Task one"
        assert payload["project"] == "Inbox"
        assert payload["section"] == "backlog"


class TestAddEdgeCases:
    """Edge cases for the add handler."""

    def test_add_empty_title_returns_error(self, conn):
        parsed = _make_parsed(title_tokens=[])
        ctx = {"sender_id": "U001"}

        result = add_handler(parsed, conn, ctx)

        assert "Error" in result
        assert "title" in result.lower()

    def test_add_nonexistent_project_returns_error(self, conn):
        parsed = _make_parsed(
            title_tokens=["Some", "task"],
            project="NonExistent",
        )
        ctx = {"sender_id": "U001"}

        result = add_handler(parsed, conn, ctx)

        assert "Error" in result
        assert "NonExistent" in result

    def test_add_due_clear_sentinel_stored_as_null(self, conn):
        parsed = _make_parsed(title_tokens=["Task"], due="-")
        ctx = {"sender_id": "U001"}

        result = add_handler(parsed, conn, ctx)

        assert "due:-" in result

        row = conn.execute("SELECT due FROM tasks WHERE id = 1").fetchone()
        assert row[0] is None
