"""Sequential schema migration runner for the OpenClaw TODO plugin."""

from __future__ import annotations

import logging
import sqlite3
from typing import Callable

logger = logging.getLogger(__name__)

# Type alias for a migration callable: receives a connection, performs DDL/DML.
MigrationFn = Callable[[sqlite3.Connection], None]

# Ordered list of migrations. Index 0 = migration to go from version 0 → 1, etc.
_migrations: list[MigrationFn] = []


def register(fn: MigrationFn) -> MigrationFn:
    """Decorator to register a migration function."""
    _migrations.append(fn)
    return fn


def _ensure_version_table(conn: sqlite3.Connection) -> None:
    """Create ``schema_version`` table with version=0 if it does not exist."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);"
    )
    row = conn.execute("SELECT version FROM schema_version;").fetchone()
    if row is None:
        conn.execute("INSERT INTO schema_version (version) VALUES (0);")
        conn.commit()


def get_version(conn: sqlite3.Connection) -> int:
    """Return the current schema version."""
    _ensure_version_table(conn)
    row = conn.execute("SELECT version FROM schema_version;").fetchone()
    return row[0]


def migrate(conn: sqlite3.Connection) -> int:
    """Apply all outstanding migrations and return the final version.

    Each migration runs inside a transaction.  On failure the transaction
    is rolled back and a ``RuntimeError`` is raised with a clear message.
    """
    _ensure_version_table(conn)
    current = get_version(conn)
    target = len(_migrations)

    if current >= target:
        logger.debug("Schema up-to-date at version %d", current)
        return current

    for idx in range(current, target):
        version_to_apply = idx + 1
        migration_fn = _migrations[idx]
        logger.info("Migrating from version %d to %d", idx, version_to_apply)
        try:
            migration_fn(conn)
            conn.execute(
                "UPDATE schema_version SET version = ?;", (version_to_apply,)
            )
            conn.commit()
        except Exception as exc:
            conn.rollback()
            raise RuntimeError(
                f"Migration to version {version_to_apply} failed: {exc}"
            ) from exc

    final = get_version(conn)
    logger.info("Migrations complete. Schema at version %d", final)
    return final
