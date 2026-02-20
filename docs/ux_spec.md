# OpenClaw TODO Plugin -- UX Specification

> Version 1.0 | 2026-02-20
> Based on PRD v1.1 (DM-based)

---

## Table of Contents

1. [Overview](#1-overview)
2. [Interaction Model](#2-interaction-model)
3. [Command Reference and User Flows](#3-command-reference-and-user-flows)
4. [Response Formatting](#4-response-formatting)
5. [Error Messages](#5-error-messages)
6. [Edge Cases](#6-edge-cases)
7. [Input Parsing Rules](#7-input-parsing-rules)

---

## 1. Overview

The OpenClaw TODO Plugin is a text-based task management system that lives inside Slack DMs. Users interact with the bot by sending messages that start with `/todo`. The bot parses the command and replies in the same DM thread with structured, plain-text responses.

### Design Principles

- **Zero ambiguity**: Every command produces exactly one response. The user always knows whether the action succeeded or failed.
- **Minimal typing**: Sensible defaults (project = `Inbox`, section = `backlog`, assignee = sender) mean most commands need only a title.
- **Scannable output**: Responses use fixed-width IDs, consistent emoji prefixes, and aligned columns so users can scan quickly.
- **Fail loudly**: Invalid input is rejected with a clear reason and the original request is not applied. No partial writes.

---

## 2. Interaction Model

### 2.1 Entry Point

The user opens a DM conversation with the OpenClaw Slack bot and types messages beginning with `/todo`.

### 2.2 Message Recognition

| Message pattern | Bot behavior |
|---|---|
| Starts with `/todo` | Parsed as a command |
| Anything else | Ignored silently (no reply) |

### 2.3 Response Timing

The bot replies in the same DM channel. All responses are ephemeral-style (visible only to the sender) when technically possible; otherwise they appear as normal bot messages in the DM.

### 2.4 No Confirmation Dialogs

v1 has no interactive buttons, modals, or confirmation prompts. Every command is executed (or rejected) immediately upon receipt.

---

## 3. Command Reference and User Flows

### 3.1 `/todo add` -- Create a Task

**Purpose**: Create a new task with optional project, section, assignees, and due date.

**Syntax**:
```
/todo add <title> [@user ...] [/p <project>] [/s <section>] [due:<date>]
```

**Defaults**:
| Parameter | Default |
|---|---|
| project | `Inbox` |
| section | `backlog` |
| assignees | sender |
| due | none |

**Flow**:
1. User sends `/todo add Buy groceries`
2. Bot creates task in Inbox/backlog, assigns to sender
3. Bot replies with confirmation

**Examples**:

```
Input:  /todo add Buy groceries
Output: :white_check_mark: Added #42 (Inbox/backlog) due:- assignees:@phil -- Buy groceries
```

```
Input:  /todo add Fix login bug @alice /p Backend /s doing due:2026-03-15
Output: :white_check_mark: Added #43 (Backend/doing) due:2026-03-15 assignees:@alice -- Fix login bug
```

```
Input:  /todo add Review PR @bob @carol /p Frontend
Output: :white_check_mark: Added #44 (Frontend/backlog) due:- assignees:@bob, @carol -- Review PR
```

**Success response format**:
```
:white_check_mark: Added #<id> (<project>/<section>) due:<date|-> assignees:<@user>[, <@user>...] -- <title>
```

---

### 3.2 `/todo list` -- List Tasks

**Purpose**: Display a filtered, sorted list of tasks.

**Syntax**:
```
/todo list [mine|all|@user] [/p <project>] [/s <section>] [open|done|drop] [limit:N]
```

**Defaults**:
| Parameter | Default |
|---|---|
| scope | `mine` |
| status filter | `open` |
| limit | 30 |

**Flow**:
1. User sends `/todo list`
2. Bot queries tasks where sender is an assignee, status is open
3. Bot returns a numbered list sorted by due date (ascending, nulls last), then by ID (descending)

**Example output**:
```
:clipboard: TODO List (mine / open) -- 3 tasks

#50  due:2026-02-21  (Backend/doing)    @phil        Deploy hotfix
#48  due:2026-03-01  (Inbox/backlog)    @phil        Buy groceries
#45  due:-           (Frontend/waiting) @phil, @bob  Review PR

Showing 3 of 3. Use limit:N to see more.
```

**Empty state**:
```
:clipboard: TODO List (mine / open) -- 0 tasks

No tasks found.
```

**Scope behavior**:
| Scope | What it shows |
|---|---|
| `mine` | Tasks where sender is in the assignee list |
| `all` | All shared tasks + sender's private tasks (never other users' private tasks) |
| `@user` | Tasks where the mentioned user is an assignee (shared projects only, plus sender's private if sender = mentioned user) |

---

### 3.3 `/todo board` -- Kanban Board View

**Purpose**: Display tasks grouped by section in a kanban-style text layout.

**Syntax**:
```
/todo board [mine|all|@user] [/p <project>] [open|done|drop] [limitPerSection:N]
```

**Defaults**:
| Parameter | Default |
|---|---|
| scope | `mine` |
| status filter | `open` |
| limitPerSection | 10 |

**Flow**:
1. User sends `/todo board /p Backend`
2. Bot queries matching tasks and groups them by section
3. Bot returns sections in fixed order: BACKLOG, DOING, WAITING, DONE, DROP

**Example output**:
```
:bar_chart: Board (mine / open) /p Backend

-- BACKLOG (2) --
#50  due:2026-03-10  @phil        Set up CI pipeline
#47  due:-           @phil        Write migration script

-- DOING (1) --
#51  due:2026-02-22  @phil        Deploy hotfix

-- WAITING (0) --
(empty)

-- DONE (0) --
(empty)

-- DROP (0) --
(empty)
```

**Notes**:
- Sections with zero items still appear with `(empty)` to maintain the full board structure.
- Each section header shows the count of items.
- When `limitPerSection` is reached, append `... and N more` below the last item in that section.

---

### 3.4 `/todo move` -- Move a Task to a Different Section

**Purpose**: Change the section (kanban column) of a task.

**Syntax**:
```
/todo move <id> <section>
```

**Valid sections**: `backlog`, `doing`, `waiting`, `done`, `drop`

**Flow**:
1. User sends `/todo move 50 doing`
2. Bot validates permission and section name
3. Bot updates the task and replies

**Example**:
```
Input:  /todo move 50 doing
Output: :arrow_right: Moved #50 to doing (Backend) -- Deploy hotfix
```

---

### 3.5 `/todo done` -- Mark a Task as Done

**Purpose**: Shortcut to move a task to the `done` section and set its status to `done`.

**Syntax**:
```
/todo done <id>
```

**Flow**:
1. User sends `/todo done 50`
2. Bot sets section=done, status=done, records closed_at
3. Bot replies with confirmation

**Example**:
```
Input:  /todo done 50
Output: :white_check_mark: Done #50 (Backend) -- Deploy hotfix
```

---

### 3.6 `/todo drop` -- Drop a Task

**Purpose**: Mark a task as dropped (cancelled/abandoned).

**Syntax**:
```
/todo drop <id>
```

**Flow**:
1. User sends `/todo drop 50`
2. Bot sets section=drop, status=dropped, records closed_at
3. Bot replies with confirmation

**Example**:
```
Input:  /todo drop 50
Output: :wastebasket: Dropped #50 (Backend) -- Deploy hotfix
```

---

### 3.7 `/todo edit` -- Edit a Task

**Purpose**: Modify one or more fields of an existing task.

**Syntax**:
```
/todo edit <id> [<new title>] [@user ...] [/p <project>] [/s <section>] [due:<date>|due:-]
```

**Rules**:
- If `@user` mentions are present, the assignee list is **fully replaced** (not appended).
- `due:-` clears the due date (sets it to null).
- New title text is everything before the first option token (`/p`, `/s`, `due:`, or `@mention`). If empty, the title is unchanged.
- Fields not specified in the command remain unchanged.

**Flow**:
1. User sends `/todo edit 50 Deploy hotfix v2 due:2026-03-01`
2. Bot updates title and due date
3. Bot replies with the updated state

**Example**:
```
Input:  /todo edit 50 Deploy hotfix v2 due:2026-03-01
Output: :pencil2: Edited #50 (Backend/doing) due:2026-03-01 assignees:@phil -- Deploy hotfix v2
```

```
Input:  /todo edit 50 @alice @bob
Output: :pencil2: Edited #50 (Backend/doing) due:2026-03-01 assignees:@alice, @bob -- Deploy hotfix v2
```

```
Input:  /todo edit 50 due:-
Output: :pencil2: Edited #50 (Backend/doing) due:- assignees:@alice, @bob -- Deploy hotfix v2
```

**Success response format** (same structure as add):
```
:pencil2: Edited #<id> (<project>/<section>) due:<date|-> assignees:<@user>[, ...] -- <title>
```

---

### 3.8 `/todo project list` -- List Projects

**Purpose**: Show all projects visible to the sender.

**Syntax**:
```
/todo project list
```

**Flow**:
1. User sends `/todo project list`
2. Bot returns shared projects and the sender's private projects

**Example output**:
```
:file_folder: Projects

Shared:
  - Inbox (12 tasks)
  - Backend (5 tasks)
  - Frontend (8 tasks)

Private (yours):
  - Personal (3 tasks)
  - Side Project (1 task)
```

**Empty state**:
```
:file_folder: Projects

Shared:
  - Inbox (0 tasks)

Private (yours):
  (none)
```

---

### 3.9 `/todo project set-private <name>` -- Make a Project Private

**Purpose**: Convert a shared project to private or create a new private project.

**Syntax**:
```
/todo project set-private <name>
```

**Flow**:

Case A -- Project does not exist:
1. Bot creates a new private project owned by the sender.
2. Reply: `:lock: Created private project "<name>".`

Case B -- Sender already has a private project with this name:
1. Reply: `:lock: Project "<name>" is already private.`

Case C -- Shared project exists, conversion attempt:
1. Bot scans all tasks in the project for non-owner assignees.
2. If none found: convert to private, reply `:lock: Project "<name>" is now private.`
3. If found: reject with error (see [Section 5.3](#53-set-private-validation-error)).

---

### 3.10 `/todo project set-shared <name>` -- Make a Project Shared

**Purpose**: Convert a private project to shared or create a new shared project.

**Syntax**:
```
/todo project set-shared <name>
```

**Flow**:

Case A -- Shared project with this name already exists:
1. Reply: `:globe_with_meridians: Project "<name>" is already shared.`

Case B -- No shared project with this name:
1. Bot creates (or converts) the project to shared visibility.
2. Reply: `:globe_with_meridians: Project "<name>" is now shared.`

Case C -- Name conflict with an existing shared project:
1. Reply: `:x: A shared project named "<name>" already exists.`

---

## 4. Response Formatting

### 4.1 General Structure

All bot responses follow this pattern:

```
<emoji> <Action verb> <details>
```

| Action | Emoji | Verb |
|---|---|---|
| Add | :white_check_mark: | Added |
| List | :clipboard: | TODO List |
| Board | :bar_chart: | Board |
| Move | :arrow_right: | Moved |
| Done | :white_check_mark: | Done |
| Drop | :wastebasket: | Dropped |
| Edit | :pencil2: | Edited |
| Project list | :file_folder: | Projects |
| Set private | :lock: | (varies by case) |
| Set shared | :globe_with_meridians: | (varies by case) |
| Error | :x: | (error message) |
| Warning/reject | :warning: | (warning message) |

### 4.2 Task Line Format

Whenever a single task is displayed inline (in list, board, or as a command result), it uses:

```
#<id>  due:<YYYY-MM-DD|->  (<project>/<section>)  <assignees>  <title>
```

- `id`: Left-padded for alignment in lists (e.g., `#42`, `# 7` -- optional, simple left-align is acceptable in v1).
- `due`: Always shown. `-` when no due date.
- `assignees`: Comma-separated Slack mentions. Displayed as `@username` in Slack's rendered view.
- `title`: The full task title, untruncated.

### 4.3 List/Board Headers

Lists and boards begin with a header line summarizing the query:

```
:clipboard: TODO List (<scope> / <status>) -- <count> tasks
```
```
:bar_chart: Board (<scope> / <status>) [/p <project>]
```

### 4.4 Pagination Footer

When the result set exceeds the limit:
```
Showing <displayed> of <total>. Use limit:N to see more.
```

For board view:
```
... and <N> more
```
(appears below the last item in a section that hit `limitPerSection`)

### 4.5 Text Encoding

- All responses are plain Slack mrkdwn (Slack's markdown variant).
- No block kit or attachments in v1.
- User mentions are rendered as `<@UXXXXXXXX>` which Slack auto-formats.

---

## 5. Error Messages

### 5.1 Input Validation Errors

| Condition | Error message |
|---|---|
| Unknown command | `:x: Unknown command. Available: add, list, board, move, done, drop, edit, project` |
| Missing title on add | `:x: Title is required. Usage: /todo add <title> [options]` |
| Missing task ID | `:x: Task ID is required. Usage: /todo <command> <id>` |
| Invalid task ID (not a number) | `:x: Invalid task ID "<input>". Must be a number.` |
| Task not found | `:x: Task #<id> not found.` |
| Invalid section name | `:x: Invalid section "<input>". Must be one of: backlog, doing, waiting, done, drop` |
| Invalid date format | `:x: Invalid date "<input>". Use YYYY-MM-DD or MM-DD.` |
| Invalid date value (e.g. 02-30) | `:x: Invalid date "02-30". This date does not exist.` |
| Empty project name | `:x: Project name is required after /p.` |

### 5.2 Permission Errors

| Condition | Error message |
|---|---|
| Accessing another user's private project | `:x: Project "<name>" not found.` (deliberately vague to avoid leaking existence) |
| Editing a task without permission | `:x: You don't have permission to modify task #<id>.` |

### 5.3 Set-Private Validation Error

When `/todo project set-private` fails due to non-owner assignees:

```
:x: Cannot set project "<name>" to private: found tasks assigned to non-owner users.
e.g. #12 assignees:@alice, #18 assignees:@carol, #21 assignees:@bob
Please reassign or remove these assignees first.
```

- Show up to 10 violating tasks.
- If more than 10, append: `... and <N> more tasks with external assignees.`

### 5.4 Private Project Assignee Rejection

When trying to assign a non-owner user to a task in a private project (on add or edit):

```
:warning: Private project "<name>" is owner-only. Cannot assign <@user> (not the owner).
Request was not applied.
```

### 5.5 Project Name Conflicts

| Condition | Error message |
|---|---|
| Creating/renaming to an existing shared name | `:x: A shared project named "<name>" already exists.` |
| Private name conflict for same owner | `:x: You already have a private project named "<name>".` |

---

## 6. Edge Cases

### 6.1 Empty Inputs

| Scenario | Behavior |
|---|---|
| `/todo` (no subcommand) | Reply with help text listing available commands |
| `/todo add` (no title) | Error: title required |
| `/todo edit 50` (no changes) | Reply: `:information_source: No changes specified for #50.` |
| `/todo list /p NonExistent` | Error: project not found |

### 6.2 Duplicate Operations

| Scenario | Behavior |
|---|---|
| `/todo done 50` when already done | Reply: `:information_source: Task #50 is already done.` |
| `/todo drop 50` when already dropped | Reply: `:information_source: Task #50 is already dropped.` |
| `/todo move 50 doing` when already in doing | Reply: `:information_source: Task #50 is already in doing.` |

### 6.3 Project Auto-Creation

- When `/todo add ... /p NewProject` references a project that does not exist, the bot creates it as a **shared** project automatically and includes a note in the response:
  ```
  :white_check_mark: Added #55 (NewProject/backlog) due:- assignees:@phil -- Task title
  :information_source: Project "NewProject" was created (shared).
  ```
- Exception: `Inbox` is always auto-created as shared if it does not exist.

### 6.4 Case Sensitivity

- **Section names**: Case-insensitive input, stored lowercase. `DOING`, `Doing`, `doing` all resolve to `doing`.
- **Project names**: Case-sensitive. `Backend` and `backend` are different projects.
- **Commands**: Case-insensitive. `/todo ADD`, `/TODO add`, `/todo Add` all work.

### 6.5 Whitespace and Formatting

- Leading/trailing whitespace in titles is trimmed.
- Multiple spaces between words in a title are collapsed to a single space.
- Empty title after trimming triggers the "title required" error.

### 6.6 Special Characters in Titles

- Titles may contain any UTF-8 characters except newlines.
- Slack mrkdwn special characters (`*`, `_`, `~`, `` ` ``) in titles are escaped in the response to prevent formatting artifacts.

### 6.7 Due Date Edge Cases

| Input | Resolved date (assuming current year 2026) |
|---|---|
| `due:2026-03-15` | `2026-03-15` |
| `due:03-15` | `2026-03-15` |
| `due:3-5` | `2026-03-05` |
| `due:02-29` | Error (2026 is not a leap year) |
| `due:00-01` | Error (invalid month) |
| `due:12-32` | Error (invalid day) |
| `due:-` | Clears due date (null) |
| `due:yesterday` | Error (invalid format) |

---

## 7. Input Parsing Rules

### 7.1 Token Order

The parser processes the message left to right. Recognized option tokens are:

| Token | Pattern | Notes |
|---|---|---|
| `/p` | `/p <word>` | Next whitespace-delimited word is the project name |
| `/s` | `/s <word>` | Next word is the section name |
| `due:` | `due:<value>` | No space between `due:` and the value |
| `@mention` | `<@UXXXXXXXX>` | Slack user mention (may appear multiple times) |
| `limit:` | `limit:<N>` | Positive integer |
| `limitPerSection:` | `limitPerSection:<N>` | Positive integer |

### 7.2 Title Extraction (for add/edit)

Everything that is **not** a recognized option token or mention is treated as the title. The title words are concatenated in their original order.

Example parse:
```
/todo add Fix the login bug @alice /p Backend due:03-15

Parsed:
  command   = add
  title     = "Fix the login bug"
  assignees = [@alice]
  project   = "Backend"
  due       = "2026-03-15"
  section   = (default: backlog)
```

### 7.3 Mention Handling

- Slack internally sends mentions as `<@U04ABCD1234>`.
- The bot resolves these to display names in responses when possible.
- If a mentioned user cannot be resolved, the raw `<@U...>` format is preserved.

### 7.4 Scope Keywords (for list/board)

The first non-option argument after the subcommand determines scope:

| Keyword | Meaning |
|---|---|
| `mine` (or omitted) | Tasks assigned to sender |
| `all` | Shared tasks + sender's private tasks |
| `@user` | Tasks assigned to the mentioned user |

### 7.5 Status Keywords (for list/board)

| Keyword | Meaning |
|---|---|
| `open` (or omitted) | Tasks with status = open |
| `done` | Tasks with status = done |
| `drop` | Tasks with status = dropped |

---

## Appendix: Help Text

When the user sends `/todo` with no subcommand (or `/todo help`), the bot replies:

```
:book: OpenClaw TODO -- Commands

/todo add <title> [@user] [/p project] [/s section] [due:date]
    Create a new task.

/todo list [mine|all|@user] [/p project] [/s section] [open|done|drop] [limit:N]
    List tasks.

/todo board [mine|all|@user] [/p project] [open|done|drop] [limitPerSection:N]
    Show kanban board view.

/todo move <id> <section>
    Move a task to a section (backlog, doing, waiting, done, drop).

/todo done <id>
    Mark a task as done.

/todo drop <id>
    Drop (cancel) a task.

/todo edit <id> [title] [@user] [/p project] [/s section] [due:date|due:-]
    Edit a task. Mentions replace all assignees. due:- clears the date.

/todo project list
    Show all visible projects.

/todo project set-private <name>
    Make a project private (owner-only).

/todo project set-shared <name>
    Make a project shared.
```
