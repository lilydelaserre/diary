import sqlite3


class SummaryService:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def summarize(self, from_date: str, to_date: str) -> dict:
        # Tasks active (scheduled) in the date range
        active_rows = self.conn.execute(
            "SELECT id, title, done, priority, scheduled_date FROM tasks "
            "WHERE scheduled_date >= ? AND scheduled_date <= ? AND archived = 0",
            (from_date, to_date),
        ).fetchall()

        # Tasks completed in the range (have a "Status changed from * to done" log entry in range)
        completed_count = self.conn.execute(
            "SELECT COUNT(DISTINCT al.task_id) FROM activity_log al "
            "JOIN tasks t ON al.task_id = t.id "
            "WHERE al.source = 'system' AND al.content LIKE '%done%' "
            "AND al.timestamp >= ? AND al.timestamp <= ?",
            (from_date + "T00:00:00", to_date + "T23:59:59"),
        ).fetchone()[0]

        return {
            "tasks_active": len(active_rows),
            "tasks_completed": completed_count,
            "active_tasks": [
                {"id": r["id"], "title": r["title"], "done": bool(r["done"]),
                 "priority": r["priority"], "scheduled_date": r["scheduled_date"]}
                for r in active_rows
            ],
        }
