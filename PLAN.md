# Diary — Implementation Plan

## Principles

1. **Test-driven development**: Write tests first, then implement to make them pass.
2. **Parameterized tests**: Use pytest parametrize for all operations to cover happy paths and edge cases in a compact way.
3. **Top-down**: Start with architecture (project skeleton, interfaces, stubs) before filling in implementation details.
4. **Incremental**: Each phase produces something that works and can be verified independently. Later phases build on earlier ones without rewriting them.

---

## Phase 1: Skeleton + DB + Models

**First step**: Create `docs/phase1-tasks.md` — a detailed task list covering every file to create, every test to write, and every stub to define, ordered top-down (project structure → DB schema → models → CLI stubs → tests). Follow TDD: write tests before implementation. Use parameterized tests. Do not start coding until the task document is reviewed and confirmed.

**Goal**: Project structure exists, database schema creates correctly, data models serialize/deserialize, CLI entry point runs with stub subcommands.

**What to build:**
- `pyproject.toml` with all dependencies (textual, strands-agents, pydantic, pytest, etc.)
- `src/diary/cli.py` — entry point with subcommand stubs (`tui`, `chat`, `api`, `notify`, `install`). Each prints "not implemented yet" and exits.
- `src/diary/db.py` — SQLite connection, WAL mode, full schema creation (tasks, tags, task_tags, activity_log, tasks_fts, notification_state), FTS5 sync triggers.
- `src/diary/models.py` — Pydantic models: `Task`, `ActivityLogEntry`, `Tag`, plus request/response models for create/update operations.
- `src/diary/service/` — stub modules with all method signatures defined, raising `NotImplementedError`.
- `src/diary/config.py` — load TOML config with defaults.

**Verification criteria:**
- [ ] `diary --help` prints subcommands and exits 0
- [ ] `diary tui`, `diary chat`, `diary api`, `diary notify`, `diary install` each exit with a "not implemented" message
- [ ] Database file is created at configured path with all tables and indexes when the app initializes
- [ ] All tables match the schema in DESIGN.md (verified by querying `sqlite_master`)
- [ ] FTS5 triggers exist and are correctly defined
- [ ] Pydantic models round-trip: create a model instance → serialize to dict/JSON → deserialize back → equal to original
- [ ] Config loads from TOML file with correct defaults when file is missing or partially filled
- [ ] All tests pass: `pytest`

---

## Phase 2: Service Layer — TaskService

**First step**: Create `docs/phase2-tasks.md` — a detailed task list covering every method to implement, every test to write, and the order of implementation (interfaces/signatures first → tests → implementation). Follow TDD: write parameterized tests for each method before implementing it. Do not start coding until the task document is reviewed and confirmed.

**Goal**: Full task CRUD with system activity log auto-generation. The core of the app works.

**Depends on**: Phase 1 (DB, models)

**What to build:**
- `TaskService.create_task(title, description?, priority?, due_date?, scheduled_date?, tags?)` → creates task + system log entry "Task created" + sets tags
- `TaskService.get_task(id)` → returns task with activity log and tags
- `TaskService.list_tasks(filters)` → supports all filter combinations: scheduled (today/date/none), status, priority, tag, search (FTS5), date range, archived flag, verbose
- `TaskService.update_task(id, **fields)` → updates fields, generates system log entries for each changed field
- `TaskService.archive_task(id, reason)` → sets archived=true, archive_reason, generates system log
- `TaskService.unarchive_task(id)` → sets archived=false, clears reason, sets scheduled_date=null (backlog), generates system log

**Verification criteria:**
- [ ] Create a task with only title → task exists in DB with correct defaults (status=todo, priority=medium, scheduled_date=null, archived=false)
- [ ] Create a task with all fields → all fields persisted correctly
- [ ] Create a task with tags → tags created in tags table, linked in task_tags
- [ ] Create a task with existing tag names → reuses existing tag rows, no duplicates
- [ ] Get task by ID → returns complete task with tags and activity log entries
- [ ] Get task with invalid ID → returns appropriate error
- [ ] List tasks with no filters → returns all non-archived tasks
- [ ] List tasks with each filter individually → correct results (parameterized across all filter types)
- [ ] List tasks with combined filters → correct intersection
- [ ] FTS search matches title and description content, returns ranked results
- [ ] Update task status → field changes + system log entry "Status changed from X to Y"
- [ ] Update task priority → field changes + system log entry "Priority changed from X to Y"
- [ ] Update task scheduled_date → field changes + system log entry "Scheduled for YYYY-MM-DD" or "Moved to backlog"
- [ ] Update multiple fields at once → one system log entry per changed field
- [ ] Update with no actual changes → no system log entries generated
- [ ] Archive task without reason → rejected with error
- [ ] Archive task with reason → archived=true, reason set, system log entry
- [ ] Unarchive task → archived=false, reason cleared, scheduled_date=null, system log entry
- [ ] Archived tasks excluded from list by default, included with --archived flag
- [ ] `updated_at` timestamp changes on every update
- [ ] All tests pass: `pytest`

---

## Phase 3: Service Layer — ActivityLogService + TagService + SummaryService

**First step**: Create `docs/phase3-tasks.md` — a detailed task list covering every method to implement, every test to write, and the order of implementation (interfaces/signatures first → tests → implementation). Follow TDD: write parameterized tests for each method before implementing it. Do not start coding until the task document is reviewed and confirmed.

**Goal**: Complete service layer. All business logic is implemented and tested.

**Depends on**: Phase 2 (TaskService, because log/tag operations reference tasks)

**What to build:**
- `ActivityLogService.add_entry(task_id, source, content)` → creates entry with auto-generated timestamp and ID
- `ActivityLogService.edit_entry(entry_id, content)` → updates content text only
- `ActivityLogService.delete_entry(entry_id)` → hard deletes the entry
- `ActivityLogService.list_entries(task_id)` → returns entries ordered by timestamp
- `TagService.list_all_tags()` → returns all tags that exist in the system
- `TagService.set_task_tags(task_id, tag_names)` → replaces task's tags, creates new tag rows as needed, cleans up orphaned tags
- `SummaryService.summarize(from_date, to_date)` → returns task counts (created, completed, in-progress), activity log entries, and work periods for the date range

**Verification criteria:**
- [ ] Add entry with each source type (user, ai, system) → persisted with correct source and auto-generated timestamp
- [ ] Add entry to non-existent task → rejected with error
- [ ] Edit entry → content changes, timestamp and source unchanged
- [ ] Edit non-existent entry → rejected with error
- [ ] Delete entry → entry gone from DB (hard delete)
- [ ] Delete non-existent entry → rejected with error
- [ ] List entries for a task → ordered by timestamp ascending
- [ ] List entries for task with no entries → empty list
- [ ] List all tags → returns deduplicated tag names across all tasks
- [ ] Set task tags with mix of new and existing tag names → new tags created, existing reused
- [ ] Set task tags to empty list → all tags removed from task, orphaned tags cleaned up
- [ ] Summary for date range → correct counts of tasks created, completed, and active in that range
- [ ] Summary with no activity in range → zero counts, empty lists
- [ ] Work periods computed correctly for a task that moved in and out of active work
- [ ] All tests pass: `pytest`

---

## Phase 4: CLI API (`diary api`)

**First step**: Create `docs/phase4-tasks.md` — a detailed task list covering every command to implement, every test to write, and the order of implementation (argparse structure first → tests → implementation per command). Follow TDD: write parameterized tests for each command before implementing it. Do not start coding until the task document is reviewed and confirmed.

**Goal**: Machine-friendly CLI that external AIs can use. Full task management from the command line.

**Depends on**: Phase 3 (complete service layer)

**What to build:**
- `diary api list` with all filter flags (`--scheduled`, `--status`, `--priority`, `--tag`, `--search`, `--from`, `--to`, `--archived`, `--verbose`, `--format brief|json`)
- `diary api show <task-id>`
- `diary api add --title <title> [--description] [--priority] [--tags] [--due] [--schedule]`
- `diary api update <task-id> [--title] [--description] [--status] [--priority] [--tags] [--due] [--schedule]`
- `diary api log <task-id> <message>`
- `diary api archive <task-id> --reason <reason>`
- `diary api unarchive <task-id>`
- `--help` on every command and subcommand

**Verification criteria:**
- [ ] Every command has `--help` that prints usage and exits 0
- [ ] `diary api list` with no flags → JSON array of non-archived tasks (id, title, status, priority, tags)
- [ ] `diary api list --verbose` → includes all fields + activity log
- [ ] `diary api list --format brief` → human-readable text output (the zsh hook format)
- [ ] Each filter flag works individually (parameterized test across all flags)
- [ ] Combined filters work (e.g., `--scheduled today --priority high`)
- [ ] `diary api show <id>` → full JSON task detail with activity log
- [ ] `diary api show <invalid-id>` → error on stderr, exit code 1
- [ ] `diary api add --title "Test"` → creates task, prints JSON with new task ID, exit code 0
- [ ] `diary api add` without `--title` → error on stderr, exit code 1
- [ ] `diary api update <id> --status done` → updates task, prints updated JSON, exit code 0
- [ ] `diary api log <id> "message"` → adds user entry, exit code 0
- [ ] `diary api archive <id> --reason "done"` → archives, exit code 0
- [ ] `diary api archive <id>` without `--reason` → error, exit code 1
- [ ] `diary api unarchive <id>` → unarchives to backlog, exit code 0
- [ ] All JSON output is valid JSON (parseable by `json.loads`)
- [ ] All errors go to stderr, all data goes to stdout
- [ ] All tests pass: `pytest`

**Milestone**: After this phase, the app is a fully functional CLI task manager. You can manage tasks entirely from the command line, and external AIs can interact with it via `diary api`.

---

## Phase 5: AI Agent

**First step**: Create `docs/phase5-tasks.md` — a detailed task list covering every tool to define, the system prompt to write, the chat REPL to build, and every test to write, ordered top-down (agent setup → tool definitions → tests → REPL). Follow TDD: write parameterized tests for each tool before implementing it. Do not start coding until the task document is reviewed and confirmed.

**Goal**: Conversational AI that manages tasks through natural language. Both `diary chat` and the TUI chat use this.

**Depends on**: Phase 3 (service layer — the agent calls service methods via tools)

**What to build:**
- `agent/tools.py` — tool definitions wrapping service layer methods (list_tasks, show_task, create_task, update_task, add_log_entry, archive_task, unarchive_task, list_tags, get_summary)
- `agent/agent.py` — Strands Agent setup with system prompt encoding all conversational principles (transparency, proactive field gathering, confirmation before mutation, concise responses, tag suggestion)
- `chat.py` — `diary chat` REPL that wires terminal I/O to the agent

**Verification criteria:**
- [ ] Each agent tool calls the correct service method with correct parameters (parameterized test across all tools)
- [ ] Agent tools do NOT include activity log edit or delete
- [ ] `diary chat` starts, accepts input, and exits on 'quit'
- [ ] Agent can list today's tasks when asked (integration test with seeded DB)
- [ ] Agent can create a task from natural language and asks about all unfilled optional fields
- [ ] Agent presents a confirmation summary before any mutation
- [ ] Agent calls `list_tags` and suggests relevant tags when creating a task
- [ ] Agent can update a task (change status, priority, schedule) with confirmation
- [ ] Agent can add an activity log entry to a task
- [ ] Agent can summarize a date range
- [ ] Agent persists conversation context to task activity log when asked (source=ai)
- [ ] Conversation history is retained within a session (multi-turn works)
- [ ] All tests pass: `pytest`

**Milestone**: After this phase, you can manage tasks entirely through conversation. `diary chat` is your primary interaction mode.

---

## Phase 6: TUI

**First step**: Create `docs/phase6-tasks.md` — a detailed task list covering every screen, widget, and interaction to build, and every test to write, ordered top-down (app shell → screens → widgets → manual operations → tests). Follow TDD where possible (Textual's pilot testing framework). Do not start coding until the task document is reviewed and confirmed.

**Goal**: Full terminal UI with task panels, detail view, manual operations, and embedded AI chat overlay.

**Depends on**: Phase 5 (agent — for the chat overlay), Phase 3 (service layer — for manual operations)

**What to build:**
- `tui/app.py` — Textual app with main screen
- `tui/screens/` — main screen, history screen, archive screen
- `tui/widgets/` — task list widget, task detail widget, chat overlay widget
- Main screen: today panel (left top), backlog panel (left bottom), task detail (right)
- Chat overlay: [C] to expand full screen, [C] to collapse
- Manual operations: create, edit fields, change status/priority, schedule/backlog, add/edit/delete activity log entries, archive/unarchive
- [R] refresh shortcut to reload from DB
- Keyboard navigation and shortcuts

**Verification criteria:**
- [ ] `diary tui` launches without errors
- [ ] Today panel shows tasks with `scheduled_date=today`, sorted by priority
- [ ] Backlog panel shows tasks with `scheduled_date=null`, sorted by priority
- [ ] Selecting a task shows full detail + activity log in right panel
- [ ] [C] expands chat overlay to full screen, [C] collapses back
- [ ] Chat overlay uses the same agent as `diary chat` — can create/update/log tasks
- [ ] After AI makes changes via chat, pressing [R] shows updated data in panels
- [ ] Manual create task → task appears in correct panel
- [ ] Manual edit any field → field updates, system log generated
- [ ] Manual change status → status updates in list and detail
- [ ] Manual schedule/backlog → task moves between panels
- [ ] Manual add activity log entry → entry appears in detail view
- [ ] Manual edit activity log entry → text changes
- [ ] Manual delete activity log entry → entry removed
- [ ] Manual archive with reason → task disappears from active panels
- [ ] Manual unarchive → task reappears in backlog
- [ ] History screen shows completed tasks by date
- [ ] Archive screen shows archived tasks with reasons
- [ ] [R] refresh reloads all data from DB
- [ ] All tests pass: `pytest`

**Milestone**: After this phase, the app is feature-complete. Full TUI + chat + CLI API.

---

## Phase 7: Notifications + Zsh + Install

**First step**: Create `docs/phase7-tasks.md` — a detailed task list covering the notify command, launchd plists, zsh snippet, install command, and every test to write, ordered top-down (notification_state logic → notify command → templates → install command → tests). Follow TDD for testable logic. Do not start coding until the task document is reviewed and confirmed.

**Goal**: Daily reminders and terminal integration. The "don't forget" layer.

**Depends on**: Phase 4 (CLI API — zsh hook uses `diary api list`)

**What to build:**
- `notify.py` — `diary notify morning|evening` command. Checks `notification_state` table, sends macOS notification via `terminal-notifier`, marks as sent.
- `install/com.diary.notify.morning.plist` — launchd plist template for morning job
- `install/com.diary.notify.evening.plist` — launchd plist template for evening job
- `install/zsh_hook.zsh` — zsh snippet template
- `diary install` command — reads config, prints customized plist XML and zsh snippet to stdout with instructions

**Verification criteria:**
- [ ] `diary notify morning` sends a macOS notification (manual verification on macOS)
- [ ] `diary notify morning` run twice on same day → only sends once (second run is no-op)
- [ ] `diary notify evening` same behavior as morning
- [ ] Notification click action runs `open -a Warp` (manual verification)
- [ ] `notification_state` table correctly tracks sent status per date
- [ ] `diary install` prints valid launchd plist XML with correct times from config
- [ ] `diary install` prints valid zsh snippet
- [ ] Zsh snippet in `.zshrc` prints today's task summary on new terminal open
- [ ] Zsh snippet silently does nothing if diary is not installed or DB doesn't exist
- [ ] All tests pass: `pytest`

**Milestone**: App is fully complete for v1. Daily workflow is: notification reminds you → open Warp → see summary → `diary tui` or `diary chat` → manage tasks → evening notification → review → done.
