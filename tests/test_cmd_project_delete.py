"""Tests for the /todo project delete subcommand handler."""

from __future__ import annotations

import json

from openclaw_todo.cmd_project_delete import delete_handler
from openclaw_todo.parser import ParsedCommand
from tests.conftest import seed_task as _seed_task


def _make_parsed(*tokens: str) -> ParsedCommand:
    """Build a ParsedCommand with title_tokens = ["delete", ...tokens]."""
    return ParsedCommand(
        command="project",
        args=[],
        project=None,
        section=None,
        due=None,
        mentions=[],
        title_tokens=["delete", *tokens],
    )


def _make_parsed_no_name() -> ParsedCommand:
    return ParsedCommand(
        command="project",
        args=[],
        project=None,
        section=None,
        due=None,
        mentions=[],
        title_tokens=["delete"],
    )


class TestDeleteSharedProject:
    """Delete a shared project with no tasks."""

    def test_delete_empty_shared_project(self, conn):
        conn.execute("INSERT INTO projects (name, visibility) VALUES ('Shopping', 'shared');")
        conn.commit()

        result = delete_handler(_make_parsed("Shopping"), conn, {"sender_id": "U001"})

        assert "Deleted project" in result
        assert "Shopping" in result
        assert "(shared)" in result

        row = conn.execute("SELECT id FROM projects WHERE name = 'Shopping';").fetchone()
        assert row is None

    def test_event_logged(self, conn):
        conn.execute("INSERT INTO projects (name, visibility) VALUES ('Shopping', 'shared');")
        conn.commit()

        delete_handler(_make_parsed("Shopping"), conn, {"sender_id": "U001"})

        event = conn.execute(
            "SELECT actor_user_id, action, payload FROM events "
            "WHERE action = 'project.delete' ORDER BY id DESC LIMIT 1;"
        ).fetchone()
        assert event is not None
        assert event[0] == "U001"
        payload = json.loads(event[2])
        assert payload["name"] == "Shopping"
        assert payload["visibility"] == "shared"


class TestDeletePrivateProject:
    """Delete a private project."""

    def test_delete_empty_private_project(self, conn):
        conn.execute(
            "INSERT INTO projects (name, visibility, owner_user_id) "
            "VALUES ('Personal', 'private', 'U001');"
        )
        conn.commit()

        result = delete_handler(_make_parsed("Personal"), conn, {"sender_id": "U001"})

        assert "Deleted project" in result
        assert "Personal" in result
        assert "(private)" in result

        row = conn.execute("SELECT id FROM projects WHERE name = 'Personal';").fetchone()
        assert row is None

    def test_non_owner_cannot_delete_private(self, conn):
        """Non-owner gets 'not found' to hide existence (privacy by obscurity)."""
        conn.execute(
            "INSERT INTO projects (name, visibility, owner_user_id) "
            "VALUES ('Secret', 'private', 'U001');"
        )
        conn.commit()

        result = delete_handler(_make_parsed("Secret"), conn, {"sender_id": "U002"})

        assert "not found" in result

        # Project should still exist
        row = conn.execute("SELECT id FROM projects WHERE name = 'Secret';").fetchone()
        assert row is not None


class TestDeleteBlockedByTasks:
    """Deletion blocked when project has tasks."""

    def test_shared_project_with_tasks(self, conn):
        _seed_task(conn, project_name="Work", title="Do stuff", created_by="U001")

        result = delete_handler(_make_parsed("Work"), conn, {"sender_id": "U001"})

        assert "❌" in result
        assert "Cannot delete" in result
        assert "1 task(s)" in result
        assert "Work" in result

        # Project should still exist
        row = conn.execute("SELECT id FROM projects WHERE name = 'Work';").fetchone()
        assert row is not None

    def test_multiple_tasks_shows_count(self, conn):
        _seed_task(conn, project_name="Work", title="Task 1", created_by="U001")
        _seed_task(conn, project_name="Work", title="Task 2", created_by="U001")
        _seed_task(conn, project_name="Work", title="Task 3", created_by="U001")

        result = delete_handler(_make_parsed("Work"), conn, {"sender_id": "U001"})

        assert "3 task(s)" in result


class TestDeleteNotFound:
    """Error when project does not exist."""

    def test_nonexistent_project(self, conn):
        result = delete_handler(_make_parsed("NonExistent"), conn, {"sender_id": "U001"})

        assert "❌" in result
        assert "not found" in result
        assert "NonExistent" in result


class TestDeleteInboxBlocked:
    """System project Inbox cannot be deleted."""

    def test_inbox_deletion_blocked(self, conn):
        result = delete_handler(_make_parsed("Inbox"), conn, {"sender_id": "U001"})

        assert "❌" in result
        assert "Cannot delete" in result
        assert "Inbox" in result

        # Inbox should still exist
        row = conn.execute("SELECT id FROM projects WHERE name = 'Inbox';").fetchone()
        assert row is not None


class TestDeleteValidation:
    """Input validation edge cases."""

    def test_missing_name(self, conn):
        result = delete_handler(_make_parsed_no_name(), conn, {"sender_id": "U001"})

        assert "❌" in result
        assert "Project name is required" in result

    def test_option_a_private_first(self, conn):
        """When both private and shared exist with same name, private is resolved first."""
        conn.execute("INSERT INTO projects (name, visibility) VALUES ('Work', 'shared');")
        conn.execute(
            "INSERT INTO projects (name, visibility, owner_user_id) "
            "VALUES ('Work', 'private', 'U001');"
        )
        conn.commit()

        result = delete_handler(_make_parsed("Work"), conn, {"sender_id": "U001"})

        assert "Deleted project" in result
        assert "(private)" in result

        # Shared project should still exist
        row = conn.execute(
            "SELECT id FROM projects WHERE name = 'Work' AND visibility = 'shared';"
        ).fetchone()
        assert row is not None
