# OpenClaw TODO Plugin

A Slack DM-based task management plugin for the [OpenClaw](https://github.com/pillip/openclaw) gateway. Manage personal and team tasks with kanban-style boards, project isolation, and due dates — all from Slack.

## Features

- `/todo add`, `list`, `board`, `move`, `done`, `drop`, `edit` commands
- Project management: shared and private projects with visibility isolation
- Kanban board view (backlog / doing / waiting / done / drop)
- Due date tracking with MM-DD shorthand normalisation
- Assignee mentions via Slack `<@USER>` syntax
- SQLite backend with WAL mode (zero external dependencies)

## Installation

### From wheel (recommended)

```bash
# Build the wheel
make build

# Install in your environment
pip install dist/openclaw_todo_plugin-*.whl
```

### Development install

```bash
# Clone and install with dev dependencies
git clone https://github.com/pillip/openclaw_todo_plugin.git
cd openclaw_todo_plugin
uv sync
```

## Configuration

### Database path

By default the plugin stores data at `~/.openclaw/workspace/.todo/todo.sqlite3`. The directory is created automatically on first use.

To override, pass a custom `db_path` when calling the plugin entry point:

```python
from openclaw_todo.plugin import handle_message

response = handle_message("/todo add Buy milk", {"sender_id": "U001"}, db_path="/custom/path/todo.db")
```

### OpenClaw gateway integration

The plugin registers itself via the `openclaw.plugins` entry point. After installation, the OpenClaw gateway discovers it automatically:

```python
# Entry point: openclaw_todo.plugin:handle_message
from importlib.metadata import entry_points

plugins = entry_points(group="openclaw.plugins")
todo_plugin = plugins["todo"].load()  # -> handle_message function
```

## Usage

All commands are prefixed with `/todo`:

| Command | Description | Example |
|---------|-------------|---------|
| `add <title> [options]` | Create a task | `/todo add Buy milk /p Home due:03-15` |
| `list [scope] [options]` | List tasks | `/todo list all /p Work` |
| `board [options]` | Kanban board view | `/todo board /p Work` |
| `move <id> /s <section>` | Move task to section | `/todo move 3 /s doing` |
| `edit <id> [title] [options]` | Edit a task | `/todo edit 3 New title /s doing` |
| `done <id>` | Mark task as done | `/todo done 3` |
| `drop <id>` | Drop (cancel) a task | `/todo drop 3` |
| `project list` | List projects | `/todo project list` |
| `project set-shared <name>` | Create/convert to shared | `/todo project set-shared Work` |
| `project set-private <name>` | Create/convert to private | `/todo project set-private MyStuff` |

### Options

| Option | Description | Example |
|--------|-------------|---------|
| `/p <name>` | Project name | `/p Work` |
| `/s <section>` | Section (backlog/doing/waiting/done/drop) | `/s doing` |
| `due:<date>` | Due date (YYYY-MM-DD or MM-DD) | `due:2026-03-15` or `due:03-15` |
| `due:-` | Clear due date | `due:-` |
| `<@USER>` | Assign user | `<@U12345>` |

## Development

```bash
# Run tests
make test

# Lint
make lint

# Auto-format
make format

# Build wheel
make build
```

## Requirements

- Python >= 3.11
- No runtime dependencies (SQLite is in the Python stdlib)
