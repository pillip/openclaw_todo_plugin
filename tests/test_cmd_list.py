"""Tests for the /todo list command handler."""

from __future__ import annotations

from openclaw_todo.cmd_list import list_handler
from openclaw_todo.parser import ParsedCommand


def _seed_tasks(conn):
    """Seed test data: shared 'Inbox' + private 'Secret' project with tasks."""
    # Inbox already exists from V1 migration (id=1)
    inbox_id = conn.execute("SELECT id FROM projects WHERE name = 'Inbox'").fetchone()[0]

    # Create a private project for U002
    conn.execute("INSERT INTO projects (name, visibility, owner_user_id) " "VALUES ('Secret', 'private', 'U002');")
    secret_id = conn.execute("SELECT id FROM projects WHERE name = 'Secret'").fetchone()[0]

    # Create a shared project 'Backend'
    conn.execute("INSERT INTO projects (name, visibility) VALUES ('Backend', 'shared');")
    backend_id = conn.execute("SELECT id FROM projects WHERE name = 'Backend'").fetchone()[0]

    # Tasks in Inbox, assigned to U001
    conn.execute(
        "INSERT INTO tasks (title, project_id, section, due, status, created_by) "
        "VALUES ('Task A', ?, 'backlog', '2026-03-01', 'open', 'U001');",
        (inbox_id,),
    )
    conn.execute("INSERT INTO task_assignees (task_id, assignee_user_id) VALUES (1, 'U001');")

    # Task in Inbox, assigned to U002
    conn.execute(
        "INSERT INTO tasks (title, project_id, section, due, status, created_by) "
        "VALUES ('Task B', ?, 'doing', '2026-02-15', 'open', 'U002');",
        (inbox_id,),
    )
    conn.execute("INSERT INTO task_assignees (task_id, assignee_user_id) VALUES (2, 'U002');")

    # Task in Secret (private, owner=U002), assigned to U002
    conn.execute(
        "INSERT INTO tasks (title, project_id, section, due, status, created_by) "
        "VALUES ('Private task', ?, 'backlog', NULL, 'open', 'U002');",
        (secret_id,),
    )
    conn.execute("INSERT INTO task_assignees (task_id, assignee_user_id) VALUES (3, 'U002');")

    # Task in Backend, assigned to U001, no due
    conn.execute(
        "INSERT INTO tasks (title, project_id, section, due, status, created_by) "
        "VALUES ('Task C', ?, 'backlog', NULL, 'open', 'U001');",
        (backend_id,),
    )
    conn.execute("INSERT INTO task_assignees (task_id, assignee_user_id) VALUES (4, 'U001');")

    # Done task in Inbox, assigned to U001
    conn.execute(
        "INSERT INTO tasks (title, project_id, section, due, status, created_by) "
        "VALUES ('Done task', ?, 'done', '2026-01-10', 'done', 'U001');",
        (inbox_id,),
    )
    conn.execute("INSERT INTO task_assignees (task_id, assignee_user_id) VALUES (5, 'U001');")

    # Dropped task in Inbox, assigned to U001
    conn.execute(
        "INSERT INTO tasks (title, project_id, section, due, status, created_by) "
        "VALUES ('Dropped task', ?, 'drop', NULL, 'dropped', 'U001');",
        (inbox_id,),
    )
    conn.execute("INSERT INTO task_assignees (task_id, assignee_user_id) VALUES (6, 'U001');")

    conn.commit()


def _make_parsed(
    *,
    title_tokens: list[str] | None = None,
    project: str | None = None,
    section: str | None = None,
    mentions: list[str] | None = None,
) -> ParsedCommand:
    return ParsedCommand(
        command="list",
        args=[],
        project=project,
        section=section,
        due=None,
        mentions=mentions or [],
        title_tokens=title_tokens or [],
    )


class TestListMineDefault:
    """Default scope=mine returns only sender's assigned tasks."""

    def test_list_mine_default(self, conn):
        _seed_tasks(conn)
        parsed = _make_parsed()
        ctx = {"sender_id": "U001"}

        result = list_handler(parsed, conn, ctx)

        # U001 is assigned to Task A (#1) and Task C (#4), both open
        assert "#1" in result
        assert "Task A" in result
        assert "#4" in result
        assert "Task C" in result

        # Should NOT include U002's tasks or done tasks
        assert "Task B" not in result
        assert "Private task" not in result
        assert "Done task" not in result


class TestListAllExcludesOthersPrivate:
    """scope=all shows shared + sender's private, excludes others' private."""

    def test_list_all_excludes_others_private(self, conn):
        _seed_tasks(conn)
        parsed = _make_parsed(title_tokens=["all"])
        ctx = {"sender_id": "U001"}

        result = list_handler(parsed, conn, ctx)

        # Should include shared project tasks (Task A, Task B, Task C)
        assert "Task A" in result
        assert "Task B" in result
        assert "Task C" in result

        # Should NOT include U002's private project tasks
        assert "Private task" not in result

    def test_list_all_includes_own_private(self, conn):
        _seed_tasks(conn)
        parsed = _make_parsed(title_tokens=["all"])
        ctx = {"sender_id": "U002"}

        result = list_handler(parsed, conn, ctx)

        # U002 can see their own private tasks
        assert "Private task" in result
        # And shared tasks
        assert "Task A" in result


class TestListWithProjectFilter:
    """Project filter limits results to specific project."""

    def test_list_with_project_filter(self, conn):
        _seed_tasks(conn)
        parsed = _make_parsed(title_tokens=["all"], project="Backend")
        ctx = {"sender_id": "U001"}

        result = list_handler(parsed, conn, ctx)

        assert "Task C" in result
        assert "Task A" not in result
        assert "Task B" not in result

    def test_list_with_nonexistent_project(self, conn):
        _seed_tasks(conn)
        parsed = _make_parsed(project="NonExistent")
        ctx = {"sender_id": "U001"}

        result = list_handler(parsed, conn, ctx)

        assert "❌" in result
        assert "NonExistent" in result


class TestListSortingOrder:
    """Sorting: due NOT NULL first (ASC), then NULLs, within same due id DESC."""

    def test_list_sorting_order(self, conn):
        _seed_tasks(conn)
        # Use scope=all to get multiple tasks for U001
        parsed = _make_parsed(title_tokens=["all"])
        ctx = {"sender_id": "U001"}

        result = list_handler(parsed, conn, ctx)
        lines = result.strip().split("\n")

        # Expected order:
        # Task B (due:2026-02-15) — has due, earliest
        # Task A (due:2026-03-01) — has due, later
        # Task C (due:NULL) — no due, id=4
        # Extract task IDs from lines starting with "#"
        ids = []
        for line in lines:
            if not line.startswith("#"):
                continue
            start = line.index("#") + 1
            end = line.index(" ", start)
            ids.append(int(line[start:end]))

        assert ids == [2, 1, 4]


class TestListLimit:
    """limit:N caps the number of results."""

    def test_list_limit(self, conn):
        _seed_tasks(conn)
        parsed = _make_parsed(title_tokens=["all", "limit:1"])
        ctx = {"sender_id": "U001"}

        result = list_handler(parsed, conn, ctx)
        # Count task lines (lines starting with "#")
        task_lines = [line for line in result.strip().split("\n") if line.startswith("#")]

        assert len(task_lines) == 1

    def test_list_invalid_limit(self, conn):
        parsed = _make_parsed(title_tokens=["limit:abc"])
        ctx = {"sender_id": "U001"}

        result = list_handler(parsed, conn, ctx)

        assert "❌" in result
        assert "limit" in result.lower()

    def test_list_zero_limit(self, conn):
        parsed = _make_parsed(title_tokens=["limit:0"])
        ctx = {"sender_id": "U001"}

        result = list_handler(parsed, conn, ctx)

        assert "❌" in result
        assert "positive" in result.lower()

    def test_list_negative_limit(self, conn):
        parsed = _make_parsed(title_tokens=["limit:-5"])
        ctx = {"sender_id": "U001"}

        result = list_handler(parsed, conn, ctx)

        assert "❌" in result
        assert "positive" in result.lower()


class TestListSectionFilter:
    """Section filter via /s option."""

    def test_list_section_filter(self, conn):
        _seed_tasks(conn)
        parsed = _make_parsed(title_tokens=["all"], section="doing")
        ctx = {"sender_id": "U001"}

        result = list_handler(parsed, conn, ctx)

        assert "Task B" in result
        assert "Task A" not in result
        assert "Task C" not in result


class TestListStatusToken:
    """Status filter via title_tokens: open, done, drop."""

    def test_list_done_token(self, conn):
        _seed_tasks(conn)
        parsed = _make_parsed(title_tokens=["done"])
        ctx = {"sender_id": "U001"}

        result = list_handler(parsed, conn, ctx)

        assert "Done task" in result
        assert "Task A" not in result
        assert "Task C" not in result
        assert "/ done)" in result  # header shows status=done

    def test_list_drop_token(self, conn):
        _seed_tasks(conn)
        parsed = _make_parsed(title_tokens=["drop"])
        ctx = {"sender_id": "U001"}

        result = list_handler(parsed, conn, ctx)

        assert "Dropped task" in result
        assert "Task A" not in result
        assert "/ dropped)" in result  # header shows status=dropped

    def test_list_open_token(self, conn):
        _seed_tasks(conn)
        parsed = _make_parsed(title_tokens=["open"])
        ctx = {"sender_id": "U001"}

        result = list_handler(parsed, conn, ctx)

        # Same as default — open tasks only
        assert "Task A" in result
        assert "Done task" not in result
        assert "Dropped task" not in result
        assert "/ open)" in result

    def test_list_done_token_with_all_scope(self, conn):
        _seed_tasks(conn)
        parsed = _make_parsed(title_tokens=["all", "done"])
        ctx = {"sender_id": "U001"}

        result = list_handler(parsed, conn, ctx)

        assert "Done task" in result
        assert "Task A" not in result

    def test_list_done_token_no_conflict_with_section(self, conn):
        """done as title_token should not conflict with /s section."""
        _seed_tasks(conn)
        # /s done via parsed.section still works
        parsed = _make_parsed(section="done")
        ctx = {"sender_id": "U001"}

        result = list_handler(parsed, conn, ctx)

        assert "Done task" in result
        assert "Task A" not in result


class TestListNoResults:
    """Empty result set returns informational message."""

    def test_list_no_results(self, conn):
        parsed = _make_parsed()
        ctx = {"sender_id": "U999"}

        result = list_handler(parsed, conn, ctx)

        assert "No tasks found." in result
        assert "0 tasks" in result
