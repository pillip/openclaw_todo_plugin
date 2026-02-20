"""Tests for the command parser."""

import pytest

from openclaw_todo.parser import DUE_CLEAR, ParseError, ParsedCommand, parse


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
    from datetime import date

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
