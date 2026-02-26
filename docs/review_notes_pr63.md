# PR #63 Review Notes -- ISSUE-035: Error Message UX Spec Alignment

> Reviewer: Claude Opus 4.6 (automated review)
> Date: 2026-02-26
> Branch: (error message UX spec alignment)

**Test run:** 277 passed, 0 failed (6.08s). No blocking issues found.

---

## Code Review

### Overall Assessment

The PR achieves its stated goal: aligning all error, informational, and warning messages across 10 source files with UX spec sections 3.1--3.5. Emoji prefixes are applied consistently, and the test suite has been updated to match. Code quality is good.

### Positive Observations

1. **Consistent emoji prefixing.** All error paths use the cross-mark prefix, informational messages use the info prefix (already-done/noop), and warnings use the warning prefix for private assignee rejection. The pattern is easy to audit across all 10 files.

2. **Good extraction of `validate_private_assignees` into `permissions.py`.** This avoids duplicating the Korean-format warning string between `cmd_add.py` and `cmd_edit.py`. The `cmd_edit.py` handler correctly delegates to the shared function.

3. **Parameterized `_close_task` in `cmd_done_drop.py`.** The emoji and verb are passed in as parameters, keeping the done/drop handlers DRY while allowing distinct response formatting.

4. **Test coverage is thorough.** Each message path (error, noop, success, permission denied) has at least one assertion checking the emoji prefix or key phrase. Edge cases like missing task ID, invalid task ID, nonexistent task, and already-closed tasks are all covered.

### Findings

#### CQ-1: Inconsistent private-assignee warning format between cmd_add.py and permissions.py (Medium)

**Files:**
- `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/cmd_add.py` (lines 67--72)
- `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/permissions.py` (lines 85--86)

`cmd_add.py` produces a warning that includes the project name:

```python
f'Private project("{project.name}") ... assignees({formatted}) ...'
```

While `permissions.py` (used by `cmd_edit.py`) produces a generic warning without the project name:

```python
f"Private project ... assignees({formatted}) ..."
```

Users see a slightly different warning depending on whether the constraint is triggered via `add` vs `edit`. The `cmd_add.py` handler should call `validate_private_assignees` instead of inlining its own version.

**Recommendation:** Extend `validate_private_assignees` to accept an optional `project_name` parameter and unify both call sites. This is a low-risk follow-up.

#### CQ-2: No project-name validation in set-private and set-shared handlers (Low)

**Files:**
- `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/cmd_project_set_private.py` (line 31)
- `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/cmd_project_set_shared.py` (line 28)

The `cmd_add.py` handler validates project names (1--128 characters, alphanumeric plus spaces/hyphens/underscores) before auto-creating. The `set-private` and `set-shared` handlers accept any string as a project name when creating new projects (Step 3 path). A user could create a project with special characters or extremely long names.

**Recommendation:** Extract the project-name validation from `cmd_add.py` into a shared utility and reuse it in both project subcommand handlers.

#### CQ-3: Violation list in set-private uses comma-joined single line (Low)

**File:** `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/cmd_project_set_private.py` (lines 100--101)

When many tasks violate the private-assignee constraint, the `task_lines` string can become very long because all shown tasks are comma-joined on a single line. For better readability in Slack, consider using newline-separated entries.

#### CQ-4: Edit handler SQL constructed via f-string join -- add defensive comment (Low)

**File:** `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/cmd_edit.py` (line 117)

```python
sql = f"UPDATE tasks SET {', '.join(update_fields)} WHERE id = ?;"
```

The `update_fields` list is fully controlled by code (hardcoded column names like `"title = ?"`) and is safe. However, the pattern is fragile -- any future change that accidentally lets user input into `update_fields` would create a SQL injection vector. Adding a comment or assertion would be prudent.

#### CQ-5: Missing test for Korean message content in validate_private_assignees (Low)

**File:** `/Users/pillip/project/practice/openclaw_todo_plugin/tests/test_permissions.py` (lines 90--93)

The test only checks that the result is not None and that the user ID appears. It does not assert the Korean UX format string from the spec. A more specific assertion would catch regressions if the message wording changes.

---

## Security Findings

### No Critical or High severity issues found.

### Medium

#### SEC-1: User-supplied values reflected in error messages without escaping

**Severity:** Medium

**Files (representative examples):**
- `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/dispatcher.py` line 126 -- unknown command name
- `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/cmd_move.py` line 31 -- invalid task ID
- `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/cmd_move.py` line 40 -- invalid section token
- `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/cmd_edit.py` line 79 -- project name
- `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/cmd_list.py` lines 49--51 -- limit value

User input (command names, task IDs, section tokens, project names, limit values) is interpolated directly into response strings. In the current architecture (Slack bot returning plain text), this is not directly exploitable -- Slack handles rendering. However:

- If the response format ever changes to HTML or Markdown with rendering (e.g., a web dashboard), these become XSS vectors.
- Slack interprets some mrkdwn formatting, so crafted input could produce unexpected formatting.

The parser already constrains most inputs (mentions match `<@U[A-Z0-9]+>`, sections from a fixed set, dates validated). Residual risk is in free-text fields echoed in error messages.

**Recommendation:** No immediate fix required. If a web UI is planned, add an output-encoding layer.

### Low

#### SEC-2: No rate limiting on project auto-creation

**Severity:** Low

**File:** `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/cmd_add.py` (lines 33--55)

Any user can auto-create unlimited shared projects via `add` commands with novel `/p` names. The name validation (lines 36--39) prevents some abuse, but a malicious user could still create many projects to pollute the database.

**Recommendation:** Consider a per-user project creation rate limit or maximum project count as a follow-up.

#### SEC-3: No project-level authorization for visibility changes

**Severity:** Low

**Files:**
- `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/cmd_project_set_private.py`
- `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/cmd_project_set_shared.py`

Any user can convert a shared project to private (claiming ownership). There is no "project admin" concept. The `set-private` handler does check for non-owner assignee violations, which mitigates the worst case, but does not prevent the conversion itself.

**Recommendation:** Acceptable for current scope (small team plugin). If the user base grows, introduce project-level roles.

#### SEC-4: sender_id trusted without format validation

**Severity:** Low

**File:** All command handlers via `context["sender_id"]`.

The `context` dict is populated by the plugin server from the Slack event payload. If the server verifies Slack request signatures, this is safe. However, there is no defensive check that `sender_id` is non-empty and matches the expected format (`U[A-Z0-9]+`).

**Recommendation:** Add a guard in `dispatch()` to validate `sender_id` format. Low priority.

---

## Summary Table

| Category | Critical | High | Medium | Low |
|----------|----------|------|--------|-----|
| Security | 0 | 0 | 1 | 3 |
| Code Quality | -- | -- | 1 | 4 |

**Verdict:** The PR is ready to merge. All findings are non-blocking. The medium-severity items (CQ-1 and SEC-1) should be tracked as follow-up issues.

### Suggested Follow-up Issues

1. **Unify private-assignee warning format** -- Refactor `cmd_add.py` to use `validate_private_assignees` from `permissions.py` (CQ-1).
2. **Extract and share project-name validation** -- Reuse the validation logic from `cmd_add.py` in `set-private`/`set-shared` (CQ-2).
3. **Add output encoding layer** -- Prepare for non-Slack rendering contexts (SEC-1).
4. **Project creation rate limiting** -- Prevent abuse via unlimited auto-creation (SEC-2).
5. **Project-level authorization** -- Introduce admin roles for project visibility changes (SEC-3).
