import sqlite3
import uuid
from datetime import date, datetime
from diary.models import Task, ActivityLogEntry, CreateTaskRequest, UpdateTaskRequest, TaskListFilters

PRIORITY_ORDER = {"high": 1, "medium": 2, "low": 3}


class TaskService:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create_task(self, request: CreateTaskRequest) -> Task:
        task_id = str(uuid.uuid4())
        now = datetime.now().isoformat(timespec="seconds")
        self.conn.execute(
            "INSERT INTO tasks (id, title, description, done, priority, due_date, scheduled_date, archived, created_at, updated_at) "
            "VALUES (?, ?, ?, 0, ?, ?, ?, 0, ?, ?)",
            (task_id, request.title, request.description, request.priority,
             request.due_date, request.scheduled_date, now, now),
        )
        if request.tags:
            self._set_tags(task_id, request.tags)
        self._add_system_log(task_id, "Task created")
        if request.scheduled_date:
            self._add_system_log(task_id, f"Scheduled for {request.scheduled_date}")
        self.conn.commit()
        return self.get_task(task_id)

    def get_task(self, task_id: str) -> Task:
        row = self.conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise ValueError(f"Task not found: {task_id}")
        tags = [r["name"] for r in self.conn.execute(
            "SELECT t.name FROM tags t JOIN task_tags tt ON t.id = tt.tag_id WHERE tt.task_id = ? ORDER BY t.name",
            (task_id,),
        )]
        log_entries = [
            ActivityLogEntry(id=r["id"], task_id=r["task_id"], timestamp=r["timestamp"], source=r["source"], content=r["content"])
            for r in self.conn.execute(
                "SELECT * FROM activity_log WHERE task_id = ? ORDER BY timestamp ASC", (task_id,),
            )
        ]
        return Task(
            id=row["id"], title=row["title"], description=row["description"],
            done=bool(row["done"]), priority=row["priority"], tags=tags,
            due_date=row["due_date"], scheduled_date=row["scheduled_date"],
            archived=bool(row["archived"]), archive_reason=row["archive_reason"],
            created_at=row["created_at"], updated_at=row["updated_at"],
            activity_log=log_entries,
        )

    def list_tasks(self, filters: TaskListFilters) -> list[Task]:
        conditions = []
        params = []

        if not filters.archived:
            conditions.append("t.archived = 0")

        if filters.scheduled is not None:
            if filters.scheduled == "none":
                conditions.append("t.scheduled_date IS NULL")
            elif filters.scheduled == "today":
                conditions.append("t.scheduled_date = ?")
                params.append(date.today().isoformat())
            else:
                conditions.append("t.scheduled_date = ?")
                params.append(filters.scheduled)

        if filters.done is not None:
            conditions.append("t.done = ?")
            params.append(1 if filters.done else 0)

        if filters.priority is not None:
            conditions.append("t.priority = ?")
            params.append(filters.priority)

        join_clauses = ""
        if filters.tag is not None:
            join_clauses += " JOIN task_tags tt ON t.id = tt.task_id JOIN tags tg ON tt.tag_id = tg.id"
            conditions.append("tg.name = ?")
            params.append(filters.tag)

        if filters.search is not None:
            join_clauses += " JOIN tasks_fts fts ON t.rowid = fts.rowid"
            conditions.append("tasks_fts MATCH ?")
            params.append(filters.search)

        where = " AND ".join(conditions) if conditions else "1=1"
        sql = f"SELECT DISTINCT t.* FROM tasks t{join_clauses} WHERE {where} ORDER BY CASE t.priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 WHEN 'low' THEN 3 END"

        rows = self.conn.execute(sql, params).fetchall()
        tasks = []
        for row in rows:
            tags = [r["name"] for r in self.conn.execute(
                "SELECT tg.name FROM tags tg JOIN task_tags tt ON tg.id = tt.tag_id WHERE tt.task_id = ? ORDER BY tg.name",
                (row["id"],),
            )]
            activity_log = None
            if filters.verbose:
                activity_log = [
                    ActivityLogEntry(id=r["id"], task_id=r["task_id"], timestamp=r["timestamp"], source=r["source"], content=r["content"])
                    for r in self.conn.execute(
                        "SELECT * FROM activity_log WHERE task_id = ? ORDER BY timestamp ASC", (row["id"],),
                    )
                ]
            tasks.append(Task(
                id=row["id"], title=row["title"], description=row["description"],
                done=bool(row["done"]), priority=row["priority"], tags=tags,
                due_date=row["due_date"], scheduled_date=row["scheduled_date"],
                archived=bool(row["archived"]), archive_reason=row["archive_reason"],
                created_at=row["created_at"], updated_at=row["updated_at"],
                activity_log=activity_log,
            ))
        return tasks

    def update_task(self, task_id: str, request: UpdateTaskRequest) -> Task:
        current = self.get_task(task_id)
        now = datetime.now().isoformat(timespec="seconds")
        changes = []

        field_map = {
            "title": ("title", None),
            "description": ("description", None),
            "done": ("done", lambda o, n: "Marked as done" if n else "Reopened"),
            "priority": ("priority", lambda o, n: f"Priority changed from {o} to {n}"),
            "due_date": ("due_date", None),
            "scheduled_date": ("scheduled_date", None),
        }

        for field, (col, log_fn) in field_map.items():
            new_val = getattr(request, field)
            if new_val is None:
                continue

            # Handle "none" sentinel for clearing nullable fields
            if new_val == "none" and field in ("scheduled_date", "due_date"):
                new_val = None

            old_val = getattr(current, field)
            if new_val == old_val:
                continue

            # Convert bool for DB
            db_val = int(new_val) if isinstance(new_val, bool) else new_val
            self.conn.execute(f"UPDATE tasks SET {col} = ? WHERE id = ?", (db_val, task_id))
            changes.append((field, old_val, new_val))

            if log_fn:
                self._add_system_log(task_id, log_fn(old_val, new_val))
            elif field == "title":
                self._add_system_log(task_id, "Title changed")
            elif field == "description":
                self._add_system_log(task_id, "Description updated")
            elif field == "due_date":
                if new_val is None:
                    self._add_system_log(task_id, "Due date cleared")
                else:
                    self._add_system_log(task_id, f"Due date set to {new_val}")
            elif field == "scheduled_date":
                if new_val is None:
                    self._add_system_log(task_id, "Moved to backlog")
                else:
                    self._add_system_log(task_id, f"Scheduled for {new_val}")

        # Handle tags
        if request.tags is not None:
            old_tags = sorted(current.tags)
            new_tags = sorted(set(request.tags))
            if old_tags != new_tags:
                self._set_tags(task_id, request.tags)
                old_str = ", ".join(f"#{t}" for t in old_tags) or "(none)"
                new_str = ", ".join(f"#{t}" for t in new_tags) or "(none)"
                self._add_system_log(task_id, f"Tags changed from {old_str} to {new_str}")
                changes.append(("tags", old_tags, new_tags))

        if changes:
            self.conn.execute("UPDATE tasks SET updated_at = ? WHERE id = ?", (now, task_id))

        self.conn.commit()
        return self.get_task(task_id)

    def archive_task(self, task_id: str, reason: str) -> Task:
        if not reason or not reason.strip():
            raise ValueError("Archive reason is required")
        current = self.get_task(task_id)
        if current.archived:
            raise ValueError(f"Task is already archived: {task_id}")
        now = datetime.now().isoformat(timespec="seconds")
        self.conn.execute(
            "UPDATE tasks SET archived = 1, archive_reason = ?, updated_at = ? WHERE id = ?",
            (reason, now, task_id),
        )
        self._add_system_log(task_id, f"Task archived: {reason}")
        self.conn.commit()
        return self.get_task(task_id)

    def unarchive_task(self, task_id: str) -> Task:
        current = self.get_task(task_id)
        if not current.archived:
            raise ValueError(f"Task is not archived: {task_id}")
        now = datetime.now().isoformat(timespec="seconds")
        self.conn.execute(
            "UPDATE tasks SET archived = 0, archive_reason = NULL, scheduled_date = NULL, updated_at = ? WHERE id = ?",
            (now, task_id),
        )
        self._add_system_log(task_id, "Task unarchived")
        self.conn.commit()
        return self.get_task(task_id)

    def _set_tags(self, task_id: str, tag_names: list[str]) -> None:
        self.conn.execute("DELETE FROM task_tags WHERE task_id = ?", (task_id,))
        for name in set(tag_names):
            tag_id = self.conn.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()
            if tag_id is None:
                new_id = str(uuid.uuid4())
                self.conn.execute("INSERT INTO tags (id, name) VALUES (?, ?)", (new_id, name))
                tag_id_val = new_id
            else:
                tag_id_val = tag_id["id"]
            self.conn.execute("INSERT INTO task_tags (task_id, tag_id) VALUES (?, ?)", (task_id, tag_id_val))

    def _add_system_log(self, task_id: str, content: str) -> None:
        self.conn.execute(
            "INSERT INTO activity_log (id, task_id, timestamp, source, content) VALUES (?, ?, ?, 'system', ?)",
            (str(uuid.uuid4()), task_id, datetime.now().isoformat(timespec="seconds"), content),
        )
