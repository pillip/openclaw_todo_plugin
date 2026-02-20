"""Database connection helper for the OpenClaw TODO plugin."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_DB_DIR = Path.home() / ".openclaw" / "workspace" / ".todo"
DEFAULT_DB_NAME = "todo.sqlite3"


def get_connection(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Open (or create) the SQLite database and apply pragmas.

    If *db_path* is ``None`` the default location
    ``~/.openclaw/workspace/.todo/todo.sqlite3`` is used.

    The directory tree is created recursively when absent.
    """
    if db_path is None:
        db_path = DEFAULT_DB_DIR / DEFAULT_DB_NAME
    else:
        db_path = Path(db_path)

    db_dir = db_path.parent
    is_new = not db_path.exists()

    if not db_dir.exists():
        db_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Created DB directory: %s", db_dir)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=3000;")
    conn.execute("PRAGMA foreign_keys=ON;")

    if is_new:
        logger.info("Created new database: %s", db_path)
    else:
        logger.debug("Opened database: %s", db_path)

    return conn
