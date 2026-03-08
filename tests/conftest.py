import sqlite3
import pytest
from diary.db import init_db
from diary.service.tasks import TaskService
from diary.service.activity_log import ActivityLogService
from diary.service.tags import TagService
from diary.service.summary import SummaryService


@pytest.fixture
def db():
    """Provide a fresh in-memory SQLite database with schema initialized."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    init_db(conn)
    yield conn
    conn.close()


@pytest.fixture
def task_service(db):
    return TaskService(db)


@pytest.fixture
def log_service(db):
    return ActivityLogService(db)


@pytest.fixture
def tag_service(db):
    return TagService(db)


@pytest.fixture
def summary_service(db):
    return SummaryService(db)


@pytest.fixture
def tmp_config(tmp_path):
    return tmp_path / "config.toml"
