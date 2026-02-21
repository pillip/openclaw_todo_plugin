"""Command dispatcher: routes parsed commands to handler functions."""

from __future__ import annotations

import logging
import sqlite3

from typing import Callable

from openclaw_todo.db import get_connection
from openclaw_todo.migrations import migrate
from openclaw_todo.parser import ParsedCommand, ParseError, parse

import openclaw_todo.schema_v1 as _schema_v1  # noqa: F401 — registers migrations

from openclaw_todo.cmd_add import add_handler as _add_handler  # noqa: E402
from openclaw_todo.cmd_list import list_handler as _list_handler  # noqa: E402

# Type alias for command handler functions.
HandlerFn = Callable[[ParsedCommand, sqlite3.Connection, dict], str]

logger = logging.getLogger(__name__)

USAGE = (
    "Usage: /todo <command> [options]\n"
    "Commands: add, list, board, move, done, drop, edit, project"
)

PROJECT_USAGE = (
    "Usage: /todo project <subcommand>\n"
    "Subcommands: list, set-private, set-shared"
)

# Valid top-level command names
_VALID_COMMANDS = frozenset(
    {"add", "list", "board", "move", "done", "drop", "edit", "project"}
)

# Valid project subcommands
_VALID_PROJECT_SUBS = frozenset({"list", "set-private", "set-shared"})


def _init_db(db_path: str | None = None) -> sqlite3.Connection:
    """Open DB connection and ensure schema is up-to-date."""
    conn = get_connection(db_path)
    migrate(conn)
    return conn


def _stub_handler(command: str, parsed: ParsedCommand, conn: sqlite3.Connection, context: dict) -> str:
    """Placeholder for commands not yet implemented."""
    return f"Command '{command}' is not yet implemented."


# Handler registry: command name -> callable(parsed, conn, context) -> str
_handlers: dict[str, HandlerFn] = {
    "add": _add_handler,
    "list": _list_handler,
}


def _get_handler(command: str) -> HandlerFn:
    """Look up a handler, falling back to stub."""
    return _handlers.get(command, lambda parsed, conn, ctx: _stub_handler(command, parsed, conn, ctx))


def register_handler(command: str, fn: HandlerFn) -> None:
    """Register a handler function for a top-level command."""
    _handlers[command] = fn


def dispatch(text: str, context: dict, db_path: str | None = None) -> str:
    """Parse the remainder text and dispatch to the appropriate handler.

    *text* is the message content **after** the ``/todo`` prefix has been
    stripped.  *context* must contain at least ``sender_id``.
    """
    try:
        parsed = parse(text)
    except ParseError as exc:
        return f"Parse error: {exc}"

    command = parsed.command

    if command not in _VALID_COMMANDS:
        logger.info("Unknown command: %s", command)
        return f"Unknown command: '{command}'\n{USAGE}"

    logger.info("Dispatching command=%s", command)

    conn = _init_db(db_path)
    try:
        if command == "project":
            return _dispatch_project(parsed, conn, context)

        handler = _get_handler(command)
        return handler(parsed, conn, context)
    finally:
        conn.close()


def _dispatch_project(parsed: ParsedCommand, conn: sqlite3.Connection, context: dict) -> str:
    """Route ``/todo project <subcommand>`` to the correct project handler."""
    # The subcommand is the first title_token or arg
    sub_tokens = parsed.title_tokens or parsed.args
    if not sub_tokens:
        return PROJECT_USAGE

    sub = sub_tokens[0].lower()

    # Handle "set-private" and "set-shared" which may come as two tokens
    # e.g. "/todo project set-private MyProject"
    if sub not in _VALID_PROJECT_SUBS:
        logger.info("Unknown project subcommand: %s", sub)
        return f"Unknown project subcommand: '{sub}'\n{PROJECT_USAGE}"

    logger.info("Dispatching command=project sub=%s", sub)

    handler_name = f"project_{sub.replace('-', '_')}"
    handler: HandlerFn = _handlers.get(handler_name, lambda parsed, conn, ctx: _stub_handler(f"project {sub}", parsed, conn, ctx))
    return handler(parsed, conn, context)
