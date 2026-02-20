# OpenClaw TODO Plugin

Slack DM-based team/personal TODO system — an OpenClaw plugin.

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

The plugin runs within the OpenClaw Gateway. It registers a `/todo` command handler that processes messages in Slack DMs.

```bash
# Start via OpenClaw Gateway (details TBD based on Gateway docs)
uv run openclaw-gateway
```

### DB Location

The SQLite database is automatically created at:
```
~/.openclaw/workspace/.todo/todo.sqlite3
```

## Test

```bash
# Run all tests
uv run pytest -q

# Run with coverage
uv run pytest --cov=src --cov-report=term-missing

# Run smoke tests only
uv run pytest -m smoke -q
```

## Commands

| Command | Description |
|---------|-------------|
| `/todo add <title> [@user] [/p project] [/s section] [due:date]` | Create a task |
| `/todo list [mine\|all\|@user] [/p project] [/s section]` | List tasks |
| `/todo board [mine\|all\|@user] [/p project]` | Kanban board view |
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
│   └── openclaw_todo_plugin/
│       ├── __init__.py          # Plugin entry point
│       ├── commands/            # Command handlers
│       ├── db/                  # Connection + migrations
│       ├── repositories/        # SQL data access
│       ├── services/            # Business logic + permissions
│       ├── parser.py            # Input tokenizer/parser
│       ├── formatter.py         # Response formatting
│       └── errors.py            # Custom exceptions
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
