"""Tests for the schema migration framework."""

import sqlite3

import pytest

from openclaw_todo.db import get_connection
from openclaw_todo.migrations import (
    _migrations,
    get_version,
    migrate,
    register,
)


@pytest.fixture(autouse=True)
def _clean_migrations():
    """Save and restore the global migrations list around each test."""
    saved = _migrations.copy()
    _migrations.clear()
    yield
    _migrations.clear()
    _migrations.extend(saved)


@pytest.fixture()
def conn(tmp_path):
    """Return a fresh SQLite connection via get_connection."""
    c = get_connection(tmp_path / "test.sqlite3")
    yield c
    c.close()


def test_fresh_db_gets_version_table(conn):
    """A fresh DB should get schema_version table with version=0."""
    version = get_version(conn)
    assert version == 0
    # Table should exist
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version';"
    ).fetchone()
    assert row is not None


def test_applies_migrations_sequentially(conn):
    """Migrations should be applied in order, incrementing version."""

    @register
    def migration_1(c: sqlite3.Connection) -> None:
        c.execute("CREATE TABLE t1 (id INTEGER PRIMARY KEY);")

    @register
    def migration_2(c: sqlite3.Connection) -> None:
        c.execute("CREATE TABLE t2 (id INTEGER PRIMARY KEY);")

    final = migrate(conn)
    assert final == 2

    # Both tables should exist
    tables = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table';"
        ).fetchall()
    }
    assert "t1" in tables
    assert "t2" in tables


def test_idempotent_on_rerun(conn):
    """Re-running migrate on an up-to-date DB should be a no-op."""

    @register
    def migration_1(c: sqlite3.Connection) -> None:
        c.execute("CREATE TABLE t1 (id INTEGER PRIMARY KEY);")

    assert migrate(conn) == 1
    # Second run should not fail and should return same version
    assert migrate(conn) == 1


def test_rollback_on_failure(conn):
    """A failing migration should rollback and raise RuntimeError."""

    @register
    def migration_ok(c: sqlite3.Connection) -> None:
        c.execute("CREATE TABLE t_ok (id INTEGER PRIMARY KEY);")

    @register
    def migration_bad(c: sqlite3.Connection) -> None:
        raise ValueError("intentional failure")

    # First migration succeeds
    # Second should fail — but we call migrate which tries both
    # Since migration_ok is index 0 and migration_bad is index 1,
    # migration_ok will succeed first, then migration_bad will fail.
    with pytest.raises(RuntimeError, match="Migration to version 2 failed"):
        migrate(conn)

    # Version should be 1 (first migration committed, second rolled back)
    assert get_version(conn) == 1

    # t_ok should exist (committed), but nothing from bad migration
    tables = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table';"
        ).fetchall()
    }
    assert "t_ok" in tables
