# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

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
- `.github/workflows/ci.yml`: GitHub Actions CI pipeline (push + PR on main, Python 3.11 + uv + pytest)
- Branch protection: `test` job as required status check on main

### Fixed
- Enable `PRAGMA foreign_keys=ON` in `get_connection()` for referential integrity
- Leap-year `due:02-29` parsing in MM-DD format (strptime year-1900 bug)

## [0.1.0] - 2026-02-20

### Added
- Project scaffold with `pyproject.toml` (uv, Python >=3.11)
- `src/openclaw_todo/` package with `__version__`
- `handle_message(text, context)` plugin entry point
- `/todo` prefix matching (non-todo messages silently ignored)
- Smoke tests for plugin entry point (4 tests)
