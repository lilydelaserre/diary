"""Tests for Pydantic models."""
import pytest
from datetime import date
from diary.models import Task, ActivityLogEntry, Tag, CreateTaskRequest, UpdateTaskRequest, TaskListFilters


class TestTaskModel:
    def test_minimal_task(self):
        t = Task(id="1", title="Test", created_at="2026-01-01", updated_at="2026-01-01")
        assert t.done is False
        assert t.priority == "medium"
        assert t.status == "todo"
        assert t.tags == []

    def test_done_task_status(self):
        t = Task(id="1", title="Test", done=True, created_at="2026-01-01", updated_at="2026-01-01")
        assert t.status == "done"

    def test_scheduled_past_status(self):
        t = Task(id="1", title="Test", scheduled_date="2020-01-01",
                 created_at="2026-01-01", updated_at="2026-01-01")
        assert t.status == "in-progress"

    def test_scheduled_future_status(self):
        t = Task(id="1", title="Test", scheduled_date="2099-01-01",
                 created_at="2026-01-01", updated_at="2026-01-01")
        assert t.status == "todo"

    def test_scheduled_today_status(self):
        t = Task(id="1", title="Test", scheduled_date=date.today().isoformat(),
                 created_at="2026-01-01", updated_at="2026-01-01")
        assert t.status == "in-progress"

    def test_done_overrides_scheduled(self):
        t = Task(id="1", title="Test", done=True, scheduled_date="2020-01-01",
                 created_at="2026-01-01", updated_at="2026-01-01")
        assert t.status == "done"

    def test_roundtrip(self):
        t = Task(id="1", title="Test", priority="high", tags=["a"],
                 created_at="2026-01-01", updated_at="2026-01-01")
        d = t.model_dump()
        t2 = Task(**{k: v for k, v in d.items() if k != "status"})
        assert t2.title == t.title
        assert t2.priority == t.priority


class TestActivityLogEntry:
    @pytest.mark.parametrize("source", ["user", "ai", "system"])
    def test_valid_source(self, source):
        e = ActivityLogEntry(id="1", task_id="t1", timestamp="2026-01-01", source=source, content="test")
        assert e.source == source


class TestCreateTaskRequest:
    def test_defaults(self):
        r = CreateTaskRequest(title="Test")
        assert r.priority == "medium"
        assert r.tags is None

    def test_all_fields(self):
        r = CreateTaskRequest(title="T", description="D", priority="high",
                              tags=["a"], due_date="2026-01-01", scheduled_date="2026-01-01")
        assert r.title == "T"


class TestUpdateTaskRequest:
    def test_all_none_by_default(self):
        r = UpdateTaskRequest()
        assert r.title is None
        assert r.done is None
        assert r.priority is None

    @pytest.mark.parametrize("field,value", [
        ("title", "New"),
        ("done", True),
        ("priority", "high"),
        ("tags", ["a"]),
    ])
    def test_individual_field_set(self, field, value):
        r = UpdateTaskRequest(**{field: value})
        assert getattr(r, field) == value


class TestTaskListFilters:
    def test_defaults(self):
        f = TaskListFilters()
        assert f.done is None
        assert f.archived is False
        assert f.verbose is False
