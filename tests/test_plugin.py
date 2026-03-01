"""Tests for the plugin entry-point."""

import pytest

from openclaw_todo.plugin import handle_message


@pytest.fixture()
def db_path(tmp_path):
    return str(tmp_path / "test.sqlite3")


def test_ignores_non_todo_message(db_path):
    """Messages not starting with /todo should be silently ignored."""
    assert handle_message("hello world", {"sender_id": "U1"}, db_path=db_path) is None
    assert handle_message("", {"sender_id": "U1"}, db_path=db_path) is None
    assert handle_message("some random text", {"sender_id": "U1"}, db_path=db_path) is None
    assert handle_message("/todox something", {"sender_id": "U1"}, db_path=db_path) is None


def test_dispatches_todo_prefix(db_path):
    """Messages starting with /todo should return a response."""
    result = handle_message("/todo add buy milk", {"sender_id": "U1"}, db_path=db_path)
    assert result is not None
    assert isinstance(result, str)


def test_todo_prefix_with_whitespace(db_path):
    """Leading/trailing whitespace should not prevent matching."""
    result = handle_message("  /todo add task  ", {"sender_id": "U1"}, db_path=db_path)
    assert result is not None


def test_todo_without_subcommand(db_path):
    """/todo alone should return detailed help."""
    result = handle_message("/todo", {"sender_id": "U1"}, db_path=db_path)
    assert result is not None
    assert "📖 OpenClaw TODO" in result
    assert "/todo add" in result
    assert "/todo list" in result
    assert "/todo board" in result


def test_todo_help_command(db_path):
    """/todo help should return the same detailed help."""
    result = handle_message("/todo help", {"sender_id": "U1"}, db_path=db_path)
    assert result is not None
    assert "📖 OpenClaw TODO" in result
    assert "/todo add" in result
    assert "/todo project" in result
