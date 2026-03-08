import sqlite3
import uuid
from diary.models import Tag


class TagService:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def list_all_tags(self) -> list[Tag]:
        rows = self.conn.execute("SELECT * FROM tags ORDER BY name").fetchall()
        return [Tag(id=r["id"], name=r["name"]) for r in rows]

    def set_task_tags(self, task_id: str, tag_names: list[str]) -> list[Tag]:
        if self.conn.execute("SELECT 1 FROM tasks WHERE id = ?", (task_id,)).fetchone() is None:
            raise ValueError(f"Task not found: {task_id}")

        self.conn.execute("DELETE FROM task_tags WHERE task_id = ?", (task_id,))

        result = []
        for name in sorted(set(tag_names)):
            row = self.conn.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()
            if row is None:
                tag_id = str(uuid.uuid4())
                self.conn.execute("INSERT INTO tags (id, name) VALUES (?, ?)", (tag_id, name))
            else:
                tag_id = row["id"]
            self.conn.execute("INSERT INTO task_tags (task_id, tag_id) VALUES (?, ?)", (task_id, tag_id))
            result.append(Tag(id=tag_id, name=name))

        # Clean up orphaned tags
        self.conn.execute(
            "DELETE FROM tags WHERE id NOT IN (SELECT DISTINCT tag_id FROM task_tags)"
        )
        self.conn.commit()
        return result
