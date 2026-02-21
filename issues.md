# OpenClaw TODO Plugin -- Issues

> Auto-generated from `openclaw_todo_plugin_prd.md` (PRD v1.1)
> Date: 2026-02-20

---

## Issue #1: Plugin skeleton and entry point

| Field       | Value                                  |
|-------------|----------------------------------------|
| Track       | Backend                                |
| Milestone   | M0                                     |
| Status      | done                                   |
| Priority    | P0                                     |
| Estimate    | 1d                                     |
| Branch      | `feature/001-plugin-skeleton`          |
| GH-Issue    | https://github.com/pillip/openclaw_todo_plugin/issues/1 |
| PR          | https://github.com/pillip/openclaw_todo_plugin/pull/2 |

**Description**
Create the Python project scaffold: `pyproject.toml` (uv), `src/openclaw_todo/` package layout, and the plugin entry-point that the OpenClaw gateway will load. The plugin must expose a callable that receives raw Slack DM text and a sender context dict.

**Acceptance Criteria**
- [ ] `pyproject.toml` exists with Python >=3.11, pytest, pytest-cov dev deps
- [ ] `src/openclaw_todo/__init__.py` exposes `__version__`
- [ ] `src/openclaw_todo/plugin.py` contains `handle_message(text: str, context: dict) -> str` entry point
- [ ] Messages not starting with `/todo` are silently ignored (returns `None`)
- [ ] `uv sync && uv run pytest -q` passes (trivial smoke test)

**Tests**
- `tests/test_plugin.py::test_ignores_non_todo_message`
- `tests/test_plugin.py::test_dispatches_todo_prefix`

**Rollback**
Delete branch; no runtime dependency.

**Observability**
`logger.debug` on every inbound message; `logger.info` when `/todo` prefix matched.

**Dependencies**
None.

---

## Issue #2: DB module -- connection helper and pragma setup

| Field       | Value                                  |
|-------------|----------------------------------------|
| Track       | Backend / Data                         |
| Milestone   | M1                                     |
| Status      | done                                   |
| Priority    | P0                                     |
| Estimate    | 0.5d                                   |
| Branch      | `feature/002-db-connection`            |
| GH-Issue    | https://github.com/pillip/openclaw_todo_plugin/issues/3 |
| PR          | https://github.com/pillip/openclaw_todo_plugin/pull/4 |

**Description**
Implement `src/openclaw_todo/db.py` with a `get_connection(db_path)` helper that creates the `~/.openclaw/workspace/.todo/` directory tree if missing, opens (or creates) `todo.sqlite3`, and applies `PRAGMA journal_mode=WAL` and `PRAGMA busy_timeout=3000`.

**Acceptance Criteria**
- [ ] Directory is created recursively when absent
- [ ] SQLite connection returned with WAL mode enabled
- [ ] `busy_timeout` is 3000
- [ ] Calling `get_connection` twice returns usable connections (no lock conflict)

**Tests**
- `tests/test_db.py::test_creates_directory_and_file` (tmp_path)
- `tests/test_db.py::test_wal_mode_enabled`
- `tests/test_db.py::test_busy_timeout`

**Rollback**
Revert module; no schema changes yet.

**Observability**
`logger.info` on first DB creation; `logger.debug` on each connection open.

**Dependencies**
#1

---

## Issue #3: Schema migration framework and schema_version table

| Field       | Value                                  |
|-------------|----------------------------------------|
| Track       | Backend / Data                         |
| Milestone   | M1                                     |
| Status      | done                                   |
| Priority    | P0                                     |
| Estimate    | 1d                                     |
| Branch      | `feature/003-schema-migration`         |
| GH-Issue    | https://github.com/pillip/openclaw_todo_plugin/issues/5 |
| PR          | https://github.com/pillip/openclaw_todo_plugin/pull/6 |

**Description**
Implement a simple sequential migration runner. On startup, read `schema_version` (create if missing), compare to available migrations list, and apply outstanding migrations in order inside a transaction.

**Acceptance Criteria**
- [ ] `schema_version` table created with single row `version=0` if absent
- [ ] Migrations are Python callables registered in an ordered list
- [ ] Each migration runs inside a transaction; version incremented on success
- [ ] Re-running on an up-to-date DB is a no-op
- [ ] Failing migration rolls back and raises with clear message

**Tests**
- `tests/test_migrations.py::test_fresh_db_gets_version_table`
- `tests/test_migrations.py::test_applies_migrations_sequentially`
- `tests/test_migrations.py::test_idempotent_on_rerun`
- `tests/test_migrations.py::test_rollback_on_failure`

**Rollback**
Drop `schema_version` table; revert module.

**Observability**
`logger.info("Migrating from version %d to %d", current, target)` per step.

**Dependencies**
#2

---

## Issue #4: V1 schema migration -- projects, tasks, task_assignees, events

| Field       | Value                                  |
|-------------|----------------------------------------|
| Track       | Backend / Data                         |
| Milestone   | M1                                     |
| Status      | done                                   |
| Priority    | P0                                     |
| Estimate    | 1d                                     |
| Branch      | `feature/004-v1-schema`                |
| GH-Issue    | https://github.com/pillip/openclaw_todo_plugin/issues/7 |
| PR          | https://github.com/pillip/openclaw_todo_plugin/pull/8 |

**Description**
Register migration v1 that creates the four tables (`projects`, `tasks`, `task_assignees`, `events`) with all columns, CHECK constraints, and partial unique indexes as specified in PRD section 6.3. Also seed shared project `Inbox`.

**Acceptance Criteria**
- [ ] `projects` table with `ux_projects_shared_name` and `ux_projects_private_owner_name` partial unique indexes
- [ ] `tasks` table with section and status CHECK constraints
- [ ] `task_assignees` table with composite PK and secondary index
- [ ] `events` audit table created
- [ ] Shared `Inbox` project auto-created (INSERT OR IGNORE)
- [ ] `schema_version` = 1 after migration

**Tests**
- `tests/test_migrations.py::test_v1_tables_exist`
- `tests/test_migrations.py::test_v1_inbox_created`
- `tests/test_migrations.py::test_v1_shared_unique_index_enforced`
- `tests/test_migrations.py::test_v1_private_unique_index_enforced`

**Rollback**
Drop all four tables + reset schema_version to 0.

**Observability**
Log table creation counts.

**Dependencies**
#3

---

## Issue #5: Command parser -- tokenizer and option extraction

| Field       | Value                                  |
|-------------|----------------------------------------|
| Track       | Backend                                |
| Milestone   | M2                                     |
| Status      | doing                                  |
| Priority    | P0                                     |
| Estimate    | 1d                                     |
| Branch      | `feature/005-parser-tokenizer`         |
| GH-Issue    | https://github.com/pillip/openclaw_todo_plugin/issues/9 |
| PR          | --                                     |

**Description**
Implement `src/openclaw_todo/parser.py` that takes raw message text (after `/todo` prefix) and returns a `ParsedCommand` dataclass containing: `command` (str), `args` (list), `project` (str|None), `section` (str|None), `due` (str|None, normalised to YYYY-MM-DD), `mentions` (list of Slack user IDs), and remaining `title_tokens`.

Parsing rules:
- `/p <name>` extracts project
- `/s <section>` extracts section (validate against enum)
- `due:YYYY-MM-DD` or `due:MM-DD` extracts and normalises due date
- `due:-` clears due (sentinel)
- `<@U...>` patterns extracted as mentions
- Everything else before first option token is title

**Acceptance Criteria**
- [ ] `/p MyProject` correctly extracted; token consumed
- [ ] `/s doing` validated; invalid section raises `ParseError`
- [ ] `due:03-15` normalised to `2026-03-15`
- [ ] `due:2026-02-30` raises `ParseError` (invalid date)
- [ ] `<@U12345>` extracted into mentions list
- [ ] Multiple mentions supported
- [ ] Title tokens are non-option, non-mention tokens before first option

**Tests**
- `tests/test_parser.py::test_extract_project`
- `tests/test_parser.py::test_extract_section_valid`
- `tests/test_parser.py::test_extract_section_invalid`
- `tests/test_parser.py::test_due_mm_dd_normalisation`
- `tests/test_parser.py::test_due_full_date`
- `tests/test_parser.py::test_due_invalid_date`
- `tests/test_parser.py::test_due_clear`
- `tests/test_parser.py::test_mentions_extraction`
- `tests/test_parser.py::test_title_extraction`

**Rollback**
Revert module; no side effects.

**Observability**
`logger.debug("Parsed: %s", parsed_command)`

**Dependencies**
#1

---

## Issue #6: /todo add command

| Field       | Value                                  |
|-------------|----------------------------------------|
| Track       | Backend                                |
| Milestone   | M3                                     |
| Status      | TODO                                   |
| Priority    | P0                                     |
| Estimate    | 1.5d                                   |
| Branch      | `feature/006-cmd-add`                  |
| GH-Issue    | --                                     |
| PR          | --                                     |

**Description**
Implement the `add` subcommand handler. Resolves project (default `Inbox`), applies defaults (section=`backlog`, assignees=sender if none mentioned), validates private-project assignee constraint (PRD 3.3), inserts task + task_assignees rows, logs event, and returns formatted confirmation.

**Acceptance Criteria**
- [ ] Task inserted with correct project_id, section, due, status='open', created_by
- [ ] Assignees default to sender when no mentions
- [ ] Multiple mentions create multiple task_assignee rows
- [ ] Private project + non-owner assignee returns warning and does NOT insert
- [ ] Non-existent project: `Inbox` auto-created as shared; others return error
- [ ] Response format: `Added #<id> (<project>/<section>) due:<due|-> assignees:<mentions> -- <title>`
- [ ] Event row written to `events` table

**Tests**
- `tests/test_cmd_add.py::test_add_default_inbox`
- `tests/test_cmd_add.py::test_add_with_project_section_due`
- `tests/test_cmd_add.py::test_add_private_rejects_other_assignee`
- `tests/test_cmd_add.py::test_add_assignee_defaults_to_sender`
- `tests/test_cmd_add.py::test_add_multiple_assignees`

**Rollback**
Revert handler; tasks table unchanged structurally.

**Observability**
`logger.info("Task #%d created in %s/%s by %s", id, project, section, sender)`

**Dependencies**
#4, #5

---

## Issue #7: Project resolver helper

| Field       | Value                                  |
|-------------|----------------------------------------|
| Track       | Backend                                |
| Milestone   | M3                                     |
| Status      | TODO                                   |
| Priority    | P0                                     |
| Estimate    | 0.5d                                   |
| Branch      | `feature/007-project-resolver`         |
| GH-Issue    | --                                     |
| PR          | --                                     |

**Description**
Implement `resolve_project(conn, name, sender_id) -> Project` following PRD 3.2 (Option A): sender's private project with that name takes priority, then shared, then error/auto-create for Inbox.

**Acceptance Criteria**
- [ ] Private project of sender matched first
- [ ] Falls back to shared if no private match
- [ ] Returns error when neither exists (except Inbox which is auto-created)
- [ ] Returns project row with id, name, visibility, owner_user_id

**Tests**
- `tests/test_project_resolver.py::test_private_takes_priority`
- `tests/test_project_resolver.py::test_falls_back_to_shared`
- `tests/test_project_resolver.py::test_inbox_auto_created`
- `tests/test_project_resolver.py::test_unknown_project_error`

**Rollback**
Revert module.

**Observability**
`logger.debug("Resolved project '%s' -> id=%d vis=%s", name, id, visibility)`

**Dependencies**
#4

---

## Issue #8: /todo list command

| Field       | Value                                  |
|-------------|----------------------------------------|
| Track       | Backend                                |
| Milestone   | M3                                     |
| Status      | TODO                                   |
| Priority    | P1                                     |
| Estimate    | 1d                                     |
| Branch      | `feature/008-cmd-list`                 |
| GH-Issue    | --                                     |
| PR          | --                                     |

**Description**
Implement the `list` subcommand. Supports scope (mine/all/<@USER>), project filter, section filter, status filter (open/done/drop), and limit. Sorting: due ASC (NULLs last), then id DESC. Excludes other users' private projects.

**Acceptance Criteria**
- [ ] Default scope=mine, status=open, limit=30
- [ ] `mine` filters to tasks where sender is an assignee
- [ ] `all` includes shared + sender's private (excludes others' private)
- [ ] `/p` and `/s` filters applied correctly
- [ ] Sorting: due NOT NULL first, due ASC, id DESC
- [ ] limit:N respected
- [ ] Output lists tasks in formatted lines

**Tests**
- `tests/test_cmd_list.py::test_list_mine_default`
- `tests/test_cmd_list.py::test_list_all_excludes_others_private`
- `tests/test_cmd_list.py::test_list_with_project_filter`
- `tests/test_cmd_list.py::test_list_sorting_order`
- `tests/test_cmd_list.py::test_list_limit`

**Rollback**
Revert handler; read-only operation.

**Observability**
`logger.info("list: scope=%s project=%s returned %d rows", scope, project, count)`

**Dependencies**
#6, #7

---

## Issue #9: /todo board command

| Field       | Value                                  |
|-------------|----------------------------------------|
| Track       | Backend                                |
| Milestone   | M3                                     |
| Status      | done                                   |
| Priority    | P1                                     |
| Estimate    | 1d                                     |
| Branch      | `feature/009-cmd-board`                |
| GH-Issue    | https://github.com/pillip/openclaw_todo_plugin/issues/30 |
| PR          | https://github.com/pillip/openclaw_todo_plugin/pull/31 |

**Description**
Implement the `board` subcommand. Groups tasks by section in fixed order (BACKLOG, DOING, WAITING, DONE, DROP), applies scope/project/status filters, and limits per section. Format: section headers with task lines underneath.

**Acceptance Criteria**
- [ ] Sections displayed in order: BACKLOG -> DOING -> WAITING -> DONE -> DROP
- [ ] Empty sections shown with "(empty)" or omitted (decide and document)
- [ ] `limitPerSection:N` caps items per section (default 10)
- [ ] Scope/project filters identical to `list`
- [ ] Each task line: `#id due:<date|-> assignees:<@U..> title`

**Tests**
- `tests/test_cmd_board.py::test_board_section_order`
- `tests/test_cmd_board.py::test_board_limit_per_section`
- `tests/test_cmd_board.py::test_board_scope_filter`

**Rollback**
Revert handler; read-only operation.

**Observability**
`logger.info("board: scope=%s project=%s sections=%s", ...)`

**Dependencies**
#8

---

## Issue #10: /todo move command

| Field       | Value                                  |
|-------------|----------------------------------------|
| Track       | Backend                                |
| Milestone   | M3                                     |
| Status      | done                                   |
| Priority    | P1                                     |
| Estimate    | 0.5d                                   |
| Branch      | `feature/010-cmd-move`                 |
| GH-Issue    | https://github.com/pillip/openclaw_todo_plugin/issues/23 |
| PR          | https://github.com/pillip/openclaw_todo_plugin/pull/24 |

**Description**
Implement the `move` subcommand. Validates section enum, checks permissions (private: owner only; shared: assignee or created_by), updates task section and updated_at, logs event.

**Acceptance Criteria**
- [ ] Section validated against enum; invalid returns error
- [ ] Private project: only owner can move
- [ ] Shared project: only assignee or created_by can move
- [ ] `updated_at` set on change
- [ ] Event logged
- [ ] Response confirms new section

**Tests**
- `tests/test_cmd_move.py::test_move_valid_section`
- `tests/test_cmd_move.py::test_move_invalid_section`
- `tests/test_cmd_move.py::test_move_private_owner_only`
- `tests/test_cmd_move.py::test_move_shared_permission`

**Rollback**
Revert handler.

**Observability**
`logger.info("Task #%d moved to %s by %s", id, section, sender)`

**Dependencies**
#6, #7

---

## Issue #11: /todo done and /todo drop commands

| Field       | Value                                  |
|-------------|----------------------------------------|
| Track       | Backend                                |
| Milestone   | M3                                     |
| Status      | done                                   |
| Priority    | P1                                     |
| Estimate    | 0.5d                                   |
| Branch      | `feature/011-cmd-done-drop`            |
| GH-Issue    | https://github.com/pillip/openclaw_todo_plugin/issues/26 |
| PR          | https://github.com/pillip/openclaw_todo_plugin/pull/27 |

**Description**
Implement `done` and `drop` subcommands. Both set section and status accordingly, record `closed_at`, validate permissions same as `move`, and log event.

**Acceptance Criteria**
- [ ] `done`: section='done', status='done', closed_at=now
- [ ] `drop`: section='drop', status='dropped', closed_at=now
- [ ] Permissions enforced (same as move)
- [ ] Already-closed task returns informational message (idempotent or error -- decide)
- [ ] Event logged for each

**Tests**
- `tests/test_cmd_done_drop.py::test_done_sets_fields`
- `tests/test_cmd_done_drop.py::test_drop_sets_fields`
- `tests/test_cmd_done_drop.py::test_permission_check`
- `tests/test_cmd_done_drop.py::test_already_done`

**Rollback**
Revert handler.

**Observability**
`logger.info("Task #%d %s by %s", id, action, sender)`

**Dependencies**
#10

---

## Issue #12: /todo edit command

| Field       | Value                                  |
|-------------|----------------------------------------|
| Track       | Backend                                |
| Milestone   | M3                                     |
| Status      | done                                   |
| Priority    | P1                                     |
| Estimate    | 1.5d                                   |
| Branch      | `feature/012-cmd-edit`                 |
| GH-Issue    | https://github.com/pillip/openclaw_todo_plugin/issues/34 |
| PR          | https://github.com/pillip/openclaw_todo_plugin/pull/35 |

**Description**
Implement the `edit` subcommand (v1 replace semantics). Supports changing title, assignees (full replace), project, section, and due. Validates private-project assignee constraint on both source and target project. Logs event with old/new diff in payload.

**Acceptance Criteria**
- [ ] Title updated only if non-option tokens present
- [ ] Mentions present -> assignees fully replaced (DELETE + INSERT)
- [ ] `due:-` clears due to NULL
- [ ] `/p <newProject>` moves task to new project (project_id updated)
- [ ] Private project assignee validation applied to target project
- [ ] If moving to private project with non-owner assignees -> warning, no change
- [ ] Event payload contains changed fields
- [ ] Permissions: private owner only; shared assignee/created_by

**Tests**
- `tests/test_cmd_edit.py::test_edit_title`
- `tests/test_cmd_edit.py::test_edit_assignees_replace`
- `tests/test_cmd_edit.py::test_edit_due_clear`
- `tests/test_cmd_edit.py::test_edit_move_project`
- `tests/test_cmd_edit.py::test_edit_private_assignee_rejected`
- `tests/test_cmd_edit.py::test_edit_no_change_fields`

**Rollback**
Revert handler.

**Observability**
`logger.info("Task #%d edited by %s: fields=%s", id, sender, changed_fields)`

**Dependencies**
#6, #7, #10

---

## Issue #13: /todo project list command

| Field       | Value                                  |
|-------------|----------------------------------------|
| Track       | Backend                                |
| Milestone   | M4                                     |
| Status      | done                                   |
| Priority    | P1                                     |
| Estimate    | 0.5d                                   |
| Branch      | `feature/013-cmd-project-list`         |
| GH-Issue    | https://github.com/pillip/openclaw_todo_plugin/issues/28 |
| PR          | Merged via PR #27 (bundled with Issue #11) |

**Description**
Implement `/todo project list`. Returns all shared projects and the sender's private projects. Format: grouped by visibility with name and task count.

**Acceptance Criteria**
- [ ] Shared projects listed regardless of sender
- [ ] Sender's private projects listed
- [ ] Other users' private projects NOT shown
- [ ] Each project shows name, visibility, task count

**Tests**
- `tests/test_cmd_project.py::test_project_list_shows_shared`
- `tests/test_cmd_project.py::test_project_list_shows_own_private`
- `tests/test_cmd_project.py::test_project_list_hides_others_private`

**Rollback**
Revert handler; read-only.

**Observability**
`logger.info("project list: %d shared, %d private for %s", ...)`

**Dependencies**
#7

---

## Issue #14: /todo project set-private command with assignee validation

| Field       | Value                                  |
|-------------|----------------------------------------|
| Track       | Backend                                |
| Milestone   | M4                                     |
| Status      | done                                   |
| Priority    | P0                                     |
| Estimate    | 1.5d                                   |
| Branch      | `feature/014-cmd-project-set-private`  |
| GH-Issue    | https://github.com/pillip/openclaw_todo_plugin/issues/32 |
| PR          | https://github.com/pillip/openclaw_todo_plugin/pull/33 |

**Description**
Implement `/todo project set-private <name>` with the assignee validation described in PRD 3.4. Resolution flow: if sender already has private with that name -> noop; if shared exists -> attempt conversion; if neither -> create new private. Conversion scans all tasks in the project and rejects if any task has a non-owner assignee.

**Acceptance Criteria**
- [ ] Already-private for sender: returns "already private" message
- [ ] Shared -> private: scans tasks; all assignees are owner -> success (visibility='private', owner_user_id=sender)
- [ ] Shared -> private: at least one non-owner assignee -> error with task IDs and violating assignee list (max 10)
- [ ] Neither exists: creates new private project with owner=sender
- [ ] Error message format matches PRD example
- [ ] Event logged

**Tests**
- `tests/test_cmd_project.py::test_set_private_already_private`
- `tests/test_cmd_project.py::test_set_private_shared_success`
- `tests/test_cmd_project.py::test_set_private_shared_rejected_non_owner_assignee`
- `tests/test_cmd_project.py::test_set_private_creates_new`
- `tests/test_cmd_project.py::test_set_private_error_message_format`

**Rollback**
Revert handler; no schema change.

**Observability**
`logger.info("project set-private: %s result=%s by %s", name, result, sender)`

**Dependencies**
#7, #13

---

## Issue #15: /todo project set-shared command

| Field       | Value                                  |
|-------------|----------------------------------------|
| Track       | Backend                                |
| Milestone   | M4                                     |
| Status      | done                                   |
| Priority    | P1                                     |
| Estimate    | 0.5d                                   |
| Branch      | `feature/015-cmd-project-set-shared`   |
| GH-Issue    | https://github.com/pillip/openclaw_todo_plugin/issues/36 |
| PR          | https://github.com/pillip/openclaw_todo_plugin/pull/37 |

**Description**
Implement `/todo project set-shared <name>`. Creates a shared project if none exists. If a shared project with that name already exists, noop. Global uniqueness enforced by DB index.

**Acceptance Criteria**
- [ ] New shared project created when name is free
- [ ] Existing shared project: returns "already shared" / noop
- [ ] Name conflict with existing shared: returns exists message (index enforces)
- [ ] Event logged

**Tests**
- `tests/test_cmd_project.py::test_set_shared_creates_new`
- `tests/test_cmd_project.py::test_set_shared_already_exists_noop`
- `tests/test_cmd_project.py::test_set_shared_name_conflict`

**Rollback**
Revert handler.

**Observability**
`logger.info("project set-shared: %s result=%s", name, result)`

**Dependencies**
#7, #13

---

## Issue #16: Command dispatcher and routing

| Field       | Value                                  |
|-------------|----------------------------------------|
| Track       | Backend                                |
| Milestone   | M3                                     |
| Status      | TODO                                   |
| Priority    | P0                                     |
| Estimate    | 0.5d                                   |
| Branch      | `feature/016-dispatcher`               |
| GH-Issue    | --                                     |
| PR          | --                                     |

**Description**
Implement the dispatcher in `plugin.py` that maps the parsed command name to handler functions: `add`, `list`, `board`, `move`, `done`, `drop`, `edit`, `project`. The `project` command further dispatches to `list`, `set-private`, `set-shared`. Unknown commands return a help/error message.

**Acceptance Criteria**
- [ ] All valid command names routed to correct handler
- [ ] `project` subcommands routed correctly
- [ ] Unknown command returns usage hint
- [ ] DB connection initialised (migration check) before first command execution

**Tests**
- `tests/test_dispatcher.py::test_routes_known_commands`
- `tests/test_dispatcher.py::test_project_sub_routing`
- `tests/test_dispatcher.py::test_unknown_command_help`

**Rollback**
Revert module.

**Observability**
`logger.info("Dispatching command=%s sub=%s", command, sub)`

**Dependencies**
#5

---

## Issue #17: Permission helper module

| Field       | Value                                  |
|-------------|----------------------------------------|
| Track       | Backend                                |
| Milestone   | M3                                     |
| Status      | done                                   |
| Priority    | P0                                     |
| Estimate    | 0.5d                                   |
| Branch      | `feature/017-permissions`              |
| GH-Issue    | https://github.com/pillip/openclaw_todo_plugin/issues/21 |
| PR          | (merged directly on main)              |

**Description**
Extract shared permission-checking logic into `src/openclaw_todo/permissions.py`. Provides `can_write_task(conn, task_id, sender_id) -> bool` and `validate_private_assignees(project, assignees, owner_id) -> Optional[str]` (returns warning message or None).

**Acceptance Criteria**
- [ ] Private project: only owner can write
- [ ] Shared project: only assignee or created_by can write
- [ ] `validate_private_assignees` returns warning string when non-owner assignees present for private project
- [ ] Returns None for shared projects or when all assignees are owner

**Tests**
- `tests/test_permissions.py::test_private_owner_can_write`
- `tests/test_permissions.py::test_private_non_owner_rejected`
- `tests/test_permissions.py::test_shared_assignee_can_write`
- `tests/test_permissions.py::test_shared_creator_can_write`
- `tests/test_permissions.py::test_validate_private_assignees_warning`

**Rollback**
Revert module.

**Observability**
`logger.debug("Permission check: task=%d sender=%s result=%s", ...)`

**Dependencies**
#4

---

## Issue #18: Parser unit tests (comprehensive)

| Field       | Value                                  |
|-------------|----------------------------------------|
| Track       | QA                                     |
| Milestone   | M5                                     |
| Status      | done                                   |
| Priority    | P1                                     |
| Estimate    | 1d                                     |
| Branch      | `feature/018-parser-tests`             |
| GH-Issue    | issues/39                              |
| PR          | pull/40                                |

**Description**
Expand parser test coverage to include edge cases: multiple options in varied order, due at year boundary, empty title, mentions mixed with options, unicode in titles, extra whitespace handling.

**Acceptance Criteria**
- [ ] >=95% line coverage on `parser.py`
- [ ] Edge cases documented in test docstrings
- [ ] All tests pass with `uv run pytest tests/test_parser.py -v`

**Tests**
- `tests/test_parser.py::test_options_in_any_order`
- `tests/test_parser.py::test_due_year_boundary`
- `tests/test_parser.py::test_empty_title_no_crash`
- `tests/test_parser.py::test_unicode_title`
- `tests/test_parser.py::test_extra_whitespace`
- `tests/test_parser.py::test_mixed_mentions_and_options`

**Rollback**
Revert test file; no production code change.

**Observability**
CI coverage report.

**Dependencies**
#5

---

## Issue #19: SQLite end-to-end integration tests

| Field       | Value                                  |
|-------------|----------------------------------------|
| Track       | QA                                     |
| Milestone   | M5                                     |
| Status      | done                                   |
| Priority    | P1                                     |
| Estimate    | 1.5d                                   |
| Branch      | `feature/019-e2e-tests`               |
| GH-Issue    | https://github.com/pillip/openclaw_todo_plugin/issues/38 |
| PR          | https://github.com/pillip/openclaw_todo_plugin/pull/41 |

**Description**
Write integration tests that exercise the full flow through `handle_message` with a real (tmp_path) SQLite database. Cover the main user stories: add a task, list it, move it, mark done, edit it, manage projects, and validate private project constraints.

**Acceptance Criteria**
- [ ] Each test uses a fresh DB via `tmp_path` fixture
- [ ] Scenarios: add->list, add->move->board, add->done, add->edit, project set-private rejection
- [ ] Private project visibility enforced end-to-end
- [ ] Due normalisation verified in DB
- [ ] All tests pass with `uv run pytest tests/test_e2e.py -v`

**Tests**
- `tests/test_e2e.py::test_add_and_list_roundtrip`
- `tests/test_e2e.py::test_add_move_board`
- `tests/test_e2e.py::test_done_and_drop`
- `tests/test_e2e.py::test_edit_title_and_assignees`
- `tests/test_e2e.py::test_private_project_isolation`
- `tests/test_e2e.py::test_set_private_rejects_foreign_assignees`
- `tests/test_e2e.py::test_due_normalisation_stored_correctly`

**Rollback**
Revert test file.

**Observability**
CI test results and coverage delta.

**Dependencies**
#6, #8, #9, #10, #11, #12, #14, #15

---

## Issue #20: Packaging and distribution setup

| Field       | Value                                  |
|-------------|----------------------------------------|
| Track       | DevOps                                 |
| Milestone   | M6                                     |
| Status      | done                                   |
| Priority    | P2                                     |
| Estimate    | 1d                                     |
| Branch      | `feature/020-packaging`               |
| GH-Issue    | https://github.com/pillip/openclaw_todo_plugin/issues/42 |
| PR          | https://github.com/pillip/openclaw_todo_plugin/pull/43 |

**Description**
Finalise `pyproject.toml` metadata (name, version, description, license, entry-points), add a `Makefile` with targets for lint/test/build, and document installation instructions in README. Ensure the plugin can be installed as a package and discovered by the OpenClaw gateway.

**Acceptance Criteria**
- [ ] `pyproject.toml` has complete metadata and entry-point for OpenClaw plugin discovery
- [ ] `make lint` runs ruff + black --check
- [ ] `make test` runs pytest with coverage
- [ ] `make build` produces a wheel via `uv build`
- [ ] `pip install <wheel>` in a clean venv makes the plugin importable
- [ ] README documents installation and configuration (DB path env var)

**Tests**
- Manual: install wheel in fresh venv, import module, call `handle_message`
- `make test` passes in CI

**Rollback**
Revert packaging changes.

**Observability**
Build artifact size logged; CI publishes wheel as artifact.

**Dependencies**
#19

---

## Dependency Graph (summary)

```
#1  Plugin skeleton
 |
 +--#2  DB connection
 |   |
 |   +--#3  Migration framework
 |       |
 |       +--#4  V1 schema
 |           |
 |           +--#7  Project resolver
 |           |   |
 |           |   +--#13 project list
 |           |   +--#14 project set-private
 |           |   +--#15 project set-shared
 |           |
 |           +--#17 Permissions helper
 |
 +--#5  Parser
 |   |
 |   +--#18 Parser tests (M5)
 |
 +--#16 Dispatcher
     |
     +--#6  cmd add       (#4,#5,#7,#17)
     +--#8  cmd list      (#6,#7)
     +--#9  cmd board     (#8)
     +--#10 cmd move      (#6,#7,#17)
     +--#11 cmd done/drop (#10)
     +--#12 cmd edit      (#6,#7,#10,#17)

#19 E2E tests    (all commands)
#20 Packaging    (#19)
#21 CI workflow   (standalone)
```

---

## Issue #21: GitHub Actions CI 워크플로우

| Field       | Value                                  |
|-------------|----------------------------------------|
| Track       | DevOps                                 |
| Milestone   | M0                                     |
| Status      | done                                   |
| Priority    | P0                                     |
| Estimate    | 0.5d                                   |
| Branch      | `feature/021-ci-workflow`              |
| GH-Issue    | https://github.com/pillip/openclaw_todo_plugin/issues/19 |
| PR          | https://github.com/pillip/openclaw_todo_plugin/pull/20 |

**Description**
PR 머지 전 자동 테스트 검증을 위한 GitHub Actions CI 파이프라인을 추가합니다. push (main) + pull_request (main) 트리거로 Python 3.11 + uv + pytest 기반 테스트를 실행합니다.

**Acceptance Criteria**
- [ ] `.github/workflows/ci.yml` 생성
- [ ] PR 생성 시 CI가 자동 실행됨
- [ ] `uv run pytest -q --tb=short` 통과가 머지 조건

**Dependencies**
None.

---

## Issue #22: Plugin install E2E tests via entry-point discovery

| Field       | Value                                  |
|-------------|----------------------------------------|
| Track       | QA                                     |
| Milestone   | M5                                     |
| Status      | done                                   |
| Priority    | P1                                     |
| Estimate    | 0.5d                                   |
| Branch      | `feature/022-plugin-install-e2e`       |
| GH-Issue    | https://github.com/pillip/openclaw_todo_plugin/issues/44 |
| PR          | https://github.com/pillip/openclaw_todo_plugin/pull/45 |

**Description**
Add E2E tests that discover the plugin via `importlib.metadata.entry_points(group="openclaw.plugins")`, load the `todo` entry-point, and exercise the full command flow through the discovered function. Unlike `test_e2e.py` which imports `handle_message` directly, these tests verify that the package installation and entry-point registration work correctly.

**Acceptance Criteria**
- [ ] `openclaw.plugins` group contains `todo` entry-point after `uv sync`
- [ ] Loaded function is callable with correct signature (text, context, db_path)
- [ ] Full command flow works via entry-point-loaded function (add, list, move, edit, done)
- [ ] Private project isolation verified via entry-point path
- [ ] Multi-user shared project collaboration verified
- [ ] Tests marked with `@pytest.mark.install` for selective execution

**Tests**
- `tests/test_plugin_install_e2e.py::TestEntryPointDiscovery::test_todo_entry_point_exists`
- `tests/test_plugin_install_e2e.py::TestEntryPointDiscovery::test_loaded_function_is_callable`
- `tests/test_plugin_install_e2e.py::TestEntryPointDiscovery::test_loaded_function_signature`
- `tests/test_plugin_install_e2e.py::TestPluginViaEntryPoint::test_non_todo_returns_none`
- `tests/test_plugin_install_e2e.py::TestPluginViaEntryPoint::test_add_and_list_roundtrip`
- `tests/test_plugin_install_e2e.py::TestPluginViaEntryPoint::test_full_lifecycle`
- `tests/test_plugin_install_e2e.py::TestPluginViaEntryPoint::test_private_project_isolation`
- `tests/test_plugin_install_e2e.py::TestPluginViaEntryPoint::test_multiple_users_shared_project`

**Rollback**
Revert test file; no production code change.

**Dependencies**
#20

---

## Issue #23: HTTP Server Bridge for OpenClaw JS Gateway

| Field       | Value                                  |
|-------------|----------------------------------------|
| Track       | Backend / Integration                  |
| Milestone   | M7                                     |
| Status      | done                                   |
| Priority    | P1                                     |
| Estimate    | 1.5d                                   |
| Branch      | `feature/023-http-bridge`              |
| GH-Issue    | --                                     |
| PR          | --                                     |

**Description**
Add an HTTP server bridge so the Python plugin can be used from JS/TS-only OpenClaw gateways. The Python side wraps `handle_message` in a stdlib `http.server` (`POST /message`, `GET /health`). A thin JS/TS bridge plugin calls it via `fetch`. Zero runtime dependencies on both sides.

**Acceptance Criteria**
- [ ] `src/openclaw_todo/server.py` — HTTP server with `/message` and `/health` endpoints
- [ ] `src/openclaw_todo/__main__.py` — `python -m openclaw_todo` runs the server
- [ ] `pyproject.toml` — `openclaw-todo-server` CLI entry point
- [ ] `bridge/openclaw-todo/` — JS bridge plugin (openclaw.plugin.json, index.ts, package.json, tsconfig.json)
- [ ] `tests/test_server.py` — health, message, error handling tests
- [ ] Environment variables: `OPENCLAW_TODO_PORT`, `OPENCLAW_TODO_DB_PATH`, `OPENCLAW_TODO_URL`
- [ ] 127.0.0.1 binding, graceful SIGINT/SIGTERM shutdown

**Tests**
- `tests/test_server.py::TestHealthEndpoint::test_health_ok`
- `tests/test_server.py::TestHealthEndpoint::test_unknown_get_path_404`
- `tests/test_server.py::TestMessageEndpoint::test_todo_add_returns_response`
- `tests/test_server.py::TestMessageEndpoint::test_non_todo_returns_null`
- `tests/test_server.py::TestMessageEndpoint::test_todo_usage`
- `tests/test_server.py::TestErrorHandling::test_empty_body_400`
- `tests/test_server.py::TestErrorHandling::test_invalid_json_400`
- `tests/test_server.py::TestErrorHandling::test_missing_fields_422`
- `tests/test_server.py::TestErrorHandling::test_unknown_post_path_404`

**Rollback**
Remove server.py, __main__.py, bridge/ directory; revert pyproject.toml scripts.

**Dependencies**
#1, #20
