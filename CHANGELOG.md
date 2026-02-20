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
