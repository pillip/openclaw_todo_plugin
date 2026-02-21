"""Tests for the /todo project set-shared subcommand handler."""

from __future__ import annotations

import json

from openclaw_todo.cmd_project_set_shared import set_shared_handler
from openclaw_todo.parser import ParsedCommand


def _make_parsed(project_name: str) -> ParsedCommand:
    return ParsedCommand(
        command="project",
        args=[],
        project=None,
        section=None,
        due=None,
        mentions=[],
        title_tokens=["set-shared", project_name],
    )


def _make_parsed_no_name() -> ParsedCommand:
    return ParsedCommand(
        command="project",
        args=[],
        project=None,
        section=None,
        due=None,
        mentions=[],
        title_tokens=["set-shared"],
    )


class TestSetSharedAlreadyShared:
    """If a shared project with the name exists, return noop."""

    def test_already_shared_noop(self, conn):
        conn.execute("INSERT INTO projects (name, visibility) VALUES ('Backend', 'shared');")
        conn.commit()

        result = set_shared_handler(_make_parsed("Backend"), conn, {"sender_id": "U001"})

        assert "already shared" in result.lower()
        assert "Backend" in result

    def test_already_shared_inbox(self, conn):
        """The default Inbox project is already shared."""
        result = set_shared_handler(_make_parsed("Inbox"), conn, {"sender_id": "U001"})

        assert "already shared" in result.lower()


class TestSetSharedConvertPrivate:
    """Private -> shared conversion when sender owns a private project."""

    def test_convert_private_to_shared(self, conn):
        conn.execute("INSERT INTO projects (name, visibility, owner_user_id) " "VALUES ('MyProj', 'private', 'U001');")
        conn.commit()

        result = set_shared_handler(_make_parsed("MyProj"), conn, {"sender_id": "U001"})

        assert "now shared" in result.lower()

        # Verify DB state
        row = conn.execute("SELECT visibility, owner_user_id FROM projects WHERE name = 'MyProj';").fetchone()
        assert row[0] == "shared"
        assert row[1] is None  # owner cleared for shared projects

    def test_convert_private_updated_at(self, conn):
        """Conversion updates the updated_at timestamp."""
        conn.execute(
            "INSERT INTO projects (name, visibility, owner_user_id, updated_at) "
            "VALUES ('MyProj', 'private', 'U001', '2020-01-01 00:00:00');"
        )
        conn.commit()

        set_shared_handler(_make_parsed("MyProj"), conn, {"sender_id": "U001"})

        row = conn.execute("SELECT updated_at FROM projects WHERE name = 'MyProj';").fetchone()
        assert row[0] != "2020-01-01 00:00:00"

    def test_event_logged_on_conversion(self, conn):
        conn.execute("INSERT INTO projects (name, visibility, owner_user_id) " "VALUES ('MyProj', 'private', 'U001');")
        conn.commit()

        set_shared_handler(_make_parsed("MyProj"), conn, {"sender_id": "U001"})

        event = conn.execute(
            "SELECT actor_user_id, action, payload FROM events "
            "WHERE action = 'project.set_shared' ORDER BY id DESC LIMIT 1;"
        ).fetchone()
        assert event is not None
        assert event[0] == "U001"
        assert event[1] == "project.set_shared"
        payload = json.loads(event[2])
        assert payload["name"] == "MyProj"
        assert payload["old_visibility"] == "private"

    def test_other_users_private_not_converted(self, conn):
        """Another user's private project is not found; a new shared project is created."""
        conn.execute("INSERT INTO projects (name, visibility, owner_user_id) " "VALUES ('MyProj', 'private', 'U002');")
        conn.commit()

        result = set_shared_handler(_make_parsed("MyProj"), conn, {"sender_id": "U001"})

        # Should create a new shared project, not convert U002's private
        assert "created shared" in result.lower()

        # U002's private should remain untouched
        row = conn.execute(
            "SELECT visibility, owner_user_id FROM projects " "WHERE name = 'MyProj' AND visibility = 'private';"
        ).fetchone()
        assert row is not None
        assert row[1] == "U002"


class TestSetSharedCreatesNew:
    """Neither shared nor private exists: creates new shared project."""

    def test_creates_new_shared(self, conn):
        result = set_shared_handler(_make_parsed("NewProj"), conn, {"sender_id": "U001"})

        assert "created shared" in result.lower()
        assert "NewProj" in result

        # Verify in DB
        row = conn.execute("SELECT visibility, owner_user_id FROM projects WHERE name = 'NewProj';").fetchone()
        assert row is not None
        assert row[0] == "shared"
        assert row[1] is None

    def test_event_logged_on_create(self, conn):
        set_shared_handler(_make_parsed("NewProj"), conn, {"sender_id": "U001"})

        event = conn.execute(
            "SELECT actor_user_id, action, payload FROM events "
            "WHERE action = 'project.create_shared' ORDER BY id DESC LIMIT 1;"
        ).fetchone()
        assert event is not None
        assert event[0] == "U001"
        payload = json.loads(event[2])
        assert payload["name"] == "NewProj"


class TestSetSharedEdgeCases:
    """Edge cases and validation."""

    def test_missing_project_name(self, conn):
        result = set_shared_handler(_make_parsed_no_name(), conn, {"sender_id": "U001"})
        assert "project name required" in result.lower()
