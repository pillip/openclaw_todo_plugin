# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- `command_prefix` and `bypass_llm` fields in `openclaw.plugin.json` manifest — Gateway can skip LLM pipeline and call plugin handler directly (PR #51)

### Changed
- Command prefix changed from `/todo` to `todo:` — avoids both Slack slash-command interception and OpenClaw `!` bash reservation
- Relax Python version requirement to `>=3.10`

### Fixed
- Add `SO_REUSEADDR` to HTTP server for clean systemd restarts
- Add `id` and `configSchema` to OpenClaw plugin manifest
- Add `openclaw.extensions` to bridge `package.json`

### Added
- HTTP server bridge for JS/TS OpenClaw gateway (Issue #23): stdlib `http.server` wrapping `handle_message` with `POST /message` and `GET /health` endpoints
- `openclaw-todo-server` CLI entry point and `python -m openclaw_todo` support
- JS/TS bridge plugin (`bridge/openclaw-todo/`) using Node built-in `fetch` — zero npm dependencies
- Environment variables: `OPENCLAW_TODO_PORT`, `OPENCLAW_TODO_DB_PATH`, `OPENCLAW_TODO_URL`
- Server tests (10 tests): health, message dispatch, error handling, body size limit
- Request body size limit (1 MiB) with 413 response
- Plugin install E2E tests (Issue #22): 8 tests verifying entry-point discovery via `importlib.metadata.entry_points` and full command flow through the loaded function
- `@pytest.mark.install` marker for selective E2E test execution

### Fixed
- Hardened `_query_task` SQL column interpolation with allowlist validation in both `test_e2e.py` and `test_plugin_install_e2e.py`

### Previous (Unreleased)

### Added
- `db.py`: `get_connection(db_path)` helper with recursive directory creation, WAL mode, busy_timeout=3000
- DB connection tests (4 tests)
- `migrations.py`: sequential schema migration framework with `@register`, `migrate()`, `get_version()`
- Migration tests (4 tests): fresh DB, sequential apply, idempotent rerun, rollback on failure
- `schema_v1.py`: V1 migration creating projects, tasks, task_assignees, events tables
- Partial unique indexes for shared/private project name constraints
- Shared `Inbox` project auto-seeded
- V1 schema tests (7 tests): tables, indexes, CHECK constraints, Inbox

- `parser.py`: command tokenizer with `/p`, `/s`, `due:`, `<@U...>` extraction and `ParsedCommand` dataclass
- Parser tests (13 tests): project, section, due normalisation, mentions, title extraction
- `project_resolver.py`: project name resolution with private-first (PRD 3.2 Option A), Inbox auto-create
- Project resolver tests (6 tests): private priority, shared fallback, Inbox auto-create, unknown error
- `dispatcher.py`: command dispatcher with two-level routing (top-level + project subcommands), handler registry, DB init
- Plugin `handle_message` delegates to dispatcher instead of placeholder response
- Dispatcher tests (20 tests): command routing, project sub-routing, unknown commands, parse errors, DB init
- `permissions.py`: `can_write_task()` (private: owner only, shared: assignee/creator) and `validate_private_assignees()` helpers
- Permission tests (11 tests): private/shared write checks, creator+assignee overlap, private assignee validation
- `cmd_add.py`: `/todo add` command handler with project resolution, assignee defaults, private-project validation, event logging
- `add` handler registered in dispatcher (replaces stub)
- cmd_add tests (10 tests): default Inbox, explicit options, private rejection, assignee defaults, multiple assignees, event logging, edge cases
- `cmd_move.py`: `/todo move` command handler with section validation, permission checks (private: owner only, shared: assignee/creator), updated_at, event logging
- `move` handler registered in dispatcher
- cmd_move tests (13 tests): valid moves, updated_at, event logging, same-section noop, missing section/ID, invalid ID, nonexistent task, permission checks
- `cmd_list.py`: `/todo list` command handler with scope filtering (mine/all/<@USER>), project/section/status filters, sorting (due ASC NULLs last, id DESC), configurable limit
- `list` handler registered in dispatcher
- cmd_list tests (12 tests): mine default, all scope, private visibility, project/section filters, sorting, limit, edge cases
- `cmd_done_drop.py`: `/todo done` and `/todo drop` command handlers with shared `_close_task` helper, sets section/status/closed_at, permission checks, event logging
- `done` and `drop` handlers registered in dispatcher
- cmd_done_drop tests (14 tests): field updates, event logging, permissions (private/shared), already-closed idempotency, validation edge cases
- `cmd_board.py`: `/todo board` kanban view command grouping tasks by section (BACKLOG/DOING/WAITING/DONE/DROP), scope/project/status filters, limitPerSection with overflow
- `board` handler registered in dispatcher
- cmd_board tests (17 tests): section order, counts, empty sections, limit/overflow, scope filters, project filter, private visibility, task line format, edge cases
- `cmd_project_list.py`: `/todo project list` subcommand showing shared + sender's private projects with task counts
- `project_list` handler registered in dispatcher via project sub-routing
- cmd_project_list tests (6 tests): shared visibility, task counts, own private shown, others hidden, bidirectional privacy, default Inbox
- `cmd_edit.py`: `/todo edit` command with v1 replace semantics — title, assignees (full replace), project move, section, due (including due:- clear), private assignee validation, event diff payload
- `edit` handler registered in dispatcher
- cmd_edit tests (20 tests): title/assignees/due/section/project editing, permissions, private validation, event logging, edge cases
- `cmd_project_set_private.py`: `/todo project set-private <name>` command with three resolution paths (already-private noop, shared→private conversion with assignee validation, create new private project), event logging
- `project_set_private` handler registered in dispatcher via project sub-routing
- cmd_project_set_private tests (11 tests): already-private, shared conversion success/rejection, new project creation, assignee validation, event logging, edge cases
- `cmd_project_set_shared.py`: `/todo project set-shared <name>` command with three resolution paths (already-shared noop, private→shared conversion, create new shared project), event logging, TOCTOU race handling via IntegrityError catch
- `project_set_shared` handler registered in dispatcher via project sub-routing
- cmd_project_set_shared tests (9 tests): already-shared noop, Inbox detection, private→shared conversion, updated_at, event logging, other user isolation, new creation, edge cases
- Comprehensive parser unit tests (Issue #18): expanded from 13 to 50 tests, achieving 100% line coverage on `parser.py`. Covers: options in any order, due date boundaries, empty titles, unicode, whitespace, mixed mentions/options, missing option args, ID extraction, case-insensitive commands, all valid sections
- SQLite E2E integration tests (Issue #19): 20 tests exercising full `handle_message` flows with real SQLite via `tmp_path`. Covers: add→list, add→move→board, done/drop, edit, private project isolation, set-private rejection, due normalisation, set-shared flow, full lifecycle, cross-user write denial on private tasks
- `.github/workflows/ci.yml`: GitHub Actions CI pipeline (push + PR on main, Python 3.11 + uv + pytest)
- Branch protection: `test` job as required status check on main
- Packaging and distribution setup (Issue #20): complete `pyproject.toml` metadata (license, authors, classifiers, `openclaw.plugins` entry-point), `Makefile` (lint/format/test/build/clean), comprehensive `README.md` with install/config/usage docs
- Dev tooling: `ruff` + `black` dev dependencies with consistent config (line-length=120, py311 target)

### Fixed
- Import ordering across all source and test files (ruff I001)
- Ambiguous variable names in `test_cmd_board.py` (E741 `l` → `line`/`ln`)
- Lambda assignment in `dispatcher.py` (E731 → explicit `if`/`return`)
- `conftest` import path (`from conftest` → `from tests.conftest`) in 4 test files
- `black` formatting applied across 30 files
- Enable `PRAGMA foreign_keys=ON` in `get_connection()` for referential integrity
- Leap-year `due:02-29` parsing in MM-DD format (strptime year-1900 bug)

## [0.1.0] - 2026-02-20

### Added
- Project scaffold with `pyproject.toml` (uv, Python >=3.11)
- `src/openclaw_todo/` package with `__version__`
- `handle_message(text, context)` plugin entry point
- `/todo` prefix matching (non-todo messages silently ignored)
- Smoke tests for plugin entry point (4 tests)
