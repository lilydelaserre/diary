import pytest
from diary.models import CreateTaskRequest


@pytest.fixture
def task_with_logs(task_service, log_service):
    """Create a task and return it for log tests."""
    return task_service.create_task(CreateTaskRequest(title="Log test task"))


class TestAddEntry:
    @pytest.mark.parametrize("source", ["user", "ai", "system"])
    def test_add_entry_by_source(self, log_service, task_with_logs, source):
        entry = log_service.add_entry(task_with_logs.id, source, f"Entry from {source}")
        assert entry.task_id == task_with_logs.id
        assert entry.source == source
        assert entry.content == f"Entry from {source}"
        assert entry.id is not None
        assert entry.timestamp is not None

    def test_add_entry_nonexistent_task(self, log_service):
        with pytest.raises(ValueError):
            log_service.add_entry("nonexistent", "user", "test")


class TestEditEntry:
    def test_edit_content(self, log_service, task_with_logs):
        entry = log_service.add_entry(task_with_logs.id, "user", "Original")
        edited = log_service.edit_entry(entry.id, "Updated content")
        assert edited.content == "Updated content"
        assert edited.timestamp == entry.timestamp
        assert edited.source == entry.source

    def test_edit_nonexistent(self, log_service):
        with pytest.raises(ValueError):
            log_service.edit_entry("nonexistent", "new content")


class TestDeleteEntry:
    def test_delete_entry(self, log_service, task_with_logs):
        entry = log_service.add_entry(task_with_logs.id, "user", "Delete me")
        log_service.delete_entry(entry.id)
        entries = log_service.list_entries(task_with_logs.id)
        assert all(e.id != entry.id for e in entries)

    def test_delete_nonexistent(self, log_service):
        with pytest.raises(ValueError):
            log_service.delete_entry("nonexistent")


class TestListEntries:
    def test_ordered_by_timestamp(self, log_service, task_with_logs, db):
        # Insert with explicit timestamps to control order
        db.execute(
            "INSERT INTO activity_log (id, task_id, timestamp, source, content) VALUES (?, ?, ?, ?, ?)",
            ("e1", task_with_logs.id, "2026-01-01T08:00:00", "user", "First"),
        )
        db.execute(
            "INSERT INTO activity_log (id, task_id, timestamp, source, content) VALUES (?, ?, ?, ?, ?)",
            ("e3", task_with_logs.id, "2026-01-03T08:00:00", "user", "Third"),
        )
        db.execute(
            "INSERT INTO activity_log (id, task_id, timestamp, source, content) VALUES (?, ?, ?, ?, ?)",
            ("e2", task_with_logs.id, "2026-01-02T08:00:00", "user", "Second"),
        )
        db.commit()
        entries = log_service.list_entries(task_with_logs.id)
        contents = [e.content for e in entries]
        # The "Task created" system entry comes first (from create_task), then our entries
        assert "First" in contents
        assert contents.index("First") < contents.index("Second") < contents.index("Third")

    def test_empty_list(self, log_service, db):
        # Create a task with no extra logs (only system "Task created")
        db.execute(
            "INSERT INTO tasks (id, title, done, priority, created_at, updated_at) "
            "VALUES ('bare', 'Bare task', 0, 'medium', '2026-01-01T00:00:00', '2026-01-01T00:00:00')"
        )
        db.commit()
        entries = log_service.list_entries("bare")
        assert entries == []

    def test_nonexistent_task(self, log_service):
        with pytest.raises(ValueError):
            log_service.list_entries("nonexistent")
