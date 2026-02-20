# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- `db.py`: `get_connection(db_path)` helper with recursive directory creation, WAL mode, busy_timeout=3000
- DB connection tests (4 tests)

## [0.1.0] - 2026-02-20

### Added
- Project scaffold with `pyproject.toml` (uv, Python >=3.11)
- `src/openclaw_todo/` package with `__version__`
- `handle_message(text, context)` plugin entry point
- `/todo` prefix matching (non-todo messages silently ignored)
- Smoke tests for plugin entry point (4 tests)
