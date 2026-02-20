"""Tests for the database connection helper."""

from openclaw_todo.db import get_connection


def test_creates_directory_and_file(tmp_path):
    """get_connection should create the directory tree and DB file."""
    db_path = tmp_path / "nested" / "dir" / "test.sqlite3"
    conn = get_connection(db_path)
    try:
        assert db_path.exists()
        assert db_path.parent.exists()
    finally:
        conn.close()


def test_wal_mode_enabled(tmp_path):
    """WAL journal mode must be active."""
    db_path = tmp_path / "test.sqlite3"
    conn = get_connection(db_path)
    try:
        result = conn.execute("PRAGMA journal_mode;").fetchone()
        assert result[0] == "wal"
    finally:
        conn.close()


def test_busy_timeout(tmp_path):
    """busy_timeout must be 3000 ms."""
    db_path = tmp_path / "test.sqlite3"
    conn = get_connection(db_path)
    try:
        result = conn.execute("PRAGMA busy_timeout;").fetchone()
        assert result[0] == 3000
    finally:
        conn.close()


def test_two_connections_no_conflict(tmp_path):
    """Two connections to the same DB should not conflict."""
    db_path = tmp_path / "test.sqlite3"
    conn1 = get_connection(db_path)
    conn2 = get_connection(db_path)
    try:
        conn1.execute("CREATE TABLE t (id INTEGER PRIMARY KEY);")
        conn1.commit()
        rows = conn2.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
        assert any(r[0] == "t" for r in rows)
    finally:
        conn1.close()
        conn2.close()
