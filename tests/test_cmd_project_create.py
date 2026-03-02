"""Tests for the /todo project create subcommand handler."""

from __future__ import annotations

import json

from openclaw_todo.cmd_project_create import create_handler
from openclaw_todo.parser import ParsedCommand


def _make_parsed(*tokens: str) -> ParsedCommand:
    """Build a ParsedCommand with title_tokens = ["create", ...tokens]."""
    return ParsedCommand(
        command="project",
        args=[],
        project=None,
        section=None,
        due=None,
        mentions=[],
        title_tokens=["create", *tokens],
    )


def _make_parsed_no_name() -> ParsedCommand:
    return ParsedCommand(
        command="project",
        args=[],
        project=None,
        section=None,
        due=None,
        mentions=[],
        title_tokens=["create"],
    )


class TestCreateSharedDefault:
    """Default visibility (shared) when no visibility arg is given."""

    def test_create_shared_default(self, conn):
        result = create_handler(_make_parsed("Shopping"), conn, {"sender_id": "U001"})

        assert "Created project" in result
        assert "Shopping" in result
        assert "(shared)" in result

        row = conn.execute(
            "SELECT visibility, owner_user_id FROM projects WHERE name = 'Shopping';"
        ).fetchone()
        assert row[0] == "shared"
        assert row[1] is None

    def test_create_shared_explicit(self, conn):
        result = create_handler(_make_parsed("Shopping", "shared"), conn, {"sender_id": "U001"})

        assert "Created project" in result
        assert "(shared)" in result

    def test_event_logged(self, conn):
        create_handler(_make_parsed("Shopping"), conn, {"sender_id": "U001"})

        event = conn.execute(
            "SELECT actor_user_id, action, payload FROM events "
            "WHERE action = 'project.create' ORDER BY id DESC LIMIT 1;"
        ).fetchone()
        assert event is not None
        assert event[0] == "U001"
        payload = json.loads(event[2])
        assert payload["name"] == "Shopping"
        assert payload["visibility"] == "shared"


class TestCreatePrivate:
    """Explicit private visibility."""

    def test_create_private(self, conn):
        result = create_handler(_make_parsed("Personal", "private"), conn, {"sender_id": "U001"})

        assert "Created project" in result
        assert "Personal" in result
        assert "(private" in result
        assert "<@U001>" in result

        row = conn.execute(
            "SELECT visibility, owner_user_id FROM projects WHERE name = 'Personal';"
        ).fetchone()
        assert row[0] == "private"
        assert row[1] == "U001"

    def test_event_logged(self, conn):
        create_handler(_make_parsed("Personal", "private"), conn, {"sender_id": "U001"})

        event = conn.execute(
            "SELECT actor_user_id, action, payload FROM events "
            "WHERE action = 'project.create' ORDER BY id DESC LIMIT 1;"
        ).fetchone()
        payload = json.loads(event[2])
        assert payload["visibility"] == "private"


class TestCreateDuplicateErrors:
    """Duplicate name detection via DB constraints."""

    def test_shared_duplicate_blocked(self, conn):
        conn.execute("INSERT INTO projects (name, visibility) VALUES ('Shopping', 'shared');")
        conn.commit()

        result = create_handler(_make_parsed("Shopping"), conn, {"sender_id": "U001"})

        assert "❌" in result
        assert "already exists" in result
        assert "Shopping" in result

    def test_private_same_owner_duplicate_blocked(self, conn):
        conn.execute(
            "INSERT INTO projects (name, visibility, owner_user_id) "
            "VALUES ('Personal', 'private', 'U001');"
        )
        conn.commit()

        result = create_handler(_make_parsed("Personal", "private"), conn, {"sender_id": "U001"})

        assert "❌" in result
        assert "already have a private project" in result

    def test_private_different_owner_allowed(self, conn):
        """Different owners can have private projects with the same name."""
        conn.execute(
            "INSERT INTO projects (name, visibility, owner_user_id) "
            "VALUES ('Personal', 'private', 'U002');"
        )
        conn.commit()

        result = create_handler(_make_parsed("Personal", "private"), conn, {"sender_id": "U001"})

        assert "Created project" in result

    def test_shared_and_private_same_name_coexist(self, conn):
        """A shared and private project can have the same name."""
        conn.execute("INSERT INTO projects (name, visibility) VALUES ('Work', 'shared');")
        conn.commit()

        result = create_handler(_make_parsed("Work", "private"), conn, {"sender_id": "U001"})
        assert "Created project" in result
        assert "(private" in result


class TestCreateValidation:
    """Input validation edge cases."""

    def test_missing_name(self, conn):
        result = create_handler(_make_parsed_no_name(), conn, {"sender_id": "U001"})

        assert "❌" in result
        assert "Project name is required" in result

    def test_invalid_visibility(self, conn):
        result = create_handler(_make_parsed("Shopping", "public"), conn, {"sender_id": "U001"})

        assert "❌" in result
        assert "Invalid visibility" in result
        assert "public" in result

    def test_visibility_case_insensitive(self, conn):
        result = create_handler(_make_parsed("Shopping", "SHARED"), conn, {"sender_id": "U001"})

        assert "Created project" in result
        assert "(shared)" in result

    def test_visibility_private_case_insensitive(self, conn):
        result = create_handler(_make_parsed("Personal", "Private"), conn, {"sender_id": "U001"})

        assert "Created project" in result
        assert "(private" in result
