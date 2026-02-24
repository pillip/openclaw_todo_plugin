# PR #61 Review Notes -- ISSUE-034: Move section shorthand

> Reviewer: Claude Opus 4.6 (automated review)
> Date: 2026-02-24
> Branch: (move section shorthand)

---

## Code Review

### Summary

PR #61 adds shorthand syntax support for the `move` command, allowing users to write `todo: move <id> doing` instead of requiring the `/s` flag (`todo: move <id> /s doing`). The implementation is minimal and well-scoped: 4 lines of logic in `cmd_move.py` and 5 new test cases in `test_cmd_move.py`.

### Correctness

**Overall: Good.** The implementation is correct and handles the key scenarios properly.

| Aspect | Status | Notes |
|--------|--------|-------|
| Shorthand resolves valid sections | PASS | `title_tokens[0]` checked against `VALID_SECTIONS` |
| Case insensitive matching | PASS | `.lower()` applied before lookup |
| `/s` flag takes priority over shorthand | PASS | `parsed.section` checked first (line 34) |
| Invalid shorthand token falls through to error | PASS | Returns "section required" error |
| All 18 tests pass | PASS | Verified locally |

### Findings

#### [Info] Shorthand only reads the first title_token

The shorthand logic at lines 35-38 of `cmd_move.py` only inspects `title_tokens[0]`. If additional tokens follow (e.g., `todo: move 5 doing extra stuff`), they are silently ignored. This is acceptable behavior for a move command since it only needs one target section, but worth noting -- the extra tokens are simply discarded without warning.

**Verdict:** Acceptable as-is. No action needed.

#### [Info] Lowercased shorthand stored directly

When the shorthand path is taken, `token.lower()` is stored as `target_section` (line 38). This means the DB always receives a lowercase section name, which is consistent with how the `/s` flag path works in the parser (parser.py line 102). Good consistency.

#### [Info] Error message updated

Line 40 changed the error message from referencing `/s <section>` to just `<section>`, which matches the new shorthand UX. Good attention to detail.

### Test Coverage

The 5 new tests in `TestMoveSectionShorthand` cover the essential scenarios:

| Test | What it validates |
|------|-------------------|
| `test_move_shorthand_doing` | Happy path with DB verification |
| `test_move_shorthand_waiting` | Second valid section name |
| `test_move_shorthand_case_insensitive` | Uppercase "DOING" maps to "doing" |
| `test_move_slash_s_takes_priority_over_shorthand` | `/s` flag wins when both present |
| `test_move_shorthand_invalid_token_errors` | Non-section word returns error |

**Missing but low priority:**
- No test for shorthand with `title_tokens=["done"]` or `title_tokens=["drop"]` -- but the set-membership check is generic so these are implicitly covered.
- No integration test verifying the full parse-to-handler path (e.g., `parse("move 5 doing")` fed into `move_handler`). The unit tests construct `ParsedCommand` manually via `_make_parsed`, so the parser's `title_tokens` extraction for the move command is not exercised end-to-end in this test file. Consider adding a small integration test in a follow-up.

### Maintainability

- The `_make_parsed` helper was cleanly extended with the `title_tokens` parameter (default `None` mapped to `[]`), maintaining backward compatibility with existing tests.
- The shorthand logic is 4 lines with clear intent. No unnecessary complexity.

---

## Security Findings

### Critical / High

None.

### Medium

None.

### Low

#### [Low] S-01: No additional input validation concerns

The shorthand token is validated against `VALID_SECTIONS` (a `frozenset` of known-good values) before being used in a parameterized SQL query. There is no injection risk. The existing parameterized query pattern (`?` placeholders) at lines 43-46 and 60-63 of `cmd_move.py` properly prevents SQL injection regardless of input.

**Verdict:** No action required.

### Summary

| Severity | Count | Details |
|----------|-------|---------|
| Critical | 0 | -- |
| High | 0 | -- |
| Medium | 0 | -- |
| Low | 0 | S-01 is informational only (no actual vulnerability) |

The PR introduces no new security concerns. All user input flows through either set-membership validation (`VALID_SECTIONS`) or parameterized SQL queries. No hardcoded secrets, no auth bypasses, no XSS vectors, and no new dependencies.

---

## Follow-up Issues (Proposed)

1. **Integration test for shorthand parse path**: Add a test that feeds raw text through `parse("move 5 doing")` and verifies `title_tokens` contains `["doing"]` after the arg extraction, then passes the result to `move_handler`. This would close the gap between the parser and handler unit tests.

2. **Warn on extra tokens**: Consider logging a debug-level warning when `title_tokens` has more than one element in the move command, so users get feedback if they accidentally type extra words.
