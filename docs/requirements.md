# OpenClaw TODO Plugin -- Requirements Document

> **Version**: 1.0
> **Date**: 2026-02-20
> **Source PRD**: `openclaw_todo_plugin_prd.md` v1.1
> **Status**: Draft

---

## 1. Purpose

Define the functional and non-functional requirements for a Slack-based TODO management plugin (OpenClaw TODO Plugin). The plugin operates via DM with a Slack bot, stores data in SQLite3, and supports private/shared project workflows with zero LLM cost.

---

## 2. Scope

### 2.1 In Scope (MVP / v1)

| Area | Details |
|------|---------|
| **Command interface** | `/todo add`, `list`, `board`, `move`, `done`, `drop`, `edit` |
| **Project management** | `/todo project list`, `set-private`, `set-shared` |
| **Storage** | Single shared SQLite3 file with WAL mode |
| **Input channel** | DM with the OpenClaw Slack bot (primary path) |
| **Due date parsing** | `YYYY-MM-DD` and `MM-DD` with year inference |
| **Assignee resolution** | Slack `<@U...>` mentions; multi-assignee support |
| **Visibility model** | Private (owner-only) and shared projects |
| **Schema migration** | `schema_version` table; auto-create DB and default `Inbox` project on first run |
| **Audit log** | `events` table recording actor, action, task, and payload |

### 2.2 Out of Scope

- Natural language / LLM-based task creation (Phase 2).
- Channel or thread-based usage (app mention `@openclaw /todo ...`).
- Recurring / repeating tasks.
- Reminders, notifications, or scheduled digests.
- Multi-workspace federation or cross-workspace sharing.
- Web UI or dashboard.
- Task attachments or file uploads.
- Real-time sync with external project management tools.

---

## 3. Assumptions

| # | Assumption |
|---|-----------|
| A1 | The OpenClaw Gateway is already deployed and can route DM messages to plugins. |
| A2 | Each Slack user has a unique, stable `user_id` (`U...` format). |
| A3 | A single SQLite3 file is sufficient for the expected concurrency (small-to-medium teams). |
| A4 | Server timezone is `Asia/Seoul` for date inference. |
| A5 | The bot has DM read/write permissions via Slack OAuth scopes. |
| A6 | Plugin packaging and distribution follows existing OpenClaw conventions (npm). |

---

## 4. Constraints

| # | Constraint |
|---|-----------|
| C1 | Zero LLM calls -- all parsing is deterministic. |
| C2 | SQLite3 only; no external database dependency. |
| C3 | DB file location fixed at `~/.openclaw/workspace/.todo/todo.sqlite3`. |
| C4 | Section values are a closed enum: `backlog`, `doing`, `waiting`, `done`, `drop`. |
| C5 | Status values are a closed enum: `open`, `done`, `dropped`. |

---

## 5. Risks

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|-----------|
| R1 | SQLite write contention under high concurrency | Medium | Medium | WAL mode + `busy_timeout=3000`; monitor lock wait times. |
| R2 | Project name collision confusion (private vs shared same name) | Medium | Low | Private-first resolution + operational guidance to avoid same names. |
| R3 | Schema migration failure corrupts DB | Low | High | Wrap migrations in transactions; back up DB file before migration. |
| R4 | Slack API rate limits on bot DM responses | Low | Medium | Queue responses; respect Slack rate limit headers. |
| R5 | Date parsing edge cases (leap years, locale) | Low | Low | Strict `datetime` validation; reject invalid dates with clear error. |

---

## 6. Functional Requirements

### FR-1: Command Parser

| ID | Requirement |
|----|------------|
| FR-1.1 | The plugin MUST recognize messages starting with `/todo` as commands and ignore all other messages. |
| FR-1.2 | The parser MUST extract tokens: title text, `<@U...>` mentions, `/p <project>`, `/s <section>`, and `due:` value. |
| FR-1.3 | `due:MM-DD` or `due:M-D` MUST be expanded to `due:YYYY-MM-DD` using the current server year. |
| FR-1.4 | Invalid dates (e.g., `02-30`) MUST return a user-facing error. |
| FR-1.5 | `due:-` MUST clear (set to NULL) the due date. |

### FR-2: Task Commands

#### FR-2.1 `/todo add`

| ID | Requirement |
|----|------------|
| FR-2.1.1 | Create a task with provided title, assignees, project, section, and due date. |
| FR-2.1.2 | Defaults: project=`Inbox`, section=`backlog`, assignees=sender, due=NULL. |
| FR-2.1.3 | If the target project does not exist and is `Inbox`, auto-create it as shared. |
| FR-2.1.4 | If the target is a private project and any assignee is not the owner, reject with a warning message and do not create the task. |
| FR-2.1.5 | Return a confirmation message including: task ID, project, section, due, assignees, and title. |

**Acceptance Criteria (add)**:
- AC-2.1.A: Running `/todo add Buy milk` creates task #N in Inbox/backlog with sender as assignee; response contains `Added #N`.
- AC-2.1.B: Running `/todo add Deploy <@U2> /p Ops /s doing due:03-15` creates a task in project Ops, section doing, due set to current-year-03-15, assignee U2.
- AC-2.1.C: Running `/todo add Secret <@U2> /p MyPrivate` where MyPrivate is a private project owned by sender returns a warning and does NOT create the task.
- AC-2.1.D: Running `/todo add First task` when no DB file exists triggers DB creation, schema application, Inbox project creation, then creates the task.

#### FR-2.2 `/todo list`

| ID | Requirement |
|----|------------|
| FR-2.2.1 | List tasks filtered by scope (`mine`/`all`/`<@USER>`), project, section, and status. |
| FR-2.2.2 | Defaults: scope=`mine`, status=`open`, limit=30. |
| FR-2.2.3 | Sort order: due (non-null first, ascending), then id descending. |
| FR-2.2.4 | `all` scope returns shared tasks plus sender's private project tasks; never shows other users' private tasks. |

**Acceptance Criteria (list)**:
- AC-2.2.A: `/todo list` returns only open tasks where sender is an assignee, limited to 30, sorted by due then id.
- AC-2.2.B: `/todo list all` includes tasks from shared projects and the sender's private projects, but excludes other users' private project tasks.
- AC-2.2.C: `/todo list /p Ops /s doing` returns only tasks in project Ops, section doing.

#### FR-2.3 `/todo board`

| ID | Requirement |
|----|------------|
| FR-2.3.1 | Display tasks grouped by section in order: BACKLOG, DOING, WAITING, DONE, DROP. |
| FR-2.3.2 | Defaults: scope=`mine`, status=`open`, limitPerSection=10. |
| FR-2.3.3 | Each item shows: `#id due assignees title`. |

**Acceptance Criteria (board)**:
- AC-2.3.A: `/todo board /p Ops` displays tasks grouped under section headers in the correct order.
- AC-2.3.B: Each section contains at most 10 items by default.

#### FR-2.4 `/todo move`

| ID | Requirement |
|----|------------|
| FR-2.4.1 | Move a task to a specified section. |
| FR-2.4.2 | Validate section against the enum. |
| FR-2.4.3 | Authorization: private project -- owner only; shared project -- assignee or created_by. |

**Acceptance Criteria (move)**:
- AC-2.4.A: `/todo move 42 doing` updates task #42 section to doing and returns confirmation.
- AC-2.4.B: A user who is neither assignee nor creator of a shared task receives an authorization error.

#### FR-2.5 `/todo done` and `/todo drop`

| ID | Requirement |
|----|------------|
| FR-2.5.1 | `/todo done <id>`: set section=`done`, status=`done`, record `closed_at`. |
| FR-2.5.2 | `/todo drop <id>`: set section=`drop`, status=`dropped`, record `closed_at`. |
| FR-2.5.3 | Authorization rules match FR-2.4.3. |

**Acceptance Criteria (done/drop)**:
- AC-2.5.A: `/todo done 42` sets task #42 to done status with a non-null `closed_at` timestamp.
- AC-2.5.B: `/todo drop 42` sets task #42 to dropped status with a non-null `closed_at` timestamp.

#### FR-2.6 `/todo edit`

| ID | Requirement |
|----|------------|
| FR-2.6.1 | Update a task's title, assignees, project, section, and/or due date. |
| FR-2.6.2 | If mentions are provided, assignees are fully replaced (not appended). |
| FR-2.6.3 | `due:-` clears the due date. |
| FR-2.6.4 | If editing moves a task into or within a private project and any assignee is not the owner, reject with a warning. |
| FR-2.6.5 | Title is inferred from text preceding option tokens; if empty, title is unchanged. |

**Acceptance Criteria (edit)**:
- AC-2.6.A: `/todo edit 42 New title due:04-01` updates both title and due date; response confirms changes.
- AC-2.6.B: `/todo edit 42 <@U3>` replaces all assignees with U3 only.
- AC-2.6.C: `/todo edit 42 due:-` sets due to NULL.

### FR-3: Project Commands

#### FR-3.1 `/todo project list`

| ID | Requirement |
|----|------------|
| FR-3.1.1 | Return all shared projects and the sender's private projects. |
| FR-3.1.2 | Never expose other users' private projects. |

#### FR-3.2 `/todo project set-private <name>`

| ID | Requirement |
|----|------------|
| FR-3.2.1 | If the sender already owns a private project with `<name>`, return success (idempotent). |
| FR-3.2.2 | If a shared project `<name>` exists, attempt to convert it to private (owner=sender). |
| FR-3.2.3 | Before conversion, scan all tasks in the project. If ANY task has an assignee who is not the sender, reject with an error listing up to 10 violating task IDs and assignees. |
| FR-3.2.4 | If neither exists, create a new private project with owner=sender. |

**Acceptance Criteria (set-private)**:
- AC-3.2.A: Converting a shared project with only owner-assigned tasks succeeds; project visibility becomes `private`.
- AC-3.2.B: Converting a shared project where task #12 is assigned to `<@U2>` fails with an error message containing `#12` and `<@U2>`.
- AC-3.2.C: Running `set-private NewProj` when no project exists creates a private project owned by sender.

#### FR-3.3 `/todo project set-shared <name>`

| ID | Requirement |
|----|------------|
| FR-3.3.1 | If a shared project `<name>` exists, no-op. |
| FR-3.3.2 | If it does not exist, create it. |
| FR-3.3.3 | If a shared project with `<name>` already exists (global uniqueness conflict), return an error. |

### FR-4: Project Name Resolution

| ID | Requirement |
|----|------------|
| FR-4.1 | When `/p <name>` is specified, resolve by: (1) sender's private project with that name, (2) shared project with that name, (3) error or auto-create per context. |
| FR-4.2 | Shared project names MUST be globally unique. |
| FR-4.3 | Private project names MUST be unique per owner. |

### FR-5: Database Initialization

| ID | Requirement |
|----|------------|
| FR-5.1 | On first command or gateway startup, create the directory `~/.openclaw/workspace/.todo/` if absent. |
| FR-5.2 | Create `todo.sqlite3` with the full v1 schema if the file does not exist. |
| FR-5.3 | Create `schema_version` table and set version=1. |
| FR-5.4 | Auto-create shared project `Inbox` (idempotent). |
| FR-5.5 | Set `PRAGMA journal_mode=WAL` and `PRAGMA busy_timeout=3000` on every connection. |

**Acceptance Criteria (DB init)**:
- AC-5.A: Deleting the DB file and running any `/todo` command recreates the DB with all tables and the `Inbox` project.
- AC-5.B: `schema_version` table contains exactly one row with `version=1`.

### FR-6: Audit Events

| ID | Requirement |
|----|------------|
| FR-6.1 | Every state-changing command (add, move, done, drop, edit, set-private, set-shared) MUST insert a row into the `events` table. |
| FR-6.2 | Each event records: timestamp, actor user ID, action name, task ID (if applicable), and a JSON payload with before/after state. |

---

## 7. Non-Functional Requirements

| ID | Requirement | Metric |
|----|------------|--------|
| NFR-1 | **Latency**: Command response time | p95 < 500ms for any single command (excluding Slack network round-trip). |
| NFR-2 | **Reliability**: No data loss on concurrent writes | Zero data corruption over 1000 concurrent write operations using WAL mode. |
| NFR-3 | **Availability**: Plugin uptime | Matches OpenClaw Gateway uptime; no independent failure modes. |
| NFR-4 | **Correctness**: Date parsing | 100% of valid `YYYY-MM-DD` and `MM-DD` inputs produce correct stored dates; 100% of invalid dates return errors. |
| NFR-5 | **Security**: Private project isolation | Zero information leakage: private project tasks MUST never appear in another user's list/board output. |
| NFR-6 | **Testability**: Unit + integration test coverage | >= 80% line coverage on parser and command handler modules. |
| NFR-7 | **Maintainability**: Schema migration | Forward-only migrations; each migration is idempotent and wrapped in a transaction. |
| NFR-8 | **Capacity**: Task volume | Support up to 100,000 tasks per DB file without degradation beyond NFR-1. |

---

## 8. Success Metrics

| Metric | Target | Measurement |
|--------|--------|------------|
| Command success rate | >= 99% of well-formed commands execute without error | `events` table: count(success) / count(total) |
| Adoption | >= 5 active users within 2 weeks of deployment | Distinct `actor_user_id` in events table |
| Task throughput | >= 50 tasks created per week across team | Weekly count of `add` events |
| Mean response time | < 300ms (p50) | Instrumented timer in command handler |
| Test pass rate | 100% on CI before merge | pytest exit code |

---

## 9. Data Model Summary

Four core tables plus one metadata table:

- **projects** (id, name, visibility, owner_user_id, created_at, updated_at)
  - Unique index on `name` where `visibility='shared'`
  - Unique index on `(owner_user_id, name)` where `visibility='private'`
- **tasks** (id, title, project_id, section, due, status, created_by, created_at, updated_at, closed_at)
- **task_assignees** (task_id, assignee_user_id) -- composite PK
- **events** (id, ts, actor_user_id, action, task_id, payload)
- **schema_version** (version)

---

## 10. Traceability Matrix

| PRD Section | Requirement IDs |
|-------------|----------------|
| 2 (Slack usage) | FR-1.1, FR-1.2 |
| 3 (Core policies) | FR-4.1--4.3, FR-2.1.4, FR-2.6.4, FR-3.2.3 |
| 4 (Due parser) | FR-1.3--1.5 |
| 5 (Command spec) | FR-2.1--2.6, FR-3.1--3.3 |
| 6 (Data model) | Section 9 |
| 7 (DB init/migration) | FR-5.1--5.5 |
| 8 (Permissions) | FR-2.4.3, FR-2.5.3, NFR-5 |
| 9 (Acceptance) | All AC-* entries |
