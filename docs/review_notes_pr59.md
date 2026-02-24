# PR #59 Review Notes -- Auto-Create Shared Projects

**Branch**: `issue/ISSUE-033-auto-create-project`
**Reviewer**: Claude Opus 4.6 (automated)
**Date**: 2026-02-24

---

## Code Review

### 1. Overall Design

The approach is clean: catch `ProjectNotFoundError` in `add_handler`, INSERT a new shared
project, then continue with task creation. The event logging (`project.auto_create`) provides
good auditability.

### 2. `Project` Import (Line 10) -- NOT Unused

The `Project` import from `project_resolver` **is used** on line 42 to construct the
`Project` dataclass after the auto-create SELECT. No change needed.

```python
# src/openclaw_todo/cmd_add.py:10
from openclaw_todo.project_resolver import Project, ProjectNotFoundError, resolve_project

# src/openclaw_todo/cmd_add.py:42
project = Project(id=row[0], name=row[1], visibility=row[2], owner_user_id=row[3])
```

### 3. SELECT-After-INSERT Pattern (Line 38-41)

The original code did `INSERT` then `SELECT ... WHERE name = ? AND visibility = 'shared'` to
get the row back. This is correct but slightly fragile -- if a future migration ever allows
duplicate shared names, the SELECT could return the wrong row. Using `cursor.lastrowid`
would be more precise. Minor concern; no fix applied.

### 4. Test Coverage Assessment

**Covered well:**
- Happy path auto-create (test_add_nonexistent_project_auto_creates)
- Existing project does not trigger auto-create message
- Event logging for auto-create
- Private project with same name takes priority

**Missing edge cases (proposed as follow-ups):**
- Project name with leading/trailing whitespace
- Project name with special characters or SQL metacharacters
- Empty project name (parsed.project = "")
- Very long project name (>128 chars) -- now validated by the fix
- Concurrent auto-create (IntegrityError race) -- now handled by the fix

### 5. Minor Style Notes

- Line 64 has implicit string concatenation for the SQL query:
  `"INSERT INTO tasks ... " "VALUES ..."`
  This works but an f-string or single string literal would be clearer.

---

## Security Findings

### [High] S1: Race Condition / IntegrityError on Concurrent Auto-Create

**File**: `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/cmd_add.py`
**Lines**: 34-42 (original)

**Description**: The `projects` table has a unique partial index
`ux_projects_shared_name ON projects(name) WHERE visibility = 'shared'`. If two concurrent
`/todo add` commands reference the same nonexistent project, both would pass the
`resolve_project` call, both would attempt to INSERT, and the second would raise
`sqlite3.IntegrityError`. This would crash the handler and return an unhandled 500 to the
user.

**Fix applied**: Wrapped the INSERT in a `try/except sqlite3.IntegrityError` block. On
conflict, the code falls through to the SELECT which retrieves the row created by the
winning request.

```python
try:
    conn.execute(
        "INSERT INTO projects (name, visibility, owner_user_id) VALUES (?, 'shared', NULL);",
        (stripped,),
    )
except sqlite3.IntegrityError:
    logger.debug("Concurrent auto-create for project '%s'; falling back to SELECT", stripped)
```

**Status**: Fixed.

### [Medium] S2: No Validation on Auto-Created Project Name

**File**: `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/cmd_add.py`
**Lines**: 33-37 (original)

**Description**: The original code inserted `project_name` directly into the `projects` table
with no length or character validation. While the SQL uses parameterized queries (safe from
injection), a user could create projects with names like:

- Empty string or whitespace-only
- Extremely long strings (thousands of characters)
- Names containing control characters, newlines, or other problematic content

This could cause display issues, storage bloat, or downstream parsing problems.

**Fix applied**: Added validation before auto-create:
- Name must be 1-128 characters after stripping whitespace
- Only alphanumeric characters, spaces, hyphens, and underscores are allowed

```python
stripped = project_name.strip()
if not stripped or len(stripped) > 128:
    return "Error: project name must be 1-128 characters."
if not all(c.isalnum() or c in " _-" for c in stripped):
    return "Error: project name may only contain letters, digits, spaces, hyphens, and underscores."
```

**Status**: Fixed.

### [Low] S3: SQL Queries Use Parameterized Binding -- Verified Safe

**File**: `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/cmd_add.py`

All SQL in `cmd_add.py` uses `?` parameter binding. No string interpolation or formatting is
used to build SQL. **No injection risk**.

Verified queries:
- Line 35: `INSERT INTO projects ... VALUES (?, 'shared', NULL)` -- parameterized
- Line 39: `SELECT ... WHERE name = ? AND visibility = 'shared'` -- parameterized
- Line 64: `INSERT INTO tasks ... VALUES (?, ?, ?, ?, 'open', ?)` -- parameterized
- Line 72: `INSERT INTO task_assignees ... VALUES (?, ?)` -- parameterized

**Status**: No issue.

---

## Follow-Up Issues

1. **Add test for IntegrityError race condition**: Simulate concurrent auto-create by
   manually inserting a shared project between `resolve_project` and the INSERT, then verify
   the handler still succeeds. This would require mocking or a two-thread test setup.

2. **Centralize project name validation**: The validation rules added here should ideally
   live in a shared utility (e.g., `project_resolver.validate_project_name()`) so that any
   future project-creation paths (admin commands, API) apply the same rules.

3. **Consider `INSERT OR IGNORE` + SELECT pattern**: Instead of try/except, the INSERT
   could use `INSERT OR IGNORE` (like the Inbox seed in `project_resolver.py` line 69) for
   a cleaner approach. This would silently skip on conflict and the subsequent SELECT would
   still find the row.

4. **Add tests for project name validation edge cases**: Empty string, whitespace-only,
   128+ character names, names with special characters.
