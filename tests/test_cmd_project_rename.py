"""Tests for the /todo project rename subcommand handler."""

from __future__ import annotations

import json

from openclaw_todo.cmd_project_rename import rename_handler
from openclaw_todo.parser import ParsedCommand


def _make_parsed(*tokens: str) -> ParsedCommand:
    """Build a ParsedCommand with title_tokens = ["rename", ...tokens]."""
    return ParsedCommand(
        command="project",
        args=[],
        project=None,
        section=None,
        due=None,
        mentions=[],
        title_tokens=["rename", *tokens],
    )


class TestRenameShared:
    """Rename a shared project."""

    def test_rename_shared_success(self, conn):
        conn.execute("INSERT INTO projects (name, visibility) VALUES ('OldName', 'shared');")
        conn.commit()

        result = rename_handler(_make_parsed("OldName", "NewName"), conn, {"sender_id": "U001"})

        assert "Renamed project" in result
        assert '"OldName"' in result
        assert '"NewName"' in result
        assert "(shared)" in result

        # Verify DB
        row = conn.execute("SELECT name FROM projects WHERE name = 'NewName';").fetchone()
        assert row is not None
        old = conn.execute("SELECT name FROM projects WHERE name = 'OldName';").fetchone()
        assert old is None

    def test_rename_shared_updated_at(self, conn):
        conn.execute(
            "INSERT INTO projects (name, visibility, updated_at) "
            "VALUES ('OldName', 'shared', '2020-01-01 00:00:00');"
        )
        conn.commit()

        rename_handler(_make_parsed("OldName", "NewName"), conn, {"sender_id": "U001"})

        row = conn.execute("SELECT updated_at FROM projects WHERE name = 'NewName';").fetchone()
        assert row[0] != "2020-01-01 00:00:00"

    def test_event_logged(self, conn):
        conn.execute("INSERT INTO projects (name, visibility) VALUES ('OldName', 'shared');")
        conn.commit()

        rename_handler(_make_parsed("OldName", "NewName"), conn, {"sender_id": "U001"})

        event = conn.execute(
            "SELECT actor_user_id, action, payload FROM events "
            "WHERE action = 'project.rename' ORDER BY id DESC LIMIT 1;"
        ).fetchone()
        assert event is not None
        assert event[0] == "U001"
        payload = json.loads(event[2])
        assert payload["old_name"] == "OldName"
        assert payload["new_name"] == "NewName"
        assert payload["visibility"] == "shared"


class TestRenamePrivate:
    """Rename a private project."""

    def test_rename_private_success(self, conn):
        conn.execute(
            "INSERT INTO projects (name, visibility, owner_user_id) "
            "VALUES ('MyProj', 'private', 'U001');"
        )
        conn.commit()

        result = rename_handler(_make_parsed("MyProj", "MyNewProj"), conn, {"sender_id": "U001"})

        assert "Renamed project" in result
        assert "(private)" in result

        row = conn.execute("SELECT name FROM projects WHERE name = 'MyNewProj';").fetchone()
        assert row is not None

    def test_non_owner_cannot_rename_private(self, conn):
        """Non-owner gets 'not found' to hide existence."""
        conn.execute(
            "INSERT INTO projects (name, visibility, owner_user_id) "
            "VALUES ('Secret', 'private', 'U002');"
        )
        conn.commit()

        result = rename_handler(_make_parsed("Secret", "NewSecret"), conn, {"sender_id": "U001"})

        assert "not found" in result
        # Original name should be unchanged
        row = conn.execute("SELECT name FROM projects WHERE name = 'Secret';").fetchone()
        assert row is not None


class TestRenameDuplicateErrors:
    """Duplicate new-name detection via DB constraints."""

    def test_shared_new_name_duplicate_blocked(self, conn):
        conn.execute("INSERT INTO projects (name, visibility) VALUES ('ProjA', 'shared');")
        conn.execute("INSERT INTO projects (name, visibility) VALUES ('ProjB', 'shared');")
        conn.commit()

        result = rename_handler(_make_parsed("ProjA", "ProjB"), conn, {"sender_id": "U001"})

        assert "❌" in result
        assert "already exists" in result
        assert "ProjB" in result

    def test_private_same_owner_new_name_duplicate_blocked(self, conn):
        conn.execute(
            "INSERT INTO projects (name, visibility, owner_user_id) "
            "VALUES ('ProjA', 'private', 'U001');"
        )
        conn.execute(
            "INSERT INTO projects (name, visibility, owner_user_id) "
            "VALUES ('ProjB', 'private', 'U001');"
        )
        conn.commit()

        result = rename_handler(_make_parsed("ProjA", "ProjB"), conn, {"sender_id": "U001"})

        assert "❌" in result
        assert "already have a private project" in result


class TestRenameEdgeCases:
    """Edge cases and validation."""

    def test_missing_args(self, conn):
        parsed = ParsedCommand(
            command="project",
            args=[],
            project=None,
            section=None,
            due=None,
            mentions=[],
            title_tokens=["rename"],
        )
        result = rename_handler(parsed, conn, {"sender_id": "U001"})
        assert "❌" in result
        assert "Both old and new names are required" in result

    def test_missing_new_name(self, conn):
        parsed = ParsedCommand(
            command="project",
            args=[],
            project=None,
            section=None,
            due=None,
            mentions=[],
            title_tokens=["rename", "OldName"],
        )
        result = rename_handler(parsed, conn, {"sender_id": "U001"})
        assert "❌" in result
        assert "Both old and new names are required" in result

    def test_project_not_found(self, conn):
        result = rename_handler(_make_parsed("NoSuchProject", "NewName"), conn, {"sender_id": "U001"})

        assert "❌" in result
        assert "not found" in result
        assert "NoSuchProject" in result

    def test_same_name_noop(self, conn):
        conn.execute("INSERT INTO projects (name, visibility) VALUES ('SameProj', 'shared');")
        conn.commit()

        result = rename_handler(_make_parsed("SameProj", "SameProj"), conn, {"sender_id": "U001"})

        assert "already has that name" in result

    def test_option_a_private_first_resolution(self, conn):
        """When both private and shared exist, private is resolved first."""
        conn.execute("INSERT INTO projects (name, visibility) VALUES ('Ambiguous', 'shared');")
        conn.execute(
            "INSERT INTO projects (name, visibility, owner_user_id) "
            "VALUES ('Ambiguous', 'private', 'U001');"
        )
        conn.commit()

        result = rename_handler(
            _make_parsed("Ambiguous", "Renamed"), conn, {"sender_id": "U001"}
        )

        assert "(private)" in result
        # Shared still exists with original name
        shared = conn.execute(
            "SELECT name FROM projects WHERE name = 'Ambiguous' AND visibility = 'shared';"
        ).fetchone()
        assert shared is not None

    def test_tasks_remain_associated_after_rename(self, conn):
        """Tasks reference project_id FK, so rename doesn't break association."""
        conn.execute("INSERT INTO projects (name, visibility) VALUES ('Work', 'shared');")
        conn.commit()
        pid = conn.execute("SELECT id FROM projects WHERE name = 'Work';").fetchone()[0]
        conn.execute(
            "INSERT INTO tasks (title, project_id, section, status, created_by) "
            "VALUES ('My task', ?, 'backlog', 'open', 'U001');",
            (pid,),
        )
        conn.commit()

        rename_handler(_make_parsed("Work", "Office"), conn, {"sender_id": "U001"})

        # Task still linked to same project_id
        task = conn.execute(
            "SELECT t.title, p.name FROM tasks t JOIN projects p ON t.project_id = p.id "
            "WHERE t.title = 'My task';"
        ).fetchone()
        assert task[1] == "Office"
