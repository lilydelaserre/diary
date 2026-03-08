# Phase 3 — Tasks: ActivityLogService + TagService + SummaryService

## Approach

Top-down: define service interfaces → write tests → implement. Each service is independent so we implement them sequentially: ActivityLogService first (most used), then TagService, then SummaryService.

Note: TaskService already handles tag creation/linking and system log insertion internally. The standalone services here provide the additional operations needed by clients directly (e.g., TUI editing log entries, AI listing all tags).

---

## Tasks

### 1. Add fixtures

1.1. In `tests/conftest.py`, add fixtures for `ActivityLogService`, `TagService`, `SummaryService`.

### 2. Tests + Implementation: ActivityLogService

2.1. Write tests in `tests/test_activity_log_service.py`:

**add_entry:**
- Add entry with source="user" → persisted with auto-generated id, timestamp, correct task_id
- Add entry with source="ai" → persisted with source="ai"
- Add entry with source="system" → persisted with source="system"
- Add entry to non-existent task → raises ValueError
- Parameterize across all three source types

**edit_entry:**
- Edit existing entry → content changes, timestamp and source unchanged
- Edit non-existent entry → raises ValueError

**delete_entry:**
- Delete existing entry → entry gone from DB
- Delete non-existent entry → raises ValueError

**list_entries:**
- List entries for task with multiple entries → ordered by timestamp ascending
- List entries for task with no entries → empty list
- List entries for non-existent task → raises ValueError

2.2. Implement `ActivityLogService`:
- `add_entry`: validate task exists, generate UUID + timestamp, INSERT, return entry
- `edit_entry`: validate entry exists, UPDATE content only, return updated entry
- `delete_entry`: validate entry exists, DELETE
- `list_entries`: validate task exists, SELECT ORDER BY timestamp ASC

### 3. Tests + Implementation: TagService

3.1. Write tests in `tests/test_tag_service.py`:

**list_all_tags:**
- No tags exist → empty list
- Multiple tags across tasks → returns all unique tags
- Tags ordered alphabetically

**set_task_tags:**
- Set tags on task with no existing tags → tags created and linked
- Set tags replacing existing tags → old links removed, new links created
- Set tags with mix of new and existing tag names → new tags created, existing reused
- Set empty list → all tags removed, orphaned tags cleaned up
- Set on non-existent task → raises ValueError
- Duplicate tag names → deduplicated

3.2. Implement `TagService`:
- `list_all_tags`: SELECT all from tags ORDER BY name
- `set_task_tags`: DELETE existing links, INSERT OR IGNORE new tags, INSERT new links, clean up orphaned tags (tags with no task_tags references)

### 4. Tests + Implementation: SummaryService

4.1. Write tests in `tests/test_summary_service.py`:

**summarize:**
- Date range with tasks created, completed, and active → correct counts
- Date range with no activity → zero counts
- Returns list of tasks that were active (scheduled) in the range
- Returns count of tasks completed in the range
- Work periods computed correctly for task that moved in/out of active work

4.2. Implement `SummaryService`:
- Query tasks where scheduled_date falls in range OR status changed to done in range (via activity log)
- Count tasks created in range (created_at)
- Count tasks completed in range (activity log "Status changed" to done)
- Return structured dict with counts and task summaries

---

## Order of Execution

1. Add fixtures to conftest.py
2. Write ActivityLogService tests (2.1) → they fail
3. Implement ActivityLogService (2.2) → tests pass
4. Write TagService tests (3.1) → they fail
5. Implement TagService (3.2) → tests pass
6. Write SummaryService tests (4.1) → they fail
7. Implement SummaryService (4.2) → tests pass
8. Run full test suite → all green (Phase 1 + 2 + 3)

---

## Verification

Phase 3 is complete when:
- [ ] Add log entry with each source type → persisted correctly
- [ ] Add entry to non-existent task → ValueError
- [ ] Edit entry → content changes, timestamp/source unchanged
- [ ] Edit non-existent entry → ValueError
- [ ] Delete entry → hard deleted
- [ ] Delete non-existent entry → ValueError
- [ ] List entries → ordered by timestamp
- [ ] List entries for empty task → empty list
- [ ] List all tags → unique, alphabetical
- [ ] Set task tags → creates/reuses/removes correctly
- [ ] Set empty tags → cleans up orphans
- [ ] Summary for date range → correct counts
- [ ] Summary with no activity → zeros
- [ ] All tests pass: `pytest`
