"""Agent tool functions wrapping the service layer.

Each tool is a plain function decorated with @tool from strands.
make_tools() returns a dict of {name: tool_fn} bound to service instances.
"""
from strands.tools import tool
from diary.models import CreateTaskRequest, UpdateTaskRequest, TaskListFilters
from diary.service.tasks import TaskService
from diary.service.activity_log import ActivityLogService
from diary.service.tags import TagService
from diary.service.summary import SummaryService


def make_tools(
    task_svc: TaskService,
    log_svc: ActivityLogService,
    tag_svc: TagService,
    summary_svc: SummaryService,
) -> dict:
    """Create tool functions bound to the given service instances. Returns {name: tool_fn}."""

    @tool
    def list_tasks(
        scheduled: str | None = None,
        status: str | None = None,
        priority: str | None = None,
        tag: str | None = None,
        search: str | None = None,
        archived: bool = False,
    ) -> list[dict]:
        """List tasks with optional filters. Returns a list of task summaries."""
        filters = TaskListFilters(
            scheduled=scheduled, status=status, priority=priority,
            tag=tag, search=search, archived=archived,
        )
        tasks = task_svc.list_tasks(filters)
        return [t.model_dump(exclude_none=True) for t in tasks]

    @tool
    def show_task(task_id: str) -> dict:
        """Show full detail of a single task including its activity log."""
        return task_svc.get_task(task_id).model_dump(exclude_none=True)

    @tool
    def create_task(
        title: str,
        description: str | None = None,
        priority: str = "medium",
        tags: list[str] | None = None,
        due_date: str | None = None,
        scheduled_date: str | None = None,
    ) -> dict:
        """Create a new task. Returns the created task."""
        req = CreateTaskRequest(
            title=title, description=description, priority=priority,
            tags=tags, due_date=due_date, scheduled_date=scheduled_date,
        )
        return task_svc.create_task(req).model_dump(exclude_none=True)

    @tool
    def update_task(
        task_id: str,
        title: str | None = None,
        description: str | None = None,
        done: bool | None = None,
        priority: str | None = None,
        tags: list[str] | None = None,
        due_date: str | None = None,
        scheduled_date: str | None = None,
    ) -> dict:
        """Update an existing task. Only provided fields are changed. Returns the updated task."""
        req = UpdateTaskRequest(
            title=title, description=description, done=done,
            priority=priority, tags=tags, due_date=due_date,
            scheduled_date=scheduled_date,
        )
        return task_svc.update_task(task_id, req).model_dump(exclude_none=True)

    @tool
    def add_log_entry(task_id: str, content: str) -> dict:
        """Add an activity log entry to a task. Source is always 'ai'."""
        entry = log_svc.add_entry(task_id, "ai", content)
        return entry.model_dump()

    @tool
    def archive_task(task_id: str, reason: str) -> dict:
        """Archive a task with a reason. Returns the archived task."""
        return task_svc.archive_task(task_id, reason).model_dump(exclude_none=True)

    @tool
    def unarchive_task(task_id: str) -> dict:
        """Unarchive a task. It returns to the backlog. Returns the unarchived task."""
        return task_svc.unarchive_task(task_id).model_dump(exclude_none=True)

    @tool
    def list_tags() -> list[str]:
        """List all existing tags in the system, alphabetically."""
        return [t.name for t in tag_svc.list_all_tags()]

    @tool
    def get_summary(from_date: str, to_date: str) -> dict:
        """Get a summary of tasks for a date range (YYYY-MM-DD)."""
        return summary_svc.summarize(from_date, to_date)

    return {
        "list_tasks": list_tasks,
        "show_task": show_task,
        "create_task": create_task,
        "update_task": update_task,
        "add_log_entry": add_log_entry,
        "archive_task": archive_task,
        "unarchive_task": unarchive_task,
        "list_tags": list_tags,
        "get_summary": get_summary,
    }
