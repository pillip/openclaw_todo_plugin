# Review Notes -- PR #47: Change command prefix from /todo to !todo

**Reviewer**: Claude Opus 4.6
**Date**: 2026-02-21
**PR**: https://github.com/pillip/openclaw_todo_plugin/pull/47

---

## Code Review

### Summary

PR #47 changes the user-facing command prefix from `/todo` to `!todo` because
Slack intercepts `/slash` commands. The change touches the prefix constant,
dispatcher usage strings, bridge trigger pattern, and test files.

### Findings

#### 1. Missed user-facing error strings in 6 command handlers (Fixed)

The PR updated the prefix in `plugin.py`, `dispatcher.py`, and all test files,
but **missed the `Usage:` error strings** returned to users in the following
source files:

| File | Line | Old string |
|------|------|------------|
| `src/openclaw_todo/cmd_add.py` | 26 | `Usage: /todo add <title> [options]` |
| `src/openclaw_todo/cmd_move.py` | 26 | `Usage: /todo move <id> /s <section>` |
| `src/openclaw_todo/cmd_move.py` | 36 | `Usage: /todo move <id> /s <section>` |
| `src/openclaw_todo/cmd_done_drop.py` | 32 | `Usage: /todo {action} <id>` |
| `src/openclaw_todo/cmd_edit.py` | 22 | `Usage: /todo edit <id> [title] [options]` |
| `src/openclaw_todo/cmd_project_set_private.py` | 30 | `Usage: /todo project set-private <name>` |
| `src/openclaw_todo/cmd_project_set_shared.py` | 27 | `Usage: /todo project set-shared <name>` |

**Status**: Fixed in this review. All `/todo` in user-facing error messages
under `src/` have been updated to `!todo`. Tests pass (253/253).

#### 2. Remaining `/todo` references in docstrings and comments (Follow-up)

The following files still contain `/todo` in docstrings, comments, or log
messages. These are not user-facing but should be updated for consistency:

- `src/openclaw_todo/plugin.py` -- docstring (line 17) and log message (line 26)
- `src/openclaw_todo/dispatcher.py` -- docstrings (lines 80, 108, 117)
- `src/openclaw_todo/parser.py` -- docstrings (lines 1, 27, 68)
- `src/openclaw_todo/cmd_add.py` -- module docstring (line 1)
- `src/openclaw_todo/cmd_move.py` -- module docstring (line 1)
- `src/openclaw_todo/cmd_done_drop.py` -- module docstring (line 1)
- `src/openclaw_todo/cmd_edit.py` -- module docstring (line 1)
- `src/openclaw_todo/cmd_board.py` -- module docstring (line 1)
- `src/openclaw_todo/cmd_list.py` -- module docstring (line 1)
- `src/openclaw_todo/cmd_project_list.py` -- module docstring (line 1)
- `src/openclaw_todo/cmd_project_set_private.py` -- module docstring (line 1)
- `src/openclaw_todo/cmd_project_set_shared.py` -- module docstring (line 1)
- `bridge/openclaw-todo/index.ts` -- file header comment (line 2)
- Various test file docstrings in `tests/test_dispatcher.py`, `tests/test_cmd_*.py`

**Recommendation**: Create a follow-up issue to do a bulk docstring/comment
sweep replacing `/todo` with `!todo` across all source and test files.

#### 3. Remaining `/todo` references in documentation (Follow-up)

- `README.md` -- usage examples and command table (lines 7, 46, 63-76)
- `docs/README.md` -- architecture description and command table (lines 23, 54-63)
- `openclaw_todo_plugin_prd.md` -- many references throughout

**Recommendation**: Create a follow-up issue to update documentation. The PRD
may intentionally keep the original notation, but README files should reflect
the actual prefix.

#### 4. Code quality of the PR changes

The actual changes in the PR are clean and consistent:
- `_TODO_PREFIX` constant correctly updated in `plugin.py`
- `USAGE` and `PROJECT_USAGE` strings correctly updated in `dispatcher.py`
- Bridge trigger regex `^!todo(\s|$)` correctly updated in `openclaw.plugin.json`
- All test files consistently updated

### Test Results

```
253 passed in 5.89s
```

---

## Security Findings

### Low

#### L1: No injection risk from `!` prefix

The `!` character has no special meaning in SQL, Python string formatting, or
the regex-based trigger pattern. The prefix matching in `plugin.py` uses strict
equality/startswith checks (line 23), not regex, so there is no injection vector.

The bridge trigger regex `^!todo(\s|$)` correctly anchors the pattern with `^`
and bounds the match with `(\s|$)`, preventing partial matches.

#### L2: No new security concerns introduced

This PR is a pure string constant change. No new inputs, endpoints, or
dependencies are added. The existing input validation and parameterized SQL
queries remain unchanged.

---

## Actions Taken

1. Fixed 6 user-facing error messages in command handlers (see Finding 1)
2. Verified all 253 tests pass after fixes

## Proposed Follow-up Issues

1. **Docstring/comment sweep**: Update all remaining `/todo` references in
   source code docstrings, comments, and log messages to `!todo`
2. **Documentation update**: Update `README.md` and `docs/README.md` to
   reflect the `!todo` prefix
