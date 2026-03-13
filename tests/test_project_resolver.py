"""Tests for the project resolver."""

import pytest

from openclaw_todo.project_resolver import (
    AmbiguousProjectError,
    ProjectNotFoundError,
    resolve_project,
)


def test_ambiguous_raises_when_both_exist(conn):
    """When both shared and private exist, AmbiguousProjectError is raised."""
    conn.execute("INSERT INTO projects (name, visibility) VALUES ('Work', 'shared');")
    conn.execute("INSERT INTO projects (name, visibility, owner_user_id) VALUES ('Work', 'private', 'U1');")
    conn.commit()

    with pytest.raises(AmbiguousProjectError, match="Ambiguous"):
        resolve_project(conn, "Work", "U1")


def test_falls_back_to_shared(conn):
    """If no private match, shared project should be returned."""
    conn.execute("INSERT INTO projects (name, visibility) VALUES ('Team', 'shared');")
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
    conn.execute("INSERT INTO projects (name, visibility, owner_user_id) " "VALUES ('Secret', 'private', 'U2');")
    conn.commit()

    with pytest.raises(ProjectNotFoundError):
        resolve_project(conn, "Secret", "U1")


def test_visibility_shared_resolves_shared(conn):
    """Explicit visibility='shared' resolves the shared project."""
    conn.execute("INSERT INTO projects (name, visibility) VALUES ('Work', 'shared');")
    conn.execute("INSERT INTO projects (name, visibility, owner_user_id) VALUES ('Work', 'private', 'U1');")
    conn.commit()

    result = resolve_project(conn, "Work", "U1", visibility="shared")
    assert result.visibility == "shared"
    assert result.name == "Work"


def test_visibility_private_resolves_private(conn):
    """Explicit visibility='private' resolves the private project."""
    conn.execute("INSERT INTO projects (name, visibility) VALUES ('Work', 'shared');")
    conn.execute("INSERT INTO projects (name, visibility, owner_user_id) VALUES ('Work', 'private', 'U1');")
    conn.commit()

    result = resolve_project(conn, "Work", "U1", visibility="private")
    assert result.visibility == "private"
    assert result.owner_user_id == "U1"


def test_no_ambiguity_when_only_private(conn):
    """No ambiguity error when only private project exists."""
    conn.execute("INSERT INTO projects (name, visibility, owner_user_id) VALUES ('Solo', 'private', 'U1');")
    conn.commit()

    result = resolve_project(conn, "Solo", "U1")
    assert result.visibility == "private"


def test_no_ambiguity_when_only_shared(conn):
    """No ambiguity error when only shared project exists."""
    conn.execute("INSERT INTO projects (name, visibility) VALUES ('Solo', 'shared');")
    conn.commit()

    result = resolve_project(conn, "Solo", "U1")
    assert result.visibility == "shared"


def test_visibility_private_not_found(conn):
    """Explicit visibility='private' raises when no private project exists."""
    conn.execute("INSERT INTO projects (name, visibility) VALUES ('OnlyShared', 'shared');")
    conn.commit()

    with pytest.raises(ProjectNotFoundError):
        resolve_project(conn, "OnlyShared", "U1", visibility="private")


def test_visibility_shared_not_found(conn):
    """Explicit visibility='shared' raises when no shared project exists."""
    conn.execute("INSERT INTO projects (name, visibility, owner_user_id) VALUES ('OnlyPriv', 'private', 'U1');")
    conn.commit()

    with pytest.raises(ProjectNotFoundError):
        resolve_project(conn, "OnlyPriv", "U1", visibility="shared")
