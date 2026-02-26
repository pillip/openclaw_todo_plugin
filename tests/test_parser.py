"""Tests for the command parser."""

from datetime import date

import pytest

from openclaw_todo.parser import DUE_CLEAR, ParseError, parse


def test_extract_project():
    """/p MyProject should be extracted and token consumed."""
    result = parse("add Buy milk /p MyProject")
    assert result.project == "MyProject"
    assert result.command == "add"
    assert "Buy" in result.title_tokens
    assert "/p" not in result.title_tokens
    assert "MyProject" not in result.title_tokens


def test_extract_section_valid():
    """/s doing should be validated and extracted."""
    result = parse("add Task /s doing")
    assert result.section == "doing"


def test_extract_section_invalid():
    """Invalid section should raise ParseError."""
    with pytest.raises(ParseError, match="Invalid section"):
        parse("add Task /s invalid_section")


def test_due_mm_dd_normalisation():
    """due:03-15 should be normalised to current-year YYYY-MM-DD."""
    result = parse("add Task due:03-15")
    expected = f"{date.today().year}-03-15"
    assert result.due == expected


def test_due_full_date():
    """due:2026-06-01 should be kept as-is."""
    result = parse("add Task due:2026-06-01")
    assert result.due == "2026-06-01"


def test_due_invalid_date():
    """due:2026-02-30 should raise ParseError."""
    with pytest.raises(ParseError, match="Invalid due date"):
        parse("add Task due:2026-02-30")


def test_due_clear():
    """due:- should set the clear sentinel."""
    result = parse("add Task due:-")
    assert result.due == DUE_CLEAR


def test_mentions_extraction():
    """<@U12345> patterns should be extracted into mentions."""
    result = parse("add Task <@U12345> <@UABCDE>")
    assert result.mentions == ["U12345", "UABCDE"]
    assert "<@U12345>" not in result.title_tokens


def test_title_extraction():
    """Non-option, non-mention tokens should become title_tokens."""
    result = parse("add Buy groceries and cook dinner /p Home due:2026-03-01")
    assert result.title_tokens == ["Buy", "groceries", "and", "cook", "dinner"]
    assert result.project == "Home"
    assert result.due == "2026-03-01"


def test_command_extraction():
    """The first token should be the command."""
    result = parse("list mine /p Work")
    assert result.command == "list"
    assert "mine" in result.title_tokens


def test_move_extracts_id_as_arg():
    """move command should extract task id as first arg."""
    result = parse("move 42 /s doing")
    assert result.command == "move"
    assert result.args == ["42"]
    assert result.section == "doing"


def test_empty_command_raises():
    """Empty text after /todo should raise ParseError."""
    with pytest.raises(ParseError, match="Empty command"):
        parse("")


def test_section_case_insensitive():
    """/s DOING should be normalised to lowercase."""
    result = parse("add Task /s DOING")
    assert result.section == "doing"


# --- Issue #18: Comprehensive edge-case tests ---


class TestOptionsInAnyOrder:
    """Options (/p, /s, due:, mentions) can appear in any position."""

    def test_options_before_title(self):
        """Options placed before the title tokens are extracted correctly."""
        result = parse("add /p Work /s doing due:2026-05-01 Finish report")
        assert result.project == "Work"
        assert result.section == "doing"
        assert result.due == "2026-05-01"
        assert result.title_tokens == ["Finish", "report"]

    def test_options_interspersed(self):
        """Options interspersed between title tokens are all extracted."""
        result = parse("add Buy /p Home groceries /s backlog due:2026-06-01")
        assert result.project == "Home"
        assert result.section == "backlog"
        assert result.due == "2026-06-01"
        assert result.title_tokens == ["Buy", "groceries"]

    def test_all_options_at_end(self):
        """All options after the title tokens."""
        result = parse("add Deploy server <@UADMIN> /p Infra /s doing due:2026-07-15")
        assert result.project == "Infra"
        assert result.section == "doing"
        assert result.due == "2026-07-15"
        assert result.mentions == ["UADMIN"]
        assert result.title_tokens == ["Deploy", "server"]

    def test_duplicate_option_last_wins(self):
        """If the same option appears twice, the last value wins."""
        result = parse("add Task /p Alpha /p Beta")
        assert result.project == "Beta"

    def test_duplicate_section_last_wins(self):
        """If /s appears twice, the last value wins."""
        result = parse("add Task /s backlog /s doing")
        assert result.section == "doing"


class TestDueYearBoundary:
    """Due date edge cases around year boundaries and leap years."""

    def test_due_feb_29_leap_year(self):
        """due:02-29 should succeed if current year is a leap year (or use full date)."""
        # Use full date format to guarantee a leap year
        result = parse("add Task due:2028-02-29")
        assert result.due == "2028-02-29"

    def test_due_dec_31(self):
        """due:12-31 should normalise to current year Dec 31."""
        from datetime import date

        result = parse("add Task due:12-31")
        assert result.due == f"{date.today().year}-12-31"

    def test_due_jan_01(self):
        """due:01-01 should normalise to current year Jan 1."""
        from datetime import date

        result = parse("add Task due:1-1")
        assert result.due == f"{date.today().year}-01-01"

    def test_due_mm_dd_invalid_month(self):
        """due:13-01 (invalid month) should raise ParseError."""
        with pytest.raises(ParseError, match="Invalid due date"):
            parse("add Task due:13-01")

    def test_due_mm_dd_invalid_day(self):
        """due:02-30 (Feb 30) in MM-DD format should raise ParseError."""
        with pytest.raises(ParseError, match="Invalid due date"):
            parse("add Task due:2-30")

    def test_due_feb_29_non_leap_year(self):
        """due:02-29 on a non-leap year (2026) should raise ParseError."""
        with pytest.raises(ParseError, match="Invalid due date"):
            parse("add Task due:2026-02-29")

    def test_due_month_zero(self):
        """due:00-01 (month 0) should raise ParseError."""
        with pytest.raises(ParseError, match="Invalid due date"):
            parse("add Task due:00-01")

    def test_due_day_32(self):
        """due:12-32 (day 32) should raise ParseError."""
        with pytest.raises(ParseError, match="Invalid due date"):
            parse("add Task due:12-32")

    def test_due_garbage_string(self):
        """due:notadate should raise ParseError."""
        with pytest.raises(ParseError, match="Invalid due date"):
            parse("add Task due:notadate")


class TestEmptyTitleNoCrash:
    """Commands with no title tokens should not crash."""

    def test_add_bare_command(self):
        """parse("add") with no arguments at all produces empty title_tokens."""
        result = parse("add")
        assert result.command == "add"
        assert result.title_tokens == []
        assert result.args == []

    def test_add_no_title_only_options(self):
        """add with only options and no title tokens produces empty title_tokens."""
        result = parse("add /p Work /s doing")
        assert result.command == "add"
        assert result.title_tokens == []
        assert result.project == "Work"

    def test_list_no_extra_tokens(self):
        """list with no arguments produces empty title_tokens."""
        result = parse("list")
        assert result.command == "list"
        assert result.title_tokens == []

    def test_move_only_id(self):
        """move with only an ID and no other tokens."""
        result = parse("move 5")
        assert result.command == "move"
        assert result.args == ["5"]
        assert result.title_tokens == []

    def test_whitespace_only_raises(self):
        """Whitespace-only input should raise ParseError."""
        with pytest.raises(ParseError, match="Empty command"):
            parse("   ")


class TestUnicodeTitle:
    """Unicode characters in titles should be preserved."""

    def test_korean_title(self):
        """Korean text in title should be preserved."""
        result = parse("add 우유 사기 /p 집")
        assert result.title_tokens == ["우유", "사기"]
        assert result.project == "집"

    def test_emoji_in_title(self):
        """Emoji characters in title should be preserved."""
        result = parse("add Fix bug 🐛 /s doing")
        assert "🐛" in result.title_tokens
        assert result.section == "doing"

    def test_mixed_unicode_and_ascii(self):
        """Mixed unicode and ASCII in the same command."""
        result = parse("add 日本語タスク due:2026-04-01 <@UJAPAN>")
        assert result.title_tokens == ["日本語タスク"]
        assert result.due == "2026-04-01"
        assert result.mentions == ["UJAPAN"]


class TestExtraWhitespace:
    """Extra whitespace should be handled gracefully."""

    def test_leading_trailing_whitespace(self):
        """Leading and trailing whitespace stripped."""
        result = parse("  add  Task  ")
        assert result.command == "add"
        assert result.title_tokens == ["Task"]

    def test_multiple_spaces_between_tokens(self):
        """Multiple spaces between tokens treated as single separator."""
        result = parse("add   Buy   milk   /p   Home")
        assert result.title_tokens == ["Buy", "milk"]
        assert result.project == "Home"

    def test_tabs_in_input(self):
        """Tab characters should be treated as whitespace separators."""
        result = parse("add\tTask\t/s\tdoing")
        assert result.command == "add"
        assert result.title_tokens == ["Task"]
        assert result.section == "doing"


class TestMixedMentionsAndOptions:
    """Mentions and options can appear together in any order."""

    def test_mentions_between_options(self):
        """Mentions between /p and /s should be extracted correctly."""
        result = parse("add Task /p Work <@UALICE> /s doing <@UBOB>")
        assert result.project == "Work"
        assert result.section == "doing"
        assert set(result.mentions) == {"UALICE", "UBOB"}
        assert result.title_tokens == ["Task"]

    def test_mentions_with_due(self):
        """Mentions combined with due date."""
        result = parse("add Review PR <@UDEV1> <@UDEV2> due:2026-03-20")
        assert result.mentions == ["UDEV1", "UDEV2"]
        assert result.due == "2026-03-20"
        assert result.title_tokens == ["Review", "PR"]

    def test_all_options_and_multiple_mentions(self):
        """All option types plus multiple mentions in a single command."""
        result = parse("add Deploy <@UA> <@UB> /p Infra /s doing due:2026-08-01")
        assert result.project == "Infra"
        assert result.section == "doing"
        assert result.due == "2026-08-01"
        assert result.mentions == ["UA", "UB"]
        assert result.title_tokens == ["Deploy"]


class TestMissingOptionArguments:
    """Missing arguments for /p and /s should raise ParseError."""

    def test_p_at_end_without_value(self):
        """/p at end of input without a project name raises ParseError."""
        with pytest.raises(ParseError, match="/p requires a project name"):
            parse("add Task /p")

    def test_s_at_end_without_value(self):
        """/s at end of input without a section name raises ParseError."""
        with pytest.raises(ParseError, match="/s requires a section name"):
            parse("add Task /s")


class TestIdExtractionCommands:
    """Commands that extract an ID as the first arg: move, done, drop, edit."""

    def test_done_extracts_id(self):
        """done command extracts task ID as first arg."""
        result = parse("done 99")
        assert result.command == "done"
        assert result.args == ["99"]

    def test_drop_extracts_id(self):
        """drop command extracts task ID as first arg."""
        result = parse("drop 7")
        assert result.command == "drop"
        assert result.args == ["7"]

    def test_edit_extracts_id_with_title_tokens(self):
        """edit command extracts ID and preserves remaining title tokens."""
        result = parse("edit 3 New title text /s doing")
        assert result.command == "edit"
        assert result.args == ["3"]
        assert result.title_tokens == ["New", "title", "text"]
        assert result.section == "doing"

    def test_add_does_not_extract_id(self):
        """add command does NOT extract first token as ID."""
        result = parse("add 42 is the answer")
        assert result.command == "add"
        assert result.args == []
        assert result.title_tokens == ["42", "is", "the", "answer"]


class TestCommandCaseInsensitive:
    """Command names should be case-insensitive."""

    def test_uppercase_command(self):
        """ADD should be normalised to add."""
        result = parse("ADD Task")
        assert result.command == "add"

    def test_mixed_case_command(self):
        """LiSt should be normalised to list."""
        result = parse("LiSt")
        assert result.command == "list"


class TestAllSections:
    """All valid sections should be accepted."""

    @pytest.mark.parametrize("section", ["backlog", "doing", "waiting", "done", "drop"])
    def test_valid_section(self, section):
        """Each valid section name is accepted."""
        result = parse(f"add Task /s {section}")
        assert result.section == section
