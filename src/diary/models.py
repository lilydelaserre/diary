from datetime import date
from typing import Literal
from pydantic import BaseModel, computed_field


class ActivityLogEntry(BaseModel):
    id: str
    task_id: str
    timestamp: str
    source: Literal["user", "ai", "system"]
    content: str


class Tag(BaseModel):
    id: str
    name: str


class Task(BaseModel):
    id: str
    title: str
    description: str | None = None
    done: bool = False
    priority: Literal["high", "medium", "low"] = "medium"
    tags: list[str] = []
    due_date: str | None = None
    scheduled_date: str | None = None
    archived: bool = False
    archive_reason: str | None = None
    created_at: str
    updated_at: str
    activity_log: list[ActivityLogEntry] | None = None

    @computed_field
    @property
    def status(self) -> str:
        """Derived status: done > in-progress (scheduled <= today) > todo."""
        if self.done:
            return "done"
        if self.scheduled_date and self.scheduled_date <= date.today().isoformat():
            return "in-progress"
        return "todo"


class CreateTaskRequest(BaseModel):
    title: str
    description: str | None = None
    priority: Literal["high", "medium", "low"] = "medium"
    tags: list[str] | None = None
    due_date: str | None = None
    scheduled_date: str | None = None


class UpdateTaskRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    done: bool | None = None
    priority: Literal["high", "medium", "low"] | None = None
    tags: list[str] | None = None
    due_date: str | None = None
    scheduled_date: str | None = None


class TaskListFilters(BaseModel):
    scheduled: str | None = None
    done: bool | None = None
    priority: str | None = None
    tag: str | None = None
    search: str | None = None
    from_date: str | None = None
    to_date: str | None = None
    archived: bool = False
    verbose: bool = False
