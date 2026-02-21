"""Tests for the /todo move command handler."""

from __future__ import annotations

import json

from openclaw_todo.cmd_move import move_handler
from openclaw_todo.parser import ParsedCommand

from tests.conftest import seed_task as _seed_task


def _make_parsed(*, args=None, section=None) -> ParsedCommand:
    return ParsedCommand(
        command="move",
        args=args or [],
        section=section,
    )


class TestMoveValidSection:
    """Move a task to a valid section."""

    def test_move_valid_section(self, conn):
        task_id = _seed_task(conn)
        parsed = _make_parsed(args=[str(task_id)], section="doing")
        ctx = {"sender_id": "U001"}

        result = move_handler(parsed, conn, ctx)

        assert f"Moved #{task_id}" in result
        assert "doing" in result

        row = conn.execute("SELECT section FROM tasks WHERE id = ?", (task_id,)).fetchone()
        assert row[0] == "doing"

    def test_move_updates_updated_at(self, conn):
        task_id = _seed_task(conn)
        old_ts = conn.execute("SELECT updated_at FROM tasks WHERE id = ?", (task_id,)).fetchone()[0]

        parsed = _make_parsed(args=[str(task_id)], section="doing")
        move_handler(parsed, conn, {"sender_id": "U001"})

        new_ts = conn.execute("SELECT updated_at FROM tasks WHERE id = ?", (task_id,)).fetchone()[0]
        assert new_ts >= old_ts

    def test_move_logs_event(self, conn):
        task_id = _seed_task(conn)
        parsed = _make_parsed(args=[str(task_id)], section="doing")
        move_handler(parsed, conn, {"sender_id": "U001"})

        event = conn.execute(
            "SELECT actor_user_id, action, task_id, payload FROM events WHERE action = 'task.move'"
        ).fetchone()
        assert event is not None
        assert event[0] == "U001"
        assert event[2] == task_id

        payload = json.loads(event[3])
        assert payload["old_section"] == "backlog"
        assert payload["new_section"] == "doing"

    def test_move_same_section_noop(self, conn):
        task_id = _seed_task(conn, section="doing")
        parsed = _make_parsed(args=[str(task_id)], section="doing")

        result = move_handler(parsed, conn, {"sender_id": "U001"})

        assert "already in section" in result


class TestMoveInvalidSection:
    """Invalid section returns error."""

    def test_move_missing_section(self, conn):
        task_id = _seed_task(conn)
        parsed = _make_parsed(args=[str(task_id)], section=None)

        result = move_handler(parsed, conn, {"sender_id": "U001"})

        assert "Error" in result
        assert "section required" in result

    def test_move_missing_task_id(self, conn):
        parsed = _make_parsed(args=[], section="doing")

        result = move_handler(parsed, conn, {"sender_id": "U001"})

        assert "Error" in result
        assert "task ID required" in result

    def test_move_invalid_task_id(self, conn):
        parsed = _make_parsed(args=["abc"], section="doing")

        result = move_handler(parsed, conn, {"sender_id": "U001"})

        assert "Error" in result
        assert "invalid task ID" in result

    def test_move_nonexistent_task(self, conn):
        parsed = _make_parsed(args=["9999"], section="doing")

        result = move_handler(parsed, conn, {"sender_id": "U001"})

        assert "Error" in result
        assert "not found" in result


class TestMovePrivateOwnerOnly:
    """Private project: only owner can move."""

    def test_move_private_owner_can_move(self, conn):
        task_id = _seed_task(
            conn, project_name="MyPrivate", visibility="private",
            owner="UOWNER", created_by="UOWNER", assignees=["UOWNER"],
        )
        parsed = _make_parsed(args=[str(task_id)], section="doing")

        result = move_handler(parsed, conn, {"sender_id": "UOWNER"})

        assert f"Moved #{task_id}" in result

    def test_move_private_non_owner_rejected(self, conn):
        task_id = _seed_task(
            conn, project_name="MyPrivate", visibility="private",
            owner="UOWNER", created_by="UOWNER", assignees=["UOWNER"],
        )
        parsed = _make_parsed(args=[str(task_id)], section="doing")

        result = move_handler(parsed, conn, {"sender_id": "UOTHER"})

        assert "Error" in result
        assert "permission denied" in result


class TestMoveSharedPermission:
    """Shared project: only assignee or created_by can move."""

    def test_move_shared_assignee_can_move(self, conn):
        task_id = _seed_task(
            conn, created_by="UCREATOR", assignees=["UASSIGNEE"],
        )
        parsed = _make_parsed(args=[str(task_id)], section="doing")

        result = move_handler(parsed, conn, {"sender_id": "UASSIGNEE"})

        assert f"Moved #{task_id}" in result

    def test_move_shared_creator_can_move(self, conn):
        task_id = _seed_task(
            conn, created_by="UCREATOR", assignees=["UASSIGNEE"],
        )
        parsed = _make_parsed(args=[str(task_id)], section="doing")

        result = move_handler(parsed, conn, {"sender_id": "UCREATOR"})

        assert f"Moved #{task_id}" in result

    def test_move_shared_unrelated_user_rejected(self, conn):
        task_id = _seed_task(
            conn, created_by="UCREATOR", assignees=["UASSIGNEE"],
        )
        parsed = _make_parsed(args=[str(task_id)], section="doing")

        result = move_handler(parsed, conn, {"sender_id": "URANDOM"})

        assert "Error" in result
        assert "permission denied" in result
