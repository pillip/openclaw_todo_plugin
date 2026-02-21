"""End-to-end integration tests exercising full flows through handle_message.

Each test uses a fresh SQLite database via tmp_path, calling the real
plugin entry point with no mocks.
"""

from __future__ import annotations

import sqlite3

import pytest

from openclaw_todo.plugin import handle_message


@pytest.fixture()
def db_path(tmp_path):
    """Provide a fresh DB path per test."""
    return str(tmp_path / "e2e.sqlite3")


def _msg(text: str, sender: str, db_path: str) -> str:
    """Send a !todo command and return the response (asserts non-None)."""
    result = handle_message(f"!todo {text}", {"sender_id": sender}, db_path=db_path)
    assert result is not None, f"Expected response for: !todo {text}"
    return result


def _extract_task_id(add_result: str) -> str:
    """Extract the task ID from an 'Added #N ...' response."""
    return add_result.split("#")[1].split(" ")[0]


_ALLOWED_COLUMNS = frozenset({
    "*", "id", "title", "status", "section", "due",
    "project_id", "created_by", "closed_at", "created_at", "updated_at",
})


def _query_task(db_path: str, task_id: str, columns: str = "*") -> tuple | None:
    """Query a task row by ID using a context-managed connection.

    ``columns`` must be a comma-separated list of column names drawn from
    ``_ALLOWED_COLUMNS`` to prevent SQL injection in test helpers.
    """
    parts = [c.strip() for c in columns.split(",")]
    disallowed = set(parts) - _ALLOWED_COLUMNS
    if disallowed:
        raise ValueError(f"Disallowed columns: {disallowed}")
    safe_columns = ", ".join(parts)
    with sqlite3.connect(db_path) as conn:
        return conn.execute(
            f"SELECT {safe_columns} FROM tasks WHERE id = ?;",
            (int(task_id),),
        ).fetchone()


# ---------------------------------------------------------------------------
# Scenario 1: add -> list roundtrip
# ---------------------------------------------------------------------------
class TestAddAndListRoundtrip:
    """Add a task and verify it appears in list output."""

    def test_add_then_list_shows_task(self, db_path):
        result = _msg("add buy milk", "U001", db_path)
        assert "Added #" in result

        listing = _msg("list", "U001", db_path)
        assert "buy milk" in listing

    def test_add_with_project_then_list_filters(self, db_path):
        # Create shared projects first, then add tasks
        _msg("project set-shared Work", "U001", db_path)
        _msg("project set-shared Personal", "U001", db_path)

        _msg("add task1 /p Work", "U001", db_path)
        _msg("add task2 /p Personal", "U001", db_path)

        work_list = _msg("list /p Work", "U001", db_path)
        assert "task1" in work_list
        assert "task2" not in work_list

    def test_add_multiple_then_list_all(self, db_path):
        _msg("add alpha", "U001", db_path)
        _msg("add beta", "U001", db_path)
        _msg("add gamma", "U001", db_path)

        listing = _msg("list all", "U001", db_path)
        assert "alpha" in listing
        assert "beta" in listing
        assert "gamma" in listing


# ---------------------------------------------------------------------------
# Scenario 2: add -> move -> board
# ---------------------------------------------------------------------------
class TestAddMoveBoardFlow:
    """Add a task, move it to doing, verify on board."""

    def test_move_then_board_shows_section(self, db_path):
        add_result = _msg("add implement feature", "U001", db_path)
        task_id = _extract_task_id(add_result)

        move_result = _msg(f"move {task_id} /s doing", "U001", db_path)
        assert "moved" in move_result.lower()

        board = _msg("board", "U001", db_path)
        assert "DOING" in board
        assert "implement feature" in board

    def test_board_empty_sections_shown(self, db_path):
        """Board should show section headers even if empty."""
        board = _msg("board", "U001", db_path)
        assert "BACKLOG" in board


# ---------------------------------------------------------------------------
# Scenario 3: add -> done / drop
# ---------------------------------------------------------------------------
class TestDoneAndDropFlow:
    """Mark tasks as done or dropped, verify status changes."""

    def test_add_then_done(self, db_path):
        add_result = _msg("add finish report", "U001", db_path)
        task_id = _extract_task_id(add_result)

        done_result = _msg(f"done {task_id}", "U001", db_path)
        assert "done" in done_result.lower()

        row = _query_task(db_path, task_id, "status, section, closed_at")
        assert row is not None, f"Task #{task_id} not found in DB"
        assert row[0] == "done"
        assert row[1] == "done"
        assert row[2] is not None  # closed_at set

    def test_add_then_drop(self, db_path):
        add_result = _msg("add cancelled task", "U001", db_path)
        task_id = _extract_task_id(add_result)

        drop_result = _msg(f"drop {task_id}", "U001", db_path)
        assert "drop" in drop_result.lower()

        row = _query_task(db_path, task_id, "status, section")
        assert row is not None
        assert row[0] == "dropped"
        assert row[1] == "drop"

    def test_done_task_not_in_default_list(self, db_path):
        """Done tasks should not appear in the default (open) list."""
        _msg("add task1", "U001", db_path)
        add2 = _msg("add task2", "U001", db_path)
        task2_id = _extract_task_id(add2)
        _msg(f"done {task2_id}", "U001", db_path)

        listing = _msg("list", "U001", db_path)
        assert "task1" in listing
        assert "task2" not in listing


# ---------------------------------------------------------------------------
# Scenario 4: add -> edit
# ---------------------------------------------------------------------------
class TestEditFlow:
    """Edit task properties and verify changes."""

    def test_edit_title(self, db_path):
        add_result = _msg("add old title", "U001", db_path)
        task_id = _extract_task_id(add_result)

        edit_result = _msg(f"edit {task_id} new title", "U001", db_path)
        assert "Edited" in edit_result

        row = _query_task(db_path, task_id, "title")
        assert row is not None
        assert row[0] == "new title"

    def test_edit_section(self, db_path):
        add_result = _msg("add some task", "U001", db_path)
        task_id = _extract_task_id(add_result)

        _msg(f"edit {task_id} /s doing", "U001", db_path)

        row = _query_task(db_path, task_id, "section")
        assert row is not None
        assert row[0] == "doing"

    def test_edit_due(self, db_path):
        add_result = _msg("add deadline task", "U001", db_path)
        task_id = _extract_task_id(add_result)

        _msg(f"edit {task_id} due:2026-12-31", "U001", db_path)

        row = _query_task(db_path, task_id, "due")
        assert row is not None
        assert row[0] == "2026-12-31"


# ---------------------------------------------------------------------------
# Scenario 5: private project visibility isolation
# ---------------------------------------------------------------------------
class TestPrivateProjectIsolation:
    """Private project tasks are only visible to their owner."""

    def test_private_task_hidden_from_others(self, db_path):
        # U001 creates a private project and adds a task
        _msg("project set-private Secret", "U001", db_path)
        _msg("add secret task /p Secret", "U001", db_path)

        # U001 can see it
        u1_list = _msg("list all", "U001", db_path)
        assert "secret task" in u1_list

        # U002 cannot see it
        u2_list = _msg("list all", "U002", db_path)
        assert "secret task" not in u2_list

    def test_private_project_not_in_other_users_project_list(self, db_path):
        _msg("project set-private MyPrivate", "U001", db_path)

        u1_projects = _msg("project list", "U001", db_path)
        assert "MyPrivate" in u1_projects

        u2_projects = _msg("project list", "U002", db_path)
        assert "MyPrivate" not in u2_projects

    def test_private_task_write_denied_for_non_owner(self, db_path):
        """Non-owner cannot edit/move/done tasks in a private project."""
        _msg("project set-private Private", "U001", db_path)
        add_result = _msg("add owned task /p Private", "U001", db_path)
        task_id = _extract_task_id(add_result)

        # U002 should be denied write access
        edit_result = _msg(f"edit {task_id} hacked", "U002", db_path)
        assert "denied" in edit_result.lower() or "error" in edit_result.lower()


# ---------------------------------------------------------------------------
# Scenario 6: set-private rejects foreign assignees
# ---------------------------------------------------------------------------
class TestSetPrivateRejectsForeignAssignees:
    """Converting to private fails if tasks have non-owner assignees."""

    def test_set_private_rejected_with_foreign_assignee(self, db_path):
        # Create a shared project and add a task with another assignee
        _msg("project set-shared TeamProj", "U001", db_path)
        _msg("add shared task /p TeamProj <@U002>", "U001", db_path)

        # Try to set it private — should be rejected
        result = _msg("project set-private TeamProj", "U001", db_path)
        assert "cannot" in result.lower()


# ---------------------------------------------------------------------------
# Scenario 7: due date normalisation
# ---------------------------------------------------------------------------
class TestDueNormalisationStored:
    """Due dates in MM-DD format are normalised to YYYY-MM-DD in the DB."""

    def test_mmdd_normalised_to_yyyy(self, db_path):
        add_result = _msg("add task due:03-15", "U001", db_path)
        task_id = _extract_task_id(add_result)

        row = _query_task(db_path, task_id, "due")
        assert row is not None
        # Should be YYYY-MM-DD format (current or next year)
        assert len(row[0]) == 10
        assert row[0].endswith("-03-15")

    def test_full_date_stored_as_is(self, db_path):
        add_result = _msg("add task due:2026-06-01", "U001", db_path)
        task_id = _extract_task_id(add_result)

        row = _query_task(db_path, task_id, "due")
        assert row is not None
        assert row[0] == "2026-06-01"


# ---------------------------------------------------------------------------
# Scenario 8: project set-shared flow
# ---------------------------------------------------------------------------
class TestProjectSetSharedFlow:
    """End-to-end project set-shared scenarios."""

    def test_create_shared_project_and_add_task(self, db_path):
        create_result = _msg("project set-shared TeamBoard", "U001", db_path)
        assert "created" in create_result.lower()

        _msg("add team task /p TeamBoard", "U001", db_path)

        # Both users can see it
        u1_list = _msg("list all /p TeamBoard", "U001", db_path)
        assert "team task" in u1_list

        u2_list = _msg("list all /p TeamBoard", "U002", db_path)
        assert "team task" in u2_list

    def test_private_to_shared_conversion(self, db_path):
        _msg("project set-private MyProj", "U001", db_path)
        _msg("add private task /p MyProj", "U001", db_path)

        # Convert to shared
        result = _msg("project set-shared MyProj", "U001", db_path)
        assert "now shared" in result.lower()

        # U002 can now see the task
        u2_list = _msg("list all /p MyProj", "U002", db_path)
        assert "private task" in u2_list


# ---------------------------------------------------------------------------
# Scenario 9: full lifecycle
# ---------------------------------------------------------------------------
class TestFullLifecycle:
    """A complete task lifecycle: add -> edit -> move -> done."""

    def test_task_lifecycle(self, db_path):
        # Create project first
        _msg("project set-shared Work", "U001", db_path)

        # Add
        add_result = _msg("add initial title /p Work", "U001", db_path)
        assert "Added #" in add_result
        task_id = _extract_task_id(add_result)

        # Edit title
        _msg(f"edit {task_id} updated title", "U001", db_path)

        # Move to doing
        _msg(f"move {task_id} /s doing", "U001", db_path)

        # Verify on board
        board = _msg("board /p Work", "U001", db_path)
        assert "updated title" in board
        assert "DOING" in board

        # Mark done
        _msg(f"done {task_id}", "U001", db_path)

        # Verify in DB
        row = _query_task(db_path, task_id, "title, status, section")
        assert row is not None
        assert row[0] == "updated title"
        assert row[1] == "done"
        assert row[2] == "done"
