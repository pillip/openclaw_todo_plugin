"""Tests for the command dispatcher and routing."""

from __future__ import annotations

import sqlite3

import pytest

from openclaw_todo.dispatcher import (
    _handlers,
    dispatch,
    register_handler,
)


@pytest.fixture()
def db_path(tmp_path):
    """Provide a temporary DB path for each test."""
    return str(tmp_path / "test.sqlite3")


@pytest.fixture(autouse=True)
def _clean_handlers():
    """Ensure handler registry is clean between tests."""
    saved = dict(_handlers)
    yield
    _handlers.clear()
    _handlers.update(saved)


class TestRoutesKnownCommands:
    """Verify that all valid command names are routed to their handler."""

    def test_add_routes_to_handler(self, db_path):
        """The add command routes to the real add handler."""
        result = dispatch("add something", {"sender_id": "U1"}, db_path=db_path)
        assert "Added #" in result

    def test_list_routes_to_handler(self, db_path):
        """The list command routes to the real list handler."""
        result = dispatch("list", {"sender_id": "U1"}, db_path=db_path)
        assert "not yet implemented" not in result.lower()

    def test_move_routes_to_handler(self, db_path):
        """The move command routes to the real move handler."""
        result = dispatch("move 1 /s doing", {"sender_id": "U1"}, db_path=db_path)
        assert "not yet implemented" not in result.lower()

    def test_done_routes_to_handler(self, db_path):
        """The done command routes to the real done handler."""
        result = dispatch("done 1", {"sender_id": "U1"}, db_path=db_path)
        assert "not yet implemented" not in result.lower()

    def test_drop_routes_to_handler(self, db_path):
        """The drop command routes to the real drop handler."""
        result = dispatch("drop 1", {"sender_id": "U1"}, db_path=db_path)
        assert "not yet implemented" not in result.lower()

    def test_board_routes_to_handler(self, db_path):
        """The board command routes to the real board handler."""
        result = dispatch("board", {"sender_id": "U1"}, db_path=db_path)
        assert "not yet implemented" not in result.lower()

    def test_edit_routes_to_handler(self, db_path):
        """The edit command routes to the real edit handler."""
        result = dispatch("edit 1", {"sender_id": "U1"}, db_path=db_path)
        assert "not yet implemented" not in result.lower()

    def test_registered_handler_called(self, db_path):
        """A registered handler is called instead of the stub."""
        called_with = {}

        def fake_add(parsed, conn, ctx):
            called_with["parsed"] = parsed
            called_with["ctx"] = ctx
            return "added!"

        register_handler("add", fake_add)

        result = dispatch("add buy milk", {"sender_id": "U1"}, db_path=db_path)
        assert result == "added!"
        assert called_with["parsed"].command == "add"
        assert "buy" in called_with["parsed"].title_tokens


class TestProjectSubRouting:
    """Verify /todo project subcommand routing."""

    def test_project_list_routes(self, db_path):
        """`/todo project list` routes to the project_list handler."""
        called = {"hit": False}

        def fake_project_list(parsed, conn, ctx):
            called["hit"] = True
            return "project list!"

        register_handler("project_list", fake_project_list)

        result = dispatch("project list", {"sender_id": "U1"}, db_path=db_path)
        assert called["hit"]
        assert result == "project list!"

    def test_project_set_private_routes(self, db_path):
        """`/todo project set-private` routes correctly."""
        called = {"hit": False}

        def fake_handler(parsed, conn, ctx):
            called["hit"] = True
            return "set private!"

        register_handler("project_set_private", fake_handler)

        result = dispatch("project set-private MyProj", {"sender_id": "U1"}, db_path=db_path)
        assert called["hit"]
        assert result == "set private!"

    def test_project_set_shared_routes(self, db_path):
        """`/todo project set-shared` routes correctly."""
        called = {"hit": False}

        def fake_handler(parsed, conn, ctx):
            called["hit"] = True
            return "set shared!"

        register_handler("project_set_shared", fake_handler)

        result = dispatch("project set-shared MyProj", {"sender_id": "U1"}, db_path=db_path)
        assert called["hit"]
        assert result == "set shared!"

    def test_project_no_subcommand(self, db_path):
        """`/todo project` without subcommand returns usage."""
        result = dispatch("project", {"sender_id": "U1"}, db_path=db_path)
        assert "Subcommands" in result

    def test_project_unknown_subcommand(self, db_path):
        """Unknown project subcommand returns error + usage."""
        result = dispatch("project foobar", {"sender_id": "U1"}, db_path=db_path)
        assert "Unknown project subcommand" in result
        assert "foobar" in result


class TestHelpCommand:
    """help command returns detailed usage information."""

    def test_help_returns_detailed_help(self, db_path):
        result = dispatch("help", {"sender_id": "U1"}, db_path=db_path)
        assert "📖 OpenClaw TODO" in result
        assert "todo: add" in result
        assert "todo: list" in result
        assert "todo: board" in result
        assert "todo: move" in result
        assert "todo: done" in result
        assert "todo: drop" in result
        assert "todo: edit" in result
        assert "todo: project list" in result

    def test_help_does_not_open_db(self, db_path):
        """help should return immediately without opening a DB connection."""
        # If this doesn't raise, help didn't try to open DB
        result = dispatch("help", {"sender_id": "U1"}, db_path=None)
        assert "📖 OpenClaw TODO" in result


class TestUnknownCommandHelp:
    """Unknown commands return a helpful error message."""

    def test_unknown_command_help(self, db_path):
        result = dispatch("foobar something", {"sender_id": "U1"}, db_path=db_path)
        assert "Unknown command" in result
        assert "foobar" in result
        assert "Commands:" in result

    def test_parse_error_returned(self, db_path):
        """Parser errors are returned as user-facing messages."""
        result = dispatch("add /s invalid_section title", {"sender_id": "U1"}, db_path=db_path)
        assert "Parse error" in result


class TestDbInitialization:
    """Verify DB is initialized before command execution."""

    def test_db_initialized_with_schema(self, db_path):
        """Dispatching a command initializes the DB with migrations."""
        dispatch("add something", {"sender_id": "U1"}, db_path=db_path)

        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT version FROM schema_version").fetchone()
        conn.close()
        assert row is not None
        assert row[0] >= 1
