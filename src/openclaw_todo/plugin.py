"""Plugin entry-point for the OpenClaw gateway."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_TODO_PREFIX = "/todo"


def handle_message(text: str, context: dict) -> str | None:
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
        return "Usage: /todo <command> [options]\nCommands: add, list, board, move, done, drop, edit, project"

    # Placeholder: will be replaced by dispatcher in Issue #16
    return f"TODO command received: {remainder}"
