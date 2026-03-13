"""Tests for the /todo board command handler."""

from __future__ import annotations

from openclaw_todo.cmd_board import board_handler
from openclaw_todo.parser import ParsedCommand
from tests.conftest import seed_task as _seed_task


def _make_parsed(**kwargs) -> ParsedCommand:
    defaults = {"command": "board", "title_tokens": [], "args": [], "project_visibility": None}
    defaults.update(kwargs)
    return ParsedCommand(**defaults)


class TestBoardSectionOrder:
    """Sections appear in fixed order: BACKLOG, DOING, WAITING, DONE, DROP."""

    def test_all_sections_shown(self, conn):
        _seed_task(conn, title="t1", section="backlog")
        parsed = _make_parsed()
        result = board_handler(parsed, conn, {"sender_id": "U001"})

        sections = [line for line in result.splitlines() if line.startswith("—")]
        assert len(sections) == 5
        assert "BACKLOG" in sections[0]
        assert "DOING" in sections[1]
        assert "WAITING" in sections[2]
        assert "DONE" in sections[3]
        assert "DROP" in sections[4]

    def test_empty_sections_show_empty(self, conn):
        """Sections with no tasks show (empty)."""
        _seed_task(conn, title="only in backlog", section="backlog")
        parsed = _make_parsed()
        result = board_handler(parsed, conn, {"sender_id": "U001"})

        lines = result.splitlines()
        for i, line in enumerate(lines):
            if "DOING" in line:
                assert lines[i + 1] == "(empty)"
                break

    def test_tasks_grouped_correctly(self, conn):
        """Tasks appear under their correct section."""
        _seed_task(conn, title="backlog task", section="backlog")
        _seed_task(conn, title="doing task", section="doing")

        parsed = _make_parsed()
        result = board_handler(parsed, conn, {"sender_id": "U001"})

        lines = result.splitlines()
        backlog_idx = next(i for i, line in enumerate(lines) if "BACKLOG" in line)
        doing_idx = next(i for i, line in enumerate(lines) if "DOING" in line)

        backlog_content = "\n".join(lines[backlog_idx:doing_idx])
        assert "backlog task" in backlog_content

        doing_content = "\n".join(lines[doing_idx:])
        assert "doing task" in doing_content

    def test_header_format(self, conn):
        """Board header includes scope and status."""
        _seed_task(conn, title="t1")
        parsed = _make_parsed()
        result = board_handler(parsed, conn, {"sender_id": "U001"})

        header = result.splitlines()[0]
        assert "📊" in header
        assert "mine" in header
        assert "open" in header

    def test_section_counts(self, conn):
        """Section headers show task counts."""
        _seed_task(conn, title="t1", section="backlog")
        _seed_task(conn, title="t2", section="backlog")
        _seed_task(conn, title="t3", section="doing")

        parsed = _make_parsed()
        result = board_handler(parsed, conn, {"sender_id": "U001"})

        lines = result.splitlines()
        backlog_line = next(line for line in lines if "BACKLOG" in line)
        doing_line = next(line for line in lines if "DOING" in line)
        assert "(2)" in backlog_line
        assert "(1)" in doing_line


class TestBoardLimitPerSection:
    """limitPerSection caps items per section."""

    def test_limit_caps_items(self, conn):
        for i in range(5):
            _seed_task(conn, title=f"task {i}", section="backlog")

        parsed = _make_parsed(title_tokens=["limitPerSection:2"])
        result = board_handler(parsed, conn, {"sender_id": "U001"})

        lines = result.splitlines()
        backlog_idx = next(i for i, line in enumerate(lines) if "BACKLOG" in line)
        doing_idx = next(i for i, line in enumerate(lines) if "DOING" in line)

        backlog_lines = [ln for ln in lines[backlog_idx + 1 : doing_idx] if ln.strip().startswith("#")]
        assert len(backlog_lines) == 2

    def test_overflow_message(self, conn):
        for i in range(5):
            _seed_task(conn, title=f"task {i}", section="backlog")

        parsed = _make_parsed(title_tokens=["limitPerSection:2"])
        result = board_handler(parsed, conn, {"sender_id": "U001"})

        assert "... and 3 more" in result

    def test_invalid_limit(self, conn):
        parsed = _make_parsed(title_tokens=["limitPerSection:abc"])
        result = board_handler(parsed, conn, {"sender_id": "U001"})
        assert "❌" in result

    def test_zero_limit(self, conn):
        parsed = _make_parsed(title_tokens=["limitPerSection:0"])
        result = board_handler(parsed, conn, {"sender_id": "U001"})
        assert "❌" in result


class TestBoardScopeFilter:
    """Scope/project filters work like list command."""

    def test_mine_scope_default(self, conn):
        _seed_task(conn, title="my task", created_by="U001", assignees=["U001"])
        _seed_task(conn, title="other task", created_by="U002", assignees=["U002"])

        parsed = _make_parsed()
        result = board_handler(parsed, conn, {"sender_id": "U001"})

        assert "my task" in result
        assert "other task" not in result

    def test_all_scope(self, conn):
        _seed_task(conn, title="my task", created_by="U001", assignees=["U001"])
        _seed_task(conn, title="other task", created_by="U002", assignees=["U002"])

        parsed = _make_parsed(title_tokens=["all"])
        result = board_handler(parsed, conn, {"sender_id": "U001"})

        assert "my task" in result
        assert "other task" in result

    def test_project_filter(self, conn):
        _seed_task(conn, title="inbox task", project_name="Inbox")
        _seed_task(conn, title="proj task", project_name="Backend", visibility="shared")

        parsed = _make_parsed(title_tokens=["all"], project="Backend")
        result = board_handler(parsed, conn, {"sender_id": "U001"})

        assert "proj task" in result
        assert "inbox task" not in result

    def test_project_header(self, conn):
        _seed_task(conn, title="t1", project_name="Backend", visibility="shared")
        parsed = _make_parsed(title_tokens=["all"], project="Backend")
        result = board_handler(parsed, conn, {"sender_id": "U001"})

        header = result.splitlines()[0]
        assert "/p Backend" in header

    def test_private_project_hidden_from_others(self, conn):
        _seed_task(
            conn,
            title="private task",
            project_name="Secret",
            visibility="private",
            owner="UOWNER",
            created_by="UOWNER",
            assignees=["UOWNER"],
        )
        parsed = _make_parsed(title_tokens=["all"])
        result = board_handler(parsed, conn, {"sender_id": "UOTHER"})

        assert "private task" not in result


class TestBoardTaskLineFormat:
    """Each task line includes id, due, assignees, title."""

    def test_task_line_format(self, conn):
        task_id = _seed_task(conn, title="Deploy hotfix", due="2026-03-01")
        parsed = _make_parsed()
        result = board_handler(parsed, conn, {"sender_id": "U001"})

        assert f"#{task_id}" in result
        assert "due:2026-03-01" in result
        assert "<@U001>" in result
        assert "Deploy hotfix" in result

    def test_task_line_no_due(self, conn):
        _seed_task(conn, title="No due task")
        parsed = _make_parsed()
        result = board_handler(parsed, conn, {"sender_id": "U001"})

        assert "due:-" in result


class TestBoardStatusToken:
    """Status filter via title_tokens: open, done, drop."""

    def test_board_done_token(self, conn):
        _seed_task(conn, title="open task", section="doing")
        # Manually insert a done task
        inbox_id = conn.execute("SELECT id FROM projects WHERE name = 'Inbox'").fetchone()[0]
        conn.execute(
            "INSERT INTO tasks (title, project_id, section, status, created_by) "
            "VALUES ('finished task', ?, 'done', 'done', 'U001');",
            (inbox_id,),
        )
        task_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("INSERT INTO task_assignees (task_id, assignee_user_id) VALUES (?, 'U001');", (task_id,))
        conn.commit()

        parsed = _make_parsed(title_tokens=["done"])
        result = board_handler(parsed, conn, {"sender_id": "U001"})

        assert "finished task" in result
        assert "open task" not in result
        assert "/ done)" in result  # header shows status=done

    def test_board_drop_token(self, conn):
        _seed_task(conn, title="open task", section="doing")
        inbox_id = conn.execute("SELECT id FROM projects WHERE name = 'Inbox'").fetchone()[0]
        conn.execute(
            "INSERT INTO tasks (title, project_id, section, status, created_by) "
            "VALUES ('cancelled task', ?, 'drop', 'dropped', 'U001');",
            (inbox_id,),
        )
        task_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("INSERT INTO task_assignees (task_id, assignee_user_id) VALUES (?, 'U001');", (task_id,))
        conn.commit()

        parsed = _make_parsed(title_tokens=["drop"])
        result = board_handler(parsed, conn, {"sender_id": "U001"})

        assert "cancelled task" in result
        assert "open task" not in result
        assert "/ dropped)" in result

    def test_board_open_token_explicit(self, conn):
        _seed_task(conn, title="active task", section="doing")
        parsed = _make_parsed(title_tokens=["open"])
        result = board_handler(parsed, conn, {"sender_id": "U001"})

        assert "active task" in result
        assert "/ open)" in result


class TestBoardEmpty:
    """Board with no matching tasks shows all sections as empty."""

    def test_all_sections_empty(self, conn):
        parsed = _make_parsed()
        result = board_handler(parsed, conn, {"sender_id": "U001"})

        assert result.count("(empty)") == 5


class TestBoardAmbiguousProjectDisambiguation:
    """Visibility qualifier resolves ambiguous project names in board."""

    def _seed_ambiguous(self, conn):
        conn.execute("INSERT INTO projects (name, visibility, owner_user_id) VALUES ('Work', 'shared', NULL);")
        conn.execute("INSERT INTO projects (name, visibility, owner_user_id) VALUES ('Work', 'private', 'U001');")
        shared_id = conn.execute(
            "SELECT id FROM projects WHERE name = 'Work' AND visibility = 'shared'"
        ).fetchone()[0]
        private_id = conn.execute(
            "SELECT id FROM projects WHERE name = 'Work' AND visibility = 'private'"
        ).fetchone()[0]
        _seed_task(conn, title="Shared task", project_name="Inbox")  # dummy, we'll insert directly
        # Insert tasks directly to target exact project ids
        conn.execute(
            "INSERT INTO tasks (title, project_id, section, status, created_by) "
            "VALUES ('Shared board task', ?, 'backlog', 'open', 'U001');",
            (shared_id,),
        )
        tid1 = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("INSERT INTO task_assignees (task_id, assignee_user_id) VALUES (?, 'U001');", (tid1,))
        conn.execute(
            "INSERT INTO tasks (title, project_id, section, status, created_by) "
            "VALUES ('Private board task', ?, 'doing', 'open', 'U001');",
            (private_id,),
        )
        tid2 = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("INSERT INTO task_assignees (task_id, assignee_user_id) VALUES (?, 'U001');", (tid2,))
        conn.commit()

    def test_ambiguous_without_qualifier(self, conn):
        self._seed_ambiguous(conn)
        parsed = _make_parsed(project="Work")
        result = board_handler(parsed, conn, {"sender_id": "U001"})
        assert "Ambiguous" in result

    def test_disambiguate_shared(self, conn):
        self._seed_ambiguous(conn)
        parsed = _make_parsed(project="Work", project_visibility="shared")
        result = board_handler(parsed, conn, {"sender_id": "U001"})
        assert "Shared board task" in result
        assert "Private board task" not in result

    def test_disambiguate_private(self, conn):
        self._seed_ambiguous(conn)
        parsed = _make_parsed(project="Work", project_visibility="private")
        result = board_handler(parsed, conn, {"sender_id": "U001"})
        assert "Private board task" in result
        assert "Shared board task" not in result
