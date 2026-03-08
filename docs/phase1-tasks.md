# Phase 1 — Tasks: Skeleton + DB + Models

## Approach

Top-down: project structure → database → models → CLI shell → service stubs → tests.

TDD: write tests first for DB schema and models, then implement to make them pass. Service stubs just need to exist with correct signatures (no tests for NotImplementedError).

---

## Tasks

### 1. Project setup

1.1. Create `pyproject.toml` with:
  - Package metadata (name=diary, version=0.1.0)
  - Dependencies: `textual`, `strands-agents`, `strands-agents-tools`, `pydantic`, `tomli` (for TOML config on Python <3.11)
  - Dev dependencies: `pytest`, `pytest-asyncio`
  - Entry point: `diary = "diary.cli:main"`
  - Python >=3.11

1.2. Create directory structure (empty `__init__.py` files where needed):
  ```
  src/diary/__init__.py
  src/diary/cli.py
  src/diary/db.py
  src/diary/models.py
  src/diary/config.py
  src/diary/api_cli.py
  src/diary/chat.py
  src/diary/notify.py
  src/diary/service/__init__.py
  src/diary/service/tasks.py
  src/diary/service/activity_log.py
  src/diary/service/tags.py
  src/diary/service/summary.py
  src/diary/agent/__init__.py
  src/diary/agent/agent.py
  src/diary/agent/tools.py
  src/diary/tui/__init__.py
  src/diary/tui/app.py
  src/diary/tui/screens/
  src/diary/tui/widgets/
  install/
  tests/__init__.py
  tests/conftest.py
  ```

1.3. Create `tests/conftest.py` with a pytest fixture that provides a fresh in-memory SQLite database for each test (so tests don't share state or touch disk).

### 2. Config (`src/diary/config.py`)

2.1. Define a `DiaryConfig` Pydantic model with all config fields and defaults:
  - `morning_notification_time`: str, default "10:00"
  - `evening_notification_time`: str, default "18:00"
  - `workdays`: list[str], default ["mon", "tue", "wed", "thu", "fri"]
  - `notifications_enabled`: bool, default True
  - `data_dir`: str, default "~/.local/share/diary"
  - `ai_model`: str, default "us.anthropic.claude-sonnet-4-20250514-v1:0"
  - `terminal_app`: str, default "Warp"

2.2. Implement `load_config(path?)` → reads TOML from `~/.config/diary/config.toml` (or given path), merges with defaults, returns `DiaryConfig`. If file doesn't exist, returns all defaults.

### 3. Database (`src/diary/db.py`)

3.1. Implement `get_connection(db_path)` → returns a `sqlite3.Connection` with:
  - WAL mode enabled
  - Foreign keys enabled
  - Row factory set to `sqlite3.Row`

3.2. Implement `init_db(conn)` → creates all tables, indexes, FTS5 virtual table, and FTS sync triggers if they don't already exist:
  - `tasks` table (with CHECK constraints on status and priority)
  - `tags` table
  - `task_tags` join table (with foreign keys)
  - `activity_log` table (with CHECK constraint on source)
  - `activity_log` indexes (task_id, timestamp)
  - `tasks_fts` FTS5 virtual table (external content, synced to tasks)
  - FTS triggers: after INSERT, UPDATE, DELETE on tasks → sync to tasks_fts
  - `notification_state` table

3.3. Implement `get_db(config?)` → convenience function that calls `get_connection` with the configured path and `init_db`, returns ready-to-use connection.

### 4. Models (`src/diary/models.py`)

4.1. Define Pydantic models:

  - `Task`: id (str), title (str), description (str|None), status (Literal["todo","in-progress","done"]), priority (Literal["high","medium","low"]), tags (list[str]), due_date (str|None), scheduled_date (str|None), archived (bool), archive_reason (str|None), created_at (str), updated_at (str), activity_log (list[ActivityLogEntry]|None — only populated on get_task, not on list)

  - `ActivityLogEntry`: id (str), task_id (str), timestamp (str), source (Literal["user","ai","system"]), content (str)

  - `Tag`: id (str), name (str)

  - `CreateTaskRequest`: title (str), description (str|None=None), priority (Literal[...]|None="medium"), tags (list[str]|None=None), due_date (str|None=None), scheduled_date (str|None=None)

  - `UpdateTaskRequest`: title (str|None=None), description (str|None=None), status (Literal[...]|None=None), priority (Literal[...]|None=None), tags (list[str]|None=None), due_date (str|None=None), scheduled_date (str|None=None)

  - `TaskListFilters`: scheduled (str|None=None), status (str|None=None), priority (str|None=None), tag (str|None=None), search (str|None=None), from_date (str|None=None), to_date (str|None=None), archived (bool=False), verbose (bool=False)

### 5. CLI entry point (`src/diary/cli.py`)

5.1. Implement `main()` using argparse with subcommands:
  - `diary tui` → prints "Not implemented yet" and exits 0
  - `diary chat` → prints "Not implemented yet" and exits 0
  - `diary api` → delegates to `api_cli` (stub for now)
  - `diary notify` → prints "Not implemented yet" and exits 0
  - `diary install` → prints "Not implemented yet" and exits 0
  - `diary --help` → prints all subcommands
  - `diary` with no args → prints help

### 6. Service stubs

6.1. `src/diary/service/tasks.py` — `TaskService` class with method signatures:
  - `__init__(self, conn: sqlite3.Connection)`
  - `create_task(self, request: CreateTaskRequest) -> Task`
  - `get_task(self, task_id: str) -> Task`
  - `list_tasks(self, filters: TaskListFilters) -> list[Task]`
  - `update_task(self, task_id: str, request: UpdateTaskRequest) -> Task`
  - `archive_task(self, task_id: str, reason: str) -> Task`
  - `unarchive_task(self, task_id: str) -> Task`
  
  All methods raise `NotImplementedError`.

6.2. `src/diary/service/activity_log.py` — `ActivityLogService` class with method signatures:
  - `__init__(self, conn: sqlite3.Connection)`
  - `add_entry(self, task_id: str, source: str, content: str) -> ActivityLogEntry`
  - `edit_entry(self, entry_id: str, content: str) -> ActivityLogEntry`
  - `delete_entry(self, entry_id: str) -> None`
  - `list_entries(self, task_id: str) -> list[ActivityLogEntry]`
  
  All methods raise `NotImplementedError`.

6.3. `src/diary/service/tags.py` — `TagService` class with method signatures:
  - `__init__(self, conn: sqlite3.Connection)`
  - `list_all_tags(self) -> list[Tag]`
  - `set_task_tags(self, task_id: str, tag_names: list[str]) -> list[Tag]`
  
  All methods raise `NotImplementedError`.

6.4. `src/diary/service/summary.py` — `SummaryService` class with method signatures:
  - `__init__(self, conn: sqlite3.Connection)`
  - `summarize(self, from_date: str, to_date: str) -> dict`
  
  Raises `NotImplementedError`.

### 7. Tests

Write all tests FIRST, then verify they fail (because implementations are stubs or not yet written), then go back and implement tasks 2–6 to make them pass.

7.1. `tests/test_config.py`:
  - Test load_config with no file → returns all defaults
  - Test load_config with partial TOML → merges with defaults
  - Test load_config with full TOML → all values overridden
  - Parameterize across individual config fields to verify each default

7.2. `tests/test_db.py`:
  - Test init_db creates all expected tables (parameterize across table names: tasks, tags, task_tags, activity_log, notification_state)
  - Test init_db creates tasks_fts virtual table
  - Test init_db creates expected indexes (parameterize across index names)
  - Test WAL mode is enabled
  - Test foreign keys are enabled
  - Test CHECK constraints on tasks.status (parameterize valid and invalid values)
  - Test CHECK constraints on tasks.priority (parameterize valid and invalid values)
  - Test CHECK constraints on activity_log.source (parameterize valid and invalid values)
  - Test FTS triggers exist (parameterize: insert, update, delete triggers)
  - Test init_db is idempotent (call twice, no errors)

7.3. `tests/test_models.py`:
  - Test Task model round-trip: create → dict → from dict → equal (parameterize with minimal fields and all fields)
  - Test Task model JSON serialization/deserialization
  - Test ActivityLogEntry round-trip
  - Test CreateTaskRequest with defaults
  - Test CreateTaskRequest with all fields
  - Test UpdateTaskRequest with no fields (all None)
  - Test UpdateTaskRequest with each field individually (parameterize)
  - Test TaskListFilters defaults
  - Test model validation rejects invalid status values
  - Test model validation rejects invalid priority values
  - Test model validation rejects invalid source values

7.4. `tests/test_cli.py`:
  - Test `diary --help` exits 0 and prints subcommand names
  - Test each subcommand with --help exits 0 (parameterize across: tui, chat, api, notify, install)
  - Test each stub subcommand prints "Not implemented" message (parameterize)

---

## Order of Execution

1. Write `tests/conftest.py` (test infrastructure)
2. Write all test files (7.1–7.4) — tests will fail
3. Implement `pyproject.toml` (task 1.1)
4. Create directory structure (task 1.2)
5. Implement `config.py` (task 2) → config tests pass
6. Implement `db.py` (task 3) → DB tests pass
7. Implement `models.py` (task 4) → model tests pass
8. Implement `cli.py` (task 5) → CLI tests pass
9. Create service stubs (task 6) — no tests needed for stubs
10. Run full test suite → all green

---

## Verification

Phase 1 is complete when:
- [ ] `diary --help` prints subcommands and exits 0
- [ ] `diary tui`, `diary chat`, `diary api`, `diary notify`, `diary install` each exit with a "not implemented" message
- [ ] Database file is created with all tables and indexes when initialized
- [ ] All tables match the schema in DESIGN.md (verified by test_db.py)
- [ ] FTS5 triggers exist and are correctly defined
- [ ] Pydantic models round-trip correctly (verified by test_models.py)
- [ ] Config loads with correct defaults (verified by test_config.py)
- [ ] All tests pass: `pytest`
