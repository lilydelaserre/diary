"""Notification service — checks state and sends macOS notifications."""
import sqlite3
import subprocess
from datetime import date


MESSAGES = {
    "morning": "Time to check your tasks",
    "evening": "Time to review your tasks",
}


class NotificationService:
    def __init__(self, conn: sqlite3.Connection, terminal_app: str = "Warp"):
        self.conn = conn
        self.terminal_app = terminal_app

    def should_send(self, notify_type: str) -> bool:
        today = date.today().isoformat()
        col = f"{notify_type}_sent"
        row = self.conn.execute("SELECT * FROM notification_state WHERE date = ?", (today,)).fetchone()
        if row is None:
            return True
        return row[col] == 0

    def check_and_send(self, notify_type: str) -> bool:
        """Send notification if not already sent today. Returns True if sent."""
        if not self.should_send(notify_type):
            return False

        msg = MESSAGES[notify_type]
        subprocess.run([
            "terminal-notifier",
            "-title", "Diary",
            "-message", msg,
            "-execute", f"open -a {self.terminal_app}",
        ])

        today = date.today().isoformat()
        col = f"{notify_type}_sent"
        self.conn.execute(
            f"INSERT INTO notification_state (date, {col}) VALUES (?, 1) "
            f"ON CONFLICT(date) DO UPDATE SET {col} = 1",
            (today,),
        )
        self.conn.commit()
        return True
