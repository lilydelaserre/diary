import sqlite3
import uuid
from datetime import datetime
from diary.models import ActivityLogEntry


class ActivityLogService:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def _task_exists(self, task_id: str) -> bool:
        return self.conn.execute("SELECT 1 FROM tasks WHERE id = ?", (task_id,)).fetchone() is not None

    def add_entry(self, task_id: str, source: str, content: str) -> ActivityLogEntry:
        if not self._task_exists(task_id):
            raise ValueError(f"Task not found: {task_id}")
        entry_id = str(uuid.uuid4())
        now = datetime.now().isoformat(timespec="seconds")
        self.conn.execute(
            "INSERT INTO activity_log (id, task_id, timestamp, source, content) VALUES (?, ?, ?, ?, ?)",
            (entry_id, task_id, now, source, content),
        )
        self.conn.commit()
        return ActivityLogEntry(id=entry_id, task_id=task_id, timestamp=now, source=source, content=content)

    def edit_entry(self, entry_id: str, content: str) -> ActivityLogEntry:
        row = self.conn.execute("SELECT * FROM activity_log WHERE id = ?", (entry_id,)).fetchone()
        if row is None:
            raise ValueError(f"Activity log entry not found: {entry_id}")
        self.conn.execute("UPDATE activity_log SET content = ? WHERE id = ?", (content, entry_id))
        self.conn.commit()
        return ActivityLogEntry(id=row["id"], task_id=row["task_id"], timestamp=row["timestamp"], source=row["source"], content=content)

    def delete_entry(self, entry_id: str) -> None:
        row = self.conn.execute("SELECT 1 FROM activity_log WHERE id = ?", (entry_id,)).fetchone()
        if row is None:
            raise ValueError(f"Activity log entry not found: {entry_id}")
        self.conn.execute("DELETE FROM activity_log WHERE id = ?", (entry_id,))
        self.conn.commit()

    def list_entries(self, task_id: str) -> list[ActivityLogEntry]:
        if not self._task_exists(task_id):
            raise ValueError(f"Task not found: {task_id}")
        rows = self.conn.execute(
            "SELECT * FROM activity_log WHERE task_id = ? ORDER BY timestamp ASC", (task_id,),
        ).fetchall()
        return [
            ActivityLogEntry(id=r["id"], task_id=r["task_id"], timestamp=r["timestamp"], source=r["source"], content=r["content"])
            for r in rows
        ]
