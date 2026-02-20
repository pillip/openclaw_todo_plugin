"""Tests for the project resolver."""

import pytest

from openclaw_todo.db import get_connection
from openclaw_todo.migrations import _migrations, migrate
from openclaw_todo.project_resolver import (
    Project,
    ProjectNotFoundError,
    resolve_project,
)


@pytest.fixture(autouse=True)
def _load_v1():
    """Register V1 migration."""
    saved = _migrations.copy()
    _migrations.clear()
    from openclaw_todo.schema_v1 import migrate_v1
    if migrate_v1 not in _migrations:
        _migrations.append(migrate_v1)
    yield
    _migrations.clear()
    _migrations.extend(saved)


@pytest.fixture()
def conn(tmp_path):
    """Return a migrated V1 connection."""
    c = get_connection(tmp_path / "test.sqlite3")
    migrate(c)
    yield c
    c.close()


def test_private_takes_priority(conn):
    """Sender's private project should be matched before shared."""
    # Create shared and private with same name
    conn.execute(
        "INSERT INTO projects (name, visibility) VALUES ('Work', 'shared');"
    )
    conn.execute(
        "INSERT INTO projects (name, visibility, owner_user_id) "
        "VALUES ('Work', 'private', 'U1');"
    )
    conn.commit()

    result = resolve_project(conn, "Work", "U1")
    assert result.visibility == "private"
    assert result.owner_user_id == "U1"
    assert result.name == "Work"


def test_falls_back_to_shared(conn):
    """If no private match, shared project should be returned."""
    conn.execute(
        "INSERT INTO projects (name, visibility) VALUES ('Team', 'shared');"
    )
    conn.commit()

    result = resolve_project(conn, "Team", "U1")
    assert result.visibility == "shared"
    assert result.name == "Team"


def test_inbox_auto_created(conn):
    """Inbox should be auto-created as shared if not found."""
    # Delete the Inbox that was seeded by V1 migration
    conn.execute("DELETE FROM projects WHERE name = 'Inbox';")
    conn.commit()

    result = resolve_project(conn, "Inbox", "U1")
    assert result.name == "Inbox"
    assert result.visibility == "shared"
    assert result.owner_user_id is None


def test_unknown_project_error(conn):
    """Unknown project name should raise ProjectNotFoundError."""
    with pytest.raises(ProjectNotFoundError, match="Project not found"):
        resolve_project(conn, "NonExistent", "U1")


def test_inbox_already_exists(conn):
    """Inbox already seeded by V1 should resolve without re-creation."""
    result = resolve_project(conn, "Inbox", "U1")
    assert result.name == "Inbox"
    assert result.visibility == "shared"


def test_private_different_owner_not_matched(conn):
    """Private project of another owner should not be matched."""
    conn.execute(
        "INSERT INTO projects (name, visibility, owner_user_id) "
        "VALUES ('Secret', 'private', 'U2');"
    )
    conn.commit()

    with pytest.raises(ProjectNotFoundError):
        resolve_project(conn, "Secret", "U1")
