"""Tests for the plugin entry-point."""

from openclaw_todo.plugin import handle_message


def test_ignores_non_todo_message():
    """Messages not starting with /todo should be silently ignored."""
    assert handle_message("hello world", {"sender_id": "U1"}) is None
    assert handle_message("", {"sender_id": "U1"}) is None
    assert handle_message("some random text", {"sender_id": "U1"}) is None
    assert handle_message("/todox something", {"sender_id": "U1"}) is None


def test_dispatches_todo_prefix():
    """Messages starting with /todo should return a response."""
    result = handle_message("/todo add buy milk", {"sender_id": "U1"})
    assert result is not None
    assert "add buy milk" in result


def test_todo_prefix_with_whitespace():
    """Leading/trailing whitespace should not prevent matching."""
    result = handle_message("  /todo add task  ", {"sender_id": "U1"})
    assert result is not None


def test_todo_without_subcommand():
    """/todo alone should return usage information."""
    result = handle_message("/todo", {"sender_id": "U1"})
    assert result is not None
    assert "Usage" in result
