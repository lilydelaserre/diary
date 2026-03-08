import pytest
from diary.models import CreateTaskRequest, UpdateTaskRequest


class TestSummarize:
    def test_range_with_activity(self, summary_service, task_service, db):
        # Create tasks with known dates
        t1 = task_service.create_task(CreateTaskRequest(
            title="Task A", scheduled_date="2026-03-01",
        ))
        t2 = task_service.create_task(CreateTaskRequest(
            title="Task B", scheduled_date="2026-03-02",
        ))
        # Complete task B
        task_service.update_task(t2.id, UpdateTaskRequest(done=True))

        result = summary_service.summarize("2026-03-01", "2026-03-05")
        assert result["tasks_active"] >= 1
        assert result["tasks_completed"] >= 1

    def test_range_with_no_activity(self, summary_service):
        result = summary_service.summarize("2099-01-01", "2099-01-31")
        assert result["tasks_active"] == 0
        assert result["tasks_completed"] == 0

    def test_completed_count(self, summary_service, task_service):
        t1 = task_service.create_task(CreateTaskRequest(title="Done1", scheduled_date="2026-03-01"))
        t2 = task_service.create_task(CreateTaskRequest(title="Done2", scheduled_date="2026-03-01"))
        t3 = task_service.create_task(CreateTaskRequest(title="NotDone", scheduled_date="2026-03-01"))
        task_service.update_task(t1.id, UpdateTaskRequest(done=True))
        task_service.update_task(t2.id, UpdateTaskRequest(done=True))

        result = summary_service.summarize("2026-03-01", "2026-03-31")
        assert result["tasks_completed"] == 2

    def test_active_tasks_in_range(self, summary_service, task_service):
        task_service.create_task(CreateTaskRequest(title="In range", scheduled_date="2026-03-05"))
        task_service.create_task(CreateTaskRequest(title="Out of range", scheduled_date="2026-06-01"))

        result = summary_service.summarize("2026-03-01", "2026-03-31")
        active_titles = [t["title"] for t in result["active_tasks"]]
        assert "In range" in active_titles
        assert "Out of range" not in active_titles
