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
