# Phase 6 — Tasks: TUI

## Approach

Build the TUI incrementally: app shell → main screen with task panels → task detail → manual operations → chat overlay → history/archive screens. Test with Textual's pilot framework where possible.

The TUI is a thin rendering layer over the service layer. All business logic stays in services.

---

## Tasks

### 1. App shell (`tui/app.py`)

1.1. Textual App subclass with:
  - Title "Diary"
  - CSS for layout
  - Keybindings: [R]efresh, [C]hat toggle, [Q]uit, [?]Help
  - DB connection + service instances created on mount
  - Main screen as default

### 2. Main screen layout

2.1. Left side: Today panel (top) + Backlog panel (bottom)
2.2. Right side: Task detail panel
2.3. Today panel: tasks with scheduled_date=today, sorted by priority
2.4. Backlog panel: tasks with scheduled_date=null, sorted by priority
2.5. Each task item shows: priority indicator, title, status

### 3. Task detail panel

3.1. Shows selected task's full fields: title, status, priority, tags, due_date, scheduled_date, description
3.2. Activity log below fields, ordered by timestamp
3.3. Each log entry shows: timestamp, source badge, content

### 4. Manual operations

4.1. [N]ew task — modal/screen to create task (title required, optional fields)
4.2. [E]dit task — edit selected task fields
4.3. [S]tatus cycle — quick status change (todo → in-progress → done)
4.4. [P]riority cycle — quick priority change (high → medium → low → high)
4.5. [D]ate — schedule task for a date or move to backlog
4.6. [A]rchive — archive with reason prompt
4.7. [U]narchive — unarchive selected task
4.8. [L]og — add activity log entry to selected task
4.9. Edit/delete activity log entries (TUI-only operations)

### 5. Chat overlay

5.1. [C] toggles chat overlay (full screen over task panels)
5.2. Uses same agent as `diary chat`
5.3. Input field at bottom, messages scroll above
5.4. [C] again collapses back to task view

### 6. History screen

6.1. Separate screen showing completed tasks by date
6.2. Accessible via [H] keybinding

### 7. Archive screen

7.1. Separate screen showing archived tasks with reasons
7.2. Accessible via [V] keybinding (view archive)

### 8. Wire into CLI

8.1. `diary tui` calls the Textual app

---

## Order of Execution

1. App shell + main screen layout (1, 2)
2. Task detail panel (3)
3. Manual operations (4)
4. Chat overlay (5)
5. History + archive screens (6, 7)
6. Wire into CLI (8)
7. Tests throughout

---

## Verification

Phase 6 is complete when:
- [x] `diary tui` launches without errors
- [x] Today panel shows tasks scheduled for today, sorted by priority
- [x] Backlog panel shows unscheduled tasks, sorted by priority
- [x] Selecting a task shows full detail + activity log
- [x] [C] expands/collapses chat overlay
- [ ] Chat overlay can create/update tasks via AI (placeholder — uses `diary chat` for now)
- [x] [R] refreshes data from DB
- [x] All manual operations work (create, edit, status, priority, schedule, archive, unarchive, log)
- [x] Edit/delete activity log entries work (TUI only — via edit task form)
- [x] History screen shows completed tasks by date
- [x] Archive screen shows archived tasks
- [x] All tests pass: `uv run pytest` (217 passed)
