"""Plugin entry-point for the OpenClaw gateway."""

from __future__ import annotations

import logging

from openclaw_todo.dispatcher import USAGE, dispatch

logger = logging.getLogger(__name__)

_TODO_PREFIX = "todo:"


def handle_message(text: str, context: dict, db_path: str | None = None) -> str | None:
    """Process an incoming Slack DM message.

    Returns a response string for ``/todo`` commands, or ``None`` if the
    message is not a TODO command.
    """
    logger.debug("Inbound message: %s", text)

    stripped = text.strip()
    if not (stripped == _TODO_PREFIX or stripped.startswith(_TODO_PREFIX + " ")):
        return None

    logger.info("/todo prefix matched")

    remainder = stripped[len(_TODO_PREFIX) :].strip()

    if not remainder:
        return USAGE

    return dispatch(remainder, context, db_path=db_path)
