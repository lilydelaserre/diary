import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    description TEXT,
    done        INTEGER NOT NULL DEFAULT 0,
    priority    TEXT NOT NULL DEFAULT 'medium'
                CHECK (priority IN ('high', 'medium', 'low')),
    due_date    TEXT,
    scheduled_date TEXT,
    archived    INTEGER NOT NULL DEFAULT 0,
    archive_reason TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tags (
    id   TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS task_tags (
    task_id TEXT NOT NULL REFERENCES tasks(id),
    tag_id  TEXT NOT NULL REFERENCES tags(id),
    PRIMARY KEY (task_id, tag_id)
);

CREATE TABLE IF NOT EXISTS activity_log (
    id        TEXT PRIMARY KEY,
    task_id   TEXT NOT NULL REFERENCES tasks(id),
    timestamp TEXT NOT NULL,
    source    TEXT NOT NULL CHECK (source IN ('user', 'ai', 'system')),
    content   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_activity_log_task_id ON activity_log(task_id);
CREATE INDEX IF NOT EXISTS idx_activity_log_timestamp ON activity_log(timestamp);

CREATE VIRTUAL TABLE IF NOT EXISTS tasks_fts USING fts5(
    title,
    description,
    content='tasks',
    content_rowid='rowid'
);

CREATE TABLE IF NOT EXISTS notification_state (
    date          TEXT PRIMARY KEY,
    morning_sent  INTEGER NOT NULL DEFAULT 0,
    evening_sent  INTEGER NOT NULL DEFAULT 0
);
"""

FTS_TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS tasks_fts_insert AFTER INSERT ON tasks BEGIN
    INSERT INTO tasks_fts(rowid, title, description)
    VALUES (new.rowid, new.title, new.description);
END;

CREATE TRIGGER IF NOT EXISTS tasks_fts_update AFTER UPDATE ON tasks BEGIN
    INSERT INTO tasks_fts(tasks_fts, rowid, title, description)
    VALUES ('delete', old.rowid, old.title, old.description);
    INSERT INTO tasks_fts(rowid, title, description)
    VALUES (new.rowid, new.title, new.description);
END;

CREATE TRIGGER IF NOT EXISTS tasks_fts_delete AFTER DELETE ON tasks BEGIN
    INSERT INTO tasks_fts(tasks_fts, rowid, title, description)
    VALUES ('delete', old.rowid, old.title, old.description);
END;
"""


def get_connection(db_path: str) -> sqlite3.Connection:
    """Create a SQLite connection with WAL mode and foreign keys enabled."""
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Create all tables, indexes, FTS virtual table, and triggers."""
    conn.executescript(SCHEMA)
    conn.executescript(FTS_TRIGGERS)
