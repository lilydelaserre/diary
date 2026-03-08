# Phase 4 — Tasks: CLI API (`diary api`)

## Approach

Top-down: argparse structure first (all subcommands defined with args), then tests, then implement each command by wiring to the service layer.

The CLI is a thin wrapper: parse args → call service → print JSON (or brief format) → exit code.

---

## Tasks

### 1. Define argparse structure in `api_cli.py`

1.1. Create `diary api` subcommand parser with sub-subcommands:
  - `diary api list` with flags: `--scheduled`, `--status`, `--priority`, `--tag`, `--search`, `--from`, `--to`, `--archived`, `--verbose`, `--format`
  - `diary api show <task-id>`
  - `diary api add --title <title>` with optional: `--description`, `--priority`, `--tags`, `--due`, `--schedule`
  - `diary api update <task-id>` with optional: `--title`, `--description`, `--status`, `--priority`, `--tags`, `--due`, `--schedule`
  - `diary api log <task-id> <message>`
  - `diary api archive <task-id> --reason <reason>`
  - `diary api unarchive <task-id>`
  - Every command has `--help`

1.2. Wire `diary api` in `cli.py` to delegate to `api_cli.run(args)`.

### 2. Tests

2.1. Write tests in `tests/test_api_cli.py` using subprocess to invoke `diary api` commands against a temp DB.

**Help tests (parameterized):**
- Each subcommand has `--help` that exits 0

**list tests:**
- `diary api list` → JSON array, exit 0
- `diary api list --scheduled today` → only today's tasks
- `diary api list --status done` → only done tasks
- `diary api list --priority high` → only high priority
- `diary api list --tag backend` → only tagged tasks
- `diary api list --search login` → FTS results
- `diary api list --archived` → includes archived
- `diary api list --verbose` → includes activity_log in output
- `diary api list --format brief` → human-readable text, not JSON

**show tests:**
- `diary api show <id>` → full JSON with activity_log, exit 0
- `diary api show nonexistent` → error on stderr, exit 1

**add tests:**
- `diary api add --title "Test"` → JSON with new task, exit 0
- `diary api add` (no title) → error, exit non-zero

**update tests:**
- `diary api update <id> --status done` → updated JSON, exit 0
- `diary api update nonexistent --status done` → error, exit 1

**log tests:**
- `diary api log <id> "message"` → exit 0
- `diary api log nonexistent "msg"` → error, exit 1

**archive/unarchive tests:**
- `diary api archive <id> --reason "done"` → exit 0
- `diary api archive <id>` (no reason) → error, exit non-zero
- `diary api unarchive <id>` → exit 0

**Output contract:**
- All JSON output is valid JSON
- All errors go to stderr
- All data goes to stdout

### 3. Implement each command

3.1. Implement a helper `_get_db()` that loads config and returns an initialized DB connection.

3.2. Implement each subcommand handler:
  - `handle_list(args)` → TaskService.list_tasks with filters from args → print JSON or brief
  - `handle_show(args)` → TaskService.get_task → print JSON
  - `handle_add(args)` → TaskService.create_task → print JSON
  - `handle_update(args)` → TaskService.update_task → print JSON
  - `handle_log(args)` → ActivityLogService.add_entry → print JSON
  - `handle_archive(args)` → TaskService.archive_task → print JSON
  - `handle_unarchive(args)` → TaskService.unarchive_task → print JSON

3.3. Error handling: catch ValueError → print to stderr, exit 1.

---

## Order of Execution

1. Define argparse structure (1.1, 1.2)
2. Write all tests (2.1) → they fail
3. Implement `_get_db()` helper and all handlers (3.1–3.3) → tests pass
4. Run full test suite → all green

---

## Verification

Phase 4 is complete when:
- [ ] Every `diary api` subcommand has `--help` that exits 0
- [ ] `diary api list` returns valid JSON array
- [ ] Each filter flag works individually
- [ ] `--format brief` returns human-readable text
- [ ] `--verbose` includes activity_log
- [ ] `diary api show <id>` returns full task JSON
- [ ] `diary api show nonexistent` → stderr + exit 1
- [ ] `diary api add --title "X"` creates task, returns JSON
- [ ] `diary api add` without title → error
- [ ] `diary api update <id> --status done` → updated JSON
- [ ] `diary api log <id> "msg"` → exit 0
- [ ] `diary api archive <id> --reason "X"` → exit 0
- [ ] `diary api archive` without reason → error
- [ ] `diary api unarchive <id>` → exit 0
- [ ] All JSON output parseable by json.loads
- [ ] Errors on stderr, data on stdout
- [ ] All tests pass: `pytest`
