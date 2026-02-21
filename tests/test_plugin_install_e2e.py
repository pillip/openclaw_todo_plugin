"""Plugin install E2E tests via entry-point discovery.

These tests verify that the plugin package is properly installed and
discoverable via ``importlib.metadata.entry_points``, then exercise the
full command flow through the entry-point-loaded function.
"""

from __future__ import annotations

import importlib.metadata
import inspect
import sqlite3

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_path(tmp_path):
    """Provide a fresh DB path per test."""
    return str(tmp_path / "install_e2e.sqlite3")


@pytest.fixture()
def handle_message():
    """Load handle_message via entry-point discovery."""
    eps = importlib.metadata.entry_points(group="openclaw.plugins")
    todo_eps = [ep for ep in eps if ep.name == "todo"]
    assert todo_eps, "Entry-point 'todo' not found in group 'openclaw.plugins'"
    return todo_eps[0].load()


def _msg(handle_message, text: str, sender: str, db_path: str) -> str:
    """Send a todo: command via the entry-point-loaded function."""
    result = handle_message(f"todo: {text}", {"sender_id": sender}, db_path=db_path)
    assert result is not None, f"Expected response for: todo: {text}"
    return result


def _extract_task_id(add_result: str) -> str:
    """Extract task ID from 'Added #N ...' response."""
    return add_result.split("#")[1].split(" ")[0]


_ALLOWED_COLUMNS = frozenset({
    "*", "id", "title", "status", "section", "due",
    "project_id", "created_by", "closed_at", "created_at", "updated_at",
})


def _query_task(db_path: str, task_id: str, columns: str = "*") -> tuple | None:
    """Query a task row by ID.

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


# ===========================================================================
# Test Class 1: Entry-Point Discovery
# ===========================================================================
@pytest.mark.install
class TestEntryPointDiscovery:
    """Verify the package is installed and entry-point is discoverable."""

    def test_todo_entry_point_exists(self):
        """openclaw.plugins group contains a 'todo' entry-point."""
        eps = importlib.metadata.entry_points(group="openclaw.plugins")
        names = [ep.name for ep in eps]
        assert "todo" in names

    def test_loaded_function_is_callable(self, handle_message):
        """The loaded entry-point is a callable."""
        assert callable(handle_message)

    def test_loaded_function_signature(self, handle_message):
        """The loaded function has (text, context, db_path) parameters."""
        sig = inspect.signature(handle_message)
        param_names = list(sig.parameters.keys())
        assert "text" in param_names
        assert "context" in param_names
        assert "db_path" in param_names


# ===========================================================================
# Test Class 2: Full Flow via Entry-Point
# ===========================================================================
@pytest.mark.install
class TestPluginViaEntryPoint:
    """Exercise the full command flow through the entry-point-loaded function."""

    def test_non_todo_returns_none(self, handle_message, db_path):
        """Messages not starting with todo: return None."""
        result = handle_message("hello world", {"sender_id": "U001"}, db_path=db_path)
        assert result is None

    def test_add_and_list_roundtrip(self, handle_message, db_path):
        """Add a task via entry-point, then list it."""
        add_result = _msg(handle_message, "add buy groceries", "U001", db_path)
        assert "Added #" in add_result

        listing = _msg(handle_message, "list", "U001", db_path)
        assert "buy groceries" in listing

    def test_full_lifecycle(self, handle_message, db_path):
        """add -> move -> edit -> done lifecycle."""
        # Add
        add_result = _msg(handle_message, "add lifecycle task", "U001", db_path)
        task_id = _extract_task_id(add_result)

        # Move to doing
        move_result = _msg(handle_message, f"move {task_id} /s doing", "U001", db_path)
        assert "moved" in move_result.lower()

        # Edit title
        edit_result = _msg(handle_message, f"edit {task_id} renamed task", "U001", db_path)
        assert "Edited" in edit_result

        # Mark done
        done_result = _msg(handle_message, f"done {task_id}", "U001", db_path)
        assert "done" in done_result.lower()

        # Verify final state in DB
        row = _query_task(db_path, task_id, "title, status, section, closed_at")
        assert row is not None
        assert row[0] == "renamed task"
        assert row[1] == "done"
        assert row[2] == "done"
        assert row[3] is not None

    def test_private_project_isolation(self, handle_message, db_path):
        """Private project tasks are invisible to other users."""
        _msg(handle_message, "project set-private Secret", "U001", db_path)
        _msg(handle_message, "add hidden task /p Secret", "U001", db_path)

        # Owner sees it
        u1_list = _msg(handle_message, "list all", "U001", db_path)
        assert "hidden task" in u1_list

        # Other user does not
        u2_list = _msg(handle_message, "list all", "U002", db_path)
        assert "hidden task" not in u2_list

    def test_multiple_users_shared_project(self, handle_message, db_path):
        """Multiple users can collaborate on a shared project."""
        _msg(handle_message, "project set-shared TeamWork", "U001", db_path)

        # U001 adds a task
        add_result = _msg(handle_message, "add team task /p TeamWork", "U001", db_path)
        task_id = _extract_task_id(add_result)

        # U002 can see it
        u2_list = _msg(handle_message, "list all /p TeamWork", "U002", db_path)
        assert "team task" in u2_list

        # U001 can move it
        _msg(handle_message, f"move {task_id} /s doing", "U001", db_path)

        # Verify on board for U002 (scope=all to see all shared tasks)
        board = _msg(handle_message, "board all /p TeamWork", "U002", db_path)
        assert "team task" in board
        assert "DOING" in board
