# Diary

A local, single-user, AI-powered daily task management app for macOS.

Diary is a Python CLI/TUI app with an embedded AI assistant (Strands Agents + Amazon Bedrock Claude Sonnet) that manages tasks through natural language conversation. It has multiple client interfaces — a TUI, a chat REPL, a machine CLI API, and a zsh hook — all sharing a single service layer over SQLite.

## Quick Start

```bash
# Install
uv sync

# Launch the TUI
uv run diary tui

# Or chat with the AI
uv run diary chat

# Or use the CLI API
uv run diary api list
uv run diary api add --title "My task" --priority high --schedule today
```

## Features

- **TUI** (`diary tui`) — lazygit-style terminal UI with today/backlog panels, task detail with activity log, vim integration for log entries
- **AI Chat** (`diary chat`) — conversational task management via Bedrock Claude Sonnet. Create, update, schedule, and summarize tasks in natural language
- **CLI API** (`diary api`) — machine-friendly JSON commands for all task operations. Designed for external tool integration
- **Zsh hook** — prints today's tasks on every new terminal session
- **Notifications** (`diary notify`) — macOS notifications via launchd + terminal-notifier

## TUI Keybindings

| Key | Task Mode | Log Mode |
|-----|-----------|----------|
| j/k | Navigate tasks | Navigate log entries |
| 1 | Switch to Today panel | Exit to Today |
| 2 | Switch to Backlog panel | Exit to Backlog |
| 3/Enter | Enter log mode | — |
| t | Move task to today | — |
| b | Move task to backlog | — |
| x | Mark task done | — |
| p | Set priority (h/m/l) | — |
| e | Edit task field | Edit log entry |
| n | New task | — |
| l | Add log entry (inline) | Add log entry |
| L | Add log entry (vim) | Add log entry (vim) |
| d | Schedule task (date prompt) | Delete log entry |
| a | Archive task | — |
| v | View done + archived tasks | — |
| r | Refresh from DB | — |
| ? | Toggle help overlay | Toggle help overlay |
| q | Quit | Quit |

## Task Model

Tasks have a `done` boolean and a `scheduled_date`. The display status is derived:

- `done = true` → **done**
- `scheduled_date <= today` → **in-progress** (active work window)
- `scheduled_date > today` or `null` → **todo** (backlog)

Moving a task to today sets `scheduled_date` to today. Moving to backlog clears it. Marking done sets `done = true`. The activity log tracks all transitions for work period analysis.

## CLI API

```bash
diary api list [--scheduled today|none|<date>] [--done] [--priority high|medium|low]
               [--tag <tag>] [--search <text>] [--archived] [--verbose]
               [--format json|brief]
diary api show <task-id>
diary api add --title <title> [--description <desc>] [--priority h|m|l]
              [--tags <comma-sep>] [--due <date>] [--schedule <date>]
diary api update <task-id> [--title] [--description] [--done] [--undone]
                 [--priority] [--tags] [--due] [--schedule]
diary api log <task-id> <message>
diary api archive <task-id> --reason <reason>
diary api unarchive <task-id>
```

Dates accept natural language: `today`, `tomorrow`, `next thursday`, `in 5 days`, `march 15`.

## AI Setup

Requires AWS credentials with Bedrock access. Configure in `~/.config/diary/config.toml`:

```toml
ai_model = "us.anthropic.claude-sonnet-4-20250514-v1:0"
aws_profile = "bedrock"
```

## Configuration

All settings in `~/.config/diary/config.toml`. See the file for all fields with comments.

## Architecture

```
┌──────────────────────────────────────────────┐
│              SQLite DB (WAL mode)             │
│          ~/.local/share/diary/diary.db        │
└──────┬──────────┬──────────┬─────────────────┘
       │          │          │
   ┌───┴───┐ ┌───┴───┐ ┌───┴───┐
   │  TUI  │ │ Chat  │ │  API  │
   └───────┘ └───────┘ └───────┘
       All share a Python service layer.
       No HTTP server. No daemon.
```

## Development

```bash
uv sync                    # install deps
uv run pytest              # run tests
uv run diary tui           # launch TUI
uv run diary chat          # launch AI chat
```

## Project Structure

```
src/diary/
├── cli.py              # Entry point
├── db.py               # SQLite schema + connection
├── models.py           # Pydantic models (Task, etc.)
├── config.py           # TOML config loading
├── dates.py            # Natural language date parsing
├── api_cli.py          # diary api commands
├── chat.py             # diary chat REPL
├── notify.py           # diary notify command
├── install.py          # diary install command
├── service/
│   ├── tasks.py        # TaskService (CRUD, archive, system logs)
│   ├── activity_log.py # ActivityLogService
│   ├── tags.py         # TagService
│   ├── summary.py      # SummaryService
│   └── notifications.py# NotificationService
├── agent/
│   ├── agent.py        # Strands Agent factory + system prompt
│   └── tools.py        # Agent tool definitions
└── tui/
    └── app.py          # blessed-based TUI
```
