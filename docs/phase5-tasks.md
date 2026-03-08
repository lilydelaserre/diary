# Phase 5 — Tasks: AI Agent

## Approach

Top-down: agent setup + tool definitions first, then system prompt, then chat REPL. TDD where possible — tool functions are testable (they call the service layer), the REPL and LLM behavior are harder to unit test but we verify the wiring.

Key constraint: the agent tools call the service layer directly (same process), not via HTTP or CLI.

---

## Tasks

### 1. Research Strands Agents API

1.1. Check strands-agents is installed and verify the API for creating an agent with tools and a system prompt. Confirm how to define tools (decorator? class?) and how to run a conversation loop.

### 2. Define agent tools (`agent/tools.py`)

2.1. Define tool functions that wrap service layer calls:
  - `list_tasks(scheduled?, status?, priority?, tag?, search?, archived?)` → calls TaskService.list_tasks
  - `show_task(task_id)` → calls TaskService.get_task
  - `create_task(title, description?, priority?, tags?, due_date?, scheduled_date?)` → calls TaskService.create_task
  - `update_task(task_id, title?, description?, status?, priority?, tags?, due_date?, scheduled_date?)` → calls TaskService.update_task
  - `add_log_entry(task_id, content)` → calls ActivityLogService.add_entry with source="ai"
  - `archive_task(task_id, reason)` → calls TaskService.archive_task
  - `unarchive_task(task_id)` → calls TaskService.unarchive_task
  - `list_tags()` → calls TagService.list_all_tags
  - `get_summary(from_date, to_date)` → calls SummaryService.summarize

  NO tools for: delete_entry, edit_entry (restricted to TUI only)

### 3. Tests for tools

3.1. Write tests in `tests/test_agent_tools.py`:

**Parameterized: each tool calls correct service method**
- `list_tasks()` with no args → returns all non-archived tasks
- `show_task(id)` → returns task with activity log
- `create_task(title="X")` → creates task, returns it
- `update_task(id, status="done")` → updates, returns it
- `add_log_entry(id, "msg")` → adds entry with source="ai"
- `archive_task(id, "reason")` → archives
- `unarchive_task(id)` → unarchives
- `list_tags()` → returns tag list
- `get_summary(from, to)` → returns summary dict

**Verify restrictions:**
- No delete_entry tool exists
- No edit_entry tool exists

### 4. Agent setup (`agent/agent.py`)

4.1. Create agent factory function that:
  - Accepts a DB connection
  - Creates service instances
  - Creates tool functions bound to those services
  - Builds system prompt
  - Returns a configured Strands Agent

4.2. System prompt covers:
  - Always explain what you're about to do before doing it
  - Ask about every unfilled optional field when creating/updating
  - Suggest tags based on existing tags (call list_tags first)
  - Wait for explicit user confirmation before any mutation
  - Accept free-form responses
  - Keep responses concise
  - Proactively ask to persist important context to task activity log

### 5. Chat REPL (`chat.py`)

5.1. Implement `diary chat`:
  - Initialize DB, create agent
  - Print welcome message
  - Loop: read user input → send to agent → print response
  - Exit on 'quit' or 'exit'
  - Conversation history retained within session (handled by Strands Agent)

### 6. Wire into CLI

6.1. Update `cli.py` to call `chat.run()` when `diary chat` is invoked.

### 7. Integration test

7.1. Test that `diary chat` starts without errors (subprocess test, send 'quit' immediately).

---

## Order of Execution

1. Research Strands API (1.1)
2. Define tool functions (2.1)
3. Write tool tests (3.1) → they fail
4. Implement tools to pass tests (tools just call service layer)
5. Create agent setup (4.1, 4.2)
6. Implement chat REPL (5.1)
7. Wire into CLI (6.1)
8. Integration test (7.1)
9. Run full test suite → all green

---

## Verification

Phase 5 is complete when:
- [x] Each tool function calls the correct service method
- [x] No delete/edit log tools exist
- [x] add_log_entry uses source="ai"
- [x] Agent is created with system prompt and all tools
- [x] `diary chat` starts, accepts input, exits on 'quit'
- [x] Conversation history retained within session (handled by Strands Agent internally)
- [x] All tests pass: `pytest` (211 passed)
