# Architecture -- OpenClaw TODO Plugin for Slack

> Version: 1.0
> Date: 2026-02-20
> Status: Proposed
> Derived from: `openclaw_todo_plugin_prd.md` v1.1

---

## 1. System Context

This is an **OpenClaw plugin**, not a standalone application. It runs inside the OpenClaw Gateway process and communicates with users through Slack DMs. There is no HTTP server, no REST API, and no web framework. The entire system is a single Python package that the Gateway loads at startup.

```
Slack User  --(DM)--> Slack API --> OpenClaw Gateway --> TODO Plugin --> SQLite3
```

### Constraints

- No LLM calls (zero cost per invocation).
- Single SQLite3 file shared across all users within one Gateway instance.
- No external dependencies beyond the Python stdlib and the OpenClaw plugin SDK.

---

## 2. Module / Package Structure

```
openclaw_todo_plugin/
    __init__.py              # Plugin entry point; exports register()
    plugin.py                # OpenClaw plugin registration and message dispatch
    router.py                # Command routing: text -> handler
    parser.py                # Tokenizer and argument extractor
    commands/
        __init__.py
        add.py               # /todo add
        list_cmd.py          # /todo list   (avoids shadowing builtins)
        board.py             # /todo board
        move.py              # /todo move
        done.py              # /todo done
        drop.py              # /todo drop
        edit.py              # /todo edit
        project.py           # /todo project list|set-private|set-shared
    db/
        __init__.py
        connection.py        # Connection factory, WAL/busy_timeout pragmas
        migrate.py           # Schema versioning and migration runner
        migrations/
            __init__.py
            v001_initial.py  # Initial schema (projects, tasks, task_assignees, events, schema_version)
    models.py                # Dataclasses: Task, Project, Assignee, Event
    repositories/
        __init__.py
        project_repo.py      # CRUD + resolve logic for projects
        task_repo.py          # CRUD + query builders for tasks
        event_repo.py         # Append-only audit log writes
    services/
        __init__.py
        project_service.py   # Business rules for project visibility transitions
        task_service.py       # Business rules for task lifecycle
        permission.py         # Authorization checks (private/shared, owner/assignee)
    formatters.py             # Slack message formatting (board, list, confirmations)
    date_utils.py             # due parser: YYYY-MM-DD / MM-DD normalization
    errors.py                 # Domain exception hierarchy
    config.py                 # DB path resolution, timezone, defaults
tests/
    conftest.py               # Shared fixtures (in-memory SQLite, fake sender context)
    test_parser.py
    test_date_utils.py
    test_commands/
        test_add.py
        test_list.py
        test_board.py
        test_move.py
        test_done_drop.py
        test_edit.py
        test_project.py
    test_repositories/
        test_project_repo.py
        test_task_repo.py
    test_services/
        test_permission.py
        test_project_service.py
        test_task_service.py
    test_db/
        test_migrate.py
```

### Rationale

- **Flat `commands/` package**: one module per command keeps each handler under 150 lines and independently testable.
- **Repository pattern** over raw SQL in handlers: SQL stays in one place; business logic in `services/` never imports `sqlite3`.
- **No ORM**: SQLite3 stdlib driver is sufficient. An ORM would add a dependency for no gain at this scale.

---

## 3. Data Model

### 3.1 Entity-Relationship Diagram (logical)

```
projects 1---* tasks *---* task_assignees
                |
                +---* events
```

### 3.2 Tables

All timestamps are stored as ISO-8601 TEXT in UTC.

#### `schema_version`

| Column  | Type    | Notes        |
|---------|---------|--------------|
| version | INTEGER | NOT NULL     |

Single-row table. Current value determines which migrations to run.

#### `projects`

| Column         | Type    | Constraints / Default                     |
|----------------|---------|-------------------------------------------|
| id             | INTEGER | PK AUTOINCREMENT                          |
| name           | TEXT    | NOT NULL                                  |
| visibility     | TEXT    | NOT NULL CHECK IN ('shared','private')    |
| owner_user_id  | TEXT    | NULL (NULL when shared)                   |
| created_at     | TEXT    | NOT NULL DEFAULT datetime('now')          |
| updated_at     | TEXT    | NOT NULL DEFAULT datetime('now')          |

**Indexes:**

```sql
CREATE UNIQUE INDEX ux_projects_shared_name
    ON projects(name) WHERE visibility='shared';

CREATE UNIQUE INDEX ux_projects_private_owner_name
    ON projects(owner_user_id, name) WHERE visibility='private';
```

#### `tasks`

| Column      | Type    | Constraints / Default                                   |
|-------------|---------|----------------------------------------------------------|
| id          | INTEGER | PK AUTOINCREMENT                                         |
| title       | TEXT    | NOT NULL                                                 |
| project_id  | INTEGER | NOT NULL FK -> projects(id)                              |
| section     | TEXT    | NOT NULL CHECK IN ('backlog','doing','waiting','done','drop') |
| due         | TEXT    | NULL, format YYYY-MM-DD                                  |
| status      | TEXT    | NOT NULL CHECK IN ('open','done','dropped')              |
| created_by  | TEXT    | NOT NULL (Slack user id)                                 |
| created_at  | TEXT    | NOT NULL DEFAULT datetime('now')                         |
| updated_at  | TEXT    | NOT NULL DEFAULT datetime('now')                         |
| closed_at   | TEXT    | NULL                                                     |

**Indexes:**

```sql
CREATE INDEX ix_tasks_project_section ON tasks(project_id, section);
CREATE INDEX ix_tasks_status ON tasks(status);
```

#### `task_assignees`

| Column           | Type    | Constraints                  |
|------------------|---------|------------------------------|
| task_id          | INTEGER | NOT NULL FK -> tasks(id)     |
| assignee_user_id | TEXT    | NOT NULL                     |

```sql
PRIMARY KEY (task_id, assignee_user_id)
CREATE INDEX ix_task_assignees_user ON task_assignees(assignee_user_id, task_id);
```

#### `events` (audit log)

| Column         | Type    | Notes                        |
|----------------|---------|------------------------------|
| id             | INTEGER | PK AUTOINCREMENT             |
| ts             | TEXT    | NOT NULL DEFAULT datetime('now') |
| actor_user_id  | TEXT    | NOT NULL                     |
| action         | TEXT    | NOT NULL (e.g. 'task.add')   |
| task_id        | INTEGER | NULL                         |
| payload        | TEXT    | JSON blob                    |

### 3.3 Concurrency Pragmas

Applied once per connection in `db/connection.py`:

```python
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA busy_timeout=3000")
conn.execute("PRAGMA foreign_keys=ON")
```

---

## 4. APIs (Plugin Interface)

This plugin does not expose HTTP endpoints. Its "API" is the contract between OpenClaw Gateway and the plugin.

### 4.1 Plugin Registration

```python
# openclaw_todo_plugin/__init__.py

def register(gateway):
    """Called by OpenClaw Gateway at startup.

    Args:
        gateway: OpenClaw gateway instance providing hooks for
                 message handling and configuration access.
    """
    from .plugin import TodoPlugin
    plugin = TodoPlugin(gateway)
    gateway.on_dm_message(plugin.handle)
```

### 4.2 Message Handler Contract

```python
class TodoPlugin:
    def handle(self, message: IncomingMessage) -> str | None:
        """Process a Slack DM. Return reply text or None to ignore."""
```

`IncomingMessage` is an OpenClaw SDK type expected to carry at minimum:

| Field        | Type | Description                     |
|--------------|------|---------------------------------|
| text         | str  | Raw message text                |
| sender_id    | str  | Slack user ID of the sender     |
| channel_id   | str  | DM channel ID                   |
| timestamp    | str  | Slack message ts                |

### 4.3 Command Routing

`router.py` maps the second token of the message to a handler function:

```python
COMMANDS = {
    "add":     commands.add.handle,
    "list":    commands.list_cmd.handle,
    "board":   commands.board.handle,
    "move":    commands.move.handle,
    "done":    commands.done.handle,
    "drop":    commands.drop.handle,
    "edit":    commands.edit.handle,
    "project": commands.project.handle,   # sub-routes internally
}

def route(text: str, sender_id: str) -> str:
    tokens = text.strip().split()
    if not tokens or tokens[0] != "/todo":
        return None
    verb = tokens[1] if len(tokens) > 1 else "help"
    handler = COMMANDS.get(verb)
    if handler is None:
        return f"Unknown command: {verb}. Try /todo help"
    return handler(tokens[2:], sender_id)
```

### 4.4 Command Handler Signature

Every handler in `commands/` follows the same signature:

```python
def handle(args: list[str], sender_id: str) -> str:
    """Execute the command and return a Slack-formatted reply string."""
```

---

## 5. Key Flows

### 5.1 `/todo add` Flow

```
User -> Gateway -> TodoPlugin.handle()
  -> router.route() -> commands.add.handle()
    -> parser.parse_add_args(tokens)        # extract title, mentions, /p, /s, due
    -> date_utils.normalize_due(raw_due)    # MM-DD -> YYYY-MM-DD, validate
    -> project_repo.resolve(name, sender)   # private-first resolution
    -> permission.check_assignees(project, assignees, sender)  # private project guard
    -> task_repo.create(task)               # INSERT task + task_assignees
    -> event_repo.log("task.add", ...)      # audit
    -> formatters.format_add_confirm(task)  # reply string
```

### 5.2 `/todo project set-private` Flow

```
commands.project.handle(["set-private", name], sender)
  -> project_repo.resolve(name, sender)
  -> IF already private: return "already private"
  -> task_repo.find_non_owner_assignees(project_id, sender)
  -> IF any found: return error with violating task IDs
  -> project_repo.update_visibility(project_id, "private", sender)
  -> event_repo.log("project.set_private", ...)
```

---

## 6. Jobs / Background Work

There are **no background jobs** in v1. All operations are synchronous request-response within the Gateway's message handler. Potential future jobs:

| Job (future)           | Trigger         | Purpose                              |
|------------------------|-----------------|--------------------------------------|
| Due date reminders     | Cron / schedule | DM users about upcoming/overdue tasks|
| Stale task cleanup     | Weekly          | Auto-drop tasks untouched > N days   |
| DB vacuum              | Weekly          | Reclaim WAL space                    |

These would be registered via `gateway.schedule()` if the OpenClaw SDK supports it.

---

## 7. Observability

### 7.1 Structured Logging

All modules use Python's `logging` module with a shared logger name `openclaw_todo`:

```python
import logging
logger = logging.getLogger("openclaw_todo")
```

Log levels:
- **INFO**: command received (verb, sender_id, project), command completed.
- **WARNING**: permission denied, invalid input, constraint violation.
- **ERROR**: unexpected exceptions, DB errors.

### 7.2 Audit Trail

The `events` table provides a queryable audit log. Every state-changing operation (add, edit, move, done, drop, project visibility change) writes an event row with the actor, action, affected task ID, and a JSON payload of the change delta.

### 7.3 Metrics (future)

If the OpenClaw Gateway exposes a metrics interface, instrument:
- `todo_commands_total` (counter, labels: verb, status)
- `todo_command_duration_seconds` (histogram, labels: verb)
- `todo_db_errors_total` (counter)

### 7.4 Health Check

The plugin can expose a `health()` method that verifies the DB file exists and a simple `SELECT 1` succeeds.

---

## 8. Security

### 8.1 Authentication

Authentication is delegated to Slack and the OpenClaw Gateway. The plugin trusts `sender_id` from the Gateway as the authenticated identity. No additional auth layer is needed.

### 8.2 Authorization Model

| Resource        | Read                                | Write                                      |
|-----------------|-------------------------------------|--------------------------------------------|
| Shared project  | Any user (scope-filtered)           | Assignee or created_by of the task         |
| Private project | Owner only                          | Owner only                                 |

Authorization is enforced in `services/permission.py` and called by every command handler before any mutation.

### 8.3 Input Validation

- **SQL injection**: All queries use parameterized statements (`?` placeholders). No string interpolation in SQL.
- **Slack mention validation**: Assignees must match the `<@U[A-Z0-9]+>` pattern. Arbitrary text is rejected.
- **Due date validation**: Parsed through `datetime.date` -- invalid dates raise `ValueError` caught and returned as user-facing errors.
- **Section/status enum**: Checked against a frozen set before reaching the DB. The DB CHECK constraint is a secondary guard.

### 8.4 Data Isolation

Private project data is filtered at the repository layer. Queries for private projects always include `WHERE owner_user_id = ?` to prevent data leakage even if a higher layer has a bug.

### 8.5 Secrets

No API keys or secrets are stored by this plugin. The OpenClaw Gateway manages Slack API tokens.

---

## 9. Database Migration Strategy

### 9.1 Version Table

```sql
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);
INSERT INTO schema_version (version) VALUES (0);
```

### 9.2 Migration Runner (`db/migrate.py`)

```python
MIGRATIONS = [
    (1, "v001_initial", v001_initial.up),
    # (2, "v002_add_priority", v002_add_priority.up),
]

def run_migrations(conn: sqlite3.Connection) -> None:
    current = _get_current_version(conn)
    for version, name, up_fn in MIGRATIONS:
        if version > current:
            logger.info("Applying migration %s (%s)", version, name)
            up_fn(conn)
            conn.execute("UPDATE schema_version SET version = ?", (version,))
            conn.commit()
```

### 9.3 Migration File Contract

Each migration module in `db/migrations/` exports:

```python
def up(conn: sqlite3.Connection) -> None:
    """Apply this migration forward."""
    conn.executescript(SQL)
```

Down migrations are not implemented in v1. Rollback is handled by restoring a DB backup (see section 10).

### 9.4 Initialization Sequence

On first invocation or Gateway startup:

1. Resolve DB path: `~/.openclaw/workspace/.todo/todo.sqlite3`
2. Create directory if missing (`os.makedirs(..., exist_ok=True)`)
3. Open connection with WAL pragmas
4. Create `schema_version` table if not exists
5. Run pending migrations
6. Seed default `Inbox` shared project (idempotent `INSERT OR IGNORE`)

---

## 10. Deploy / Rollback

### 10.1 Packaging

The plugin is distributed as a standard Python package installable via `uv add` or `pip install` (in the OpenClaw Gateway environment):

```
pyproject.toml          # Package metadata, dependencies, entry points
openclaw_todo_plugin/   # Source
tests/                  # Not included in distribution
```

Entry point for OpenClaw plugin discovery:

```toml
[project.entry-points."openclaw.plugins"]
todo = "openclaw_todo_plugin:register"
```

### 10.2 Deployment Steps

1. **Backup DB**: `cp todo.sqlite3 todo.sqlite3.bak.$(date +%s)`
2. **Install new version**: `uv add openclaw-todo-plugin@<version>`
3. **Restart Gateway**: migrations run automatically on startup
4. **Verify**: send `/todo list` in DM, check logs for migration success

### 10.3 Rollback Steps

1. **Stop Gateway**
2. **Restore DB** (if schema changed): `cp todo.sqlite3.bak.<ts> todo.sqlite3`
3. **Install previous version**: `uv add openclaw-todo-plugin@<prev-version>`
4. **Restart Gateway**

### 10.4 Zero-Downtime Considerations

SQLite does not support concurrent schema changes from multiple writers. Since there is a single Gateway process, migrations are safe without locking beyond SQLite's built-in WAL locking. If multi-process deployment is ever needed, migration must run as a separate step before starting workers.

---

## 11. Tradeoffs and Design Decisions

### 11.1 SQLite vs. PostgreSQL

**Chosen: SQLite.**

| Factor          | SQLite                              | PostgreSQL                         |
|-----------------|-------------------------------------|------------------------------------|
| Ops complexity  | Zero (file on disk)                 | Requires running server            |
| Concurrency     | Single-writer, good enough for DMs  | Full MVCC                          |
| Scale ceiling   | ~100 concurrent users               | Thousands                          |
| Backup          | File copy                           | pg_dump / replication              |
| Migration       | Manual scripts                      | Alembic / django-migrations        |

SQLite is the right choice for a plugin that handles single-digit QPS through Slack DMs. If the team outgrows it, the repository layer abstracts SQL enough that a PostgreSQL migration is localized to `db/` and `repositories/`.

### 11.2 No ORM

Using raw `sqlite3` with parameterized queries. This avoids adding SQLAlchemy as a dependency for a plugin that has four tables. The repository layer provides the same abstraction boundary that an ORM session would.

### 11.3 Synchronous Execution

All command handlers are synchronous. The OpenClaw Gateway may be async (asyncio), but SQLite operations are fast enough (sub-millisecond for typical queries) that blocking is acceptable. If the Gateway requires async handlers, a thin `asyncio.to_thread()` wrapper in `plugin.py` is sufficient.

### 11.4 No Down Migrations

Forward-only migrations simplify the code and avoid the risk of data loss from buggy down scripts. Rollback relies on DB file backup, which is more reliable for SQLite.

### 11.5 Private-First Name Resolution

When a user references `/p MyProject`, the system checks for a private project owned by the sender before checking shared projects. This is the simplest model but can surprise users who have both a private and shared project with the same name. The PRD recommends against this pattern, and the plugin logs a warning when it detects the ambiguity.

### 11.6 Repository Pattern vs. Direct SQL in Handlers

Adds a small amount of indirection but pays for itself in testability. Tests can mock repositories instead of setting up SQLite fixtures for every command test. Integration tests still exercise the full stack.

### 11.7 Formatter as a Separate Module

Slack message formatting (mrkdwn, block kit) is isolated from business logic. If the plugin ever needs to support a second chat platform, only `formatters.py` changes.

### 11.8 Event Sourcing vs. Audit Log

The `events` table is an append-only audit log, not a full event-sourcing system. State is stored directly in `tasks` and `projects`. This is simpler to query and reason about. Full event sourcing would be over-engineering for a TODO plugin.

---

## 12. Dependency Summary

| Dependency        | Purpose                      | Required |
|-------------------|------------------------------|----------|
| Python 3.11+      | Runtime                      | Yes      |
| sqlite3 (stdlib)  | Database                     | Yes      |
| OpenClaw SDK      | Plugin registration, message hooks | Yes |
| pytest             | Testing                      | Dev only |
| pytest-cov         | Coverage reporting           | Dev only |
| ruff               | Linting                      | Dev only |
| black              | Formatting                   | Dev only |

No third-party runtime dependencies beyond the OpenClaw SDK itself.
