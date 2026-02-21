"""Tests for the /todo edit command handler."""

from __future__ import annotations

import json

from openclaw_todo.cmd_edit import edit_handler
from openclaw_todo.parser import ParsedCommand

from tests.conftest import seed_task as _seed_task


def _make_parsed(**kwargs) -> ParsedCommand:
    defaults = {"command": "edit", "args": []}
    defaults.update(kwargs)
    return ParsedCommand(**defaults)


class TestEditTitle:
    """Title updated only if non-option tokens present."""

    def test_edit_title(self, conn):
        task_id = _seed_task(conn, title="Old title")
        parsed = _make_parsed(args=[str(task_id)], title_tokens=["New", "title"])
        result = edit_handler(parsed, conn, {"sender_id": "U001"})

        assert f"#{task_id}" in result
        assert "title" in result

        row = conn.execute("SELECT title FROM tasks WHERE id = ?", (task_id,)).fetchone()
        assert row[0] == "New title"

    def test_edit_title_no_change(self, conn):
        task_id = _seed_task(conn, title="Same title")
        parsed = _make_parsed(args=[str(task_id)], title_tokens=["Same", "title"])
        result = edit_handler(parsed, conn, {"sender_id": "U001"})

        assert "No changes" in result


class TestEditAssignees:
    """Mentions present -> assignees fully replaced."""

    def test_edit_assignees_replace(self, conn):
        task_id = _seed_task(conn, assignees=["U001"])
        parsed = _make_parsed(args=[str(task_id)], mentions=["U002", "U003"])
        result = edit_handler(parsed, conn, {"sender_id": "U001"})

        assert "assignees" in result

        rows = conn.execute(
            "SELECT assignee_user_id FROM task_assignees WHERE task_id = ? ORDER BY assignee_user_id",
            (task_id,),
        ).fetchall()
        assert [r[0] for r in rows] == ["U002", "U003"]

    def test_edit_assignees_no_change(self, conn):
        task_id = _seed_task(conn, assignees=["U001"])
        parsed = _make_parsed(args=[str(task_id)], mentions=["U001"])
        result = edit_handler(parsed, conn, {"sender_id": "U001"})

        assert "No changes" in result


class TestEditDue:
    """Due date editing including clear."""

    def test_edit_due_set(self, conn):
        task_id = _seed_task(conn)
        parsed = _make_parsed(args=[str(task_id)], due="2026-03-15")
        result = edit_handler(parsed, conn, {"sender_id": "U001"})

        assert "due" in result

        row = conn.execute("SELECT due FROM tasks WHERE id = ?", (task_id,)).fetchone()
        assert row[0] == "2026-03-15"

    def test_edit_due_clear(self, conn):
        task_id = _seed_task(conn, due="2026-03-15")
        parsed = _make_parsed(args=[str(task_id)], due="-")
        result = edit_handler(parsed, conn, {"sender_id": "U001"})

        assert "due" in result

        row = conn.execute("SELECT due FROM tasks WHERE id = ?", (task_id,)).fetchone()
        assert row[0] is None

    def test_edit_due_no_change(self, conn):
        task_id = _seed_task(conn, due="2026-03-15")
        parsed = _make_parsed(args=[str(task_id)], due="2026-03-15")
        result = edit_handler(parsed, conn, {"sender_id": "U001"})

        assert "No changes" in result


class TestEditProject:
    """Moving task to another project."""

    def test_edit_move_project(self, conn):
        task_id = _seed_task(conn, project_name="Inbox")
        conn.execute(
            "INSERT INTO projects (name, visibility, owner_user_id) VALUES (?, ?, ?);",
            ("Backend", "shared", None),
        )
        conn.commit()

        parsed = _make_parsed(args=[str(task_id)], project="Backend")
        result = edit_handler(parsed, conn, {"sender_id": "U001"})

        assert "project" in result

        row = conn.execute(
            "SELECT p.name FROM tasks t JOIN projects p ON t.project_id = p.id WHERE t.id = ?",
            (task_id,),
        ).fetchone()
        assert row[0] == "Backend"

    def test_edit_project_not_found(self, conn):
        task_id = _seed_task(conn)
        parsed = _make_parsed(args=[str(task_id)], project="NonExistent")
        result = edit_handler(parsed, conn, {"sender_id": "U001"})

        assert "not found" in result


class TestEditPrivateAssignee:
    """Private project assignee validation."""

    def test_edit_private_assignee_rejected(self, conn):
        task_id = _seed_task(
            conn, project_name="MyPrivate", visibility="private",
            owner="UOWNER", created_by="UOWNER", assignees=["UOWNER"],
        )
        parsed = _make_parsed(args=[str(task_id)], mentions=["UOTHER"])
        result = edit_handler(parsed, conn, {"sender_id": "UOWNER"})

        assert "Private project" in result or "non-owner" in result

    def test_edit_private_owner_assignee_allowed(self, conn):
        task_id = _seed_task(
            conn, project_name="MyPrivate", visibility="private",
            owner="UOWNER", created_by="UOWNER", assignees=["UOWNER"],
        )
        parsed = _make_parsed(
            args=[str(task_id)], title_tokens=["Updated", "title"],
            mentions=["UOWNER"],
        )
        result = edit_handler(parsed, conn, {"sender_id": "UOWNER"})

        assert "Edited" in result


class TestEditSection:
    """Section editing via /s."""

    def test_edit_section(self, conn):
        task_id = _seed_task(conn, section="backlog")
        parsed = _make_parsed(args=[str(task_id)], section="doing")
        result = edit_handler(parsed, conn, {"sender_id": "U001"})

        assert "section" in result

        row = conn.execute("SELECT section FROM tasks WHERE id = ?", (task_id,)).fetchone()
        assert row[0] == "doing"


class TestEditEvent:
    """Event logging with change diff."""

    def test_edit_logs_event(self, conn):
        task_id = _seed_task(conn, title="Old")
        parsed = _make_parsed(args=[str(task_id)], title_tokens=["New"])
        edit_handler(parsed, conn, {"sender_id": "U001"})

        event = conn.execute(
            "SELECT actor_user_id, action, payload FROM events WHERE action = 'task.edit'"
        ).fetchone()
        assert event is not None
        assert event[0] == "U001"
        assert event[1] == "task.edit"

        payload = json.loads(event[2])
        assert payload["title"]["old"] == "Old"
        assert payload["title"]["new"] == "New"


class TestEditPermissions:
    """Permission checks."""

    def test_edit_private_non_owner_rejected(self, conn):
        task_id = _seed_task(
            conn, project_name="MyPrivate", visibility="private",
            owner="UOWNER", created_by="UOWNER", assignees=["UOWNER"],
        )
        parsed = _make_parsed(args=[str(task_id)], title_tokens=["Hacked"])
        result = edit_handler(parsed, conn, {"sender_id": "UOTHER"})

        assert "permission denied" in result

    def test_edit_shared_unrelated_rejected(self, conn):
        task_id = _seed_task(conn, created_by="UCREATOR", assignees=["UASSIGNEE"])
        parsed = _make_parsed(args=[str(task_id)], title_tokens=["Hacked"])
        result = edit_handler(parsed, conn, {"sender_id": "URANDOM"})

        assert "permission denied" in result

    def test_edit_shared_assignee_allowed(self, conn):
        task_id = _seed_task(conn, created_by="UCREATOR", assignees=["UASSIGNEE"])
        parsed = _make_parsed(args=[str(task_id)], title_tokens=["Updated"])
        result = edit_handler(parsed, conn, {"sender_id": "UASSIGNEE"})

        assert "Edited" in result


class TestEditEdgeCases:
    """Validation edge cases."""

    def test_missing_task_id(self, conn):
        result = edit_handler(_make_parsed(args=[]), conn, {"sender_id": "U001"})
        assert "task ID required" in result

    def test_invalid_task_id(self, conn):
        result = edit_handler(_make_parsed(args=["abc"]), conn, {"sender_id": "U001"})
        assert "invalid task ID" in result

    def test_nonexistent_task(self, conn):
        result = edit_handler(_make_parsed(args=["9999"]), conn, {"sender_id": "U001"})
        assert "not found" in result

    def test_no_changes(self, conn):
        task_id = _seed_task(conn)
        parsed = _make_parsed(args=[str(task_id)])
        result = edit_handler(parsed, conn, {"sender_id": "U001"})

        assert "No changes" in result

    def test_multiple_fields_at_once(self, conn):
        task_id = _seed_task(conn, title="Old", section="backlog")
        parsed = _make_parsed(
            args=[str(task_id)],
            title_tokens=["New"],
            section="doing",
            due="2026-06-01",
        )
        result = edit_handler(parsed, conn, {"sender_id": "U001"})

        assert "Edited" in result
        assert "title" in result
        assert "section" in result
        assert "due" in result

        row = conn.execute(
            "SELECT title, section, due FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        assert row[0] == "New"
        assert row[1] == "doing"
        assert row[2] == "2026-06-01"
