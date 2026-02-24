"""Tests for the /todo project set-private subcommand handler."""

from __future__ import annotations

import json

from openclaw_todo.cmd_project_set_private import set_private_handler
from openclaw_todo.parser import ParsedCommand


def _make_parsed(project_name: str) -> ParsedCommand:
    return ParsedCommand(
        command="project",
        args=[],
        project=None,
        section=None,
        due=None,
        mentions=[],
        title_tokens=["set-private", project_name],
    )


def _make_parsed_no_name() -> ParsedCommand:
    return ParsedCommand(
        command="project",
        args=[],
        project=None,
        section=None,
        due=None,
        mentions=[],
        title_tokens=["set-private"],
    )


class TestSetPrivateAlreadyPrivate:
    """If sender already has a private project with the name, return noop."""

    def test_set_private_already_private(self, conn):
        conn.execute("INSERT INTO projects (name, visibility, owner_user_id) " "VALUES ('MyProj', 'private', 'U001');")
        conn.commit()

        result = set_private_handler(_make_parsed("MyProj"), conn, {"sender_id": "U001"})

        assert "already private" in result.lower()
        assert "MyProj" in result


class TestSetPrivateSharedSuccess:
    """Shared -> private succeeds when all task assignees are the owner."""

    def test_set_private_shared_success(self, conn):
        conn.execute("INSERT INTO projects (name, visibility) VALUES ('Backend', 'shared');")
        pid = conn.execute("SELECT id FROM projects WHERE name = 'Backend'").fetchone()[0]

        # Add a task assigned to sender (owner-to-be)
        conn.execute(
            "INSERT INTO tasks (title, project_id, section, status, created_by) "
            "VALUES ('task1', ?, 'backlog', 'open', 'U001');",
            (pid,),
        )
        tid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            "INSERT INTO task_assignees (task_id, assignee_user_id) VALUES (?, 'U001');",
            (tid,),
        )
        conn.commit()

        result = set_private_handler(_make_parsed("Backend"), conn, {"sender_id": "U001"})

        assert "now private" in result.lower()

        # Verify DB state
        row = conn.execute("SELECT visibility, owner_user_id FROM projects WHERE name = 'Backend';").fetchone()
        assert row[0] == "private"
        assert row[1] == "U001"

    def test_set_private_shared_no_tasks(self, conn):
        """Shared project with no tasks can be converted."""
        conn.execute("INSERT INTO projects (name, visibility) VALUES ('EmptyProj', 'shared');")
        conn.commit()

        result = set_private_handler(_make_parsed("EmptyProj"), conn, {"sender_id": "U001"})

        assert "now private" in result.lower()

    def test_event_logged_on_conversion(self, conn):
        conn.execute("INSERT INTO projects (name, visibility) VALUES ('Team', 'shared');")
        conn.commit()

        set_private_handler(_make_parsed("Team"), conn, {"sender_id": "U001"})

        event = conn.execute(
            "SELECT actor_user_id, action, payload FROM events "
            "WHERE action = 'project.set_private' ORDER BY id DESC LIMIT 1;"
        ).fetchone()
        assert event is not None
        assert event[0] == "U001"
        assert event[1] == "project.set_private"
        payload = json.loads(event[2])
        assert payload["name"] == "Team"
        assert payload["old_visibility"] == "shared"


class TestSetPrivateSharedRejected:
    """Shared -> private rejected when tasks have non-owner assignees."""

    def test_set_private_shared_rejected_non_owner_assignee(self, conn):
        conn.execute("INSERT INTO projects (name, visibility) VALUES ('Backend', 'shared');")
        pid = conn.execute("SELECT id FROM projects WHERE name = 'Backend'").fetchone()[0]

        # Task assigned to someone other than the sender
        conn.execute(
            "INSERT INTO tasks (title, project_id, section, status, created_by) "
            "VALUES ('task1', ?, 'backlog', 'open', 'U001');",
            (pid,),
        )
        tid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            "INSERT INTO task_assignees (task_id, assignee_user_id) VALUES (?, 'U002');",
            (tid,),
        )
        conn.commit()

        result = set_private_handler(_make_parsed("Backend"), conn, {"sender_id": "U001"})

        assert "Cannot set project" in result
        assert f"#{tid}" in result
        assert "<@U002>" in result

        # Verify project NOT changed
        row = conn.execute("SELECT visibility FROM projects WHERE name = 'Backend';").fetchone()
        assert row[0] == "shared"

    def test_set_private_error_message_format(self, conn):
        """Error message includes task IDs and violating assignees."""
        conn.execute("INSERT INTO projects (name, visibility) VALUES ('Backend', 'shared');")
        pid = conn.execute("SELECT id FROM projects WHERE name = 'Backend'").fetchone()[0]

        # Two tasks, each with a different non-owner assignee
        for i, assignee in enumerate(["U002", "U003"]):
            conn.execute(
                "INSERT INTO tasks (title, project_id, section, status, created_by) "
                "VALUES (?, ?, 'backlog', 'open', 'U001');",
                (f"task{i}", pid),
            )
            tid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                "INSERT INTO task_assignees (task_id, assignee_user_id) VALUES (?, ?);",
                (tid, assignee),
            )
        conn.commit()

        result = set_private_handler(_make_parsed("Backend"), conn, {"sender_id": "U001"})

        assert "Cannot set project" in result
        assert "non-owner users" in result
        assert "<@U002>" in result
        assert "<@U003>" in result

    def test_owner_assignees_not_flagged(self, conn):
        """Tasks where the only assignee is the owner should NOT cause rejection."""
        conn.execute("INSERT INTO projects (name, visibility) VALUES ('Backend', 'shared');")
        pid = conn.execute("SELECT id FROM projects WHERE name = 'Backend'").fetchone()[0]

        # Task 1: assigned to sender (OK)
        conn.execute(
            "INSERT INTO tasks (title, project_id, section, status, created_by) "
            "VALUES ('task1', ?, 'backlog', 'open', 'U001');",
            (pid,),
        )
        tid1 = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            "INSERT INTO task_assignees (task_id, assignee_user_id) VALUES (?, 'U001');",
            (tid1,),
        )

        # Task 2: assigned to both sender AND another user (violation)
        conn.execute(
            "INSERT INTO tasks (title, project_id, section, status, created_by) "
            "VALUES ('task2', ?, 'backlog', 'open', 'U001');",
            (pid,),
        )
        tid2 = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            "INSERT INTO task_assignees (task_id, assignee_user_id) VALUES (?, 'U001');",
            (tid2,),
        )
        conn.execute(
            "INSERT INTO task_assignees (task_id, assignee_user_id) VALUES (?, 'U099');",
            (tid2,),
        )
        conn.commit()

        result = set_private_handler(_make_parsed("Backend"), conn, {"sender_id": "U001"})

        # Should be rejected because of task2's non-owner assignee
        assert "Cannot set project" in result
        assert f"#{tid2}" in result
        assert "<@U099>" in result
        # task1 should NOT appear since its only assignee is the owner
        assert f"#{tid1}" not in result


class TestSetPrivateCreatesNew:
    """Neither shared nor private exists: creates new private project."""

    def test_set_private_creates_new(self, conn):
        result = set_private_handler(_make_parsed("NewProj"), conn, {"sender_id": "U001"})

        assert "created private" in result.lower()
        assert "NewProj" in result

        # Verify in DB
        row = conn.execute("SELECT visibility, owner_user_id FROM projects WHERE name = 'NewProj';").fetchone()
        assert row is not None
        assert row[0] == "private"
        assert row[1] == "U001"

    def test_event_logged_on_create(self, conn):
        set_private_handler(_make_parsed("NewProj"), conn, {"sender_id": "U001"})

        event = conn.execute(
            "SELECT actor_user_id, action, payload FROM events "
            "WHERE action = 'project.create_private' ORDER BY id DESC LIMIT 1;"
        ).fetchone()
        assert event is not None
        assert event[0] == "U001"
        payload = json.loads(event[2])
        assert payload["name"] == "NewProj"


class TestSetPrivateEdgeCases:
    """Edge cases and validation."""

    def test_missing_project_name(self, conn):
        result = set_private_handler(_make_parsed_no_name(), conn, {"sender_id": "U001"})
        assert "❌" in result
        assert "Project name is required" in result

    def test_other_users_private_not_affected(self, conn):
        """Setting private for a name that another user has private should create new."""
        conn.execute("INSERT INTO projects (name, visibility, owner_user_id) " "VALUES ('MyProj', 'private', 'U002');")
        conn.commit()

        result = set_private_handler(_make_parsed("MyProj"), conn, {"sender_id": "U001"})

        # U001 doesn't have a private 'MyProj', and no shared exists
        assert "created private" in result.lower()

        # Both should exist
        count = conn.execute("SELECT COUNT(*) FROM projects WHERE name = 'MyProj';").fetchone()[0]
        assert count == 2
