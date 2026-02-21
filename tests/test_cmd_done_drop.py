"""Tests for the /todo done and /todo drop command handlers."""

from __future__ import annotations

import json

from openclaw_todo.cmd_done_drop import done_handler, drop_handler
from openclaw_todo.parser import ParsedCommand
from tests.conftest import seed_task as _seed_task


def _make_parsed(command, *, args=None) -> ParsedCommand:
    return ParsedCommand(
        command=command,
        args=args or [],
    )


class TestDoneSetsFields:
    """done sets section='done', status='done', closed_at."""

    def test_done_sets_fields(self, conn):
        task_id = _seed_task(conn)
        parsed = _make_parsed("done", args=[str(task_id)])

        result = done_handler(parsed, conn, {"sender_id": "U001"})

        assert f"#{task_id}" in result
        assert "done" in result

        row = conn.execute("SELECT section, status, closed_at FROM tasks WHERE id = ?", (task_id,)).fetchone()
        assert row[0] == "done"
        assert row[1] == "done"
        assert row[2] is not None  # closed_at set

    def test_done_logs_event(self, conn):
        task_id = _seed_task(conn)
        done_handler(_make_parsed("done", args=[str(task_id)]), conn, {"sender_id": "U001"})

        event = conn.execute("SELECT actor_user_id, action, payload FROM events WHERE action = 'task.done'").fetchone()
        assert event is not None
        assert event[0] == "U001"

        payload = json.loads(event[2])
        assert payload["new_section"] == "done"
        assert payload["new_status"] == "done"


class TestDropSetsFields:
    """drop sets section='drop', status='dropped', closed_at."""

    def test_drop_sets_fields(self, conn):
        task_id = _seed_task(conn)
        parsed = _make_parsed("drop", args=[str(task_id)])

        result = drop_handler(parsed, conn, {"sender_id": "U001"})

        assert f"#{task_id}" in result
        assert "dropped" in result

        row = conn.execute("SELECT section, status, closed_at FROM tasks WHERE id = ?", (task_id,)).fetchone()
        assert row[0] == "drop"
        assert row[1] == "dropped"
        assert row[2] is not None

    def test_drop_logs_event(self, conn):
        task_id = _seed_task(conn)
        drop_handler(_make_parsed("drop", args=[str(task_id)]), conn, {"sender_id": "U001"})

        event = conn.execute("SELECT action, payload FROM events WHERE action = 'task.drop'").fetchone()
        assert event is not None

        payload = json.loads(event[1])
        assert payload["new_section"] == "drop"
        assert payload["new_status"] == "dropped"


class TestPermissionCheck:
    """Permission enforcement matches move command rules."""

    def test_done_private_owner_allowed(self, conn):
        task_id = _seed_task(
            conn,
            project_name="MyPrivate",
            visibility="private",
            owner="UOWNER",
            created_by="UOWNER",
            assignees=["UOWNER"],
        )
        result = done_handler(_make_parsed("done", args=[str(task_id)]), conn, {"sender_id": "UOWNER"})
        assert "done" in result
        assert "Error" not in result

    def test_done_private_non_owner_rejected(self, conn):
        task_id = _seed_task(
            conn,
            project_name="MyPrivate",
            visibility="private",
            owner="UOWNER",
            created_by="UOWNER",
            assignees=["UOWNER"],
        )
        result = done_handler(_make_parsed("done", args=[str(task_id)]), conn, {"sender_id": "UOTHER"})
        assert "permission denied" in result

    def test_drop_shared_assignee_allowed(self, conn):
        task_id = _seed_task(conn, created_by="UCREATOR", assignees=["UASSIGNEE"])
        result = drop_handler(_make_parsed("drop", args=[str(task_id)]), conn, {"sender_id": "UASSIGNEE"})
        assert "dropped" in result

    def test_drop_shared_unrelated_rejected(self, conn):
        task_id = _seed_task(conn, created_by="UCREATOR", assignees=["UASSIGNEE"])
        result = drop_handler(_make_parsed("drop", args=[str(task_id)]), conn, {"sender_id": "URANDOM"})
        assert "permission denied" in result


class TestAlreadyClosed:
    """Already-closed task returns informational message."""

    def test_already_done(self, conn):
        task_id = _seed_task(conn)
        done_handler(_make_parsed("done", args=[str(task_id)]), conn, {"sender_id": "U001"})

        result = done_handler(_make_parsed("done", args=[str(task_id)]), conn, {"sender_id": "U001"})
        assert "already done" in result

    def test_already_dropped(self, conn):
        task_id = _seed_task(conn)
        drop_handler(_make_parsed("drop", args=[str(task_id)]), conn, {"sender_id": "U001"})

        result = drop_handler(_make_parsed("drop", args=[str(task_id)]), conn, {"sender_id": "U001"})
        assert "already dropped" in result

    def test_done_on_dropped_task(self, conn):
        task_id = _seed_task(conn)
        drop_handler(_make_parsed("drop", args=[str(task_id)]), conn, {"sender_id": "U001"})

        result = done_handler(_make_parsed("done", args=[str(task_id)]), conn, {"sender_id": "U001"})
        assert "already dropped" in result


class TestEdgeCases:
    """Validation edge cases."""

    def test_missing_task_id(self, conn):
        result = done_handler(_make_parsed("done", args=[]), conn, {"sender_id": "U001"})
        assert "task ID required" in result

    def test_invalid_task_id(self, conn):
        result = done_handler(_make_parsed("done", args=["abc"]), conn, {"sender_id": "U001"})
        assert "invalid task ID" in result

    def test_nonexistent_task(self, conn):
        result = done_handler(_make_parsed("done", args=["9999"]), conn, {"sender_id": "U001"})
        assert "not found" in result
