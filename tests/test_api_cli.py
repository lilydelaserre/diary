import json
import subprocess
import sys
import os
import pytest


def run_api(*args, db_path=None):
    """Run diary api command and return result."""
    env = os.environ.copy()
    if db_path:
        env["DIARY_DB"] = db_path
    return subprocess.run(
        [sys.executable, "-m", "diary.cli", "api", *args],
        capture_output=True, text=True, env=env,
    )


@pytest.fixture
def db_path(tmp_path):
    """Create a temp DB path for CLI tests."""
    return str(tmp_path / "test.db")


@pytest.fixture
def seeded_db(db_path):
    """Seed a DB with test data and return the path."""
    # Create a task via the CLI
    r = run_api("add", "--title", "CLI Task", "--priority", "high", "--tags", "backend,auth", db_path=db_path)
    assert r.returncode == 0
    task = json.loads(r.stdout)

    # Create a second task
    r2 = run_api("add", "--title", "Low Task", "--priority", "low", db_path=db_path)
    assert r2.returncode == 0

    return db_path, task["id"]


class TestApiHelp:
    @pytest.mark.parametrize("subcmd", ["list", "show", "add", "update", "log", "archive", "unarchive"])
    def test_help_exits_0(self, subcmd):
        result = run_api(subcmd, "--help")
        assert result.returncode == 0


class TestApiList:
    def test_empty_list(self, db_path):
        r = run_api("list", db_path=db_path)
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert data == []

    def test_list_returns_json(self, seeded_db):
        db_path, _ = seeded_db
        r = run_api("list", db_path=db_path)
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert len(data) == 2

    def test_list_priority_filter(self, seeded_db):
        db_path, _ = seeded_db
        r = run_api("list", "--priority", "high", db_path=db_path)
        data = json.loads(r.stdout)
        assert len(data) == 1
        assert data[0]["title"] == "CLI Task"

    def test_list_tag_filter(self, seeded_db):
        db_path, _ = seeded_db
        r = run_api("list", "--tag", "backend", db_path=db_path)
        data = json.loads(r.stdout)
        assert len(data) == 1

    def test_list_search(self, seeded_db):
        db_path, _ = seeded_db
        r = run_api("list", "--search", "CLI", db_path=db_path)
        data = json.loads(r.stdout)
        assert any("CLI" in t["title"] for t in data)

    def test_list_verbose(self, seeded_db):
        db_path, _ = seeded_db
        r = run_api("list", "--verbose", db_path=db_path)
        data = json.loads(r.stdout)
        assert "activity_log" in data[0]

    def test_list_brief_format(self, seeded_db):
        db_path, _ = seeded_db
        r = run_api("list", "--format", "brief", db_path=db_path)
        assert r.returncode == 0
        assert "Diary" in r.stdout
        assert "CLI Task" in r.stdout
        # Should NOT be valid JSON
        with pytest.raises(json.JSONDecodeError):
            json.loads(r.stdout)


class TestApiShow:
    def test_show_task(self, seeded_db):
        db_path, task_id = seeded_db
        r = run_api("show", task_id, db_path=db_path)
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert data["id"] == task_id
        assert "activity_log" in data

    def test_show_nonexistent(self, db_path):
        r = run_api("show", "nonexistent", db_path=db_path)
        assert r.returncode == 1
        assert r.stderr.strip()


class TestApiAdd:
    def test_add_minimal(self, db_path):
        r = run_api("add", "--title", "New task", db_path=db_path)
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert data["title"] == "New task"
        assert data["done"] is False
        assert data["priority"] == "medium"

    def test_add_all_fields(self, db_path):
        r = run_api("add", "--title", "Full", "--description", "desc",
                     "--priority", "high", "--tags", "a,b", "--due", "2026-03-15",
                     "--schedule", "2026-03-01", db_path=db_path)
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert data["priority"] == "high"
        assert sorted(data["tags"]) == ["a", "b"]

    def test_add_no_title_fails(self, db_path):
        r = run_api("add", db_path=db_path)
        assert r.returncode != 0


class TestApiUpdate:
    def test_update_status(self, seeded_db):
        db_path, task_id = seeded_db
        r = run_api("update", task_id, "--done", db_path=db_path)
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert data["done"] is True

    def test_update_nonexistent(self, db_path):
        r = run_api("update", "nonexistent", "--done", db_path=db_path)
        assert r.returncode == 1


class TestApiLog:
    def test_add_log(self, seeded_db):
        db_path, task_id = seeded_db
        r = run_api("log", task_id, "Did some work", db_path=db_path)
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert data["content"] == "Did some work"
        assert data["source"] == "user"

    def test_log_nonexistent(self, db_path):
        r = run_api("log", "nonexistent", "msg", db_path=db_path)
        assert r.returncode == 1


class TestApiArchive:
    def test_archive(self, seeded_db):
        db_path, task_id = seeded_db
        r = run_api("archive", task_id, "--reason", "done with it", db_path=db_path)
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert data["archived"] is True

    def test_archive_no_reason_fails(self, seeded_db):
        db_path, task_id = seeded_db
        r = run_api("archive", task_id, db_path=db_path)
        assert r.returncode != 0


class TestApiUnarchive:
    def test_unarchive(self, seeded_db):
        db_path, task_id = seeded_db
        run_api("archive", task_id, "--reason", "temp", db_path=db_path)
        r = run_api("unarchive", task_id, db_path=db_path)
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert data["archived"] is False


class TestOutputContract:
    def test_stdout_is_valid_json(self, seeded_db):
        db_path, task_id = seeded_db
        for cmd in [
            ["list"],
            ["show", task_id],
        ]:
            r = run_api(*cmd, db_path=db_path)
            json.loads(r.stdout)  # Should not raise

    def test_errors_on_stderr(self, db_path):
        r = run_api("show", "nonexistent", db_path=db_path)
        assert r.stderr.strip()
        assert r.stdout.strip() == ""
