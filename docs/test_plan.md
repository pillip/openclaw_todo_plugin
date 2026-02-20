# OpenClaw TODO Plugin -- Test Plan

> Based on PRD v1.1 at `/Users/pillip/project/practice/openclaw_todo_plugin/openclaw_todo_plugin_prd.md`
> Framework: **pytest** | DB: **SQLite3 (in-memory for tests)** | Date: 2026-02-20

---

## 1. Test Strategy

### 1.1 Objectives

- Validate all PRD acceptance criteria (Section 9).
- Ensure parser correctness for mentions, `/p`, `/s`, `due:` tokens.
- Verify DB schema creation, migration, and CRUD integrity.
- Confirm access-control rules for private/shared projects.
- Catch regressions early through an automatable smoke suite.

### 1.2 Test Levels

| Level | Scope | DB | Mocking |
|---|---|---|---|
| **Unit** | Parser functions, date normalization, individual command handlers | None or in-memory SQLite | Slack context mocked |
| **Integration** | Full command flow: parse -> handler -> DB -> response | In-memory SQLite | Slack API mocked |
| **E2E (lite)** | Multi-step scenarios (add then list, set-private with tasks) | Temp file SQLite | Slack API mocked |

### 1.3 Principles

- Every test must be **deterministic**. No real network calls; use `unittest.mock` or `pytest-mock`.
- Date-sensitive tests must **freeze time** (e.g., `freezegun` or manual patching of `datetime.now`).
- Tests touching SQLite use **in-memory** databases (`:memory:`) unless file-path behavior is explicitly under test.
- Mark slow or file-I/O tests with `@pytest.mark.integration`.

---

## 2. Fixtures Guidance

### 2.1 Core Fixtures (`conftest.py`)

| Fixture | Scope | Purpose |
|---|---|---|
| `db_conn` | function | Returns a fresh in-memory SQLite connection with schema applied and `PRAGMA journal_mode=WAL; PRAGMA busy_timeout=3000;` set. Tears down after each test. |
| `db_with_inbox` | function | Extends `db_conn`; also inserts the default shared `Inbox` project. |
| `sender_ctx` | function | Returns a mock Slack sender context: `{"user_id": "U_OWNER", "team_id": "T001"}`. |
| `other_user_ctx` | function | Returns a second mock user: `{"user_id": "U_OTHER", ...}`. |
| `frozen_now` | function | Patches `datetime.now()` to `2026-02-20T09:00:00` (Asia/Seoul). |
| `private_project` | function | Inserts a private project owned by `U_OWNER`. |
| `shared_project` | function | Inserts a shared project (e.g., "TeamWork"). |
| `sample_tasks` | function | Inserts a set of tasks across projects/sections for list/board tests. |

### 2.2 Fixture Composition

Tests that need both a private project and sample tasks should compose fixtures:

```
def test_example(db_with_inbox, private_project, sample_tasks, sender_ctx):
    ...
```

---

## 3. Test Cases -- Unit Tests

### 3.1 Parser Module

#### 3.1.1 Mention Extraction

| ID | Description | Input | Expected |
|---|---|---|---|
| P-MEN-01 | Single mention extracted | `"buy milk <@U123>"` | assignees=`["U123"]`, title=`"buy milk"` |
| P-MEN-02 | Multiple mentions | `"task <@U1> <@U2>"` | assignees=`["U1","U2"]` |
| P-MEN-03 | No mention defaults to sender | `"buy milk"` | assignees=`[sender_user_id]` |
| P-MEN-04 | Mention-like text without `<@` ignored | `"email @someone"` | assignees=`[sender_user_id]`, title includes `"@someone"` |

#### 3.1.2 Project Token (`/p`)

| ID | Description | Input | Expected |
|---|---|---|---|
| P-PRJ-01 | Project parsed | `"task /p MyProj"` | project=`"MyProj"`, title=`"task"` |
| P-PRJ-02 | No `/p` defaults to Inbox | `"task"` | project=`"Inbox"` |
| P-PRJ-03 | `/p` at end of string | `"task /p Work"` | project=`"Work"` |
| P-PRJ-04 | `/p` with no value is error | `"task /p"` | ParseError |

#### 3.1.3 Section Token (`/s`)

| ID | Description | Input | Expected |
|---|---|---|---|
| P-SEC-01 | Valid section parsed | `"task /s doing"` | section=`"doing"` |
| P-SEC-02 | Default section is backlog | `"task"` | section=`"backlog"` |
| P-SEC-03 | Invalid section rejected | `"task /s invalid"` | ParseError with message about valid sections |
| P-SEC-04 | All 5 enum values accepted | `"/s backlog"`, `"/s doing"`, `"/s waiting"`, `"/s done"`, `"/s drop"` | Each parsed correctly |

#### 3.1.4 Due Date Parsing

| ID | Description | Input | Expected |
|---|---|---|---|
| P-DUE-01 | Full date `YYYY-MM-DD` | `"due:2026-03-15"` | `"2026-03-15"` |
| P-DUE-02 | Short date `MM-DD` fills current year | `"due:03-15"` | `"2026-03-15"` (frozen year=2026) |
| P-DUE-03 | Single-digit `M-D` | `"due:3-5"` | `"2026-03-05"` |
| P-DUE-04 | Invalid date `02-30` | `"due:02-30"` | ParseError: invalid date |
| P-DUE-05 | Due clear `due:-` | `"due:-"` | due=`None` (clear) |
| P-DUE-06 | No due token | `"task"` | due=`None` |
| P-DUE-07 | Leap year valid `02-29` | `"due:2028-02-29"` | `"2028-02-29"` |
| P-DUE-08 | Non-leap year `02-29` | `"due:2026-02-29"` | ParseError |

#### 3.1.5 Combined Parsing

| ID | Description | Input | Expected |
|---|---|---|---|
| P-CMB-01 | All tokens present | `"buy milk <@U1> /p Home /s doing due:03-20"` | title=`"buy milk"`, assignees=`["U1"]`, project=`"Home"`, section=`"doing"`, due=`"2026-03-20"` |
| P-CMB-02 | Tokens in any order | `"/p Home due:03-20 buy milk /s doing <@U1>"` | Same as above |
| P-CMB-03 | Title is empty when only tokens | `"/p Home /s doing"` | title=`""` or ParseError (depends on command context) |

---

### 3.2 Due Date Normalization (standalone unit)

| ID | Description | Input | Expected |
|---|---|---|---|
| D-NORM-01 | Year auto-fill uses server year | `"06-15"` with frozen year 2026 | `"2026-06-15"` |
| D-NORM-02 | Full date passes through | `"2025-12-01"` | `"2025-12-01"` |
| D-NORM-03 | Garbage input rejected | `"abc"` | ValueError |
| D-NORM-04 | Empty string rejected | `""` | ValueError |

---

### 3.3 DB Operations (schema and CRUD)

#### 3.3.1 Schema Initialization

| ID | Description | Steps | Expected |
|---|---|---|---|
| DB-INIT-01 | Fresh DB creates all tables | Initialize on `:memory:` | Tables `projects`, `tasks`, `task_assignees`, `events`, `schema_version` exist |
| DB-INIT-02 | `schema_version` set to 1 | After init | `SELECT version FROM schema_version` returns `1` |
| DB-INIT-03 | Default `Inbox` project created | After init | Shared project named `Inbox` exists |
| DB-INIT-04 | WAL journal mode set | After init | `PRAGMA journal_mode` returns `wal` |
| DB-INIT-05 | Idempotent init (run twice) | Init -> Init again | No error, schema unchanged |

#### 3.3.2 Project CRUD

| ID | Description | Steps | Expected |
|---|---|---|---|
| DB-PRJ-01 | Create shared project | Insert `(name="Work", visibility="shared")` | Row inserted, id returned |
| DB-PRJ-02 | Duplicate shared name rejected | Insert `Inbox` again | UNIQUE constraint error |
| DB-PRJ-03 | Create private project | Insert `(name="Personal", visibility="private", owner="U1")` | Success |
| DB-PRJ-04 | Same-name private for different owners | owner=U1 "X", owner=U2 "X" | Both succeed |
| DB-PRJ-05 | Same-name private for same owner rejected | owner=U1 "X" twice | UNIQUE constraint error |
| DB-PRJ-06 | Shared and private can share name | shared "Work" + private(U1) "Work" | Both exist |

#### 3.3.3 Task CRUD

| ID | Description | Steps | Expected |
|---|---|---|---|
| DB-TSK-01 | Insert task with all fields | Full insert | Row with auto-increment id |
| DB-TSK-02 | Section enum enforced | Insert section="invalid" | CHECK constraint error |
| DB-TSK-03 | Status enum enforced | Insert status="pending" | CHECK constraint error |
| DB-TSK-04 | Assignees linked correctly | Insert task -> insert 2 assignees | `task_assignees` has 2 rows |
| DB-TSK-05 | Update section | Change backlog -> doing | section updated, updated_at changed |
| DB-TSK-06 | Mark done sets closed_at | `done` command | status=`done`, section=`done`, closed_at not null |

---

## 4. Test Cases -- Command Handlers

### 4.1 `/todo add`

| ID | Description | Input | Preconditions | Expected |
|---|---|---|---|---|
| CMD-ADD-01 | Basic add to Inbox | `add buy milk` | Inbox exists | Task in Inbox/backlog, assignee=sender |
| CMD-ADD-02 | Add with project and section | `add task /p Work /s doing` | "Work" shared exists | Task in Work/doing |
| CMD-ADD-03 | Add with assignees | `add task <@U2> <@U3>` | -- | assignees=[U2, U3] |
| CMD-ADD-04 | Add with due date | `add task due:03-15` | -- | due="2026-03-15" |
| CMD-ADD-05 | Add to nonexistent project (Inbox auto-create) | `add task` | No Inbox | Inbox auto-created, task added |
| CMD-ADD-06 | **REJECT**: Add to private project with non-owner assignee | `add task <@U_OTHER> /p MyPrivate` | MyPrivate is private, owner=sender | Warning message, task NOT created |
| CMD-ADD-07 | Add to private project with owner assignee | `add task /p MyPrivate` | owner=sender | Task created successfully |
| CMD-ADD-08 | Response format matches spec | `add buy milk` | -- | Response contains `#id`, project/section, due, assignees, title |

### 4.2 `/todo list`

| ID | Description | Input | Preconditions | Expected |
|---|---|---|---|---|
| CMD-LST-01 | Default list (mine, open) | `list` | Tasks exist | Only sender's open tasks |
| CMD-LST-02 | List all | `list all` | Shared + private tasks | Shared all + sender's private only |
| CMD-LST-03 | List by user | `list <@U2>` | U2 has tasks | Only U2's tasks |
| CMD-LST-04 | Filter by project | `list /p Work` | -- | Only Work project tasks |
| CMD-LST-05 | Filter by section | `list /s doing` | -- | Only doing section |
| CMD-LST-06 | Limit applied | `list limit:5` | 10+ tasks | Exactly 5 returned |
| CMD-LST-07 | Default limit is 30 | `list` | 50 tasks | 30 returned |
| CMD-LST-08 | Sort order: due first, due asc, id desc | `list` | Mixed due/no-due tasks | Correct ordering |
| CMD-LST-09 | **HIDDEN**: Other user's private project tasks not visible | `list all` | U_OTHER has private project with tasks | Those tasks excluded |
| CMD-LST-10 | Status filters: done, drop | `list done` | -- | Only done/dropped tasks respectively |

### 4.3 `/todo board`

| ID | Description | Input | Preconditions | Expected |
|---|---|---|---|---|
| CMD-BRD-01 | Board shows all 5 sections in order | `board` | Tasks in various sections | BACKLOG -> DOING -> WAITING -> DONE -> DROP |
| CMD-BRD-02 | Default scope is mine | `board` | -- | Only sender's tasks |
| CMD-BRD-03 | limitPerSection applied | `board limitPerSection:2` | 5 tasks per section | 2 per section max |
| CMD-BRD-04 | Private project tasks only for owner | `board all` | Private project tasks exist | Sender sees own private, not others' |

### 4.4 `/todo move`

| ID | Description | Input | Preconditions | Expected |
|---|---|---|---|---|
| CMD-MOV-01 | Move to valid section | `move 1 doing` | Task #1 in backlog | section=doing |
| CMD-MOV-02 | Invalid section rejected | `move 1 invalid` | -- | Error: invalid section |
| CMD-MOV-03 | **REJECT**: Non-owner moves private task | `move 1 doing` (sender=U_OTHER) | Task #1 in private project, owner=U_OWNER | Permission denied |
| CMD-MOV-04 | Shared task: assignee can move | `move 1 doing` (sender=assignee) | -- | Success |
| CMD-MOV-05 | Shared task: creator can move | `move 1 doing` (sender=created_by) | -- | Success |
| CMD-MOV-06 | Nonexistent task id | `move 999 doing` | -- | Error: task not found |

### 4.5 `/todo done`

| ID | Description | Input | Preconditions | Expected |
|---|---|---|---|---|
| CMD-DON-01 | Mark task done | `done 1` | Task #1 open | section=done, status=done, closed_at set |
| CMD-DON-02 | Already done task | `done 1` | Task #1 already done | Idempotent or informational message |
| CMD-DON-03 | Permission check on private task | `done 1` (non-owner) | Private project | Denied |

### 4.6 `/todo drop`

| ID | Description | Input | Preconditions | Expected |
|---|---|---|---|---|
| CMD-DRP-01 | Drop task | `drop 1` | Task #1 open | section=drop, status=dropped, closed_at set |
| CMD-DRP-02 | Permission check | `drop 1` (non-owner) | Private project | Denied |

### 4.7 `/todo edit`

| ID | Description | Input | Preconditions | Expected |
|---|---|---|---|---|
| CMD-EDT-01 | Edit title only | `edit 1 new title` | Task #1 exists | title updated |
| CMD-EDT-02 | Edit assignees (replace) | `edit 1 <@U2> <@U3>` | -- | assignees fully replaced |
| CMD-EDT-03 | Clear due | `edit 1 due:-` | Task has due | due=NULL |
| CMD-EDT-04 | Change project | `edit 1 /p NewProj` | -- | project_id updated |
| CMD-EDT-05 | Change section | `edit 1 /s waiting` | -- | section updated |
| CMD-EDT-06 | **REJECT**: Edit in private project with non-owner assignee | `edit 1 <@U_OTHER>` | Task in private project, owner=sender | Warning, no change applied |
| CMD-EDT-07 | **REJECT**: Move task to private project with non-owner assignee | `edit 1 /p PrivateProj` | Task has assignee U_OTHER | Warning, no change applied |
| CMD-EDT-08 | No title change when only option tokens given | `edit 1 /s doing` | title="original" | title remains "original" |
| CMD-EDT-09 | Nonexistent task | `edit 999 new title` | -- | Error: task not found |

---

## 5. Test Cases -- Project Commands

### 5.1 `/todo project list`

| ID | Description | Sender | Expected |
|---|---|---|---|
| PRJ-LST-01 | Returns shared projects | U1 | All shared projects |
| PRJ-LST-02 | Returns sender's private projects | U1 | Only U1's private projects |
| PRJ-LST-03 | Does not return other user's private | U1 | U2's private excluded |

### 5.2 `/todo project set-private`

| ID | Description | Preconditions | Expected |
|---|---|---|---|
| PRJ-SPR-01 | Already private -- noop | Private "X" owned by sender | Success/noop message |
| PRJ-SPR-02 | Shared to private -- no tasks | Shared "X" with 0 tasks | Converted: visibility=private, owner=sender |
| PRJ-SPR-03 | Shared to private -- all tasks owner-assigned | Shared "X", all assignees=sender | Converted successfully |
| PRJ-SPR-04 | **REJECT**: Shared to private -- non-owner assignees exist | Shared "X", task #12 has assignee U_OTHER | Error with task ids and assignee list |
| PRJ-SPR-05 | Error message includes violating task ids | Same as PRJ-SPR-04 | Message contains `#12` and `<@U_OTHER>` |
| PRJ-SPR-06 | Error caps listed violations at 10 | 15+ violating tasks | Max 10 task ids shown |
| PRJ-SPR-07 | Neither exists -- create new private | No project "X" | New private project created, owner=sender |

### 5.3 `/todo project set-shared`

| ID | Description | Preconditions | Expected |
|---|---|---|---|
| PRJ-SSH-01 | Create new shared project | Name does not exist | Created |
| PRJ-SSH-02 | Already shared -- noop | Shared "X" exists | No error, noop |
| PRJ-SSH-03 | Name conflict with existing shared | Shared "X" exists, try set-shared "X" | Noop or "already exists" |

---

## 6. Test Cases -- Edge Cases and PRD-Specific Scenarios

### 6.1 Project Name Collision Resolution (Option A: Private First)

| ID | Description | Setup | Command | Expected |
|---|---|---|---|---|
| EDGE-COL-01 | Private and shared same name -- `/p` resolves to private | Private(U1) "Work" + Shared "Work" | `add task /p Work` (sender=U1) | Task added to **private** "Work" |
| EDGE-COL-02 | No private -- falls to shared | Only shared "Work" | `add task /p Work` (sender=U1) | Task added to **shared** "Work" |
| EDGE-COL-03 | Neither exists -- auto-create behavior | No "NewProj" | `add task /p NewProj` | Shared auto-create or error (per v1 policy) |

### 6.2 Access Control Boundaries

| ID | Description | Expected |
|---|---|---|
| EDGE-ACL-01 | Non-owner cannot list private project tasks | Empty result or error |
| EDGE-ACL-02 | Non-owner cannot add to private project | Permission denied |
| EDGE-ACL-03 | Non-owner cannot move/done/drop private task | Permission denied |
| EDGE-ACL-04 | Non-owner cannot edit private task | Permission denied |

### 6.3 Concurrency and DB Integrity

| ID | Description | Expected |
|---|---|---|
| EDGE-DB-01 | Unique index prevents duplicate shared project names | UNIQUE constraint violation |
| EDGE-DB-02 | Unique index allows same private name for different owners | Both inserted |
| EDGE-DB-03 | WAL mode enabled on connection | `PRAGMA journal_mode` returns `wal` |

### 6.4 Schema Migration

| ID | Description | Expected |
|---|---|---|
| EDGE-MIG-01 | Fresh DB gets version 1 | schema_version=1 |
| EDGE-MIG-02 | Re-init on existing DB is safe | No duplicate tables, version unchanged |
| EDGE-MIG-03 | DB directory auto-created | `~/.openclaw/workspace/.todo/` created if missing |

---

## 7. Acceptance Criteria Traceability

Mapping each PRD acceptance criterion (Section 9) to test cases.

| PRD Criterion | Test Case IDs |
|---|---|
| Shared project name collision rejected | DB-PRJ-02, PRJ-SSH-03, EDGE-COL-03 |
| Private project owner-unique (cross-owner OK) | DB-PRJ-04, DB-PRJ-05, EDGE-DB-02 |
| `set-private` rejects when non-owner assignees exist | PRJ-SPR-04, PRJ-SPR-05, PRJ-SPR-06 |
| Private project + non-owner assignee = warning + reject | CMD-ADD-06, CMD-EDT-06, CMD-EDT-07 |
| `due:MM-DD` fills current year | P-DUE-02, P-DUE-03, D-NORM-01 |
| DB first-run: file + schema + Inbox | DB-INIT-01 through DB-INIT-05, EDGE-MIG-01, EDGE-MIG-03 |

---

## 8. Automation Candidates

### 8.1 High Priority (automate first)

| Area | Rationale |
|---|---|
| **Parser unit tests** (Section 3.1) | Pure functions, fast, high regression value. Run on every commit. |
| **Due date normalization** (Section 3.2) | Date logic is error-prone; requires time-freezing. |
| **DB schema init** (Section 3.3.1) | Catches migration regressions early. |
| **Private project access control** (Sections 4, 5, 6.2) | Security-critical; must never regress. |

### 8.2 Medium Priority

| Area | Rationale |
|---|---|
| **Command handler integration** (Section 4) | Parse-to-DB flow; requires fixture setup but high coverage value. |
| **Project name collision resolution** (Section 6.1) | Logic is subtle (Option A). |

### 8.3 Lower Priority / Manual

| Area | Rationale |
|---|---|
| **Response message formatting** | Cosmetic; snapshot testing if desired. |
| **Concurrency under load** | Harder to automate reliably in CI; manual or stress-test script. |

### 8.4 Suggested pytest Marks

```python
# conftest.py or pyproject.toml
markers = [
    "unit: Pure unit tests (no DB, no I/O)",
    "integration: Tests requiring DB or multi-component interaction",
    "slow: Tests with file I/O or significant setup",
]
```

---

## 9. Smoke Checklist

A minimal set of tests to run before any release or deployment. If any fail, the build is not shippable.

- [ ] **SMOKE-01**: DB initializes without error on empty state (DB-INIT-01)
- [ ] **SMOKE-02**: Default `Inbox` project exists after init (DB-INIT-03)
- [ ] **SMOKE-03**: `/todo add buy milk` creates a task in Inbox/backlog (CMD-ADD-01)
- [ ] **SMOKE-04**: `/todo list` returns the just-added task (CMD-LST-01)
- [ ] **SMOKE-05**: `/todo done <id>` marks task done with closed_at (CMD-DON-01)
- [ ] **SMOKE-06**: `/todo add task <@U_OTHER> /p PrivateProj` is rejected (CMD-ADD-06)
- [ ] **SMOKE-07**: `/todo project set-private` with non-owner assignees fails (PRJ-SPR-04)
- [ ] **SMOKE-08**: `due:03-15` parses to `2026-03-15` (P-DUE-02)
- [ ] **SMOKE-09**: Invalid due `due:02-30` returns error (P-DUE-04)
- [ ] **SMOKE-10**: `/todo board` renders sections in correct order (CMD-BRD-01)

Run with:
```bash
uv run pytest -m smoke -q --tb=short
```

---

## 10. Test Directory Structure (Recommended)

```
tests/
  conftest.py              # Shared fixtures (db_conn, sender_ctx, etc.)
  test_parser.py           # 3.1 Parser tests (P-MEN, P-PRJ, P-SEC, P-DUE, P-CMB)
  test_due_normalization.py # 3.2 Date normalization
  test_db_schema.py        # 3.3.1 Schema init and migration
  test_db_projects.py      # 3.3.2 Project CRUD
  test_db_tasks.py         # 3.3.3 Task CRUD
  test_cmd_add.py          # 4.1 /todo add
  test_cmd_list.py         # 4.2 /todo list
  test_cmd_board.py        # 4.3 /todo board
  test_cmd_move.py         # 4.4 /todo move
  test_cmd_done_drop.py    # 4.5-4.6 /todo done, drop
  test_cmd_edit.py         # 4.7 /todo edit
  test_project_cmds.py     # 5.1-5.3 project list/set-private/set-shared
  test_edge_cases.py       # 6.x Edge cases and collision resolution
```
