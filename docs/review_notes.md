# PR #2 Review Notes -- Issue #1: Plugin skeleton and entry point

> Reviewer: Claude Opus 4.6 (automated review)
> Date: 2026-02-20
> Branch: `feature/001-plugin-skeleton`

---

## Code Review

### Acceptance Criteria Checklist

| Criterion | Status | Notes |
|-----------|--------|-------|
| `pyproject.toml` with Python >=3.11, pytest, pytest-cov dev deps | PASS | Correct. Uses `dependency-groups` (PEP 735) with hatchling backend. |
| `src/openclaw_todo/__init__.py` exposes `__version__` | PASS | `__version__ = "0.1.0"` |
| `handle_message(text: str, context: dict) -> str` entry point | PASS (minor note) | Return type is `str | None`, not `str`. The AC literally says `-> str` but `None` for ignored messages is the intended behavior per the next AC. Acceptable. |
| Non-`/todo` messages silently ignored (returns `None`) | PASS | |
| `uv sync && uv run pytest -q` passes | PASS | 4 tests, 100% coverage |

### Required Tests

| Test | Status |
|------|--------|
| `test_ignores_non_todo_message` | PASS -- covers empty string, random text, `/todox` prefix-collision |
| `test_dispatches_todo_prefix` | PASS -- verifies non-None response with subcommand text |

### Findings

#### [Info] Return type annotation mismatch with AC

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/plugin.py`, line 12
- The AC states `-> str` but the implementation is `-> str | None`. This is correct behavior (returning `None` for non-todo messages is explicitly required). The AC text is slightly imprecise; the code is right.
- **Action**: None needed. Consider updating the AC wording if desired.

#### [Info] `context` parameter unused

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/plugin.py`, line 12
- `context: dict` is accepted but never read in this skeleton. This is expected for M0 -- it will be used once the dispatcher (Issue #16) and DB commands are wired in.
- **Action**: None. This is intentional scaffolding.

#### [Info] Placeholder response includes raw user input

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/plugin.py`, line 32
- `f"TODO command received: {remainder}"` echoes back unescaped user input. This is a temporary placeholder (comment says "will be replaced by dispatcher in Issue #16"). In the current context (no HTML/web rendering, Slack DM only), this is not exploitable, but see Security Findings below.
- **Action**: Track as part of Issue #16.

#### [Info] Extra tests beyond AC requirements -- good

- `test_todo_prefix_with_whitespace` and `test_todo_without_subcommand` are bonus tests covering whitespace handling and bare `/todo` usage message. Good coverage instinct.

#### [Info] Version duplication

- Version `0.1.0` appears in both `pyproject.toml` and `__init__.py`. Consider using `importlib.metadata` or dynamic versioning in a future issue to keep a single source of truth. Not a concern for M0.

#### [Low] No type hints for `context` dict

- `context: dict` is untyped (could be `dict[str, Any]` or a TypedDict). For M0 this is fine, but a `TypedDict` or dataclass should be introduced when the context shape solidifies.

### Code Quality Summary

The implementation is clean, minimal, and well-structured for a skeleton:

- Prefix matching logic (`stripped == _TODO_PREFIX or stripped.startswith(_TODO_PREFIX + " ")`) correctly avoids false positives on `/todox`.
- Logging at appropriate levels (debug for all messages, info for matches).
- Usage help returned for bare `/todo` is a nice touch.
- Test coverage is 100%.

**Verdict: APPROVE** -- no blocking issues.

---

## Security Findings

### [Low] S1: User input echoed in placeholder response

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/plugin.py`, line 32
- **Description**: The placeholder `f"TODO command received: {remainder}"` reflects user-supplied text without sanitization. In the current Slack DM context, Slack handles rendering and this is not exploitable for XSS. However, once a web dashboard or logging UI is introduced, unsanitized echo could become a reflected XSS vector.
- **Severity**: Low (Slack auto-escapes; placeholder will be replaced in Issue #16)
- **Recommendation**: When building the real dispatcher, ensure any user text echoed in responses is sanitized if it ever reaches a web context. No fix needed now.

### [Low] S2: No input length validation

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/plugin.py`, line 12
- **Description**: `handle_message` accepts arbitrarily long strings. A malicious or buggy client could send extremely large messages. Slack itself limits messages to ~40,000 characters, so this is mitigated at the transport layer.
- **Severity**: Low
- **Recommendation**: Consider adding a max-length guard in the dispatcher (Issue #16) if the plugin is ever exposed outside Slack.

### [Info] S3: No hardcoded secrets or credentials

- No API keys, tokens, or secrets found in any reviewed files. Environment variable approach is correctly deferred to future DB/config work.

### [Info] S4: Dependencies are minimal and current

- Only dev dependencies: `pytest>=7.0` and `pytest-cov>=4.0`. No known CVEs for these versions. No runtime dependencies beyond the standard library.
- Build backend `hatchling` is a well-maintained, standard tool.

### [Info] S5: No SQL, no deserialization, no file I/O

- The M0 skeleton has no database, no file operations, and no deserialization. The attack surface is effectively zero at this stage.

### Security Summary

No Critical or High severity findings. The codebase has a minimal attack surface appropriate for a plugin skeleton. Security considerations will become relevant starting with Issue #2 (DB connection) and Issue #5 (parser with user-controlled input).

---

## Follow-up Issues (proposed)

1. **Issue #16 (Dispatcher)**: When replacing the placeholder response, ensure user input is not echoed raw if the output context changes (e.g., web UI).
2. **Future**: Introduce a `TypedDict` or dataclass for the `context` parameter to enforce shape and enable static analysis.
3. **Future**: Consolidate version to a single source (e.g., `importlib.metadata.version("openclaw-todo-plugin")`).

---

# PR #4 Review Notes -- Issue #2: DB module -- connection helper and pragma setup

> Reviewer: Claude Opus 4.6 (automated review)
> Date: 2026-02-20
> Branch: `feature/002-db-connection`

---

## Code Review

### Acceptance Criteria Checklist

| Criterion | Status | Notes |
|-----------|--------|-------|
| Directory is created recursively when absent | PASS | `db_dir.mkdir(parents=True, exist_ok=True)` on line 32. Test `test_creates_directory_and_file` verifies nested `nested/dir/` creation. |
| SQLite connection returned with WAL mode enabled | PASS | `PRAGMA journal_mode=WAL` on line 36. Test verifies `fetchone()[0] == "wal"`. |
| `busy_timeout` is 3000 | PASS | `PRAGMA busy_timeout=3000` on line 37. Test verifies `fetchone()[0] == 3000`. |
| Calling `get_connection` twice returns usable connections (no lock conflict) | PASS | `test_two_connections_no_conflict` creates a table via conn1, reads via conn2. WAL mode enables this concurrency. |

### Required Tests

| Test | Status |
|------|--------|
| `tests/test_db.py::test_creates_directory_and_file` | PASS -- verifies both `db_path.exists()` and `db_path.parent.exists()` with nested `tmp_path` |
| `tests/test_db.py::test_wal_mode_enabled` | PASS -- queries `PRAGMA journal_mode` and asserts `"wal"` |
| `tests/test_db.py::test_busy_timeout` | PASS -- queries `PRAGMA busy_timeout` and asserts `3000` |

### Findings

#### [Info] TOCTOU in `is_new` logging check

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/db.py`, line 29
- `is_new = not db_path.exists()` is checked before `sqlite3.connect()`, which itself creates the file. In a concurrent scenario, the file could appear between the check and the connect. This only affects which log message is emitted (info vs. debug) and has no functional impact.
- **Action**: None required. Purely cosmetic race condition.

#### [Info] PRAGMA return values not checked

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/db.py`, lines 36-37
- `conn.execute("PRAGMA journal_mode=WAL;")` returns a result set with the actual journal mode applied. On some edge cases (e.g., read-only filesystem, in-memory DB), WAL activation can silently fall back to another mode. The code does not verify the return.
- **Action**: Low priority. Consider adding a debug-level assertion or log warning in a future hardening pass. The test suite already validates WAL is active in the happy path.

#### [Info] Default path uses `Path.home()`

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/db.py`, line 11
- `DEFAULT_DB_DIR = Path.home() / ".openclaw" / "workspace" / ".todo"` is evaluated at module import time. If `HOME` is unset (e.g., certain containerized environments), `Path.home()` raises `RuntimeError`. This is acceptable since: (a) the default is only used when `db_path is None`, and (b) the plugin is designed for environments where `HOME` is set. Callers in containers should pass an explicit path.
- **Action**: None for M1. Document the `db_path` parameter as the recommended override for non-standard environments.

#### [Info] Extra test beyond AC requirements -- good

- `test_two_connections_no_conflict` is a bonus test that exercises concurrent WAL access. This directly validates the 4th acceptance criterion and is well-structured with proper cleanup in a `finally` block.

#### [Low] Test cleanup uses `try/finally` instead of a fixture

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/tests/test_db.py`, all tests
- Each test manually opens a connection and closes it in `try/finally`. A pytest fixture (e.g., `@pytest.fixture` yielding the connection) would reduce boilerplate and guarantee cleanup even if assertion lines are added later. This is a minor style observation for 4 tests.
- **Action**: Optional refactor. Not blocking.

#### [Info] Coverage at 96%

- Line 24 (`db_path = DEFAULT_DB_DIR / DEFAULT_DB_NAME`) is uncovered because all tests pass explicit `tmp_path` paths. This is correct -- testing the default path would write to the user's actual home directory. The uncovered line is trivial assignment logic.

### Code Quality Summary

The implementation is clean, minimal, and correct:

- Function signature `get_connection(db_path: str | Path | None = None)` is flexible, accepting string, Path, or None.
- `Path(db_path)` normalization on line 26 handles string inputs.
- `exist_ok=True` on `mkdir` prevents race conditions with concurrent directory creation.
- Logging at appropriate levels: `info` for creation, `debug` for opens.
- No unnecessary dependencies -- uses only stdlib `sqlite3`, `pathlib`, and `logging`.
- 96% test coverage with all acceptance criteria verified.

**Verdict: APPROVE** -- no blocking issues.

---

## Security Findings

### [Low] S1: `db_path` parameter accepts arbitrary filesystem paths

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/db.py`, line 15
- **Description**: `get_connection(db_path)` will create directories and an SQLite database at any filesystem path the process has write access to. If a future caller passes unsanitized user input as `db_path`, this could be used for arbitrary file creation (e.g., path traversal via `../../etc/cron.d/evil`).
- **Severity**: Low (currently an internal API; no user-facing code path passes user input to `db_path`)
- **Recommendation**: When wiring `db_path` into the dispatcher (Issue #16), ensure the path comes only from configuration (env var or config file), never from user-controlled message text. Consider adding a validation that `db_path` is within an expected base directory.

### [Info] S2: No SQL injection risk

- PRAGMA statements on lines 36-37 use hardcoded string literals with no interpolation. The `db_path` is passed to `sqlite3.connect()` as a filesystem path, not as a SQL query. No injection surface exists.

### [Info] S3: No hardcoded secrets or credentials

- No API keys, tokens, or secrets found in `db.py` or `test_db.py`. The module uses only stdlib.

### [Info] S4: No new dependencies introduced

- This module uses only Python standard library (`sqlite3`, `pathlib`, `logging`). No new entries in `pyproject.toml` dependencies. Zero additional attack surface from third-party code.

### [Info] S5: SQLite WAL mode is a security-positive choice

- WAL mode improves concurrent access safety and reduces the risk of database corruption from concurrent writes. The `busy_timeout=3000` prevents immediate lock failures, which could otherwise cause data loss if a caller does not handle `sqlite3.OperationalError` properly.

### Security Summary

No Critical or High severity findings. The attack surface is minimal -- a single function that creates a local SQLite database with hardcoded pragmas. The only surface to monitor is ensuring `db_path` remains configuration-controlled as the codebase grows.

---

## Follow-up Issues (proposed)

1. **Issue #3 (Migration framework)**: When implementing migrations, ensure SQL statements use parameterized queries (not string formatting) for any dynamic values. The migration runner should validate migration callables are from a trusted registry.
2. **Future**: Add a pytest fixture for `get_connection` that yields and auto-closes, reducing `try/finally` boilerplate across DB-related test files.
3. **Future**: Consider adding a `validate_db_path(path)` helper that constrains paths to an allowed base directory, for defense-in-depth when the dispatcher wires in configuration.

---

# PR #6 Review Notes -- Issue #3: Schema migration framework and schema_version table

> Reviewer: Claude Opus 4.6 (automated review)
> Date: 2026-02-20
> Branch: `feature/003-schema-migration`

---

## Code Review

### Acceptance Criteria Checklist

| Criterion | Status | Notes |
|-----------|--------|-------|
| `schema_version` table created with single row `version=0` if absent | PASS | `_ensure_version_table` uses `CREATE TABLE IF NOT EXISTS` and inserts `version=0` only when no row exists (line 30-31). |
| Migrations are Python callables registered in an ordered list | PASS | `_migrations: list[MigrationFn]` with `@register` decorator appending to the list. Index maps directly to migration version. |
| Each migration runs inside a transaction; version incremented on success | PASS | `conn.commit()` after each successful migration (line 65). SQLite's implicit transaction wraps the migration + version update. |
| Re-running on an up-to-date DB is a no-op | PASS | `current >= target` guard on line 52 returns immediately. Test `test_idempotent_on_rerun` verifies. |
| Failing migration rolls back and raises with clear message | PASS | `conn.rollback()` in `except` block (line 67). `RuntimeError` with formatted message including version number and original exception (line 68-70). |

### Required Tests

| Test | Status |
|------|--------|
| `test_fresh_db_gets_version_table` | PASS -- verifies `get_version` returns 0 and `schema_version` table exists in `sqlite_master` |
| `test_applies_migrations_sequentially` | PASS -- registers two migrations, asserts final version is 2, verifies both tables created |
| `test_idempotent_on_rerun` | PASS -- calls `migrate` twice, both return 1, no errors |
| `test_rollback_on_failure` | PASS -- first migration commits (version 1, `t_ok` exists), second raises `ValueError`, caught as `RuntimeError`, version stays at 1 |

### Findings

#### [Medium] No constraint preventing multiple rows in `schema_version`

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/migrations.py`, line 27
- The `schema_version` table is created with `(version INTEGER NOT NULL)` but has no PRIMARY KEY, UNIQUE constraint, or CHECK constraint limiting it to a single row. If a bug or manual intervention inserts a second row, `get_version` would return whichever row SQLite returns first from `SELECT version FROM schema_version` (non-deterministic without ORDER BY).
- **Action**: Consider adding a single-row constraint in a future migration (e.g., `CHECK (rowid = 1)` or a dummy `id INTEGER PRIMARY KEY CHECK (id = 1)` column). Not blocking for M1 since all writes go through `_ensure_version_table` which correctly checks before inserting.

#### [Low] Redundant `_ensure_version_table` calls

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/migrations.py`, lines 48-49
- `migrate()` calls `_ensure_version_table(conn)` on line 48, then calls `get_version(conn)` on line 49, which internally calls `_ensure_version_table` again. This results in two `CREATE TABLE IF NOT EXISTS` and two `SELECT version` queries on every `migrate` call.
- **Action**: Minor performance concern. Could be refactored so `migrate` calls `_ensure_version_table` once and reads the version directly. Not blocking.

#### [Info] Global mutable state for migrations registry

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/migrations.py`, line 15
- `_migrations` is a module-level mutable list. This is a common pattern for migration registries and works well for single-process applications. The test suite correctly saves/restores it via the `_clean_migrations` autouse fixture (lines 16-23 in test file).
- **Action**: None. This is an appropriate pattern for this use case. If multi-process or plugin-based architectures are introduced later, consider a class-based registry.

#### [Info] Test fixture properly isolates migration state

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/tests/test_migrations.py`, lines 16-23
- The `_clean_migrations` fixture saves the original list, clears it before each test, and restores it after. This prevents test pollution and is correctly marked `autouse=True`. The save-clear-yield-clear-extend pattern is the correct idiom.

#### [Info] `conn` fixture uses `get_connection` from `db` module

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/tests/test_migrations.py`, lines 27-31
- The test fixture uses `get_connection` (from Issue #2) rather than raw `sqlite3.connect`. This ensures WAL mode and `busy_timeout` pragmas are applied, matching production behavior. This is a good integration practice.

#### [Info] Coverage at 100%

- All 41 statements in `migrations.py` are covered by the 4 tests. No untested branches.

#### [Info] Error message includes original exception

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/migrations.py`, lines 68-70
- `raise RuntimeError(...) from exc` preserves the exception chain, making debugging easier. The message format `"Migration to version {N} failed: {exc}"` clearly identifies which migration failed. This follows the acceptance criterion for "clear message."

### Code Quality Summary

The implementation is clean, correct, and minimal:

- The `@register` decorator pattern is intuitive for defining migrations in order.
- Transaction semantics are correctly handled: commit on success, rollback on failure.
- The version update uses a parameterized query (`?` placeholder on line 63), avoiding SQL injection.
- Logging at appropriate levels: `info` for migration steps and completion, `debug` for up-to-date status.
- The code correctly handles the edge case where `current > target` (e.g., if migrations are removed), treating it the same as up-to-date.
- 100% test coverage with all four required tests present and passing.

**Verdict: APPROVE** -- no blocking issues. One medium finding (missing single-row constraint) noted for follow-up.

---

## Security Findings

### [Medium] S1: `schema_version` table lacks row-count constraint

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/migrations.py`, line 27
- **Description**: The `schema_version` table has no mechanism to enforce that exactly one row exists. While the application code only writes through `_ensure_version_table` (which checks before inserting) and `migrate` (which uses `UPDATE`), a direct SQL injection in a future module or manual DB editing could insert additional rows, causing `get_version` to return an unpredictable value. This could lead to migrations being skipped or re-applied.
- **Severity**: Medium (requires either a separate SQL injection vulnerability or direct DB access to exploit; impact is schema corruption)
- **Recommendation**: In the V1 schema migration (Issue #4), alter or recreate the table with a single-row constraint, e.g., `CREATE TABLE schema_version (id INTEGER PRIMARY KEY CHECK (id = 1), version INTEGER NOT NULL)`.

### [Info] S2: No SQL injection risk in migration runner

- All SQL in `migrations.py` uses either hardcoded string literals or parameterized queries (`?` on line 63 for the version update). The `MigrationFn` type receives a `Connection` object, and it is the responsibility of each registered migration to use parameterized queries. This is correctly documented in the PR #4 review follow-up.

### [Info] S3: Migration functions are trusted code

- The `@register` decorator appends arbitrary callables to the migration list. Since migrations are defined at module import time by the application developer (not by user input), there is no injection risk. The registry is not exposed to any user-facing API.

### [Info] S4: No hardcoded secrets or credentials

- No API keys, tokens, or secrets found in `migrations.py` or `test_migrations.py`.

### [Info] S5: No new dependencies introduced

- This module uses only Python standard library (`sqlite3`, `logging`, `typing`). No new entries in `pyproject.toml` dependencies.

### [Info] S6: Exception message does not leak sensitive data

- The `RuntimeError` message on line 69 includes the migration version number and the string representation of the original exception. In this context (local SQLite, no user-supplied data in migration functions), this does not leak sensitive information. If migrations ever process user data, the exception wrapping should be reviewed to avoid leaking PII in logs.

### Security Summary

No Critical or High severity findings. One Medium finding regarding the missing single-row constraint on `schema_version`, which could lead to schema version confusion if combined with a separate vulnerability that allows arbitrary SQL execution. The recommendation is to address this in the Issue #4 V1 schema migration.

---

## Follow-up Issues (proposed)

1. **Issue #4 (V1 schema)**: Add a single-row constraint to `schema_version` (e.g., `CHECK (id = 1)` on a primary key column) as part of the V1 migration to prevent version-table corruption.
2. **Future**: Refactor `migrate()` to avoid redundant `_ensure_version_table` calls for minor performance improvement.
3. **Future**: Consider adding a `--dry-run` mode to the migration runner that reports which migrations would be applied without executing them, useful for deployment verification.

---

# PR #8 Review Notes -- Issue #4: V1 schema migration -- projects, tasks, task_assignees, events

> Reviewer: Claude Opus 4.6 (automated review)
> Date: 2026-02-20
> Branch: `feature/004-v1-schema`

---

## Code Review

### Acceptance Criteria Checklist

| Criterion | Status | Notes |
|-----------|--------|-------|
| `projects` table with `ux_projects_shared_name` and `ux_projects_private_owner_name` partial unique indexes | PASS | Table created on lines 18-26, indexes on lines 28-36 of `schema_v1.py`. Partial `WHERE` clauses match PRD exactly. |
| `tasks` table with section and status CHECK constraints | PASS | Section CHECK on line 43 (`backlog, doing, waiting, done, drop`), status CHECK on line 45 (`open, done, dropped`). Both match PRD spec. |
| `task_assignees` table with composite PK and secondary index | PASS | Composite `PRIMARY KEY (task_id, assignee_user_id)` on line 57, secondary index `ix_task_assignees_user` on lines 61-64. |
| `events` audit table created | PASS | Table on lines 66-75. Columns match PRD. |
| Shared `Inbox` project auto-created (INSERT OR IGNORE) | PASS | Line 78-81 uses `INSERT OR IGNORE` with `('Inbox', 'shared', NULL)`. |
| `schema_version` = 1 after migration | PASS | Test `test_v1_schema_version` verifies `get_version(conn) == 1`. |

### Required Tests

| Test | Status |
|------|--------|
| `test_v1_tables_exist` | PASS -- verifies all four tables exist in `sqlite_master` |
| `test_v1_inbox_created` | PASS -- verifies name='Inbox', visibility='shared', owner_user_id=None |
| `test_v1_shared_unique_index_enforced` | PASS -- duplicate shared name raises `IntegrityError` |
| `test_v1_private_unique_index_enforced` | PASS -- duplicate (owner, name) raises `IntegrityError`; different owner succeeds |

### Findings

#### [High] F1: Foreign keys not enforced -- `PRAGMA foreign_keys=ON` missing

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/db.py`, line 35-37
- **Description**: SQLite does not enforce `REFERENCES` (foreign key) clauses by default. The `PRAGMA foreign_keys=ON` must be executed on every new connection for FK constraints to be active. Without this, the `REFERENCES projects(id)` on `tasks.project_id` and `REFERENCES tasks(id)` on `task_assignees.task_id` are purely decorative -- you can insert tasks pointing to non-existent projects and assignees pointing to non-existent tasks.
- **Impact**: Referential integrity is silently not enforced, leading to orphaned rows and data corruption.
- **Fix applied**: Added `conn.execute("PRAGMA foreign_keys=ON;")` to `get_connection()` in `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/db.py`, line 38. All 19 tests pass after the fix.

#### [Medium] F2: `schema_version` single-row constraint not added in V1

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/migrations.py`, line 27
- **Description**: The PR #6 review (Medium finding S1) recommended adding a single-row constraint to `schema_version` as part of the V1 migration. This was not addressed. The table still has no PK or CHECK constraint to prevent multiple rows.
- **Action**: Should be addressed in a follow-up issue. Adding it retroactively in a later migration (e.g., V2) would require recreating the table since SQLite does not support `ALTER TABLE ADD CONSTRAINT`.

#### [Low] F3: Minor PRD deviation on `events.ts` -- NOT NULL DEFAULT added

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/schema_v1.py`, line 69
- **Description**: The PRD spec for `events.ts` says `ts TEXT` with no nullability or default constraint. The implementation adds `NOT NULL DEFAULT (datetime('now'))`. This is a sensible enhancement (audit timestamps should always be present), but it is a deviation from the spec.
- **Action**: None needed. The implementation is better than the spec. Consider updating the PRD to match.

#### [Low] F4: `events.id` uses AUTOINCREMENT, PRD says PK only

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/schema_v1.py`, line 68
- **Description**: PRD says `id INTEGER PK` for the events table. The implementation uses `INTEGER PRIMARY KEY AUTOINCREMENT`. AUTOINCREMENT prevents rowid reuse after deletion, which is actually preferable for an audit log (guarantees monotonically increasing IDs). This is a minor deviation but a positive one.
- **Action**: None needed. Consider updating the PRD.

#### [Low] F5: No test for `task_assignees` composite PK enforcement

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/tests/test_schema_v1.py`
- **Description**: The acceptance criteria mention `task_assignees` table with composite PK, but there is no test verifying that inserting a duplicate `(task_id, assignee_user_id)` pair raises `IntegrityError`. The composite PK is created, but its enforcement is untested.
- **Action**: Add a test in a follow-up to insert a duplicate pair and assert `IntegrityError`.

#### [Low] F6: No test for foreign key enforcement

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/tests/test_schema_v1.py`
- **Description**: No test verifies that inserting a task with a non-existent `project_id` raises an error, or that inserting a `task_assignee` with a non-existent `task_id` raises an error. With the FK pragma fix (F1), these would now fail correctly, but there is no test coverage for this behavior.
- **Action**: Add FK enforcement tests in a follow-up.

#### [Info] F7: Test fixture pattern is well-structured

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/tests/test_schema_v1.py`, lines 11-25
- The `_load_v1_migration` autouse fixture correctly saves, clears, imports, and restores the migration registry. The `conn` fixture properly creates a temp DB, migrates, yields, and closes. This is clean test isolation.

#### [Info] F8: CHECK constraint tests are thorough

- Tests `test_v1_section_check_constraint` and `test_v1_status_check_constraint` go beyond the required tests to verify that invalid enum values are rejected. Good defensive testing.

#### [Info] F9: 8 tests total for V1 schema, all passing

- `test_v1_tables_exist`, `test_v1_schema_version`, `test_v1_inbox_created`, `test_v1_shared_unique_index_enforced`, `test_v1_private_unique_index_enforced`, `test_v1_section_check_constraint`, `test_v1_status_check_constraint` (7 tests in `test_schema_v1.py`). Plus the rollback test verifies `conn.rollback()` is correctly called after each constraint violation test.

### Code Quality Summary

The implementation is clean, correct, and closely follows the PRD spec:

- All four tables are created with the correct columns, types, and constraints.
- Partial unique indexes use the correct `WHERE` clause syntax.
- CHECK constraints enumerate exactly the values specified in the PRD.
- `INSERT OR IGNORE` for the Inbox seed is idempotent.
- Parameterized queries are not needed here (all DDL uses string literals with no interpolation).
- The `@register` decorator integrates seamlessly with the migration framework from Issue #3.
- Test coverage is good, with 7 tests covering table existence, version, seed data, unique indexes, and CHECK constraints.

**Verdict: APPROVE with one fix applied** -- the `PRAGMA foreign_keys=ON` fix (High, F1) has been applied directly. Medium/Low findings are noted for follow-up.

---

## Security Findings

### [High] S1: Foreign key constraints not enforced (FIXED)

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/db.py`, line 35-37
- **Description**: Without `PRAGMA foreign_keys=ON`, all `REFERENCES` clauses in the V1 schema are ignored. This means a future command handler could insert tasks referencing non-existent projects or assignees referencing non-existent tasks, leading to data integrity violations that are silent and hard to debug. In a multi-user Slack plugin, this could allow one user's actions to create orphaned records that cause errors for other users.
- **Severity**: High (data integrity violation in a multi-user context; silent failure mode)
- **Fix**: Added `conn.execute("PRAGMA foreign_keys=ON;")` to `get_connection()`. All 19 tests pass.

### [Medium] S2: `schema_version` table remains unprotected against multi-row corruption

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/migrations.py`, line 27
- **Description**: Carried forward from PR #6 review. The `schema_version` table has no constraint preventing insertion of additional rows. If a separate vulnerability allows arbitrary SQL execution, an attacker could manipulate the schema version to skip or re-run migrations.
- **Severity**: Medium (requires a chained vulnerability to exploit)
- **Recommendation**: Address in a future migration that recreates the table with a single-row constraint.

### [Info] S3: No SQL injection risk in V1 migration

- All SQL in `schema_v1.py` uses hardcoded string literals. No user input, no string interpolation, no parameterized queries needed. The `INSERT OR IGNORE` for the Inbox seed uses literal values only.

### [Info] S4: No hardcoded secrets or credentials

- No API keys, tokens, or secrets found in `schema_v1.py` or `test_schema_v1.py`.

### [Info] S5: No new dependencies introduced

- The V1 migration uses only Python standard library (`sqlite3`, `logging`). No new entries in `pyproject.toml`.

### [Info] S6: CHECK constraints provide defense-in-depth

- The `section` and `status` CHECK constraints on the `tasks` table prevent invalid enum values at the database level, not just the application level. This is a security-positive pattern that prevents data corruption even if the application layer has a bug.

### Security Summary

One High severity finding (S1: missing `PRAGMA foreign_keys=ON`) was identified and fixed directly in `db.py`. One Medium finding (S2: `schema_version` single-row constraint) is carried forward from the previous review. No Critical findings.

---

## Follow-up Issues (proposed)

1. **Test coverage**: Add tests for `task_assignees` composite PK enforcement (duplicate pair should raise `IntegrityError`).
2. **Test coverage**: Add tests for foreign key enforcement (task with non-existent `project_id`, assignee with non-existent `task_id` should raise `IntegrityError` now that FK pragma is enabled).
3. **Schema version constraint**: Address the `schema_version` single-row constraint in a future migration (V2 or later) by recreating the table with `CHECK (id = 1)`.
4. **PRD sync**: Update PRD section 6.3 to add `NOT NULL DEFAULT (datetime('now'))` to `events.ts` and `AUTOINCREMENT` to `events.id` to match the implementation.
5. **DB module**: Add a test for `PRAGMA foreign_keys` returning `1` in `test_db.py` to prevent regression.

---

# PR #10 Review Notes -- Issue #5: Command parser -- tokenizer and option extraction

> Reviewer: Claude Opus 4.6 (automated review)
> Date: 2026-02-20
> Branch: `feature/005-parser-tokenizer`

---

## Code Review

### Acceptance Criteria Checklist

| Criterion | Status | Notes |
|-----------|--------|-------|
| `/p MyProject` correctly extracted; token consumed | PASS | `test_extract_project` verifies project name extracted, `/p` and value removed from `title_tokens`. |
| `/s doing` validated; invalid section raises `ParseError` | PASS | `test_extract_section_valid` and `test_extract_section_invalid` cover both paths. Case-insensitive via `.lower()`. |
| `due:03-15` normalised to `2026-03-15` (current year) | PASS | `test_due_mm_dd_normalisation` verifies with `date.today().year`. |
| `due:2026-02-30` raises `ParseError` (invalid date) | PASS | `test_due_invalid_date` asserts `ParseError` with match on "Invalid due date". |
| `<@U12345>` extracted into mentions list | PASS | `test_mentions_extraction` verifies two mentions extracted and not in `title_tokens`. |
| Multiple mentions supported | PASS | Same test covers two mentions in order. |
| Title tokens are non-option, non-mention tokens before first option | PASS | `test_title_extraction` verifies correct split with mixed options. Note: title tokens are collected from *all* positions, not just "before first option" -- this is arguably more flexible than the AC wording. |

### Required Tests

| Test | Status |
|------|--------|
| `test_extract_project` | PASS |
| `test_extract_section_valid` | PASS |
| `test_extract_section_invalid` | PASS |
| `test_due_mm_dd_normalisation` | PASS |
| `test_due_full_date` | PASS |
| `test_due_invalid_date` | PASS |
| `test_due_clear` | PASS |
| `test_mentions_extraction` | PASS |
| `test_title_extraction` | PASS |

All 9 required tests present and passing. 4 additional bonus tests (`test_command_extraction`, `test_move_extracts_id_as_arg`, `test_empty_command_raises`, `test_section_case_insensitive`). 13 parser tests total.

### Findings

#### [Medium] F1: Leap-year bug in `_normalise_due` for MM-DD format (FIXED)

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/parser.py`, lines 53-62 (after fix)
- **Description**: The original implementation used `datetime.strptime(raw, "%m-%d")` which defaults to year 1900 (not a leap year). This caused `due:02-29` to always be rejected, even when the current year is a leap year (e.g., 2028). The `replace(year=current_year)` call was never reached because `strptime` itself raised `ValueError`.
- **Fix applied**: Replaced `strptime("%m-%d")` with a regex match `(\d{1,2})-(\d{1,2})` followed by direct `date(current_year, month, day)` construction. This correctly validates Feb 29 against the actual current year.
- **Impact**: Without fix, `due:02-29` would fail in leap years (2028, 2032, etc.) when it should succeed.

#### [Low] F2: Duplicate options silently use "last wins" semantics

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/parser.py`, lines 91-117
- **Description**: If a user provides `/p First /p Second`, the parser silently uses `Second`. Same for `/s` and `due:`. This is not necessarily wrong, but it is undocumented. "Last wins" is a reasonable default, but "first wins" or "raise error on duplicate" are also valid choices.
- **Action**: Document the "last wins" behavior in the docstring or PRD. No code change needed.

#### [Low] F3: `/p` and `/s` error paths (missing argument) are untested

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/tests/test_parser.py`
- **Description**: Lines 93 and 101 (`raise ParseError("/p requires a project name")` and `/s` equivalent) are uncovered. Manual testing confirmed they work correctly, but automated test coverage is missing for these edge cases.
- **Action**: Add tests for `parse("add task /p")` and `parse("add task /s")` in a follow-up.

#### [Low] F4: `_DUE_RE` uses `.+` which accepts any characters after `due:`

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/parser.py`, line 15
- **Description**: `_DUE_RE = re.compile(r"^due:(.+)$")` will match `due:anything` and pass the value to `_normalise_due`. This is not a bug since `_normalise_due` properly validates the value, but a tighter regex like `r"^due:([\d-]+)$"` would reject obviously invalid inputs earlier and serve as documentation of expected format.
- **Action**: Optional tightening. Not blocking since validation is correct.

#### [Low] F5: Title tokens are collected from all positions, not just "before first option"

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/parser.py`, lines 126-128
- **Description**: The AC says "Title tokens are non-option, non-mention tokens before first option." The implementation collects title tokens from all positions (e.g., `add Buy /p Home milk` would produce `title_tokens=["Buy", "milk"]`). This is actually more flexible and user-friendly, but deviates from the literal AC wording.
- **Action**: Consider updating the AC to match the implementation. The current behavior is better for UX.

#### [Info] F6: `args` extraction for `move/done/drop/edit` is well-designed

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/parser.py`, lines 130-133
- The pattern of extracting the first title token as `args[0]` for ID-based commands is clean and tested by `test_move_extracts_id_as_arg`.

#### [Info] F7: Coverage at 97%

- Lines 93 and 101 (error paths for missing `/p` and `/s` arguments) are uncovered. All other branches are tested. This is acceptable for M1.

#### [Info] F8: Bonus tests add good defensive coverage

- `test_section_case_insensitive` ensures `/s DOING` normalizes to `doing`.
- `test_command_extraction` verifies the first token becomes the command.
- `test_empty_command_raises` covers the empty input guard.
- `test_move_extracts_id_as_arg` covers the args extraction logic.

### Code Quality Summary

The implementation is clean, correct, and well-structured:

- The tokenizer loop with explicit index management (`while i < len(remaining)`) is readable and handles two-token options (`/p`, `/s`) cleanly by advancing `i` by 2.
- `ParsedCommand` dataclass provides a clear, typed result structure.
- `VALID_SECTIONS` as a `frozenset` is the right choice for O(1) membership testing.
- `_MENTION_RE` uses `fullmatch` (not `match` or `search`), preventing partial matches on tokens like `<@U123>extra`.
- Error messages are descriptive and include the invalid value with `repr()` formatting.
- Logging at debug level for parsed results is appropriate.
- 97% test coverage with all 9 required tests present and 4 bonus tests.

**Verdict: APPROVE with one fix applied** -- the leap-year bug in `_normalise_due` (Medium, F1) has been fixed directly. Low findings are noted for follow-up.

---

## Security Findings

### [Medium] S1: Leap-year date validation bypass (FIXED)

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/parser.py`, `_normalise_due`
- **Description**: The original `strptime("%m-%d")` approach silently rejected valid dates (`02-29` in leap years) due to the 1900 default year. While this is a correctness issue rather than a security vulnerability, incorrect date validation can lead to denial of service (users unable to set valid due dates) and data integrity issues (dates that should be accepted are rejected).
- **Severity**: Medium (correctness bug with functional impact)
- **Fix**: Replaced with regex-based month/day extraction and direct `date()` construction with the current year.

### [Low] S2: No ReDoS risk in compiled regexes

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/parser.py`, lines 14-15
- **Description**: Both `_MENTION_RE = re.compile(r"<@(U[A-Z0-9]+)>")` and `_DUE_RE = re.compile(r"^due:(.+)$")` were tested with 100,000-character inputs and completed in under 0.1ms. Neither pattern contains nested quantifiers or alternation that could cause catastrophic backtracking.
- **Severity**: Low (no risk found, noting for completeness)

### [Low] S3: No input length validation on parser input

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/parser.py`, line 72
- **Description**: `parse(text)` accepts arbitrarily long strings. `text.strip().split()` will allocate a token list proportional to input size. Slack limits messages to ~40,000 characters, mitigating this at the transport layer, but if the parser is used outside Slack, extremely long inputs could cause memory pressure.
- **Severity**: Low (mitigated by Slack transport layer limits)
- **Recommendation**: Consider adding a max-length guard in the plugin entry point (`handle_message`) rather than the parser itself.

### [Info] S4: No injection risks

- The parser only tokenizes and validates strings. No SQL, no shell commands, no template rendering. User input flows into `ParsedCommand` fields which are plain strings. Security depends on how these values are consumed downstream (e.g., parameterized queries when writing to SQLite).

### [Info] S5: No hardcoded secrets or credentials

- No API keys, tokens, or secrets found in `parser.py` or `test_parser.py`.

### [Info] S6: No new dependencies introduced

- The parser uses only Python standard library (`re`, `datetime`, `dataclasses`, `logging`). No new entries in `pyproject.toml`.

### Security Summary

No Critical or High severity findings. One Medium finding (S1: leap-year date validation) was identified and fixed. The parser has a minimal attack surface -- it tokenizes strings and validates against known patterns. The main security consideration going forward is ensuring that `ParsedCommand` field values are used safely downstream (parameterized SQL queries, no raw echo in web contexts).

---

## Follow-up Issues (proposed)

1. **Test coverage**: Add tests for `/p` and `/s` without arguments (lines 93, 101) to cover the missing-argument error paths.
2. **Documentation**: Document "last wins" semantics for duplicate `/p`, `/s`, and `due:` options in the PRD or parser docstring.
3. **Optional**: Tighten `_DUE_RE` from `.+` to `[\d-]+` for earlier rejection of obviously invalid due values.
4. **AC clarification**: Update Issue #5 AC to reflect that title tokens are collected from all positions (not just "before first option"), matching the implemented behavior.

---

# PR #12 Review Notes -- Issue #7: Project resolver helper

> Reviewer: Claude Opus 4.6 (automated review)
> Date: 2026-02-20
> Branch: `feature/007-project-resolver`
# PR #14 Review Notes -- Issue #16: Command dispatcher and routing

> Reviewer: Claude Opus 4.6 (automated review)
> Date: 2026-02-20
> Branch: `feature-016-dispatcher`

---

## Code Review

### Acceptance Criteria Checklist

| Criterion | Status | Notes |
|-----------|--------|-------|
| Private project of sender matched first | PASS | Query on line 38-42 filters by `visibility = 'private' AND owner_user_id = ?`. Test `test_private_takes_priority` verifies. |
| Falls back to shared if no private match | PASS | Second query on line 52-56 filters by `visibility = 'shared'`. Test `test_falls_back_to_shared` verifies. |
| Returns error when neither exists (except Inbox auto-created) | PASS | `ProjectNotFoundError` raised on line 84. Inbox auto-created on lines 66-81. Tests `test_unknown_project_error` and `test_inbox_auto_created` verify. |
| Returns project row with id, name, visibility, owner_user_id | PASS | `Project` dataclass on lines 17-23 with all four fields. All tests assert on these fields. |

### Required Tests

| Test | Status |
|------|--------|
| `test_private_takes_priority` | PASS -- creates both shared and private "Work", verifies private is returned for owner U1 |
| `test_falls_back_to_shared` | PASS -- creates shared "Team" only, verifies shared returned for U1 |
| `test_inbox_auto_created` | PASS -- deletes seeded Inbox, verifies auto-creation as shared with null owner |
| `test_unknown_project_error` | PASS -- verifies `ProjectNotFoundError` raised with descriptive message |

All 4 required tests present and passing. 2 additional bonus tests (`test_inbox_already_exists`, `test_private_different_owner_not_matched`). 6 tests total.

### Findings

#### [Low] F1: Project name matching is case-sensitive

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/.worktrees/feature-007-project-resolver/src/openclaw_todo/project_resolver.py`, lines 39-42
- **Description**: The SQL queries use `WHERE name = ?` which is case-sensitive in SQLite by default (for ASCII). If a user types `/p work` but the project is named `Work`, it will not match. The PRD does not specify case-sensitivity behavior, so this is not a bug per se, but it could cause user confusion.
- **Action**: Document the case-sensitive behavior. Consider adding `COLLATE NOCASE` in a future iteration if case-insensitive matching is desired.

#### [Low] F2: Repeated `Project(id=row[0], ...)` construction pattern

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/.worktrees/feature-007-project-resolver/src/openclaw_todo/project_resolver.py`, lines 44, 58, 76
- **Description**: The same `Project(id=row[0], name=row[1], visibility=row[2], owner_user_id=row[3])` pattern appears three times. This could be extracted to a helper (e.g., `Project._from_row(row)` classmethod or a module-level `_row_to_project` function) to reduce duplication and ensure consistency if columns change.
- **Action**: Optional refactor. Not blocking for M1.

#### [Low] F3: `conn.commit()` called inside resolver for Inbox auto-creation

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/.worktrees/feature-007-project-resolver/src/openclaw_todo/project_resolver.py`, line 71
- **Description**: The resolver calls `conn.commit()` directly after the `INSERT OR IGNORE` for Inbox auto-creation. This commits any pending transaction state on the connection, which could be surprising if the caller has uncommitted changes. In the current codebase this is not an issue (resolver is called early in command handling), but it couples the resolver to transaction management.
- **Action**: Consider whether the caller should be responsible for committing. For M1 this is acceptable since the auto-creation is a one-time idempotent operation.

#### [Low] F4: No test for Inbox auto-creation when a private Inbox exists

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/.worktrees/feature-007-project-resolver/tests/test_project_resolver.py`
- **Description**: If a user has a private project named "Inbox", `resolve_project(conn, "Inbox", user_id)` will return the private project (step 1 matches). The auto-creation path (step 3) is only reached if neither private nor shared "Inbox" exists. This behavior is correct per the resolution order, but there is no test covering the scenario where a user has a private "Inbox" and the shared "Inbox" also exists -- the test should verify that the private one is returned.
- **Action**: Add a test for this edge case in a follow-up.

#### [Info] F5: `INSERT OR IGNORE` is the correct pattern for Inbox auto-creation

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/.worktrees/feature-007-project-resolver/src/openclaw_todo/project_resolver.py`, lines 67-70
- `INSERT OR IGNORE` handles the race condition where two concurrent requests try to auto-create Inbox simultaneously. The `ux_projects_shared_name` unique index on `(name) WHERE visibility = 'shared'` ensures only one shared Inbox can exist. The subsequent `SELECT` on lines 72-75 guarantees we return the correct row regardless of whether this request or another one performed the insert. This is well-designed.

#### [Info] F6: Bonus tests add good defensive coverage

- `test_inbox_already_exists` verifies that the seeded Inbox (from V1 migration) resolves without triggering auto-creation.
- `test_private_different_owner_not_matched` verifies that a private project owned by U2 is not visible to U1, correctly raising `ProjectNotFoundError`.

#### [Info] F7: Coverage at 100%

- All 31 statements in `project_resolver.py` are covered by the 6 tests. No untested branches.

#### [Info] F8: Test fixture pattern is consistent with prior PRs

- The `_load_v1` autouse fixture and `conn` fixture follow the same save-clear-restore pattern established in prior PRs. Good consistency.

### Code Quality Summary

The implementation is clean, correct, and follows the PRD resolution order exactly:

- Three-step resolution (private -> shared -> Inbox auto-create) with clear fallthrough logic.
- All SQL queries use parameterized placeholders (`?`), preventing SQL injection.
- `Project` dataclass provides a typed result with the four required fields.
- `ProjectNotFoundError` is a well-named custom exception with descriptive message.
- Logging at debug level for each resolution path aids troubleshooting.
- `INSERT OR IGNORE` handles concurrent Inbox auto-creation safely.
- 100% test coverage with all 4 required tests and 2 valuable bonus tests.
- The code is 85 lines total -- minimal and readable.

**Verdict: APPROVE** -- no Critical or High findings. All Low findings are noted for follow-up.
### Changed Files

| File | Change | Lines |
|------|--------|-------|
| `src/openclaw_todo/dispatcher.py` | NEW | 116 |
| `src/openclaw_todo/plugin.py` | MODIFIED | 33 |
| `tests/test_dispatcher.py` | NEW | 152 |
| `tests/test_plugin.py` | MODIFIED | 39 |

### Architecture Overview

The dispatcher implements a two-level routing architecture:

1. **Plugin layer** (`plugin.py`): Strips `/todo` prefix, returns USAGE for bare `/todo`, delegates remainder to `dispatch()`.
2. **Dispatcher layer** (`dispatcher.py`): Parses the remainder via the parser, validates command name against `_VALID_COMMANDS`, opens a DB connection with migration, routes to the appropriate handler (or stub), and closes the connection in a `finally` block.
3. **Project sub-routing**: `project` command delegates to `_dispatch_project()` which extracts the subcommand from `parsed.title_tokens` and routes to `project_<subcommand>` handlers in the registry.

### Findings

#### [Low] F1: Weak test assertion on stub handler (FIXED)

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/.worktrees/feature-016-dispatcher/tests/test_dispatcher.py`, line 48
- **Description**: The original assertion was:
  ```python
  assert "not yet implemented" in result.lower() or isinstance(result, str)
  ```
  The `isinstance(result, str)` clause makes this trivially true since `dispatch()` always returns `str`. The test does not actually verify that the stub handler was invoked -- any string return would pass.
- **Fix applied**: Removed the `or isinstance(result, str)` fallback. The assertion now strictly verifies that the stub handler message is present:
  ```python
  assert "not yet implemented" in result.lower()
  ```
- **Impact**: Test now correctly fails if the stub handler message format changes or if a different code path is taken.

#### [Low] F2: `_stub_handler` signature differs from `HandlerFn` type alias

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/.worktrees/feature-016-dispatcher/src/openclaw_todo/dispatcher.py`, lines 17, 47
- **Description**: The `HandlerFn` type alias is `Callable[[ParsedCommand, Connection, dict], str]` (3 args), but `_stub_handler` takes 4 args: `(command, parsed, conn, context)`. This works because `_stub_handler` is never registered directly in `_handlers` -- it is always called via a lambda wrapper in `_get_handler` (line 59) and `_dispatch_project` (line 115) that captures `command` via closure. However, the mismatch makes the code harder to follow at a glance.
- **Action**: Consider refactoring `_stub_handler` to accept `(parsed, conn, context)` and derive the command name from `parsed.command`. Not blocking since the current approach is correct.

#### [Low] F3: Long line in `_dispatch_project`

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/.worktrees/feature-016-dispatcher/src/openclaw_todo/dispatcher.py`, line 115
- **Description**: Line 115 is 116 characters, exceeding typical line length limits (88 for black, 100 for many projects). The lambda + `_handlers.get` + `_stub_handler` call is dense.
- **Action**: Consider breaking into multiple lines for readability. Not blocking.

#### [Low] F4: Global mutable `_handlers` dict shared across tests

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/.worktrees/feature-016-dispatcher/src/openclaw_todo/dispatcher.py`, line 54
- **Description**: The `_handlers` dict is module-level mutable state. The test fixture `_clean_handlers` (test file line 22-28) correctly saves and restores it between tests. However, if the test suite were run in parallel (e.g., `pytest-xdist`), the shared state could cause flaky tests.
- **Action**: For a single-process Slack plugin this is fine. Document the limitation if parallel test execution is ever introduced.

#### [Info] F5: DB connection lifecycle is correct

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/.worktrees/feature-016-dispatcher/src/openclaw_todo/dispatcher.py`, lines 86-94
- The `dispatch()` function opens the DB connection *after* validating the command name (line 80-82 returns early for unknown commands without touching the DB). The connection is always closed in a `finally` block (line 94), ensuring no leaks even if handlers raise exceptions. This is good resource management.

#### [Info] F6: Unknown commands do not open a DB connection

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/.worktrees/feature-016-dispatcher/src/openclaw_todo/dispatcher.py`, line 80-82
- The `if command not in _VALID_COMMANDS` check returns before `_init_db()` is called. This avoids unnecessary DB initialization for typos and invalid commands. Good design.

#### [Info] F7: Parse errors are caught and returned as user-facing messages

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/.worktrees/feature-016-dispatcher/src/openclaw_todo/dispatcher.py`, lines 73-76
- `ParseError` is caught and formatted as `f"Parse error: {exc}"`. The parser's error messages are descriptive (e.g., "Invalid section: 'xyz'") and do not leak internal details. This is appropriate for a Slack DM context.

#### [Info] F8: Plugin entry-point correctly wired to dispatcher

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/.worktrees/feature-016-dispatcher/src/openclaw_todo/plugin.py`
- The `handle_message()` function now delegates to `dispatch()` instead of the previous placeholder response. The prefix matching logic is unchanged and still correct. The `db_path` parameter flows through to `dispatch()` for testability.

#### [Info] F9: Schema import triggers migration registration

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/.worktrees/feature-016-dispatcher/src/openclaw_todo/dispatcher.py`, line 14
- `import openclaw_todo.schema_v1 as _schema_v1` with `# noqa: F401` ensures the `@register` decorator in `schema_v1.py` runs at import time, populating the migration registry before any `migrate()` call. This is the correct pattern for the decorator-based migration system.

#### [Info] F10: Test coverage is comprehensive

- 20 dispatcher + plugin tests covering:
  - All 7 non-project commands routed to stubs (parametrized)
  - Custom handler registration and invocation
  - All 3 project subcommands routed correctly
  - Project with no subcommand returns usage
  - Unknown project subcommand returns error
  - Unknown top-level command returns error with usage
  - Parse error propagation
  - DB initialization with schema migration
  - Plugin prefix matching (non-todo, todo, whitespace, bare /todo)

### Code Quality Summary

The dispatcher implementation is clean, well-structured, and follows good design principles:

- **Separation of concerns**: Plugin handles prefix matching; dispatcher handles parsing, validation, DB init, and routing. Each has a single responsibility.
- **Resource safety**: DB connection opened late (only for valid commands) and closed in `finally`.
- **Extensibility**: The `register_handler()` function provides a clean API for future command implementations to plug in without modifying the dispatcher.
- **Defensive routing**: Unknown commands and parse errors return helpful user-facing messages without touching the DB or raising unhandled exceptions.
- **Project sub-routing**: The `project_<subcommand>` naming convention with `replace('-', '_')` is a clean pattern for hyphenated subcommands.
- **Test isolation**: The `_clean_handlers` autouse fixture properly saves and restores the handler registry between tests.

**Verdict: APPROVE with one fix applied** -- the weak test assertion (Low, F1) has been strengthened. No Critical or High code quality issues found.

---

## Security Findings

### [Low] S1: No SQL injection risk -- parameterized queries used throughout

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/.worktrees/feature-007-project-resolver/src/openclaw_todo/project_resolver.py`, lines 38-42, 52-56
- **Description**: All SQL queries use `?` parameter placeholders for user-supplied values (`name` and `sender_id`). The Inbox auto-creation on lines 67-75 uses hardcoded string literals only. No string interpolation or f-strings are used in any SQL statement.
- **Severity**: Low (no risk found, noting for completeness)

### [Low] S2: `name` parameter is not length-validated

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/.worktrees/feature-007-project-resolver/src/openclaw_todo/project_resolver.py`, line 27
- **Description**: `resolve_project(conn, name, sender_id)` accepts arbitrarily long `name` strings. While SQLite handles this safely (TEXT has no inherent length limit), an extremely long name would result in unnecessary query execution against the database. The parser upstream (Issue #5) extracts project names from `/p <name>` tokens, and Slack limits message length to ~40,000 characters, providing transport-layer mitigation.
- **Severity**: Low (mitigated by upstream constraints)
- **Recommendation**: Consider adding a max-length check for project names in the parser or a future validation layer.

### [Low] S3: Inbox auto-creation commits transaction implicitly

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/.worktrees/feature-007-project-resolver/src/openclaw_todo/project_resolver.py`, line 71
- **Description**: `conn.commit()` inside the resolver commits all pending changes on the connection, not just the Inbox insert. If a future caller has uncommitted writes before calling `resolve_project`, those writes would be committed as a side effect. This is not exploitable but could lead to partial commits in error scenarios.
- **Severity**: Low (no current exploit path; architectural concern)
- **Recommendation**: Consider using a savepoint pattern (`SAVEPOINT` / `RELEASE`) for the Inbox auto-creation to isolate its transaction from any outer transaction.

### [Info] S4: No hardcoded secrets or credentials

- No API keys, tokens, or secrets found in `project_resolver.py` or `test_project_resolver.py`.

### [Info] S5: No new dependencies introduced

- The module uses only Python standard library (`sqlite3`, `dataclasses`, `logging`). No new entries in `pyproject.toml`.

### [Info] S6: Authorization model is correctly scoped

- The `sender_id` parameter is used correctly in the private-project query to scope visibility. User U1 cannot resolve another user's private projects. Test `test_private_different_owner_not_matched` explicitly verifies this isolation. The shared-project query correctly omits owner filtering, as shared projects are visible to all users.

### Security Summary

No Critical, High, or Medium severity findings. The implementation has a minimal attack surface -- three read queries and one idempotent insert, all using parameterized queries. The authorization model (private scoped to sender, shared visible to all) is correctly implemented and tested. Three Low findings are noted for awareness but require no immediate action.
### [Low] S1: User input reflected in error messages

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/.worktrees/feature-016-dispatcher/src/openclaw_todo/dispatcher.py`, lines 76, 82, 110
- **Description**: Three error paths echo user-supplied values back in responses:
  - `f"Parse error: {exc}"` (line 76) -- parser error messages may contain raw user input
  - `f"Unknown command: '{command}'\n{USAGE}"` (line 82) -- the command name is user input
  - `f"Unknown project subcommand: '{sub}'\n{PROJECT_USAGE}"` (line 110) -- the subcommand is user input
- **Severity**: Low. In the Slack DM context, Slack handles message escaping. The reflected values are single tokens (no spaces, limited characters after `split()` tokenization). No HTML/JS injection is possible in this context.
- **Recommendation**: If the plugin ever serves responses in a web context (e.g., dashboard, webhook response viewer), sanitize reflected values. No fix needed for current Slack-only usage.

### [Low] S2: No input length validation at dispatcher level

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/.worktrees/feature-016-dispatcher/src/openclaw_todo/dispatcher.py`, line 67
- **Description**: `dispatch(text, ...)` accepts arbitrarily long strings, which flow to `parse()` for tokenization. Slack limits messages to approximately 40,000 characters, providing transport-layer mitigation.
- **Severity**: Low (mitigated by Slack transport layer)
- **Recommendation**: Consider adding a max-length guard in `handle_message()` if the plugin is ever exposed outside Slack.

### [Low] S3: Handler exception propagation

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/.worktrees/feature-016-dispatcher/src/openclaw_todo/dispatcher.py`, lines 91-92
- **Description**: If a registered handler raises an unhandled exception, it propagates up through `dispatch()`. The `finally` block ensures the DB connection is closed, but the exception itself is not caught. In the current architecture, the caller (`handle_message` in `plugin.py`) does not catch exceptions either, so an unhandled handler error would propagate to the gateway framework.
- **Severity**: Low. The stub handlers cannot raise exceptions (they return strings). Future handler implementations should handle their own errors. A catch-all `except Exception` in `dispatch()` could provide defense-in-depth but would also mask bugs during development.
- **Recommendation**: Consider adding a top-level exception handler in `dispatch()` that logs the error and returns a generic "Internal error" message, once real handlers are implemented. During development, letting exceptions propagate is acceptable.

### [Info] S4: No SQL injection risk

- The dispatcher does not execute any SQL directly. DB interaction is limited to `_init_db()` which calls `get_connection()` and `migrate()` -- both use hardcoded SQL or parameterized queries. User input flows through `ParsedCommand` fields to handlers, which are responsible for using parameterized queries.

### [Info] S5: No hardcoded secrets or credentials

- No API keys, tokens, or secrets found in `dispatcher.py`, `plugin.py`, or their test files.

### [Info] S6: `db_path` parameter is configuration-controlled

- The `db_path` parameter in `dispatch()` and `handle_message()` flows from the caller (gateway framework), not from user input. In tests, it comes from `tmp_path`. There is no code path where a user's message text influences the DB path.

### [Info] S7: No new dependencies introduced

- The dispatcher uses only Python standard library (`sqlite3`, `logging`, `typing`) plus internal modules (`db`, `migrations`, `parser`, `schema_v1`). No new entries in `pyproject.toml`.

### Security Summary

No Critical or High severity findings. Three Low findings related to input reflection, length validation, and exception propagation are noted. The dispatcher has a minimal attack surface -- it validates commands against a whitelist, delegates parsing to the parser, and routes to registered handlers. The main security consideration for future work is ensuring that handler implementations use parameterized queries and handle their own exceptions gracefully.

---

## Follow-up Issues (proposed)

1. **Refactor**: Extract `Project(id=row[0], ...)` into a `_row_to_project(row)` helper or `Project.from_row(row)` classmethod to reduce the triple duplication.
2. **Test coverage**: Add a test for the edge case where a user has a private "Inbox" project and the shared "Inbox" also exists, verifying the private one is returned.
3. **Transaction safety**: Consider using `SAVEPOINT` / `RELEASE` for Inbox auto-creation instead of bare `conn.commit()` to avoid committing unrelated pending changes.
4. **Case sensitivity**: Document that project name matching is case-sensitive. Consider `COLLATE NOCASE` if case-insensitive matching is desired in a future iteration.
5. **Input validation**: Add a max-length check for project names in the parser or validation layer to prevent unnecessarily large queries.
1. **Exception handling**: Add a top-level `try/except` in `dispatch()` that catches unexpected handler exceptions, logs them at error level, and returns a generic user-facing error message. Defer until real handlers are implemented.
2. **Refactor `_stub_handler`**: Align `_stub_handler` signature with `HandlerFn` type alias by deriving the command name from `parsed.command` instead of passing it as a separate argument. This also eliminates the lambda wrappers in `_get_handler` and `_dispatch_project`.
3. **Line length**: Break the long line 115 in `_dispatch_project` for readability.
4. **Context typing**: Introduce a `TypedDict` or dataclass for the `context` parameter (e.g., `class DispatchContext(TypedDict): sender_id: str`) to enable static type checking.
5. **Input length guard**: Add a max-length check (e.g., 5000 chars) in `handle_message()` as defense-in-depth against oversized inputs.

---

# PR #18 Review Notes -- Issue #6: /todo add command

> Reviewer: Claude Opus 4.6 (automated review)
> Date: 2026-02-20
> Branch: `feature/006-cmd-add`

---

## Code Review

### Acceptance Criteria Checklist

| Criterion | Status | Notes |
|-----------|--------|-------|
| Task inserted with correct project_id, section, due, status='open', created_by | PASS | `test_add_default_inbox` and `test_add_with_project_section_due` verify all fields in DB |
| Assignees default to sender when no mentions | PASS | `test_add_assignee_defaults_to_sender` verifies `task_assignees` row matches sender |
| Multiple mentions create multiple task_assignee rows | PASS | `test_add_multiple_assignees` verifies two rows inserted and present in response |
| Private project + non-owner assignee returns warning and does NOT insert | PASS | `test_add_private_rejects_other_assignee` verifies warning message and zero task rows |
| Non-existent project: `Inbox` auto-created; others return error | PASS | `test_add_default_inbox` uses seeded Inbox; `test_add_nonexistent_project_returns_error` verifies error |
| Response format: `Added #<id> (<project>/<section>) due:<due\|-> assignees:<mentions> -- <title>` | PASS | All happy-path tests assert on this format |
| Event row written to `events` table | PASS | `test_event_logged` verifies actor, action, task_id, and JSON payload fields |

### Required Tests

| Test | Status |
|------|--------|
| `test_add_default_inbox` | PASS |
| `test_add_with_project_section_due` | PASS |
| `test_add_private_rejects_other_assignee` | PASS |
| `test_add_assignee_defaults_to_sender` | PASS |
| `test_add_multiple_assignees` | PASS |

All 5 required tests present and passing. 5 additional tests (`test_add_private_allows_owner_assignee`, `test_event_logged`, `test_add_empty_title_returns_error`, `test_add_nonexistent_project_returns_error`, `test_add_due_clear_sentinel_stored_as_null`). 10 tests total.

### Findings

#### [Info] F1: No explicit transaction wrapping for multi-statement write

- **File**: `src/openclaw_todo/cmd_add.py`, lines 52-80
- **Description**: The handler performs three sequential writes (task INSERT, assignee INSERTs, event INSERT) followed by a single `conn.commit()` at line 80. If any write after the task INSERT raises (e.g., duplicate assignee PK violation), partial writes remain uncommitted. SQLite's implicit rollback-on-close in the dispatcher's `finally` block protects data integrity.
- **Action**: Consider wrapping in `with conn:` (context manager) for explicit transaction semantics in a future refactor. No functional bug today.

#### [Info] F2: Missing `sender_id` key would raise unhandled KeyError

- **File**: `src/openclaw_todo/cmd_add.py`, line 22
- **Description**: `context["sender_id"]` raises `KeyError` if the key is absent. The dispatcher contract requires `sender_id` in context, so this is defensive-coding territory.
- **Action**: Acceptable. Could be improved with `.get()` + early return, but low priority given the documented contract.

#### [Info] F3: Test gap -- non-owner sender adding to another user's private project

- **File**: `tests/test_cmd_add.py`
- **Description**: No test covers the case where sender U2 tries to add a task to a private project owned by U1. The `resolve_project()` function would return `ProjectNotFoundError` (it only matches private projects of the sender), which is correct behavior. However, there is no explicit test verifying this path through `add_handler`.
- **Action**: Follow-up item. Add a test for "non-owner sender cannot resolve another user's private project."

#### [Info] F4: Title length is unbounded

- **File**: `src/openclaw_todo/cmd_add.py`, line 23
- **Description**: No max-length check on `title`. Slack messages cap at ~4000 chars, providing natural limits. The DB column is `TEXT NOT NULL` with no length constraint.
- **Action**: Consider adding a max-length check if the handler is exposed outside Slack.

#### [Info] F5: Dispatcher test correctly updated

- **File**: `tests/test_dispatcher.py`, lines 34-51
- **Description**: The parametrized stub test removed `"add"` from the stub-check list and added a dedicated `test_add_routes_to_handler` test that asserts `"Added #"` in the result. This correctly reflects that `add` is no longer a stub.

### Code Quality Summary

The implementation is clean, minimal, and correct:

- Uses `resolve_project()` for project resolution following PRD Option A (private-first).
- Private assignee validation correctly rejects non-owner assignees with a descriptive warning.
- All SQL uses parameterized queries (`?` placeholders).
- Event payload is well-structured JSON with title, project, section, due, and assignees.
- Response format matches the PRD/UX spec exactly.
- 10 tests with thorough assertions on both the response string and DB state.
- No unnecessary complexity or over-engineering.

**Verdict: APPROVE** -- no blocking issues. No fixes required.

---

## Security Findings

### [Info] S1: SQL injection -- No risk

- **File**: `src/openclaw_todo/cmd_add.py`, lines 52-78
- **Description**: All three SQL statements (task INSERT, assignee INSERT, event INSERT) use `?` parameter placeholders. No string interpolation or f-strings in SQL. Title, project_id, section, due, sender_id, and assignee values are all passed as parameters.
- **Severity**: Info (no risk found)

### [Info] S2: Authorization model is sound

- **File**: `src/openclaw_todo/cmd_add.py`, lines 41-49
- **Description**: Private project constraint correctly checks that all assignees match the project owner. The `resolve_project()` function provides implicit access control by only resolving the sender's own private projects (scoped by `owner_user_id = sender_id` in the SQL query). A non-owner sender cannot resolve another user's private project by name. The explicit assignee check in `cmd_add.py` is an additional layer for when the owner assigns tasks to others within their private project.
- **Severity**: Info (no bypass possible)

### [Info] S3: No hardcoded secrets or credentials

- No API keys, tokens, or secrets found in any changed files.

### [Info] S4: No new dependencies introduced

- `cmd_add.py` uses only standard library (`json`, `logging`, `sqlite3`) plus internal modules (`parser`, `project_resolver`). No new entries in `pyproject.toml`.

### [Info] S5: Input validation adequate

- Empty title returns error (line 25-26).
- Non-existent project returns error via `ProjectNotFoundError` (lines 30-33).
- Section validation handled by parser upstream (`VALID_SECTIONS` check).
- Due date validation handled by parser upstream (`_normalise_due`).
- Mention format constrained by parser regex (`<@U[A-Z0-9]+>`).

### Security Summary

No Critical, High, Medium, or Low severity findings. The implementation has a minimal attack surface -- three parameterized INSERT statements, project resolution with sender-scoped authorization, and input validation at both the parser and handler layers. The code is secure for the current Slack DM context.

---

## Follow-up Items

1. **Test coverage**: Add a test for non-owner sender attempting to add a task to another user's private project (should get `ProjectNotFoundError` via resolver).
2. **Transaction explicitness**: Consider wrapping the three DB writes in `with conn:` for explicit transaction semantics.
3. **Title length**: Consider adding a max-length validation (e.g., 500 chars) as defense-in-depth.
4. **Permissions module**: When Issue #17 (permissions helper) is merged, consider extracting the inline private-assignee validation to use the shared `validate_private_assignees()` function.
