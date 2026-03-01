# OpenClaw TODO Plugin

Slack DM-based team/personal TODO system — an OpenClaw plugin.
`/todo` 접두사로 LLM 없이 직접 실행되는 결정적(deterministic) TODO 관리 도구.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager

## Setup

```bash
# Clone and initialize
git clone <repo-url>
cd openclaw_todo_plugin

# Install dependencies
uv sync
```

## Run

### Native mode (OpenClaw Gateway)

플러그인은 OpenClaw Gateway에 설치되어 `/todo` 슬래시 커맨드를 LLM 없이 직접 처리합니다.
Gateway의 `registerCommand` API를 통해 LLM 파이프라인을 건너뛰고 플러그인 핸들러를 직접 호출합니다.

### Bridge mode (HTTP 서버)

JS/TS Gateway와 연동 시 HTTP bridge 서버를 사용합니다:

```bash
# Bridge 서버 시작 (port 8200)
uv run openclaw-todo-server
```

### DB Location

SQLite 데이터베이스는 첫 커맨드 실행 시 자동 생성됩니다:
```
~/.openclaw/workspace/.todo/todo.sqlite3
```

## Test

```bash
# Run all tests
uv run pytest -q

# Run with coverage
uv run pytest --cov=src --cov-report=term-missing

# Run specific test file
uv run pytest tests/test_parser.py -q
```

## Commands

| Command | Description |
|---------|-------------|
| `/todo add <title> [@user] [/p project] [/s section] [due:date]` | Create a task |
| `/todo list [mine\|all\|@user] [open\|done\|drop] [/p project] [/s section]` | List tasks |
| `/todo board [mine\|all\|@user] [open\|done\|drop] [/p project]` | Kanban board view |
| `/todo move <id> <section>` | Move task to section |
| `/todo done <id>` | Mark task done |
| `/todo drop <id>` | Drop a task |
| `/todo edit <id> [new title] [@user] [/p project] [/s section] [due:date]` | Edit a task |
| `/todo project list` | List projects |
| `/todo project set-private <name>` | Make project private |
| `/todo project set-shared <name>` | Make project shared |

## Project Structure

```
openclaw_todo_plugin/
├── src/
│   └── openclaw_todo/
│       ├── plugin.py              # Entry point (handle_message)
│       ├── dispatcher.py          # Command routing + handler registry
│       ├── parser.py              # Input tokenizer/parser
│       ├── db.py                  # SQLite connection factory (WAL)
│       ├── migrations.py          # Sequential migration runner
│       ├── schema_v1.py           # V1 DDL
│       ├── permissions.py         # can_write_task + validate_private_assignees
│       ├── project_resolver.py    # Option A (private-first) name resolution
│       ├── scope_builder.py       # list/board scope query builder
│       ├── event_logger.py        # Audit event logging
│       ├── server.py              # HTTP bridge server (port 8200)
│       ├── cmd_add.py             # add handler
│       ├── cmd_list.py            # list handler
│       ├── cmd_board.py           # board handler
│       ├── cmd_move.py            # move handler
│       ├── cmd_done_drop.py       # done/drop handler
│       ├── cmd_edit.py            # edit handler
│       ├── cmd_project_list.py    # project list handler
│       ├── cmd_project_set_private.py  # set-private handler
│       └── cmd_project_set_shared.py   # set-shared handler
├── bridge/openclaw-todo/          # JS/TS bridge for Gateway
├── tests/
├── docs/
├── issues.md
├── pyproject.toml
└── STATUS.md
```

## Documentation

- [Requirements](requirements.md)
- [UX Specification](ux_spec.md)
- [Architecture](architecture.md)
- [Test Plan](test_plan.md)
- [Issues / Task Breakdown](../issues.md)
