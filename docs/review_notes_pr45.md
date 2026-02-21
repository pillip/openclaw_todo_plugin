# PR #45 Review Notes -- Issue #22: Plugin install E2E tests via entry-point discovery

> Reviewer: Claude Opus 4.6 (automated review)
> Date: 2026-02-21
> Branch: `feature/022-plugin-install-e2e`

---

## Code Review

### Acceptance Criteria Checklist

| Criterion | Status | Notes |
|-----------|--------|-------|
| `openclaw.plugins` group contains `todo` entry-point after `uv sync` | PASS | `test_todo_entry_point_exists` verifies this |
| Loaded function is callable with correct signature | PASS | `test_loaded_function_is_callable` and `test_loaded_function_signature` verify both |
| Full command flow works via entry-point-loaded function | PASS | `test_add_and_list_roundtrip` and `test_full_lifecycle` cover add/list/move/edit/done |
| Private project isolation verified via entry-point path | PASS | `test_private_project_isolation` checks owner vs non-owner visibility |
| Multi-user shared project collaboration verified | PASS | `test_multiple_users_shared_project` covers cross-user shared project |
| Tests marked with `@pytest.mark.install` | PASS | Both test classes decorated with `@pytest.mark.install` |
| `install` marker registered in `pyproject.toml` | PASS | Added to `[tool.pytest.ini_options].markers` |

### Findings

#### 1. Consistency with test_e2e.py -- [Info]

The new file follows the same structural patterns as `test_e2e.py`: `_msg`, `_extract_task_id`, `_query_task` helpers, `db_path` fixture via `tmp_path`, class-based test organization. The key difference is the `handle_message` fixture that loads via `importlib.metadata.entry_points` instead of a direct import. This is well-designed and clearly documents the intent.

The `_msg` helper signature differs (`handle_message` is the first argument in the new file vs. a module-level import in `test_e2e.py`). This is a necessary difference given the fixture-based discovery approach.

#### 2. _extract_task_id fragility -- [Low]

`_extract_task_id` splits on `#` and ` ` to extract the task ID. If the response format ever changes (e.g., `"Added task #N: ..."` vs `"Added #N ..."`), this will silently return a wrong value rather than failing fast. Both files share this pattern.

**Recommendation (follow-up):** Consider a regex-based extraction with an explicit assertion, e.g.:
```python
import re
def _extract_task_id(add_result: str) -> str:
    match = re.search(r"#(\d+)", add_result)
    assert match, f"Could not extract task ID from: {add_result}"
    return match.group(1)
```

#### 3. No negative/error-path tests for entry-point discovery -- [Low]

The test class `TestEntryPointDiscovery` validates the happy path (entry-point exists, is callable, has correct signature). There is no test for what happens if the entry-point is missing or misconfigured. This is acceptable since the entry-point is defined in `pyproject.toml` and controlled by the project, but a follow-up could add a test that verifies graceful error messaging.

#### 4. Test count and coverage -- [Info]

The PR adds 8 new tests (3 discovery + 5 flow), bringing the total to 243. The tests cover:
- Entry-point existence and interface validation
- Non-todo message passthrough
- Add + list roundtrip
- Full lifecycle (add/move/edit/done with DB verification)
- Private project isolation
- Multi-user shared project collaboration

This is solid coverage for the entry-point discovery E2E scope.

#### 5. pyproject.toml marker addition -- [Info]

The `install` marker is properly registered in `pyproject.toml`, preventing `PytestUnknownMarkWarning`. This allows selective execution via `pytest -m install`.

#### 6. issues.md and STATUS.md updates -- [Info]

Issue #22 is properly documented with all fields filled in. STATUS.md correctly shows M5 as "In Progress" with #22 in progress. The issue description clearly distinguishes this from #19 (direct import E2E).

### Changes Applied

1. **Fixed `_query_task` SQL column interpolation** in both `tests/test_plugin_install_e2e.py` and `tests/test_e2e.py` -- see Security Findings below.

### Follow-up Issues

- [ ] **Harden `_extract_task_id`**: Replace string splitting with regex + assertion for robustness (both `test_e2e.py` and `test_plugin_install_e2e.py`)
- [ ] **DRY shared test helpers**: `_extract_task_id`, `_query_task`, and `_ALLOWED_COLUMNS` are duplicated across `test_e2e.py` and `test_plugin_install_e2e.py`. Consider extracting to a `tests/conftest.py` or `tests/helpers.py` module.

---

## Security Findings

### S1. SQL injection via f-string column interpolation in `_query_task` -- [Medium]

**Files:**
- `/Users/pillip/project/practice/openclaw_todo_plugin/tests/test_plugin_install_e2e.py` (line 51-54, before fix)
- `/Users/pillip/project/practice/openclaw_todo_plugin/tests/test_e2e.py` (line 36-39, before fix)

**Description:**
The `_query_task` helper accepted a `columns` parameter and interpolated it directly into a SQL query via f-string:
```python
f"SELECT {columns} FROM tasks WHERE id = ?;"
```

While the `id` value is properly parameterized, the `columns` argument is not sanitized. In this codebase, `columns` is always called with hardcoded string literals from test code, so there is no exploitable attack vector. However, this pattern is dangerous because:
1. It establishes a bad precedent that could be copy-pasted into production code.
2. If test helpers are ever extended to accept dynamic input (e.g., parameterized tests), it becomes exploitable.

**Severity: Medium** -- Test-only code with no user input path, but represents an unsafe SQL construction pattern.

**Remediation applied:**
Added an allowlist (`_ALLOWED_COLUMNS` frozenset) containing valid column names. The function now validates each requested column against the allowlist before interpolation:
```python
_ALLOWED_COLUMNS = frozenset({
    "*", "id", "title", "status", "section", "due",
    "project_id", "created_by", "closed_at", "created_at", "updated_at",
})

def _query_task(db_path: str, task_id: str, columns: str = "*") -> tuple | None:
    parts = [c.strip() for c in columns.split(",")]
    disallowed = set(parts) - _ALLOWED_COLUMNS
    if disallowed:
        raise ValueError(f"Disallowed columns: {disallowed}")
    safe_columns = ", ".join(parts)
    with sqlite3.connect(db_path) as conn:
        return conn.execute(
            f"SELECT {safe_columns} FROM tasks WHERE id = ?;",
            (int(task_id),),
        ).fetchone()
```

Fix applied consistently to both `test_e2e.py` and `test_plugin_install_e2e.py`.

### S2. No hardcoded secrets or credentials -- [Info / Clear]

No API keys, tokens, passwords, or other secrets found in any of the changed files. The test files use placeholder user IDs (`"U001"`, `"U002"`) and temporary database paths.

### S3. No injection risks in test input -- [Info / Clear]

Test inputs (task titles like `"buy groceries"`, `"lifecycle task"`) are plain strings with no special characters. The `handle_message` function properly routes through the parser, which is tested separately. No command injection, template injection, or XSS vectors found.

### S4. No dependency changes -- [Info / Clear]

The PR adds no new dependencies. Only `pyproject.toml` marker configuration was changed. No CVE exposure introduced.

### S5. No authentication/authorization bypass -- [Info / Clear]

The test file properly tests private project isolation (owner vs non-owner). No auth bypass patterns detected. The `context` dict with `sender_id` is the standard auth mechanism for this plugin.

---

## Test Results

All 243 tests pass after applying the `_query_task` fix:

```
243 passed in 0.72s
```

No regressions introduced.
