"""Command parser: tokenizer and option extraction for /todo commands."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime

logger = logging.getLogger(__name__)

VALID_SECTIONS = frozenset({"backlog", "doing", "waiting", "done", "drop"})

_MENTION_RE = re.compile(r"<@(U[A-Z0-9]+)>")
_DUE_RE = re.compile(r"^due:(.+)$")

# Sentinel value indicating "clear due date"
DUE_CLEAR = "-"


class ParseError(Exception):
    """Raised when the input cannot be parsed."""


@dataclass
class ParsedCommand:
    """Result of parsing a ``/todo`` message."""

    command: str
    args: list[str] = field(default_factory=list)
    project: str | None = None
    section: str | None = None
    due: str | None = None  # YYYY-MM-DD or DUE_CLEAR sentinel
    mentions: list[str] = field(default_factory=list)
    title_tokens: list[str] = field(default_factory=list)


def _normalise_due(raw: str) -> str:
    """Normalise a due-date string to ``YYYY-MM-DD`` or the clear sentinel.

    Raises :class:`ParseError` for invalid dates.
    """
    if raw == DUE_CLEAR:
        return DUE_CLEAR

    # Try full date first (YYYY-MM-DD)
    try:
        parsed = datetime.strptime(raw, "%Y-%m-%d").date()
        return parsed.isoformat()
    except ValueError:
        pass

    # Try MM-DD / M-D -- parse month and day as integers and construct with
    # the current year directly. Using strptime("%m-%d") would fail for Feb 29
    # because its default year (1900) is not a leap year.
    match = re.fullmatch(r"(\d{1,2})-(\d{1,2})", raw)
    if match:
        try:
            parsed = date(date.today().year, int(match.group(1)), int(match.group(2)))
            return parsed.isoformat()
        except ValueError:
            pass

    raise ParseError(f"Invalid due date: {raw!r}")


def parse(text: str) -> ParsedCommand:
    """Parse the text *after* the ``/todo`` prefix.

    Returns a :class:`ParsedCommand` with extracted options.
    """
    tokens = text.strip().split()
    if not tokens:
        raise ParseError("Empty command")

    command = tokens[0].lower()
    remaining = tokens[1:]

    project: str | None = None
    section: str | None = None
    due: str | None = None
    mentions: list[str] = []
    title_tokens: list[str] = []
    args: list[str] = []

    i = 0
    while i < len(remaining):
        tok = remaining[i]

        # /p <project>
        if tok == "/p":
            if i + 1 >= len(remaining):
                raise ParseError("/p requires a project name")
            project = remaining[i + 1]
            i += 2
            continue

        # /s <section>
        if tok == "/s":
            if i + 1 >= len(remaining):
                raise ParseError("/s requires a section name")
            sec = remaining[i + 1].lower()
            if sec not in VALID_SECTIONS:
                raise ParseError(f"Invalid section: {sec!r}. " f"Must be one of: {', '.join(sorted(VALID_SECTIONS))}")
            section = sec
            i += 2
            continue

        # due:VALUE
        due_match = _DUE_RE.match(tok)
        if due_match:
            due = _normalise_due(due_match.group(1))
            i += 1
            continue

        # <@U...> mention
        mention_match = _MENTION_RE.fullmatch(tok)
        if mention_match:
            mentions.append(mention_match.group(1))
            i += 1
            continue

        # Everything else: title token or arg
        title_tokens.append(tok)
        i += 1

    # For commands that take an id as first arg (move, done, drop, edit),
    # extract it from title_tokens
    if command in ("move", "done", "drop", "edit") and title_tokens:
        args.append(title_tokens.pop(0))

    result = ParsedCommand(
        command=command,
        args=args,
        project=project,
        section=section,
        due=due,
        mentions=mentions,
        title_tokens=title_tokens,
    )
    logger.debug("Parsed: %s", result)
    return result
