"""Tests for agent tool functions.

Each tool should call the correct service method and return the expected result.
No delete_entry or edit_entry tools should exist.
"""
import pytest
from datetime import date
from diary.db import init_db
from diary.models import CreateTaskRequest
from diary.service.tasks import TaskService
from diary.service.activity_log import ActivityLogService
from diary.service.tags import TagService
from diary.service.summary import SummaryService
from diary.agent.tools import make_tools


@pytest.fixture
def services(db):
    """Create all service instances from a shared DB connection."""
    return {
        "task": TaskService(db),
        "log": ActivityLogService(db),
        "tag": TagService(db),
        "summary": SummaryService(db),
    }


@pytest.fixture
def tools(services):
    """Create the tool functions dict."""
    return make_tools(
        services["task"], services["log"], services["tag"], services["summary"]
    )


@pytest.fixture
def sample_task(services):
    """Create a sample task and return it."""
    return services["task"].create_task(
        CreateTaskRequest(title="Test task", priority="high", tags=["backend"])
    )


class TestToolExists:
    """Verify the expected set of tools is returned."""

    EXPECTED = [
        "list_tasks", "show_task", "create_task", "update_task",
        "add_log_entry", "archive_task", "unarchive_task",
        "list_tags", "get_summary",
    ]

    @pytest.mark.parametrize("name", EXPECTED)
    def test_tool_exists(self, tools, name):
        assert name in tools

    def test_no_delete_entry_tool(self, tools):
        assert "delete_entry" not in tools
        assert "delete_log_entry" not in tools

    def test_no_edit_entry_tool(self, tools):
        assert "edit_entry" not in tools
        assert "edit_log_entry" not in tools

    def test_tool_count(self, tools):
        assert len(tools) == len(self.EXPECTED)


class TestListTasks:
    def test_returns_tasks(self, tools, sample_task):
        result = tools["list_tasks"]()
        assert isinstance(result, list)
        assert len(result) >= 1
        assert any(t["title"] == "Test task" for t in result)

    def test_with_filters(self, tools, sample_task):
        result = tools["list_tasks"](priority="high")
        assert len(result) >= 1
        result_none = tools["list_tasks"](priority="low")
        assert not any(t["title"] == "Test task" for t in result_none)


class TestShowTask:
    def test_returns_task_with_log(self, tools, sample_task):
        result = tools["show_task"](task_id=sample_task.id)
        assert result["title"] == "Test task"
        assert "activity_log" in result

    def test_invalid_id(self, tools):
        with pytest.raises(ValueError):
            tools["show_task"](task_id="nonexistent")


class TestCreateTask:
    def test_creates_task(self, tools):
        result = tools["create_task"](title="New task")
        assert result["title"] == "New task"
        assert result["status"] == "todo"
        assert result["priority"] == "medium"

    def test_with_all_fields(self, tools):
        result = tools["create_task"](
            title="Full task",
            description="desc",
            priority="high",
            tags=["a", "b"],
            due_date="2026-04-01",
            scheduled_date="2026-03-02",
        )
        assert result["title"] == "Full task"
        assert result["priority"] == "high"
        assert set(result["tags"]) == {"a", "b"}


class TestUpdateTask:
    def test_updates_done(self, tools, sample_task):
        result = tools["update_task"](task_id=sample_task.id, done=True)
        assert result["done"] is True

    def test_updates_priority(self, tools, sample_task):
        result = tools["update_task"](task_id=sample_task.id, priority="low")
        assert result["priority"] == "low"


class TestAddLogEntry:
    def test_adds_entry_with_ai_source(self, tools, sample_task):
        result = tools["add_log_entry"](task_id=sample_task.id, content="AI note")
        assert result["source"] == "ai"
        assert result["content"] == "AI note"


class TestArchiveTask:
    def test_archives(self, tools, sample_task):
        result = tools["archive_task"](task_id=sample_task.id, reason="Done with it")
        assert result["archived"] is True


class TestUnarchiveTask:
    def test_unarchives(self, tools, sample_task, services):
        services["task"].archive_task(sample_task.id, "temp")
        result = tools["unarchive_task"](task_id=sample_task.id)
        assert result["archived"] is False


class TestListTags:
    def test_returns_tags(self, tools, sample_task):
        result = tools["list_tags"]()
        assert isinstance(result, list)
        assert "backend" in result


class TestGetSummary:
    def test_returns_summary(self, tools, sample_task):
        today = date.today().isoformat()
        result = tools["get_summary"](from_date=today, to_date=today)
        assert "tasks_active" in result
        assert "tasks_completed" in result
