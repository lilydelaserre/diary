# Phase 2 — Tasks: Service Layer — TaskService

## Approach

Top-down: implement methods in dependency order. `create_task` and `get_task` first (everything else depends on them), then `list_tasks`, then `update_task`, then `archive`/`unarchive`.

TDD: for each method, write parameterized tests first, verify they fail, then implement.

The TaskService needs to handle tags internally (create tag rows, link via task_tags) since task creation accepts tag names. This is self-contained within TaskService for now — the standalone TagService in Phase 3 will reuse the same DB tables.

---

## Tasks

### 1. Add test fixture for TaskService

1.1. In `tests/conftest.py`, add a `task_service` fixture that creates a `TaskService(db)`.

### 2. Tests + Implementation: `create_task`

2.1. Write tests in `tests/test_task_service.py`:

**Parameterized: create with varying inputs**
- Create with title only → status=todo, priority=medium, scheduled_date=None, archived=False, tags=[], created_at and updated_at set
- Create with all fields (title, description, priority=high, due_date, scheduled_date, tags=["backend","auth"]) → all fields persisted
- Create with tags that already exist in DB → reuses existing tag rows, no duplicate tag entries
- Create with empty tags list → no tags linked
- Create with duplicate tag names in request → deduplicated

**Verify side effects:**
- After create, a system activity log entry "Task created" exists for the task
- After create with tags, tags table has the tag rows and task_tags has the links
- Returned Task object has correct id (UUID format), all fields, and tags list

2.2. Implement `create_task`:
- Generate UUID for task id
- Generate ISO datetime for created_at and updated_at
- INSERT into tasks table
- For each tag name: INSERT OR IGNORE into tags table, then INSERT into task_tags
- INSERT system activity log entry: source="system", content="Task created"
- Return the created Task by calling `get_task`

### 3. Tests + Implementation: `get_task`

3.1. Write tests:

- Get existing task → returns Task with all fields, tags list, and activity_log list
- Get task with multiple activity log entries → entries ordered by timestamp ascending
- Get task with multiple tags → tags list populated
- Get task with no tags → tags is empty list
- Get task with no activity log → activity_log is empty list
- Get non-existent task ID → raises ValueError (or appropriate error)

3.2. Implement `get_task`:
- SELECT from tasks WHERE id=?
- If not found, raise ValueError
- SELECT tag names via JOIN task_tags + tags WHERE task_id=?
- SELECT activity_log entries WHERE task_id=? ORDER BY timestamp ASC
- Assemble and return Task model

### 4. Tests + Implementation: `list_tasks`

4.1. Write tests:

**Setup**: seed DB with a variety of tasks (different statuses, priorities, scheduled dates, tags, archived states) in a fixture.

**Parameterized: individual filters**
- `scheduled="today"` (using today's date) → only tasks with scheduled_date=today
- `scheduled="2026-03-05"` → only tasks with that date
- `scheduled="none"` → only tasks with scheduled_date=NULL (backlog)
- `status="todo"` → only todo tasks
- `status="in-progress"` → only in-progress tasks
- `status="done"` → only done tasks
- `priority="high"` → only high priority
- `tag="backend"` → only tasks with that tag
- `archived=True` → includes archived tasks
- `archived=False` (default) → excludes archived tasks
- `search="login"` → FTS match on title/description

**Combined filters:**
- `scheduled="today"` + `priority="high"` → intersection
- `status="todo"` + `tag="backend"` → intersection

**Result shape:**
- Default (non-verbose): tasks have activity_log=None
- Verbose: tasks have activity_log populated
- Tasks sorted by priority (high → medium → low)

4.2. Implement `list_tasks`:
- Build SQL query dynamically based on filters
- For `scheduled="today"`: use today's ISO date
- For `scheduled="none"`: WHERE scheduled_date IS NULL
- For `search`: JOIN with tasks_fts using MATCH
- For `tag`: JOIN with task_tags + tags
- Default: WHERE archived=0
- ORDER BY priority (CASE WHEN high THEN 1, medium THEN 2, low THEN 3)
- For each task in results, fetch tags
- If verbose, also fetch activity_log per task

### 5. Tests + Implementation: `update_task`

5.1. Write tests:

**Parameterized: individual field updates with system log verification**
- Update status from todo to in-progress → field changes + system log "Status changed from todo to in-progress"
- Update status from in-progress to done → field changes + system log "Status changed from in-progress to done"
- Update priority from medium to high → field changes + system log "Priority changed from medium to high"
- Update scheduled_date from None to "2026-03-05" → field changes + system log "Scheduled for 2026-03-05"
- Update scheduled_date from "2026-03-05" to None → field changes + system log "Moved to backlog"
- Update title → field changes + system log "Title changed"
- Update description → field changes + system log "Description updated"
- Update due_date → field changes + system log "Due date set to YYYY-MM-DD" or "Due date cleared"
- Update tags from ["backend"] to ["backend","auth"] → tags updated + system log "Tags changed from #backend to #backend, #auth"

**Edge cases:**
- Update with no actual changes (same values) → no system log entries generated
- Update multiple fields at once → one system log entry per changed field
- Update non-existent task → raises ValueError
- updated_at timestamp changes on every update

5.2. Implement `update_task`:
- Fetch current task
- Compare each field in UpdateTaskRequest (skip None values)
- For each changed field: UPDATE the column, INSERT system log entry
- For tags: diff old vs new, update task_tags accordingly
- Update updated_at timestamp
- Return updated Task via `get_task`

### 6. Tests + Implementation: `archive_task`

6.1. Write tests:
- Archive task with reason → archived=True, archive_reason set, system log "Task archived: <reason>"
- Archive without reason (empty string) → raises ValueError
- Archive already-archived task → raises ValueError (or idempotent — decide)
- Archive non-existent task → raises ValueError

6.2. Implement `archive_task`:
- Validate reason is non-empty
- UPDATE tasks SET archived=1, archive_reason=? WHERE id=?
- INSERT system log entry
- Return updated Task

### 7. Tests + Implementation: `unarchive_task`

7.1. Write tests:
- Unarchive task → archived=False, archive_reason cleared, scheduled_date=NULL (backlog), system log "Task unarchived"
- Unarchive non-archived task → raises ValueError
- Unarchive non-existent task → raises ValueError

7.2. Implement `unarchive_task`:
- UPDATE tasks SET archived=0, archive_reason=NULL, scheduled_date=NULL WHERE id=?
- INSERT system log entry
- Return updated Task

---

## Order of Execution

1. Add `task_service` fixture to conftest.py
2. Write tests for `create_task` (2.1) → they fail (NotImplementedError)
3. Write tests for `get_task` (3.1) → they fail
4. Implement `get_task` (3.2) — needed by create_task's return
5. Implement `create_task` (2.2) → create + get tests pass
6. Write tests for `list_tasks` (4.1) → they fail
7. Implement `list_tasks` (4.2) → list tests pass
8. Write tests for `update_task` (5.1) → they fail
9. Implement `update_task` (5.2) → update tests pass
10. Write tests for `archive_task` (6.1) → they fail
11. Implement `archive_task` (6.2) → archive tests pass
12. Write tests for `unarchive_task` (7.1) → they fail
13. Implement `unarchive_task` (7.2) → unarchive tests pass
14. Run full test suite → all green (Phase 1 + Phase 2)

---

## Verification

Phase 2 is complete when:
- [ ] Create task with only title → correct defaults
- [ ] Create task with all fields → all persisted
- [ ] Create task with tags → tags table + task_tags populated, reuses existing tags
- [ ] Get task by ID → complete Task with tags and activity_log
- [ ] Get invalid ID → ValueError
- [ ] List with no filters → all non-archived tasks
- [ ] List with each filter individually → correct results
- [ ] List with combined filters → correct intersection
- [ ] FTS search matches title and description
- [ ] Update status → field changes + system log
- [ ] Update priority → field changes + system log
- [ ] Update scheduled_date → field changes + system log (including "Moved to backlog")
- [ ] Update multiple fields → one system log per changed field
- [ ] Update with no changes → no system log entries
- [ ] Update non-existent task → ValueError
- [ ] updated_at changes on every update
- [ ] Archive with reason → archived=True, reason set, system log
- [ ] Archive without reason → ValueError
- [ ] Archive non-existent → ValueError
- [ ] Unarchive → archived=False, reason cleared, scheduled_date=NULL, system log
- [ ] Unarchive non-archived → ValueError
- [ ] Archived tasks excluded by default, included with flag
- [ ] All tests pass: `pytest`
