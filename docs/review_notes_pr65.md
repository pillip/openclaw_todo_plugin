# Review Notes -- PR #65: Parser Edge Case Tests

**Reviewer:** Claude Opus 4.6 (automated)
**Date:** 2026-02-26
**Scope:** `tests/test_parser.py` -- 4 new test methods, no production code changes

---

## Code Review

### Summary

PR #65 adds four new test methods to existing test classes in `tests/test_parser.py`:

| Test | Class | Purpose |
|------|-------|---------|
| `test_due_feb_29_non_leap_year` | `TestDueYearBoundary` | Validates `due:2026-02-29` raises `ParseError` |
| `test_due_month_zero` | `TestDueYearBoundary` | Validates `due:00-01` raises `ParseError` |
| `test_due_day_32` | `TestDueYearBoundary` | Validates `due:12-32` raises `ParseError` |
| `test_add_bare_command` | `TestEmptyTitleNoCrash` | Validates `parse("add")` returns empty tokens/args |

All 54 parser tests pass (0.02s). No flakiness concerns.

### Positive Observations

- Tests are well-named and follow existing conventions.
- Each test has a clear, accurate docstring.
- Proper use of `pytest.raises` with `match` parameter for specificity.
- Tests are deterministic -- no time-sensitivity or external dependencies.
- Placement in existing classes is logical and maintains good organization.

### Issues Found

**[Low] `test_due_feb_29_non_leap_year` only covers the YYYY-MM-DD code path**

The test uses `due:2026-02-29`, which is parsed via the `datetime.strptime(raw, "%Y-%m-%d")` path in `_normalise_due()`. However, the MM-DD path (`due:02-29`) uses a different code branch: `date(date.today().year, month, day)`. Since 2026 is not a leap year, `due:02-29` should also raise `ParseError`, but this is not tested.

This is notable because the parser comment on line 54-55 of `parser.py` explicitly explains the MM-DD path was designed to handle Feb 29 differently from strptime. A dedicated test for the MM-DD variant would confirm both branches reject Feb 29 in non-leap years.

Suggested addition:
```python
def test_due_feb_29_mm_dd_non_leap_year(self):
    """due:02-29 in MM-DD format should also raise ParseError in a non-leap year."""
    # This test is only meaningful when date.today().year is not a leap year.
    # 2026 is not a leap year, so this test is valid through 2026.
    from datetime import date
    year = date.today().year
    if year % 4 != 0 or (year % 100 == 0 and year % 400 != 0):
        with pytest.raises(ParseError, match="Invalid due date"):
            parse("add Task due:02-29")
    else:
        pytest.skip("Current year is a leap year; MM-DD path accepts Feb 29")
```

Note: this test would become flaky in leap years (2028, 2032, etc.) -- the `pytest.skip` guard handles that, but a simpler approach is to test it as part of the full-date path only. This is a judgment call for the team.

**[Low] Redundant import of `date` on lines 3 and 152/159**

Lines 152 and 159 have `from datetime import date` inside test methods, but `date` is already imported at the module level on line 3. These local imports are harmless but unnecessary.

### Missing Edge Cases (suggestions for follow-up)

- `due:00-00` -- both month and day are zero
- `due:2026-00-01` -- zero month in YYYY-MM-DD format
- `due:` (empty value after colon) -- currently would hit `_normalise_due("")`
- Negative numbers: `due:-1-15` or `due:2026--1-01`

These are not blocking for this PR but would further harden the parser.

---

## Security Findings

### Assessment: No security issues found

This PR is test-only and does not modify production code. The tests contain:

- No hardcoded secrets, API keys, or credentials
- No filesystem, network, or subprocess calls
- No dynamic code execution (eval, exec, pickle)
- No user-controlled input passed to sensitive sinks
- No changes to authentication, authorization, or access control logic
- No new dependencies introduced

**Severity: N/A** -- clean from a security perspective.

---

## Verdict

**Approve with minor suggestions.** The four tests are correct, well-structured, and improve coverage of parser edge cases. The two low-severity observations (MM-DD path gap and redundant imports) are non-blocking and can be addressed in a follow-up.

### Follow-up Issues

1. Add `due:02-29` MM-DD path test for non-leap year coverage (pairs with `test_due_feb_29_non_leap_year`)
2. Remove redundant `from datetime import date` imports on lines 152 and 159
3. Consider adding edge cases for empty due value (`due:`) and zero-date combinations
