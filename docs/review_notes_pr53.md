# PR #53 Review Notes -- UX Response Format Unification

**Branch:** `issue/ISSUE-032-ux-response-format`
**Date:** 2026-02-24
**Reviewer:** Claude Opus 4.6 (automated)

---

## Code Review

### Summary

This PR unifies the response format across all 6 command handlers (`add`, `board`, `done`, `drop`, `edit`, `list`, `move`) with emoji prefixes, em-dash separators, and a standardized layout showing task metadata inline. The changes are clean, consistent, and well-tested.

### Correctness

1. **cmd_done_drop.py -- JOIN query is correct.** The SELECT was expanded from `SELECT section, status` to `SELECT t.title, t.section, t.status, p.name` with a JOIN to `projects`. The unpacking on line 51 matches the new column order. No issue here.

2. **cmd_move.py -- project_name fetch AFTER commit (line 76).** The query `SELECT name FROM projects WHERE id = ?` runs after `conn.commit()`. This is safe because:
   - The `project_id` was read from the `tasks` table before the update.
   - The update only modifies `section` and `updated_at` -- it does not change `project_id`.
   - SQLite connections in this codebase are single-threaded per request, so no concurrent modification risk.
   - **Minor nit:** It would be slightly cleaner to fetch the project name in the initial SELECT (alongside `title, section, project_id`) using a JOIN, avoiding the extra query. This is a performance micro-optimization, not a bug.

3. **cmd_edit.py -- post-edit re-query (lines 145-158).** The re-query reads the committed state after `conn.commit()`. This is correct and actually *safer* than assembling the response from in-memory variables, since it reflects the true database state. No race condition risk in SQLite with the single-connection model used here.

4. **cmd_list.py -- `fetch_params` separation (line 112).** Previously, `limit` was appended to the shared `params` list, which would have corrupted `params` if it were reused. The PR correctly creates a separate `fetch_params = list(params) + [limit]` so the count query and fetch query use independent parameter lists. This is a genuine improvement.

5. **cmd_list.py -- `section_label` uses `section_filter` guard (line 125).** The header only includes `/s` when `section_filter` is truthy (not None). When `parsed.section` is `"done"` or `"drop"`, `section_filter` is set to `None` because those map to status filters, not section filters. This is correct behavior.

### Edge Cases

1. **cmd_move.py line 76 -- `.fetchone()[0]` without None check.** If the project row does not exist, this would raise `TypeError`. However, since the task was successfully loaded with its `project_id` from the `tasks` table (and foreign key integrity is maintained), the project must exist. Low risk but defensive coding would add a guard.

2. **cmd_edit.py line 151 -- `final_row` unpacking without None check.** Same reasoning as above -- the task was just committed, so it must exist. Acceptable.

3. **cmd_list.py -- footer always shows "Use limit:N to see more."** Even when all tasks are displayed (displayed == total_count), the footer still suggests using `limit:N`. This is a minor UX nit -- consider suppressing the hint when all results are shown.

### Maintainability

1. **Response format consistency is good.** All mutation commands now follow the pattern:
   `{emoji} {Verb} #{id} ({project}/{section}) due:{date} assignees:{list} -- {title}`
   Read commands (`list`, `board`) have their own consistent patterns with headers/footers.

2. **The `emoji` and `verb` parameters in `_close_task` are a clean extension.** They avoid duplicating the shared logic while allowing per-command customization.

3. **Duplicated response formatting logic.** The pattern of building `due_str`, `assignee_str`, and the final formatted string appears in `cmd_add.py`, `cmd_edit.py`, and partially in `cmd_list.py` / `cmd_board.py`. A future refactor could extract a shared `format_task_line()` helper. This is a follow-up suggestion, not a blocking issue.

### Test Coverage

1. **Tests are updated correctly** to match the new response formats.

2. **Test specificity improvement.** The old tests checked for generic field names (`"title" in result`, `"due" in result`), which could match false positives. The new tests check for actual values (`"New title" in result`, `"due:2026-03-15" in result`). This is a strict improvement.

3. **`test_cmd_list.py` sorting test fix.** The old test tried to parse `#N` from every line (including the header/footer), which would fail with the new format. The fix to skip non-`#` lines is correct.

4. **Missing test: cmd_add.py emoji prefix.** No existing test explicitly verifies the new emoji prefix in `cmd_add.py` response. The existing tests for `add` check for `#{task_id}` but not for the leading emoji. Low priority since the format is simple.

5. **Missing test: cmd_move.py new format.** The move tests should verify the new format includes project name and title. Worth checking existing coverage.

---

## Security Findings

### cmd_list.py -- f-string with `where_clause` in COUNT query (Medium)

**File:** `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/cmd_list.py`, lines 95-100

```python
count_query = (
    "SELECT COUNT(*) "
    "FROM tasks t "
    "JOIN projects p ON t.project_id = p.id "
    f"WHERE {where_clause}"
)
total_count = conn.execute(count_query, params).fetchone()[0]
```

**Classification:** Medium (by convention) / **Actual risk: Low**

**Analysis:** The `where_clause` is built from `" AND ".join(conditions)` where every element in `conditions` is a hardcoded SQL fragment with `?` placeholders (e.g., `"t.status = ?"`, `"t.project_id = ?"`, `"t.section = ?"`). User input is never interpolated into the clause string itself -- it flows exclusively through the parameterized `params` list.

The same pattern is already used in the existing SELECT query on line 104-110 and in `cmd_board.py` line 75-81. This is **not a SQL injection vulnerability** because:
- Condition strings are assembled from constants in the handler code.
- `build_scope_conditions()` also returns only hardcoded SQL fragments.
- All user-supplied values go through `?` parameter binding.

**Verdict:** Safe. No fix needed. The f-string pattern is a common and acceptable way to build dynamic WHERE clauses when the clause fragments are code-controlled.

### cmd_board.py -- Same f-string pattern (Low)

**File:** `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/cmd_board.py`, line 79

Same analysis as above. The `where_clause` is built from code-controlled fragments with parameterized values. Safe.

### No hardcoded secrets or API keys (Pass)

Reviewed all changed files. No credentials, tokens, or secret values are present.

### No XSS concerns in current context (Low)

The response strings include user-controlled data (task titles, project names) embedded directly in the output string. In the current context (Slack bot / CLI plugin), these are plain-text messages and Slack handles rendering. If this output were ever rendered as HTML, the `<@UID>` patterns and user titles would need escaping. Current risk: **none** for the Slack use case.

### Input validation (Pass)

- Task IDs are validated via `int()` conversion with proper error handling.
- Scope values are checked against allowlists (`"mine"`, `"all"`).
- Limit/limitPerSection values are validated as positive integers.
- Project names go through `resolve_project()` which uses parameterized queries.

### Authentication / Authorization (Pass)

- All mutation commands (`done`, `drop`, `edit`, `move`) check `can_write_task()` before making changes.
- Private project visibility is enforced in scope queries via `build_scope_conditions()`.
- No authorization bypass introduced by this PR.

### Dependencies (Not in scope)

No dependency changes in this PR.

---

## Suggested Follow-ups

1. **Extract `format_task_response()` helper** to reduce duplication across `cmd_add.py`, `cmd_edit.py`, `cmd_done_drop.py`, and `cmd_move.py`. All share the same `{emoji} {verb} #{id} ({project}/{section}) due:{due} assignees:{list} -- {title}` pattern.

2. **Suppress "Use limit:N" footer** in `cmd_list.py` when `displayed == total_count`.

3. **Add explicit test for `cmd_add.py` emoji prefix** and `cmd_move.py` new response format including project name.

4. **Consider moving project_name fetch into the initial query** in `cmd_move.py` (JOIN instead of separate query after commit) for cleaner code.

---

**Overall verdict:** Approve. No critical or high severity issues found. The code is correct, well-tested, and the security posture is maintained. The follow-up suggestions are all low-priority improvements.
