# Review Notes -- PR #86: /todo project delete command (ISSUE-044)

**Reviewer:** Claude Opus 4.6 (automated)
**Date:** 2026-03-06
**Files reviewed:**
- `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/cmd_project_delete.py`
- `/Users/pillip/project/practice/openclaw_todo_plugin/tests/test_cmd_project_delete.py`
- `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/dispatcher.py`

---

## Code Review

### Overall Assessment

The implementation is clean, well-structured, and follows the established patterns in the codebase. The handler correctly checks for empty projects before deletion, blocks Inbox, and hides private project existence from non-owners. Test coverage is solid across all major scenarios.

### Findings

#### 1. Inbox protection is case-sensitive (Medium)

**File:** `cmd_project_delete.py:32`

```python
if project_name == "Inbox":
```

The check only blocks the exact string `"Inbox"`. If a user types `"inbox"` or `"INBOX"`, the guard is bypassed and the code proceeds to `resolve_project`. Currently `resolve_project` does a case-sensitive SQL `WHERE name = ?`, so a case-variant would hit "not found" rather than actually deleting the Inbox. This is safe in practice but fragile -- if the schema or resolver ever adds `COLLATE NOCASE`, the Inbox could become deletable.

**Recommendation:** Use case-insensitive comparison:
```python
if project_name.lower() == "inbox":
```

This is consistent with how other subcommands normalize input (e.g., `cmd_project_create.py:36`).

#### 2. Race condition: task count check + delete (Low, SQLite-specific)

**File:** `cmd_project_delete.py:46-59`

The task count SELECT and the DELETE are not wrapped in a single transaction explicitly. In SQLite with WAL mode and the default `autocommit` behavior of Python's `sqlite3` module, a DML statement (INSERT on tasks) from another connection could commit between the SELECT COUNT and the DELETE.

In practice this is extremely unlikely given:
- SQLite's single-writer lock (busy_timeout=3000)
- The plugin runs in a single-process context (OpenClaw MCP)
- Foreign keys are ON with no `ON DELETE CASCADE`, so a DELETE with dangling task FKs would fail with `FOREIGN KEY constraint failed`

The FK constraint acts as a safety net -- even if a task is inserted between the check and delete, the DELETE itself would fail. This is a good defense-in-depth.

**Recommendation (follow-up):** For correctness documentation, add a brief comment explaining the FK safety net:

```python
# Safety: foreign_keys=ON means DELETE will fail if tasks still reference this project,
# preventing a TOCTOU race between the count check and the actual delete.
```

#### 3. Only first token used as project name (Low)

**File:** `cmd_project_delete.py:27`

```python
project_name = tokens[0].strip()
```

Multi-word project names (e.g., "My Project") are not supported -- only the first token is taken. This is consistent with `cmd_project_create.py` and `cmd_project_rename.py`, so no change needed, but worth noting that multi-word names are unsupported across the board.

#### 4. Test coverage is good but missing a few edges

**Existing coverage:** shared delete, private delete, non-owner block, tasks block, not-found, Inbox block, missing name, private-first resolution.

**Missing tests (minor, follow-up):**
- Delete a project with only `done`/`dropped` tasks (to confirm they still count as blockers)
- Concurrent deletion attempt (same project deleted twice)
- `task_assignees` orphan check -- not relevant since tasks must be removed first, but good to verify the FK chain

### Dispatcher changes

The dispatcher changes are minimal and correct:
- Import added at line 18
- Handler registered as `"project_delete"` at line 108
- Help text at line 65-66
- `PROJECT_USAGE` and `_VALID_PROJECT_SUBS` already include `"delete"`

No issues found.

---

## Security Findings

### Critical

None.

### High

None.

### Medium

**M1. Inbox protection bypass via case variation**

- **Location:** `cmd_project_delete.py:32`
- **Description:** The Inbox guard uses exact case comparison `== "Inbox"`. While currently safe due to case-sensitive SQL queries, this is fragile. A schema change adding `COLLATE NOCASE` would make the Inbox deletable via `"inbox"` or `"INBOX"`.
- **Impact:** Potential deletion of the system Inbox project.
- **Fix:** Use `project_name.lower() == "inbox"` for the guard. Fix applied in this review.

### Low

**L1. TOCTOU between task count and project delete**

- **Location:** `cmd_project_delete.py:46-59`
- **Description:** No explicit transaction wrapping the count check and delete. A concurrent task insertion could pass the count check but the FK constraint provides defense-in-depth.
- **Impact:** Minimal in single-process SQLite context. FK constraint prevents data corruption.
- **Recommendation:** Add a comment documenting the FK safety net. No code change required.

**L2. User-supplied project name in log output**

- **Location:** `cmd_project_delete.py:73`
- **Description:** `project_name` is logged via `logger.info` with `%s` formatting (safe from injection). The name also appears in the event payload JSON. No risk of log injection since Python's logging module does not interpret format specifiers in the argument values.
- **Impact:** None. This is informational only.

**L3. No SQL injection risk**

- All SQL queries use parameterized queries (`?` placeholders). No string interpolation in SQL. This is correct and secure.

---

## Applied Fixes

### Fix M1: Case-insensitive Inbox guard

Changed the Inbox protection check to be case-insensitive to prevent potential bypass via case variants.

---

## Follow-up Issues

1. **Add comment explaining FK safety net** for the TOCTOU race condition (L1)
2. **Add test for done/dropped tasks** still blocking deletion
3. **Consider multi-word project name support** across all project commands (tracked separately)
