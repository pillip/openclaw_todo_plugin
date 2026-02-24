# Review Notes -- PR #57: Help Command

**Branch**: `issue/ISSUE-031-help-command`
**Reviewer**: Claude Opus 4.6 (automated)
**Date**: 2026-02-24

---

## Code Review

### Summary

This PR adds a detailed `help` command (`todo: help`) and changes the empty
`todo:` response from a short USAGE string to the same detailed HELP_TEXT.
The short USAGE string is retained for unknown-command error messages.

### Correctness

1. **`help` returns before `_init_db()` -- correct.**
   In `dispatcher.py` lines 128-129, the `help` branch returns `HELP_TEXT`
   immediately after validating that the command is in `_VALID_COMMANDS` but
   before the `_init_db()` call on line 133. This is correct and intentional:
   help is a read-only, stateless operation that needs no database. The test
   `test_help_does_not_open_db` (passing `db_path=None`) confirms this.

2. **HELP_TEXT matches the UX spec.**
   The content in `HELP_TEXT` (dispatcher.py lines 29-60) is an exact match
   with section 7.2 of `docs/ux_spec.md` (lines 615-646). All commands are
   documented with accurate syntax.

3. **Empty `todo:` now returns HELP_TEXT -- correct.**
   In `plugin.py` line 31, when `remainder` is empty after stripping the
   prefix, `HELP_TEXT` is returned. This matches the UX spec section 7.2
   which states: "`todo: help` also displays the same help."

4. **USAGE kept for unknown-command errors -- good separation.**
   The short `USAGE` string (line 63) is used only in the unknown-command
   branch (line 126). This keeps error messages concise while providing full
   detail via `help`.

5. **`"help"` added to `_VALID_COMMANDS` -- correct.**
   Without this, `help` would fall through to the "Unknown command" branch.

### Edge Cases

- `todo: help` with extra tokens (e.g., `todo: help add`): The parser will
  produce `ParsedCommand(command="help", title_tokens=["add"])`. The
  dispatcher checks `command == "help"` and returns HELP_TEXT regardless of
  extra tokens. This is acceptable behavior -- no per-command help exists yet,
  and extra tokens are harmlessly ignored.

### Maintainability

- `HELP_TEXT` is a single constant in `dispatcher.py`, imported by both
  `plugin.py` (for empty input) and used directly by `dispatch()` (for the
  `help` command). Single source of truth -- good.
- The `USAGE` string on line 63 now includes `help` in its command list,
  which is consistent.

### Test Coverage

Tests are adequate:

| Test File | Test | What It Verifies |
|---|---|---|
| `test_dispatcher.py` | `test_help_returns_detailed_help` | All major commands appear in help output |
| `test_dispatcher.py` | `test_help_does_not_open_db` | `db_path=None` works (no DB access) |
| `test_plugin.py` | `test_todo_without_subcommand` | Empty `todo:` returns HELP_TEXT |
| `test_plugin.py` | `test_todo_help_command` | `todo: help` returns HELP_TEXT |
| `test_server.py` | `test_todo_usage` | Server endpoint returns HELP_TEXT for bare `todo:` |

**Minor suggestion (not blocking)**: Could add a test asserting that
`handle_message("todo: help", ctx)` and `handle_message("todo:", ctx)`
return the exact same string (identity check), to enforce the spec
requirement that both produce identical output.

### Complexity / Duplication

No concerns. The change is minimal and well-structured.

---

## Security Findings

### Critical

None.

### High

None.

### Medium

None.

### Low

1. **[Low] User input reflected in error messages without sanitization.**
   File: `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/dispatcher.py`, line 126.
   ```python
   return f"Unknown command: '{command}'\n{USAGE}"
   ```
   The `command` value originates from user input (`tokens[0].lower()` in
   `parser.py` line 76). While this is a CLI/DM context (not HTML), if the
   response is ever rendered in a web UI without escaping, this could become
   an XSS vector. The same pattern exists on line 157 for project
   subcommands. **Risk is low** because: (a) output goes to Slack which
   handles its own escaping, and (b) the value is `.lower()`-ed so no angle
   brackets survive. No fix needed now, but worth noting for any future
   web-based rendering.

2. **[Low] `register_handler` is publicly exported with no validation.**
   File: `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/dispatcher.py`, line 106.
   The function accepts any string as a command name and any callable as a
   handler. This is an internal API used only in tests, but if exposed to
   plugin authors, it could allow overriding core commands. **No fix needed**
   for current scope.

### Informational

- The `HELP_TEXT` does not document the `help` command itself (no
  `todo: help` entry in the help output). This is consistent with the UX
  spec and is a common UX pattern -- users discover `help` from the USAGE
  hint in error messages or from the empty-input response.

---

## Verdict

**Approve.** The implementation is correct, matches the UX spec, has adequate
test coverage, and introduces no security issues. No fixes required.
