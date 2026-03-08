"""End-to-end CLI smoke tests — exercises all diary api commands in sequence."""
import json
import subprocess
import sys
import os
import pytest


def run_api(*args, db_path=None):
    env = os.environ.copy()
    if db_path:
        env["DIARY_DB"] = db_path
    return subprocess.run(
        [sys.executable, "-m", "diary.cli", "api", *args],
        capture_output=True, text=True, env=env,
    )


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "smoke.db")


class TestCLISmokeTest:
    """Full lifecycle: create → list → show → update → log → archive → unarchive."""

    def test_full_lifecycle(self, db_path):
        # 1. Create a task with natural language date
        r = run_api("add", "--title", "Smoke test task", "--priority", "high",
                     "--tags", "test,smoke", "--schedule", "today",
                     "--due", "tomorrow", "--description", "A test task",
                     db_path=db_path)
        assert r.returncode == 0, r.stderr
        task = json.loads(r.stdout)
        task_id = task["id"]
        assert task["title"] == "Smoke test task"
        assert task["priority"] == "high"
        assert task["done"] is False
        assert set(task["tags"]) == {"test", "smoke"}
        assert task["due_date"] is not None
        assert task["scheduled_date"] is not None

        # 2. List — should find the task
        r = run_api("list", db_path=db_path)
        assert r.returncode == 0
        tasks = json.loads(r.stdout)
        assert any(t["id"] == task_id for t in tasks)

        # 3. List with filters
        r = run_api("list", "--scheduled", "today", "--priority", "high", db_path=db_path)
        assert r.returncode == 0
        tasks = json.loads(r.stdout)
        assert any(t["id"] == task_id for t in tasks)

        # 4. List with brief format
        r = run_api("list", "--format", "brief", db_path=db_path)
        assert r.returncode == 0
        assert "Smoke test task" in r.stdout

        # 5. List with search
        r = run_api("list", "--search", "smoke", db_path=db_path)
        assert r.returncode == 0
        tasks = json.loads(r.stdout)
        assert len(tasks) >= 1

        # 6. List verbose
        r = run_api("list", "--verbose", db_path=db_path)
        assert r.returncode == 0
        tasks = json.loads(r.stdout)
        assert tasks[0].get("activity_log") is not None

        # 7. Show
        r = run_api("show", task_id, db_path=db_path)
        assert r.returncode == 0
        task = json.loads(r.stdout)
        assert task["title"] == "Smoke test task"
        assert task["activity_log"] is not None

        # 8. Mark done
        r = run_api("update", task_id, "--done", db_path=db_path)
        assert r.returncode == 0
        task = json.loads(r.stdout)
        assert task["done"] is True

        # 8b. Undo done
        r = run_api("update", task_id, "--undone", db_path=db_path)
        assert r.returncode == 0
        task = json.loads(r.stdout)
        assert task["done"] is False

        # 9. Update priority
        r = run_api("update", task_id, "--priority", "low", db_path=db_path)
        assert r.returncode == 0
        task = json.loads(r.stdout)
        assert task["priority"] == "low"

        # 10. Update tags
        r = run_api("update", task_id, "--tags", "updated", db_path=db_path)
        assert r.returncode == 0
        task = json.loads(r.stdout)
        assert task["tags"] == ["updated"]

        # 11. Update schedule with natural language
        r = run_api("update", task_id, "--schedule", "tomorrow", db_path=db_path)
        assert r.returncode == 0
        task = json.loads(r.stdout)
        assert task["scheduled_date"] is not None

        # 12. Move to backlog
        r = run_api("update", task_id, "--schedule", "none", db_path=db_path)
        assert r.returncode == 0
        task = json.loads(r.stdout)
        assert task["scheduled_date"] is None

        # 13. Add log entry
        r = run_api("log", task_id, "Test log entry", db_path=db_path)
        assert r.returncode == 0
        entry = json.loads(r.stdout)
        assert entry["source"] == "user"
        assert entry["content"] == "Test log entry"

        # 14. Mark done
        r = run_api("update", task_id, "--done", db_path=db_path)
        assert r.returncode == 0

        # 15. Archive
        r = run_api("archive", task_id, "--reason", "Smoke test complete", db_path=db_path)
        assert r.returncode == 0
        task = json.loads(r.stdout)
        assert task["archived"] is True

        # 16. List archived
        r = run_api("list", "--archived", db_path=db_path)
        assert r.returncode == 0
        tasks = json.loads(r.stdout)
        assert any(t["id"] == task_id and t["archived"] for t in tasks)

        # 17. Unarchive
        r = run_api("unarchive", task_id, db_path=db_path)
        assert r.returncode == 0
        task = json.loads(r.stdout)
        assert task["archived"] is False
        assert task["scheduled_date"] is None  # back to backlog

        # 18. List backlog
        r = run_api("list", "--scheduled", "none", db_path=db_path)
        assert r.returncode == 0
        tasks = json.loads(r.stdout)
        assert any(t["id"] == task_id for t in tasks)

    def test_show_invalid_id(self, db_path):
        r = run_api("show", "nonexistent", db_path=db_path)
        assert r.returncode == 1
        assert "not found" in r.stderr.lower()

    def test_add_missing_title(self, db_path):
        r = run_api("add", db_path=db_path)
        assert r.returncode != 0

    def test_archive_missing_reason(self, db_path):
        # Create a task first
        r = run_api("add", "--title", "Temp", db_path=db_path)
        task_id = json.loads(r.stdout)["id"]
        r = run_api("archive", task_id, db_path=db_path)
        assert r.returncode != 0

    def test_natural_date_in_add(self, db_path):
        r = run_api("add", "--title", "Future task", "--schedule", "in 3 days",
                     "--due", "next thursday", db_path=db_path)
        assert r.returncode == 0, r.stderr
        task = json.loads(r.stdout)
        assert task["scheduled_date"] is not None
        assert task["due_date"] is not None

    def test_help_on_all_commands(self, db_path):
        for cmd in ["list", "show", "add", "update", "log", "archive", "unarchive"]:
            r = run_api(cmd, "--help", db_path=db_path)
            assert r.returncode == 0, f"{cmd} --help failed"
            assert "usage" in r.stdout.lower() or cmd in r.stdout.lower()
