# PR #55 Review Notes -- Status Filter Token (`open|done|drop`)

**Branch**: `issue/ISSUE-030-status-filter-token`
**Reviewer**: Claude Opus 4.6 (automated)
**Date**: 2026-02-24

---

## Code Review

### Summary

The PR adds `open`, `done`, and `drop` as positional title-tokens to the `list` and `board` command handlers. The priority logic is: **status_token > /s section > default "open"**. This is a clean, well-scoped change.

### Correctness

1. **Status mapping is correct.** `drop` maps to `"dropped"` in the DB, `done` maps to `"done"`, `open` maps to `"open"`. All three paths are covered.

2. **Priority logic (cmd_list.py lines 64-74) is correct.** When `status_token` is set, it takes precedence over `/s section`. The `/s section` fallback for `done`/`drop` is preserved for backward compatibility. The `section_filter` is correctly set to `None` when the section itself is being used as a status indicator.

3. **cmd_board.py does not use `section_filter`.** This is correct -- the board groups by section so it should not filter by section. The board handler's status logic (lines 55-59) is simpler and appropriate.

### Edge Cases Reviewed

| Scenario | Behavior | Verdict |
|---|---|---|
| `list done /s backlog` (status_token + unrelated section) | status=done, section_filter=backlog | Correct -- filters done tasks in backlog section |
| `list done /s done` (status_token + conflicting section) | status=done, section_filter=None | Correct -- avoids double filtering |
| `list done /s drop` (status_token + conflicting section) | status=done, section_filter=None | Correct |
| `list /s done` (no token, section=done) | status=done, section_filter=None | Correct -- backward compat |
| `list open done` (multiple status tokens) | Last token wins (`done`) | Minor -- see below |
| `board done /s backlog` | status=done, no section filter (board never section-filters) | Correct |

### Issues Found

**[LOW] Multiple status tokens -- last-one-wins is implicit (cmd_list.py:43, cmd_board.py:36)**

If a user types `list open done`, both `open` and `done` match the `elif` branch. The loop processes them sequentially so the last one (`done`) wins. This is not necessarily wrong, but the behavior is undocumented and could surprise users. The same pattern applies to `scope` tokens (`mine`/`all`).

*Recommendation*: Accept as-is for this PR. Consider adding a warning or taking only the first status token in a follow-up.

**[LOW] Duplicated token-parsing logic between cmd_list.py and cmd_board.py**

The token loop in both handlers now shares the same `status_token` extraction pattern. The scope/limit parsing was already duplicated; this PR extends that duplication. This is not a regression -- it pre-dates this PR -- but it is worth noting as the handlers diverge further.

*Recommendation*: Follow-up issue to extract a shared `parse_list_options()` helper.

**[INFO] Header label uses `parsed.section` not `section_filter` (cmd_list.py:131)**

```python
section_label = f" /s {parsed.section}" if section_filter else ""
```

This is actually correct -- when `section_filter` is `None` (because `/s done` was used as status), the section label is suppressed. When `section_filter` has a real value, the raw `parsed.section` is shown. No issue.

### Test Coverage Assessment

**New tests (8 total):**
- `test_cmd_list.py`: 5 tests covering `done`, `drop`, `open`, `done all` combo, `/s done` backward compat
- `test_cmd_board.py`: 3 tests covering `done`, `drop`, `open`

**Coverage is good.** The key paths are all exercised. Missing edge cases (non-blocking):

- `list done /s backlog` -- status_token with a non-conflicting section filter (cmd_list.py only)
- `board done /s done` -- status_token overriding `/s section` in board context
- Multiple status tokens in a single command (e.g., `list open done`)

These are low-priority and can be added in a follow-up.

### Consistency

The pattern between `cmd_list.py` and `cmd_board.py` is consistent. Both use the same `status_token` variable name, the same token matching logic (`low in ("open", "done", "drop")`), and the same mapping (`"dropped" if status_token == "drop" else status_token`). The only difference is that `cmd_list.py` handles `section_filter` interaction, which `cmd_board.py` does not need.

---

## Security Findings

### SQL Injection -- **No issues found**

All query parameters are passed via parameterized queries (`?` placeholders). The `status_filter` value is derived from a hardcoded allowlist (`"open"`, `"done"`, `"dropped"`) -- it never contains user-supplied freeform text. The `WHERE` clause is built from trusted string fragments joined with `AND`.

Relevant code (cmd_list.py:76-77):
```python
conditions.append("t.status = ?")
params.append(status_filter)
```

The `status_filter` can only be one of three literal strings: `"open"`, `"done"`, or `"dropped"`. No injection vector exists.

### Input Validation -- **No issues found (Low severity note)**

The `status_token` matching uses an exact-match allowlist (`low in ("open", "done", "drop")`). Unrecognized tokens fall through to `remaining_tokens` (in cmd_list.py) or are silently ignored (in cmd_board.py). This is safe.

### Authentication / Authorization -- **Not affected by this PR**

Scope filtering (`mine`/`all`/`user`) and project visibility checks are unchanged and continue to use parameterized queries.

### Sensitive Data -- **No issues found**

No secrets, API keys, or credentials are introduced in this PR.

### Summary

| Severity | Count | Details |
|---|---|---|
| Critical | 0 | -- |
| High | 0 | -- |
| Medium | 0 | -- |
| Low | 2 | Multiple-status-token ambiguity; duplicated parsing logic |

**No fixes required.** All tests pass (266/266). The PR is safe to merge.

---

## Follow-up Issues (Suggested)

1. **Extract shared token-parsing helper** -- Reduce duplication between `cmd_list.py` and `cmd_board.py` by extracting scope/status/limit parsing into a shared function.
2. **Warn on multiple status tokens** -- Either take the first token or return an error when conflicting status tokens are provided (e.g., `list open done`).
3. **Add edge-case tests** -- `list done /s backlog`, multiple status tokens, `board done /s done`.
