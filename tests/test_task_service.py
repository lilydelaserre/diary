import re
from datetime import date, datetime
import pytest
from diary.models import CreateTaskRequest, UpdateTaskRequest, TaskListFilters


ISO_DATETIME_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


# ── create_task ──────────────────────────────────────────────────────────────


class TestCreateTaskDefaults:
    def test_title_only(self, task_service):
        task = task_service.create_task(CreateTaskRequest(title="Test task"))
        assert task.title == "Test task"
        assert task.done is False
        assert task.priority == "medium"
        assert task.scheduled_date is None
        assert task.due_date is None
        assert task.description is None
        assert task.archived is False
        assert task.archive_reason is None
        assert task.tags == []
        assert UUID_RE.match(task.id)
        assert ISO_DATETIME_RE.match(task.created_at)
        assert ISO_DATETIME_RE.match(task.updated_at)

    def test_all_fields(self, task_service):
        task = task_service.create_task(CreateTaskRequest(
            title="Full task",
            description="A description",
            priority="high",
            due_date="2026-03-15",
            scheduled_date="2026-03-01",
            tags=["backend", "auth"],
        ))
        assert task.title == "Full task"
        assert task.description == "A description"
        assert task.priority == "high"
        assert task.due_date == "2026-03-15"
        assert task.scheduled_date == "2026-03-01"
        assert sorted(task.tags) == ["auth", "backend"]


class TestCreateTaskTags:
    def test_reuses_existing_tags(self, task_service):
        task_service.create_task(CreateTaskRequest(title="T1", tags=["backend"]))
        task_service.create_task(CreateTaskRequest(title="T2", tags=["backend", "auth"]))
        # Only 2 unique tags should exist
        rows = task_service.conn.execute("SELECT COUNT(*) FROM tags").fetchone()[0]
        assert rows == 2

    def test_empty_tags(self, task_service):
        task = task_service.create_task(CreateTaskRequest(title="No tags", tags=[]))
        assert task.tags == []

    def test_duplicate_tags_in_request(self, task_service):
        task = task_service.create_task(CreateTaskRequest(title="Dupes", tags=["backend", "backend"]))
        assert task.tags == ["backend"]


class TestCreateTaskSystemLog:
    def test_system_log_created(self, task_service):
        task = task_service.create_task(CreateTaskRequest(title="Logged"))
        assert task.activity_log is not None
        assert len(task.activity_log) == 1
        entry = task.activity_log[0]
        assert entry.source == "system"
        assert "created" in entry.content.lower()
        assert entry.task_id == task.id


# ── get_task ─────────────────────────────────────────────────────────────────


class TestGetTask:
    def test_existing_task(self, task_service):
        created = task_service.create_task(CreateTaskRequest(title="Get me", tags=["test"]))
        fetched = task_service.get_task(created.id)
        assert fetched.id == created.id
        assert fetched.title == "Get me"
        assert fetched.tags == ["test"]
        assert fetched.activity_log is not None
        assert len(fetched.activity_log) >= 1

    def test_activity_log_ordered_by_timestamp(self, task_service, db):
        created = task_service.create_task(CreateTaskRequest(title="Ordered"))
        # Insert additional log entries with different timestamps
        db.execute(
            "INSERT INTO activity_log (id, task_id, timestamp, source, content) VALUES (?, ?, ?, ?, ?)",
            ("log-early", created.id, "2026-01-01T08:00:00", "user", "Early entry"),
        )
        db.execute(
            "INSERT INTO activity_log (id, task_id, timestamp, source, content) VALUES (?, ?, ?, ?, ?)",
            ("log-late", created.id, "2026-12-31T23:00:00", "user", "Late entry"),
        )
        db.commit()
        fetched = task_service.get_task(created.id)
        timestamps = [e.timestamp for e in fetched.activity_log]
        assert timestamps == sorted(timestamps)

    def test_nonexistent_task(self, task_service):
        with pytest.raises(ValueError):
            task_service.get_task("nonexistent-id")

    def test_task_with_no_tags(self, task_service):
        created = task_service.create_task(CreateTaskRequest(title="No tags"))
        fetched = task_service.get_task(created.id)
        assert fetched.tags == []

    def test_task_with_no_extra_log(self, task_service):
        created = task_service.create_task(CreateTaskRequest(title="Minimal"))
        fetched = task_service.get_task(created.id)
        # Only the "Task created" system entry
        assert len(fetched.activity_log) == 1


# ── list_tasks ───────────────────────────────────────────────────────────────


@pytest.fixture
def seeded_tasks(task_service):
    """Seed a variety of tasks for list/filter tests."""
    today = date.today().isoformat()
    tasks = {}
    tasks["today_high"] = task_service.create_task(CreateTaskRequest(
        title="Today high", priority="high", scheduled_date=today, tags=["backend"],
    ))
    tasks["today_med"] = task_service.create_task(CreateTaskRequest(
        title="Today medium", priority="medium", scheduled_date=today, tags=["frontend"],
    ))
    tasks["today_low"] = task_service.create_task(CreateTaskRequest(
        title="Today low", priority="low", scheduled_date=today,
    ))
    tasks["backlog_high"] = task_service.create_task(CreateTaskRequest(
        title="Backlog high", priority="high", tags=["backend"],
    ))
    tasks["backlog_med"] = task_service.create_task(CreateTaskRequest(
        title="Backlog medium", priority="medium",
    ))
    tasks["future"] = task_service.create_task(CreateTaskRequest(
        title="Future task", scheduled_date="2026-12-25",
    ))
    # A done task
    done = task_service.create_task(CreateTaskRequest(
        title="Done task", scheduled_date=today,
    ))
    task_service.update_task(done.id, UpdateTaskRequest(done=True))
    tasks["done"] = task_service.get_task(done.id)
    # An archived task
    archived = task_service.create_task(CreateTaskRequest(title="Archived task"))
    task_service.archive_task(archived.id, "no longer needed")
    tasks["archived"] = task_service.get_task(archived.id)
    # A task with searchable description
    tasks["searchable"] = task_service.create_task(CreateTaskRequest(
        title="Login bug", description="Fix the token refresh on login page",
    ))
    return tasks


class TestListTasksFilters:
    @pytest.mark.parametrize(
        "filters,expected_titles",
        [
            # scheduled=today
            (
                {"scheduled": "today"},
                {"Today high", "Today medium", "Today low", "Done task"},
            ),
            # scheduled=none (backlog)
            (
                {"scheduled": "none"},
                {"Backlog high", "Backlog medium", "Login bug"},
            ),
            # scheduled=specific date
            (
                {"scheduled": "2026-12-25"},
                {"Future task"},
            ),
            # status filters
            (
                {"done": False},
                {"Today high", "Today medium", "Today low", "Backlog high", "Backlog medium", "Future task", "Login bug"},
            ),
            (
                {"done": True},
                {"Done task"},
            ),
            # priority filter
            (
                {"priority": "high"},
                {"Today high", "Backlog high"},
            ),
            # tag filter
            (
                {"tag": "backend"},
                {"Today high", "Backlog high"},
            ),
            (
                {"tag": "frontend"},
                {"Today medium"},
            ),
        ],
    )
    def test_individual_filter(self, task_service, seeded_tasks, filters, expected_titles):
        if "scheduled" in filters and filters["scheduled"] == "today":
            filters["scheduled"] = date.today().isoformat()
        result = task_service.list_tasks(TaskListFilters(**filters))
        titles = {t.title for t in result}
        assert titles == expected_titles

    def test_archived_excluded_by_default(self, task_service, seeded_tasks):
        result = task_service.list_tasks(TaskListFilters())
        titles = {t.title for t in result}
        assert "Archived task" not in titles

    def test_archived_included_with_flag(self, task_service, seeded_tasks):
        result = task_service.list_tasks(TaskListFilters(archived=True))
        titles = {t.title for t in result}
        assert "Archived task" in titles

    def test_fts_search(self, task_service, seeded_tasks):
        result = task_service.list_tasks(TaskListFilters(search="login"))
        titles = {t.title for t in result}
        assert "Login bug" in titles

    def test_fts_search_description(self, task_service, seeded_tasks):
        result = task_service.list_tasks(TaskListFilters(search="token refresh"))
        titles = {t.title for t in result}
        assert "Login bug" in titles


class TestListTasksCombinedFilters:
    def test_scheduled_today_and_high_priority(self, task_service, seeded_tasks):
        today = date.today().isoformat()
        result = task_service.list_tasks(TaskListFilters(scheduled=today, priority="high"))
        titles = {t.title for t in result}
        assert titles == {"Today high"}

    def test_status_todo_and_tag(self, task_service, seeded_tasks):
        result = task_service.list_tasks(TaskListFilters(done=False, tag="backend"))
        titles = {t.title for t in result}
        assert titles == {"Today high", "Backlog high"}


class TestListTasksSorting:
    def test_sorted_by_priority(self, task_service, seeded_tasks):
        today = date.today().isoformat()
        result = task_service.list_tasks(TaskListFilters(scheduled=today, done=False))
        priorities = [t.priority for t in result]
        priority_order = {"high": 1, "medium": 2, "low": 3}
        numeric = [priority_order[p] for p in priorities]
        assert numeric == sorted(numeric)


class TestListTasksVerbose:
    def test_non_verbose_no_activity_log(self, task_service, seeded_tasks):
        result = task_service.list_tasks(TaskListFilters())
        for t in result:
            assert t.activity_log is None

    def test_verbose_has_activity_log(self, task_service, seeded_tasks):
        result = task_service.list_tasks(TaskListFilters(verbose=True))
        for t in result:
            assert t.activity_log is not None


# ── update_task ──────────────────────────────────────────────────────────────


class TestUpdateTaskFields:
    @pytest.mark.parametrize(
        "field,old_value,new_value,log_fragment",
        [
            ("done", None, True, "Marked as done"),
            ("priority", None, "high", "Priority changed from medium to high"),
            ("title", None, "New title", "Title changed"),
            ("description", None, "New desc", "Description updated"),
            ("due_date", None, "2026-06-01", "Due date set to 2026-06-01"),
        ],
    )
    def test_field_update_with_system_log(self, task_service, field, old_value, new_value, log_fragment):
        task = task_service.create_task(CreateTaskRequest(title="Update me"))
        updated = task_service.update_task(task.id, UpdateTaskRequest(**{field: new_value}))
        assert getattr(updated, field) == new_value
        # Check system log
        log_contents = [e.content for e in updated.activity_log if e.source == "system"]
        assert any(log_fragment in c for c in log_contents), f"Expected '{log_fragment}' in {log_contents}"

    def test_scheduled_date_set(self, task_service):
        task = task_service.create_task(CreateTaskRequest(title="Schedule me"))
        updated = task_service.update_task(task.id, UpdateTaskRequest(scheduled_date="2026-03-05"))
        assert updated.scheduled_date == "2026-03-05"
        log_contents = [e.content for e in updated.activity_log if e.source == "system"]
        assert any("Scheduled for 2026-03-05" in c for c in log_contents)

    def test_scheduled_date_cleared(self, task_service):
        task = task_service.create_task(CreateTaskRequest(title="Unschedule", scheduled_date="2026-03-05"))
        # Use a sentinel to distinguish "set to None" from "not provided"
        updated = task_service.update_task(task.id, UpdateTaskRequest(scheduled_date="none"))
        assert updated.scheduled_date is None
        log_contents = [e.content for e in updated.activity_log if e.source == "system"]
        assert any("Moved to backlog" in c for c in log_contents)

    def test_due_date_cleared(self, task_service):
        task = task_service.create_task(CreateTaskRequest(title="Clear due", due_date="2026-03-15"))
        updated = task_service.update_task(task.id, UpdateTaskRequest(due_date="none"))
        assert updated.due_date is None
        log_contents = [e.content for e in updated.activity_log if e.source == "system"]
        assert any("Due date cleared" in c for c in log_contents)

    def test_tags_update(self, task_service):
        task = task_service.create_task(CreateTaskRequest(title="Tag me", tags=["backend"]))
        updated = task_service.update_task(task.id, UpdateTaskRequest(tags=["backend", "auth"]))
        assert sorted(updated.tags) == ["auth", "backend"]
        log_contents = [e.content for e in updated.activity_log if e.source == "system"]
        assert any("Tags changed" in c for c in log_contents)


class TestUpdateTaskEdgeCases:
    def test_no_changes_no_log(self, task_service):
        task = task_service.create_task(CreateTaskRequest(title="Same"))
        initial_log_count = len(task.activity_log)
        updated = task_service.update_task(task.id, UpdateTaskRequest(title="Same"))
        system_logs_after = [e for e in updated.activity_log if e.source == "system"]
        # Only the "Task created" entry, no new ones
        assert len(system_logs_after) == initial_log_count

    def test_multiple_fields_multiple_logs(self, task_service):
        task = task_service.create_task(CreateTaskRequest(title="Multi"))
        updated = task_service.update_task(task.id, UpdateTaskRequest(
            done=True, priority="high",
        ))
        system_logs = [e for e in updated.activity_log if e.source == "system" and "created" not in e.content.lower()]
        assert len(system_logs) == 2

    def test_nonexistent_task(self, task_service):
        with pytest.raises(ValueError):
            task_service.update_task("nonexistent", UpdateTaskRequest(title="Nope"))

    def test_updated_at_changes(self, task_service):
        task = task_service.create_task(CreateTaskRequest(title="Timestamp"))
        old_updated = task.updated_at
        updated = task_service.update_task(task.id, UpdateTaskRequest(priority="high"))
        assert updated.updated_at >= old_updated


# ── archive_task ─────────────────────────────────────────────────────────────


class TestArchiveTask:
    def test_archive_with_reason(self, task_service):
        task = task_service.create_task(CreateTaskRequest(title="Archive me"))
        archived = task_service.archive_task(task.id, "no longer needed")
        assert archived.archived is True
        assert archived.archive_reason == "no longer needed"
        log_contents = [e.content for e in archived.activity_log if e.source == "system"]
        assert any("archived" in c.lower() for c in log_contents)

    def test_archive_without_reason(self, task_service):
        task = task_service.create_task(CreateTaskRequest(title="No reason"))
        with pytest.raises(ValueError):
            task_service.archive_task(task.id, "")

    def test_archive_nonexistent(self, task_service):
        with pytest.raises(ValueError):
            task_service.archive_task("nonexistent", "reason")

    def test_archive_already_archived(self, task_service):
        task = task_service.create_task(CreateTaskRequest(title="Double archive"))
        task_service.archive_task(task.id, "first time")
        with pytest.raises(ValueError):
            task_service.archive_task(task.id, "second time")


# ── unarchive_task ───────────────────────────────────────────────────────────


class TestUnarchiveTask:
    def test_unarchive(self, task_service):
        task = task_service.create_task(CreateTaskRequest(title="Unarchive me"))
        task_service.archive_task(task.id, "temp")
        unarchived = task_service.unarchive_task(task.id)
        assert unarchived.archived is False
        assert unarchived.archive_reason is None
        assert unarchived.scheduled_date is None  # back to backlog
        log_contents = [e.content for e in unarchived.activity_log if e.source == "system"]
        assert any("unarchived" in c.lower() for c in log_contents)

    def test_unarchive_non_archived(self, task_service):
        task = task_service.create_task(CreateTaskRequest(title="Not archived"))
        with pytest.raises(ValueError):
            task_service.unarchive_task(task.id)

    def test_unarchive_nonexistent(self, task_service):
        with pytest.raises(ValueError):
            task_service.unarchive_task("nonexistent")
