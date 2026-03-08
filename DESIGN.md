# Diary — High-Level Design

## 1. System Architecture

```
┌──────────────────────────────────────────────────────────┐
│                SQLite DB (shared file)                    │
│              ~/.local/share/diary/diary.db                │
└──────┬──────────┬──────────┬──────────┬──────────────────┘
       │          │          │          │
   ┌───┴───┐ ┌───┴───┐ ┌───┴───┐ ┌───┴────────┐
   │  TUI  │ │ chat  │ │  api  │ │ zsh hook   │
   └───────┘ └───────┘ └───────┘ └────────────┘

   All clients share a Python service layer that
   reads/writes SQLite directly. No HTTP server.

┌──────────────────────────────────────────────────────────┐
│              macOS launchd (2 calendar jobs)              │
│                                                          │
│  Morning job (default 10am):                             │
│    diary notify morning                                  │
│    → sends macOS notification, brings Warp to front      │
│                                                          │
│  Evening job (default 6pm):                              │
│    diary notify evening                                  │
│    → sends macOS notification, brings Warp to front      │
└──────────────────────────────────────────────────────────┘
```

### Why no HTTP server?

We originally considered a FastAPI server, but challenged the assumption. The only reason for a long-running process was notifications — and those can be handled by launchd calendar jobs that run a one-shot script and exit.

Everything else — TUI, chat, API, zsh hook — just needs to read/write the SQLite database. SQLite handles concurrent access well for a single-user app (WAL mode allows concurrent readers with serialized writes). There's never enough write contention from one person managing tasks to cause problems.

**What we gain by dropping the server:**
- No daemon to manage, monitor, or debug when it crashes
- No port allocation or socket management
- Simpler deployment — just a Python package and two launchd plists
- Faster startup for every command (no HTTP round-trip, no server health check)
- Less code overall

**What we give up:**
- If we ever want a web UI, we'd need to add a server then. But that's out of scope for v1 and possibly forever.

### Why SQLite?

- Full-text search across titles and descriptions — SQLite has FTS5 built in.
- Work periods are computed by querying activity log entries by type and date range — SQL makes this trivial.
- History/calendar views need date-range queries with aggregation — SQL is purpose-built for this.
- Single file, zero config, no separate process. Fits the "simple" philosophy.
- WAL mode handles concurrent access from multiple clients (TUI open + `diary api` from another terminal).
- A JSON file would require loading everything into memory and implementing search/filter in Python. That's more code, slower for large histories, and fragile under concurrent writes.

---

## 2. Database Schema

### 2.1 `tasks` table

```sql
CREATE TABLE tasks (
    id          TEXT PRIMARY KEY,  -- UUID
    title       TEXT NOT NULL,
    description TEXT,
    status      TEXT NOT NULL DEFAULT 'todo'
                CHECK (status IN ('todo', 'in-progress', 'done')),
    priority    TEXT NOT NULL DEFAULT 'medium'
                CHECK (priority IN ('high', 'medium', 'low')),
    due_date    TEXT,              -- ISO date (YYYY-MM-DD) or NULL
    scheduled_date TEXT,           -- ISO date or NULL (NULL = backlog)
    archived    INTEGER NOT NULL DEFAULT 0,  -- boolean
    archive_reason TEXT,
    created_at  TEXT NOT NULL,     -- ISO datetime
    updated_at  TEXT NOT NULL      -- ISO datetime
);
```

**Design rationale:**

- **`id` as UUID (text)**: Auto-incrementing integers leak information (how many tasks exist) and are awkward in CLI output. UUIDs are opaque and safe to expose. Short UUIDs (first 8 chars) can be used for display while full UUIDs are used internally. When the user types `diary api show abc12def`, they get a stable, unambiguous identifier — not a sequential number that might collide or confuse.

- **`status` as text with CHECK constraint**: Three statuses only (`todo`, `in-progress`, `done`). A separate status table would be over-engineering for three values. The CHECK constraint prevents invalid states at the database level — even if a bug in the service layer tries to set `status='banana'`, the DB rejects it. The user never sees corrupted data.

- **`priority` as text with CHECK constraint**: Same reasoning as status. Three values, enforced at DB level.

- **`due_date` and `scheduled_date` as ISO date strings**: SQLite doesn't have a native date type, but ISO strings sort correctly and are human-readable in raw DB inspection. Date-only (not datetime) because the user thinks in days — "schedule this for tomorrow" not "schedule this for 2pm tomorrow."

- **`archived` as integer (0/1)**: SQLite doesn't have booleans. Archived tasks stay in the same table with a flag rather than a separate table because un-archiving is just flipping a bit — no data migration. The "un-archive returns to backlog" flow is a single UPDATE: `SET archived=0, archive_reason=NULL, scheduled_date=NULL`.

- **`archive_reason` as nullable text**: Only populated when `archived=1`. Enforcement (require reason when archiving) lives in the service layer, not the DB, because the service layer can return a meaningful error message ("archive reason is required") while a DB constraint would just throw a generic error.

- **No `tags` column**: Tags are normalized into separate tables (see below). This is the one place where normalization matters for the user experience.

### 2.2 `tags` table

```sql
CREATE TABLE tags (
    id   TEXT PRIMARY KEY,  -- UUID
    name TEXT NOT NULL UNIQUE
);
```

### 2.3 `task_tags` join table

```sql
CREATE TABLE task_tags (
    task_id TEXT NOT NULL REFERENCES tasks(id),
    tag_id  TEXT NOT NULL REFERENCES tags(id),
    PRIMARY KEY (task_id, tag_id)
);
```

**Why a separate tags table instead of a JSON array or comma-separated string on the task?**

- The AI needs to query "all existing tags" to suggest tags for new tasks. A normalized table makes this `SELECT name FROM tags` instead of parsing every task's tag field.
- Filtering tasks by tag is a join — fast and indexable. With a string field, it'd be `LIKE '%#backend%'` which is slow and can false-match (`#backend-v2` matching a search for `#backend`).
- Adding/removing a single tag is an insert/delete on the join table, not a read-modify-write on a string field. This avoids race conditions when the TUI and `diary api` modify tags on the same task concurrently.

The UX payoff: tag filtering is fast, AI tag suggestions are accurate, and concurrent access from TUI + API doesn't corrupt tag data.

### 2.4 `activity_log` table

```sql
CREATE TABLE activity_log (
    id        TEXT PRIMARY KEY,  -- UUID
    task_id   TEXT NOT NULL REFERENCES tasks(id),
    timestamp TEXT NOT NULL,     -- ISO datetime
    source    TEXT NOT NULL CHECK (source IN ('user', 'ai', 'system')),
    content   TEXT NOT NULL
);

CREATE INDEX idx_activity_log_task_id ON activity_log(task_id);
CREATE INDEX idx_activity_log_timestamp ON activity_log(timestamp);
```

**Design rationale:**

- **Separate table, not JSON blob on task**: The history/calendar view needs to find "what was worked on March 5th" by scanning system entries across all tasks. A separate table with indexes makes this a fast query. A JSON blob would require loading and parsing every task's log.

- **`id` on each entry**: The user can delete or edit individual log entries from the TUI. Without an ID, there's no way to target a specific entry unambiguously.

- **`source` field**: Purely for display differentiation. The TUI renders them differently — system entries in gray, AI entries with a label, user entries normally. The permission boundary (only TUI can delete/edit) is enforced at the client level, not by source type.

- **Indexes on `task_id` and `timestamp`**: `task_id` index is critical for the task detail view (query all log entries for one task). `timestamp` index supports the history/calendar view (query by date range across all tasks).

### 2.5 Full-text search

```sql
CREATE VIRTUAL TABLE tasks_fts USING fts5(
    title,
    description,
    content='tasks',
    content_rowid='rowid'
);
```

Kept in sync via triggers on INSERT/UPDATE/DELETE on the `tasks` table.

**Why FTS5?**

`LIKE '%keyword%'` doesn't support ranking, is slow on large datasets, and can't handle multi-word queries. FTS5 gives ranked results, prefix matching, and phrase search. The UX difference: search returns relevant results ordered by relevance, not just substring matches.

### 2.6 `notification_state` table

```sql
CREATE TABLE notification_state (
    date          TEXT PRIMARY KEY,  -- ISO date
    morning_sent  INTEGER NOT NULL DEFAULT 0,
    evening_sent  INTEGER NOT NULL DEFAULT 0
);
```

The launchd notification jobs check this table before sending. If `morning_sent=1` for today, skip. This prevents duplicate notifications if launchd fires the job more than once (which can happen after sleep/wake cycles).

---

## 3. Service Layer

Since there's no HTTP server, all clients share a Python service layer that talks directly to SQLite.

### 3.0 Why a Single Service Layer?

The app has many entry points — TUI, chat, API CLI, zsh hook, notification script. Without a shared core, each client would need to independently implement task validation, system log generation, tag management, and state transitions. That's a recipe for inconsistent behavior and bugs.

The service layer is the **single place** where all business logic lives. Every client is a thin wrapper:

```
TUI:      UI event  → service call → render result
Chat/AI:  LLM tool  → service call → format response
API CLI:  argparse   → service call → print JSON
Zsh hook: startup    → service call → print summary
Notify:   launchd    → service call → send notification
```

No client validates input, generates system log entries, manages tags, or enforces business rules. All of that is in the service layer. This means:
- A bug fix in the service layer fixes it for all clients at once
- A new field on a task is added in one place (service + models), not four
- Behavior is guaranteed to be identical regardless of which client made the change

```
┌──────────────────────────────────────────┐
│              Service Layer               │
│                                          │
│  TaskService                             │
│    create_task(title, ...) → Task        │
│    update_task(id, ...) → Task           │
│    list_tasks(filters) → [Task]          │
│    get_task(id) → Task                   │
│    archive_task(id, reason) → Task       │
│    unarchive_task(id) → Task             │
│                                          │
│  ActivityLogService                      │
│    add_entry(task_id, source, content)   │
│    edit_entry(entry_id, content)         │
│    delete_entry(entry_id)                │
│    list_entries(task_id) → [Entry]       │
│                                          │
│  TagService                              │
│    list_all_tags() → [Tag]               │
│    set_task_tags(task_id, [tag_names])   │
│                                          │
│  SummaryService                          │
│    summarize(from_date, to_date) → data  │
│                                          │
│  NotificationService                     │
│    check_and_send(type: morning|evening) │
│                                          │
└──────────────┬───────────────────────────┘
               │
               ▼
         SQLite (WAL mode)
```

### 3.1 System Activity Log Auto-Generation

The service layer automatically creates `source=system` activity log entries when task fields change. This happens inside `TaskService.update_task()` — it compares old and new values and logs the diff.

Example: when `update_task(id, status='done')` is called, the service:
1. Reads current task (status was `in-progress`)
2. Updates the task
3. Inserts: `{source: "system", content: "Status changed from in-progress to done"}`

This is centralized in the service layer, so it works identically whether the change came from the TUI, chat, or API. The user sees a consistent audit trail regardless of which client made the change.

### 3.2 Permission Model

The service layer exposes all operations including activity log edit/delete. The restriction is enforced at the client level:

- `diary api` CLI: doesn't expose edit/delete log commands
- AI agent tools: don't include edit/delete log tools
- TUI: exposes everything

This is intentional. It's a single-user local app — adding auth to the service layer adds complexity with no real benefit. The "restriction" prevents accidental misuse by external AIs, not a security boundary.

### 3.3 Concurrency

SQLite in WAL mode allows:
- Multiple concurrent readers (TUI open + zsh hook + `diary api list` all at once — no problem)
- One writer at a time (writes are serialized with a short lock)

For a single-user task manager, write contention is effectively zero. The worst case is the TUI and `diary api` both try to update a task at the exact same millisecond — one waits a few ms for the other. The user never notices.

---

## 4. Client Design

### 4.1 CLI Entry Point

Single `diary` command with subcommands:

```
diary tui              -- launch TUI
diary chat             -- launch conversational AI chat
diary api <cmd>        -- machine-friendly commands
diary notify <type>    -- send notification (called by launchd)
diary install          -- print launchd plists and zsh snippet for manual setup
```

**Why a single entry point?**

The user types `diary` and gets to everything. No separate binaries to remember.

`diary install` prints the launchd plist XML and zsh snippet to stdout. The user copies them into place. It does not modify `.zshrc` or install plists automatically — the user controls what goes where.

### 4.2 TUI Layout

**Default view (chat collapsed):**

```
┌─────────────────────────────────────────────────────────────┐
│  Diary                              [R]efresh  [C]hat [?]Help│
├───────────────────────┬─────────────────────────────────────┤
│                       │                                     │
│   📋 Today (3)        │   Task Detail                       │
│                       │                                     │
│   ● [H] Auth refactor │   Title: Auth refactor              │
│   ○ [M] DB migration  │   Status: in-progress               │
│   ○ [L] Update docs   │   Priority: high                    │
│                       │   Tags: #backend #auth              │
│                       │   Due: 2026-03-05                   │
│───────────────────────│   Scheduled: today                  │
│                       │                                     │
│   📦 Backlog (5)      │   ── Activity Log ──                │
│                       │   Mar 1 10:30 [user] Got stuck on   │
│   ○ [H] Fix payments  │     token refresh                   │
│   ○ [M] Refactor API  │   Mar 1 09:00 [sys] Scheduled for  │
│   ○ [M] Write tests   │     today                          │
│   ○ [L] Clean up logs │   Feb 28 17:00 [sys] Status changed│
│   ○ [L] Update README │     from todo to in-progress        │
│                       │   Feb 28 09:15 [ai] Created from    │
│                       │     chat: user needs to refactor    │
│                       │     auth token handling             │
├───────────────────────┴─────────────────────────────────────┤
│  💬 [C] to open AI chat                                      │
└──────────────────────────────────────────────────────────────┘
```

**Chat expanded (overlay mode, triggered by [C] shortcut):**

```
┌─────────────────────────────────────────────────────────────┐
│  Diary — AI Chat                          [C] collapse [?]Help│
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  You: I finished the auth refactor, move DB migration        │
│       to tomorrow                                            │
│                                                              │
│  AI: I'll:                                                   │
│    1. Mark "Auth refactor" as done                           │
│    2. Schedule "DB migration" for tomorrow (Mar 2)           │
│  Confirm?                                                    │
│                                                              │
│  You: yes                                                    │
│                                                              │
│  AI: Done.                                                   │
│    - "Auth refactor" marked as done.                         │
│    - "DB migration" scheduled for Mar 2.                     │
│                                                              │
│  > _                                                         │
└──────────────────────────────────────────────────────────────┘
```

**Layout rationale:**

- **Chat as expandable overlay, not permanent panel**: The user said most TUI usage is at start/end of day for reviewing tasks. The task panels (today + backlog + detail) should get maximum screen space by default. When the user wants to chat, pressing [C] expands the chat to full screen. Pressing [C] again collapses back to the task view. This avoids the problem of a cramped three-panel layout where nothing has enough space.

- **Left panel = today + backlog**: The two views the user needs most. Today on top (primary focus), backlog below. Sorted by priority (high → medium → low).

- **Right panel = task detail + activity log**: Selecting a task on the left shows its full detail on the right. The activity log is the most important part — it's where the user sees progress and where to resume. Inline display (not a popup) means scanning tasks and reading details without mode-switching.

- **Manual refresh [R]**: Since there's no server pushing updates, the TUI reads from SQLite on launch and on manual refresh. If `diary api` modifies a task from another terminal, pressing [R] reloads. Acceptable for v1.

- **History and Archive views**: Separate screens accessed via keyboard shortcuts. Less frequent operations don't need permanent screen space.

### 4.3 Conversational Chat (diary chat)

A simple REPL loop in the terminal:

```
Diary AI Chat
Type 'quit' to exit.

You: what's on my plate today?
AI: You have 3 tasks scheduled for today:
  1. [HIGH] Auth refactor (in-progress) — last: "Got stuck on token refresh"
  2. [MED] DB migration (todo) — new, no activity yet
  3. [LOW] Update docs (todo) — no activity yet

You: I finished auth, and I need to create a task for reviewing PRs

AI: Got it. Two things:
  1. Mark "Auth refactor" as done
  2. Create new task "Review PRs"
     For the new task:
     - Priority: high, medium, or low?
     - Tags: I'd suggest #review based on existing tags. Others?
     - Schedule: today or backlog?
     - Due date: any deadline?
     - Description: any context?

You: medium, today, no due date, no description, tags are fine

AI: I'll:
  1. Mark "Auth refactor" as done
  2. Create "Review PRs" — medium priority, #review, scheduled today, no due date
  Confirm?

You: yes

AI: Done.
  - "Auth refactor" marked as done.
  - "Review PRs" created and scheduled for today.
```

**Why a separate `diary chat` in addition to the TUI chat?**

The user works across many terminals. Opening the full TUI just to say "mark auth as done" is too much friction. `diary chat` starts instantly, does the job, and you close it. The TUI is for the full picture; `diary chat` is for quick drive-by interactions.

Both use the exact same AI agent code — the only difference is the rendering layer (TUI widget vs. plain terminal I/O).

### 4.4 Machine CLI API (diary api)

Calls the service layer directly (no HTTP) and prints JSON to stdout.

```python
# Pseudocode
def main():
    args = parse_args()  # argparse with subcommands
    result = service.call(args)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result else 1)
```

Every command has `--help`. Exit code 0 on success, non-zero on failure. JSON on stdout, errors on stderr. This is the contract that external AIs rely on.

The `--format brief` flag outputs human-friendly text instead of JSON (used by the zsh hook).

### 4.5 Zsh Integration

Printed by `diary install` for the user to add to `.zshrc`:

```zsh
if command -v diary &> /dev/null; then
  diary api list --scheduled today --format brief 2>/dev/null
fi
```

Prints on every new terminal session. Output format:

```
📋 Diary — 3 tasks planned for today:
  1. [HIGH] Auth refactor
  2. [MED]  DB migration
  3. [LOW]  Update docs

Run `diary chat` to review or `diary tui` for full view.
```

`2>/dev/null` suppresses errors if the DB doesn't exist yet or diary isn't set up. The terminal opens normally without noise.

---

## 5. AI Agent Design

### 5.1 Strands Agent Setup

The AI agent is a Strands Agent with tools that call the service layer directly (same process, no HTTP).

**Tools the agent has:**

| Tool | Calls | Description |
|------|-------|-------------|
| list_tasks | TaskService.list_tasks() | List/filter tasks |
| show_task | TaskService.get_task() | Get full task detail with activity log |
| create_task | TaskService.create_task() | Create a new task |
| update_task | TaskService.update_task() | Update task fields |
| add_log_entry | ActivityLogService.add_entry() | Add activity log entry |
| archive_task | TaskService.archive_task() | Archive with reason |
| unarchive_task | TaskService.unarchive_task() | Un-archive |
| list_tags | TagService.list_all_tags() | Get all existing tags (for suggestion) |
| get_summary | SummaryService.summarize() | Get summary for date range |

**Tools the agent does NOT have:**
- Delete activity log entry
- Edit activity log entry

This is how we enforce the "AI can't delete/edit logs" restriction — the tools simply don't exist in the agent's toolkit.

### 5.2 System Prompt

The agent's system prompt encodes the conversational principles:

- Always explain what you're about to do before doing it
- When creating or updating a task, ask about every unfilled optional field the user hasn't already provided
- Suggest tags based on existing tags (call `list_tags` first)
- Wait for explicit user confirmation before any mutation
- Accept free-form responses — the user can clarify, correct, or add context, not just yes/no
- Keep responses concise — short sentences, no fluff
- When the user provides context worth saving, proactively ask "should I save this to the task?"
- Persist saved context as an activity log entry with `source=ai`

### 5.3 Conversation Flow

```
User input
    │
    ▼
Strands Agent (LLM + tools)
    │
    ├── LLM decides intent
    │   ├── Needs more info → asks user (no tool call)
    │   ├── Ready to act → presents plan, asks confirmation
    │   └── User confirmed → calls tools, reports result
    │
    ▼
Tool calls → Service layer → SQLite
    │
    ▼
Response to user
```

The LLM handles natural language understanding, intent extraction, and conversation management. The tools are simple CRUD operations. This separation means:
- Conversation logic is in the prompt, not in code
- Adding new capabilities = adding new tools + updating the prompt
- Tools are testable independently of the LLM

---

## 6. Notification System

### 6.1 Implementation

Two macOS `launchd` calendar jobs. Each runs a one-shot command and exits immediately.

**Morning job** (`com.diary.notify.morning.plist`):
- Fires at configured time (default 10:00 AM) on workdays
- Runs: `diary notify morning`
- The command checks `notification_state` table — if already sent today, exits
- Otherwise: sends macOS notification via `terminal-notifier`, marks as sent

**Evening job** (`com.diary.notify.evening.plist`):
- Fires at configured time (default 6:00 PM) on workdays
- Runs: `diary notify evening`
- Same check-and-send logic

### 6.2 Notification Content

Hardcoded messages, no DB reads for task counts (keeps the notification script dead simple):

- Morning: `"Time to check your tasks"` — title: `"Diary"`
- Evening: `"Time to review your tasks"` — title: `"Diary"`

### 6.3 Click Action

```bash
terminal-notifier \
  -title "Diary" \
  -message "Time to check your tasks" \
  -execute "open -a Warp"
```

Clicking the notification brings Warp to the foreground. The user types `diary tui` or `diary chat`. Warp doesn't support opening a new tab with a command programmatically, so this is the simplest reliable approach.

### 6.4 Config Changes

If the user changes notification times in the config file, they need to re-run `diary install` to get updated plist files and reload them with `launchctl`. This is rare (set once, forget) so the minor friction is acceptable.

---

## 7. Project Structure

```
diary/
├── pyproject.toml
├── REQUIREMENTS.md
├── DESIGN.md
├── src/
│   └── diary/
│       ├── __init__.py
│       ├── cli.py              # Entry point: diary command + subcommands
│       ├── db.py               # SQLite connection, schema init, WAL mode
│       ├── models.py           # Pydantic models (shared data shapes)
│       ├── service/
│       │   ├── __init__.py
│       │   ├── tasks.py        # TaskService (CRUD, archive, system log generation)
│       │   ├── activity_log.py # ActivityLogService (add, edit, delete, list)
│       │   ├── tags.py         # TagService (list all, set task tags)
│       │   └── summary.py      # SummaryService (date range summaries)
│       ├── agent/
│       │   ├── __init__.py
│       │   ├── agent.py        # Strands Agent setup + system prompt
│       │   └── tools.py        # Tool definitions (call service layer)
│       ├── tui/
│       │   ├── __init__.py
│       │   ├── app.py          # Textual app
│       │   ├── screens/        # TUI screens (main, history, archive)
│       │   └── widgets/        # Custom widgets (task list, detail, chat overlay)
│       ├── api_cli.py          # diary api subcommand (argparse + service calls + JSON output)
│       ├── chat.py             # diary chat REPL (agent + terminal I/O)
│       ├── notify.py           # diary notify command (notification_state + terminal-notifier)
│       └── config.py           # Config file loading (TOML)
├── install/
│   ├── com.diary.notify.morning.plist  # launchd plist template
│   ├── com.diary.notify.evening.plist  # launchd plist template
│   └── zsh_hook.zsh                    # zsh snippet template
└── tests/
```

**Why this structure?**

- **`service/` is the core**: All business logic — task CRUD, system log generation, validation, tag management — lives here. Every client (TUI, chat, API, notify) imports and calls the service layer. This is the single source of truth for "how tasks work."

- **`agent/` calls `service/` directly**: No HTTP indirection. The agent's tools are thin wrappers around service methods. This means the agent runs in the same process as the chat REPL or TUI, with no network overhead. Testing the agent = mocking the service layer.

- **`db.py` is shared**: One module handles SQLite connection, schema initialization, and WAL mode setup. All service modules import the DB connection from here. Single point of configuration.

- **`models.py` is shared**: Pydantic models define the data shapes used by the service layer, API CLI (JSON serialization), and TUI (display). One definition, used everywhere.

- **`tui/` is isolated**: The TUI imports the service layer but nothing else imports the TUI. This means the TUI can be complex (Textual widgets, screens, event handling) without affecting the rest of the codebase.

---

## 8. Key Design Decisions Summary

| Decision | Choice | Rationale (UX tie-back) |
|----------|--------|------------------------|
| Architecture | No server, shared service layer + SQLite | Simpler. No daemon to manage. Every command starts fast. User never debugs "why is the server down." |
| Database | SQLite + FTS5 + WAL mode | Full-text search, date-range queries, concurrent access from multiple terminals. Single file, zero config. |
| Notifications | launchd calendar jobs (one-shot scripts) | No persistent process. Fires at configured times, sends hardcoded message, exits. Dead simple. |
| Notification click | Opens Warp (user types `diary tui`) | Warp doesn't support opening tabs with commands programmatically. Bringing Warp to front is the most reliable approach. |
| Task ID | UUID (short display) | User-friendly in CLI, stable, unambiguous. |
| Tags | Normalized (separate table) | Fast filtering, accurate AI suggestions, safe concurrent access. |
| Activity log | Separate table with IDs per entry | Queryable for history views, individual entries targetable for edit/delete from TUI. |
| AI restriction | Client-level (tools not exposed) | Simple. Single-user app doesn't need service-level auth. |
| TUI chat | Expandable overlay (not permanent panel) | Task panels get full screen by default. Chat expands to full screen when needed, collapses back. No cramped three-panel layout. |
| `diary chat` | Separate lightweight REPL | Quick drive-by interactions from any terminal without opening the full TUI. |
| Zsh hook | Prints in every new terminal | Simple, no tracking. Reminds user of today's plan. |
| Config | TOML file | Human-readable, easy to edit. Standard for Python tools. |
| Terminal | Warp (configurable) | User's preference. Notification click action uses `open -a Warp`. |
