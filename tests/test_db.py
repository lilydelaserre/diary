import sqlite3
import pytest
from diary.db import init_db, get_connection


class TestInitDbTables:
    @pytest.mark.parametrize(
        "table_name",
        ["tasks", "tags", "task_tags", "activity_log", "notification_state"],
    )
    def test_table_exists(self, db, table_name):
        cursor = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        assert cursor.fetchone() is not None

    def test_fts_virtual_table_exists(self, db):
        cursor = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='tasks_fts'"
        )
        assert cursor.fetchone() is not None


class TestInitDbIndexes:
    @pytest.mark.parametrize(
        "index_name",
        ["idx_activity_log_task_id", "idx_activity_log_timestamp"],
    )
    def test_index_exists(self, db, index_name):
        cursor = db.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
            (index_name,),
        )
        assert cursor.fetchone() is not None


class TestInitDbConstraints:
    def _insert_task(self, db, task_id="t1", **overrides):
        defaults = dict(title="test", done=0, priority="medium",
                        created_at="2026-01-01T00:00:00", updated_at="2026-01-01T00:00:00")
        defaults.update(overrides)
        db.execute(
            "INSERT INTO tasks (id, title, done, priority, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (task_id, defaults["title"], defaults["done"], defaults["priority"],
             defaults["created_at"], defaults["updated_at"]),
        )

    @pytest.mark.parametrize("valid_priority", ["high", "medium", "low"])
    def test_valid_priority_accepted(self, db, valid_priority):
        self._insert_task(db, task_id=f"id-{valid_priority}", priority=valid_priority)

    @pytest.mark.parametrize("invalid_priority", ["urgent", "critical", "", "HIGH"])
    def test_invalid_priority_rejected(self, db, invalid_priority):
        with pytest.raises(sqlite3.IntegrityError):
            self._insert_task(db, task_id=f"id-{invalid_priority}", priority=invalid_priority)

    @pytest.mark.parametrize("valid_done", [0, 1])
    def test_valid_done_accepted(self, db, valid_done):
        self._insert_task(db, task_id=f"id-done-{valid_done}", done=valid_done)

    @pytest.mark.parametrize("valid_source", ["user", "ai", "system"])
    def test_valid_log_source_accepted(self, db, valid_source):
        self._insert_task(db, task_id="task-1")
        db.execute(
            "INSERT INTO activity_log (id, task_id, timestamp, source, content) "
            "VALUES (?, 'task-1', '2026-01-01T00:00:00', ?, 'test')",
            (f"log-{valid_source}", valid_source),
        )

    @pytest.mark.parametrize("invalid_source", ["bot", "admin", "", "USER"])
    def test_invalid_log_source_rejected(self, db, invalid_source):
        self._insert_task(db, task_id="task-src")
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO activity_log (id, task_id, timestamp, source, content) "
                "VALUES (?, 'task-src', '2026-01-01T00:00:00', ?, 'test')",
                (f"log-{invalid_source}", invalid_source),
            )


class TestInitDbFtsTriggers:
    @pytest.mark.parametrize(
        "trigger_name",
        ["tasks_fts_insert", "tasks_fts_update", "tasks_fts_delete"],
    )
    def test_fts_trigger_exists(self, db, trigger_name):
        cursor = db.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger' AND name=?",
            (trigger_name,),
        )
        assert cursor.fetchone() is not None


class TestInitDbIdempotent:
    def test_init_twice_no_error(self, db):
        init_db(db)


class TestGetConnection:
    def test_wal_mode(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        conn = get_connection(db_path)
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"
        conn.close()

    def test_foreign_keys_enabled(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        conn = get_connection(db_path)
        fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk == 1
        conn.close()
