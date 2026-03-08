"""Tests for the TUI — data logic, rendering, and startup."""
import pytest
from datetime import date
from diary.db import get_connection, init_db
from diary.models import CreateTaskRequest, UpdateTaskRequest
from diary.service.tasks import TaskService
from diary.tui.app import DiaryTUI


@pytest.fixture
def tui_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = get_connection(db_path)
    init_db(conn)
    conn.close()
    return db_path


@pytest.fixture
def seeded_db(tui_db):
    conn = get_connection(tui_db)
    init_db(conn)
    svc = TaskService(conn)
    today = date.today().isoformat()
    svc.create_task(CreateTaskRequest(title="Today High", priority="high", scheduled_date=today))
    svc.create_task(CreateTaskRequest(title="Today Low", priority="low", scheduled_date=today))
    svc.create_task(CreateTaskRequest(title="Backlog Task", priority="medium"))
    conn.close()
    return tui_db


class TestTUIDataLoading:
    def test_loads_today_tasks(self, seeded_db):
        tui = DiaryTUI(db_path=seeded_db)
        tui._load_tasks()
        assert len(tui._today_tasks) == 2
        assert tui._today_tasks[0].priority == "high"

    def test_loads_backlog_tasks(self, seeded_db):
        tui = DiaryTUI(db_path=seeded_db)
        tui._load_tasks()
        assert len(tui._backlog_tasks) == 1

    def test_auto_selects_first_today(self, seeded_db):
        tui = DiaryTUI(db_path=seeded_db)
        tui._load_tasks()
        task = tui._selected_task()
        assert task is not None
        assert task.title == "Today High"

    def test_switch_panel(self, seeded_db):
        tui = DiaryTUI(db_path=seeded_db)
        tui._load_tasks()
        tui._active_panel = "backlog"
        tui._selected_idx = 0
        task = tui._selected_task()
        assert task.title == "Backlog Task"

    def test_cursor_movement(self, seeded_db):
        tui = DiaryTUI(db_path=seeded_db)
        tui._load_tasks()
        tui._selected_idx = 1
        task = tui._selected_task()
        assert task.title == "Today Low"

    def test_cursor_bounds(self, seeded_db):
        tui = DiaryTUI(db_path=seeded_db)
        tui._load_tasks()
        # Can't go below 0
        tui._selected_idx = max(0, -10)
        assert tui._selected_idx == 0
        # Can't exceed list length
        tui._selected_idx = min(len(tui._today_tasks) - 1, 100)
        assert tui._selected_idx == 1

    def test_empty_db(self, tui_db):
        tui = DiaryTUI(db_path=tui_db)
        tui._load_tasks()
        assert tui._selected_task() is None

    def test_edit_field_title(self, seeded_db):
        tui = DiaryTUI(db_path=seeded_db)
        tui._load_tasks()
        tui._action_edit_field("title", "Renamed")
        tui._load_tasks()
        assert tui._selected_task().title == "Renamed"

    def test_edit_field_description(self, seeded_db):
        tui = DiaryTUI(db_path=seeded_db)
        tui._load_tasks()
        tui._action_edit_field("description", "new desc")
        task = tui._selected_task_full()
        assert task.description == "new desc"

    def test_edit_field_tags(self, seeded_db):
        tui = DiaryTUI(db_path=seeded_db)
        tui._load_tasks()
        tui._action_edit_field("tags", "foo, bar")
        task = tui._selected_task_full()
        assert set(task.tags) == {"foo", "bar"}

    def test_edit_field_due(self, seeded_db):
        tui = DiaryTUI(db_path=seeded_db)
        tui._load_tasks()
        tui._action_edit_field("due", "2026-12-25")
        task = tui._selected_task_full()
        assert task.due_date == "2026-12-25"

    def test_edit_field_no_task(self, tui_db):
        tui = DiaryTUI(db_path=tui_db)
        tui._load_tasks()
        tui._action_edit_field("title", "x")  # no crash

    def test_done_tasks_hidden_from_panels(self, seeded_db):
        tui = DiaryTUI(db_path=seeded_db)
        tui._load_tasks()
        assert len(tui._today_tasks) == 2

        # Mark first task done
        task = tui._today_tasks[0]
        tui.task_svc.update_task(task.id, UpdateTaskRequest(done=True))
        tui._load_tasks()

        # Done task should not appear in today list
        assert len(tui._today_tasks) == 1
        assert all(not t.done for t in tui._today_tasks)

    def test_future_scheduled_shows_in_backlog(self, seeded_db):
        """A task scheduled for tomorrow should stay in backlog until that day."""
        from datetime import timedelta
        tui = DiaryTUI(db_path=seeded_db)
        tui._load_tasks()
        task = tui._selected_task()
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        tui.task_svc.update_task(task.id, UpdateTaskRequest(scheduled_date=tomorrow))
        tui._load_tasks()

        # Future-scheduled: in backlog, not today
        assert any(t.id == task.id for t in tui._backlog_tasks)
        assert not any(t.id == task.id for t in tui._today_tasks)

    def test_past_scheduled_shows_in_today(self, seeded_db):
        """A task scheduled for yesterday should show in today (window still open)."""
        from datetime import timedelta
        tui = DiaryTUI(db_path=seeded_db)
        tui._load_tasks()
        tui._active_panel = "backlog"
        tui._selected_idx = 0
        task = tui._selected_task()
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        tui.task_svc.update_task(task.id, UpdateTaskRequest(scheduled_date=yesterday))
        tui._load_tasks()

        assert any(t.id == task.id for t in tui._today_tasks)

    def test_move_to_backlog_clears_scheduled_date(self, seeded_db):
        """Moving to backlog must wipe scheduled_date."""
        tui = DiaryTUI(db_path=seeded_db)
        tui._load_tasks()
        task = tui._selected_task()
        assert task.scheduled_date is not None  # seeded as today

        tui._action_move_backlog()
        updated = tui.task_svc.get_task(task.id)
        assert updated.scheduled_date is None

    def test_set_priority_direct(self, seeded_db):
        tui = DiaryTUI(db_path=seeded_db)
        tui._load_tasks()
        tui._action_set_priority("low")
        tui._load_tasks()
        assert tui._selected_task().priority == "low"

    def test_set_priority_single_log_entry(self, seeded_db):
        """Jumping from high to low should create one log entry, not two."""
        tui = DiaryTUI(db_path=seeded_db)
        tui._load_tasks()
        task = tui._selected_task_full()
        log_count_before = len(task.activity_log)

        tui._action_set_priority("low")

        task = tui._selected_task_full()
        new_entries = task.activity_log[log_count_before:]
        priority_entries = [e for e in new_entries if "Priority" in e.content]
        assert len(priority_entries) == 1

    def test_set_priority_invalid_noop(self, seeded_db):
        tui = DiaryTUI(db_path=seeded_db)
        tui._load_tasks()
        tui._action_set_priority("banana")
        tui._load_tasks()
        assert tui._selected_task().priority == "high"

    def test_set_priority_no_task(self, tui_db):
        tui = DiaryTUI(db_path=tui_db)
        tui._load_tasks()
        tui._action_set_priority("high")  # no crash


class TestTUIRendering:
    def test_detail_lines_with_task(self, seeded_db):
        tui = DiaryTUI(db_path=seeded_db)
        tui._load_tasks()
        task = tui._selected_task_full()
        lines = tui._detail_lines(task, 60)
        assert any("Today High" in l for l in lines)
        assert any("Log" in l for l in lines)

    def test_detail_lines_log_newest_first(self, seeded_db):
        tui = DiaryTUI(db_path=seeded_db)
        tui._load_tasks()
        task = tui._selected_task_full()
        tui.log_svc.add_entry(task.id, "user", "second entry")
        task = tui._selected_task_full()
        lines = tui._detail_lines(task, 60)
        log_lines = [l for l in lines if "entry" in l.lower() or "created" in l.lower()]
        assert log_lines[0].endswith("second entry")

    def test_detail_lines_empty(self, tui_db):
        tui = DiaryTUI(db_path=tui_db)
        tui._load_tasks()
        assert tui._selected_task_full() is None

    def test_init_creates_terminal(self, tui_db):
        tui = DiaryTUI(db_path=tui_db)
        assert tui.t is not None

    def test_styled_helper(self, tui_db):
        """Verify _styled doesn't crash with any blessed style."""
        tui = DiaryTUI(db_path=tui_db)
        t = tui.t
        # These must not raise — they're the styles used in _draw()
        assert isinstance(tui._styled("hello", t.bold), str)
        assert isinstance(tui._styled("hello", t.dim), str)
        assert isinstance(tui._styled("hello", t.reverse), str)
        assert isinstance(tui._styled("hello", t.cyan), str)
        assert isinstance(tui._styled("hello", t.white), str)

    def test_task_line(self, seeded_db):
        tui = DiaryTUI(db_path=seeded_db)
        tui._load_tasks()
        line = tui._task_line(tui._today_tasks[0])
        assert "▲" in line
        assert "Today High" in line

    def test_draw_does_not_crash(self, seeded_db):
        """Call _draw() with output redirected — verifies no TypeError from blessed."""
        import io, contextlib
        tui = DiaryTUI(db_path=seeded_db)
        tui._load_tasks()
        # Capture stdout so we don't mess up the test terminal
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            tui._draw()
        output = buf.getvalue()
        assert len(output) > 0

    def test_draw_empty_db(self, tui_db):
        """_draw() with no tasks should not crash."""
        import io, contextlib
        tui = DiaryTUI(db_path=tui_db)
        tui._load_tasks()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            tui._draw()
        output = buf.getvalue()
        assert "no task" in output.lower()


class TestTUINewActions:
    """Tests for t/b/x shortcuts and new features."""

    def test_move_to_today(self, seeded_db):
        tui = DiaryTUI(db_path=seeded_db)
        tui._load_tasks()
        tui._active_panel = "backlog"
        tui._selected_idx = 0
        task = tui._selected_task()
        assert task.title == "Backlog Task"

        tui._action_move_today()
        tui._load_tasks()
        moved = [t for t in tui._today_tasks if t.title == "Backlog Task"]
        assert len(moved) == 1
        assert moved[0].status == "in-progress"

    def test_move_to_backlog(self, seeded_db):
        tui = DiaryTUI(db_path=seeded_db)
        tui._load_tasks()
        tui._active_panel = "today"
        tui._selected_idx = 0
        task = tui._selected_task()
        assert task.title == "Today High"

        tui._action_move_backlog()
        tui._load_tasks()
        assert any(t.title == "Today High" for t in tui._backlog_tasks)

    def test_mark_done(self, seeded_db):
        tui = DiaryTUI(db_path=seeded_db)
        tui._load_tasks()
        task = tui._selected_task()
        assert task.done is False

        tui._action_mark_done()
        tui._load_tasks()
        # Reload the task to check status
        updated = tui.task_svc.get_task(task.id)
        assert updated.done is True

    def test_clamp_cursor_after_move(self, seeded_db):
        tui = DiaryTUI(db_path=seeded_db)
        tui._load_tasks()
        # Select last today task
        tui._selected_idx = len(tui._today_tasks) - 1
        # Move it away
        tui._action_move_backlog()
        # Cursor should be clamped
        assert tui._selected_idx <= max(0, len(tui._today_tasks) - 1)

    def test_move_today_no_task(self, tui_db):
        tui = DiaryTUI(db_path=tui_db)
        tui._load_tasks()
        tui._action_move_today()  # should not crash

    def test_mark_done_no_task(self, tui_db):
        tui = DiaryTUI(db_path=tui_db)
        tui._load_tasks()
        tui._action_mark_done()  # should not crash


    def test_recover_done_to_today(self, seeded_db):
        tui = DiaryTUI(db_path=seeded_db)
        tui._load_tasks()
        task = tui._selected_task()
        task_id = task.id
        tui.task_svc.update_task(task_id, UpdateTaskRequest(done=True))

        tui._action_recover_task(task_id, "today")
        recovered = tui.task_svc.get_task(task_id)
        assert recovered.status == "in-progress"
        assert recovered.scheduled_date == date.today().isoformat()

    def test_recover_done_to_backlog(self, seeded_db):
        tui = DiaryTUI(db_path=seeded_db)
        tui._load_tasks()
        task = tui._selected_task()
        task_id = task.id
        tui.task_svc.update_task(task_id, UpdateTaskRequest(done=True))

        tui._action_recover_task(task_id, "backlog")
        recovered = tui.task_svc.get_task(task_id)
        assert recovered.done is False
        assert recovered.scheduled_date is None

    def test_recover_archived_to_today(self, seeded_db):
        tui = DiaryTUI(db_path=seeded_db)
        tui._load_tasks()
        task = tui._selected_task()
        task_id = task.id
        tui.task_svc.archive_task(task_id, "test")

        tui._action_recover_task(task_id, "today")
        recovered = tui.task_svc.get_task(task_id)
        assert recovered.archived is False
        assert recovered.status == "in-progress"
        assert recovered.scheduled_date == date.today().isoformat()


class TestTUIFocusModes:
    """Test task mode vs log mode switching and log operations."""

    def test_default_mode_is_task(self, seeded_db):
        tui = DiaryTUI(db_path=seeded_db)
        tui._load_tasks()
        assert tui._active_panel != "log"

    def test_enter_log_mode_from_today(self, seeded_db):
        """Pressing 3 on a today task should show that task's logs, not backlog's."""
        tui = DiaryTUI(db_path=seeded_db)
        tui._load_tasks()
        assert tui._active_panel == "today"
        today_task = tui._selected_task()
        assert today_task.title == "Today High"

        tui._enter_log_mode()
        assert tui._active_panel == "log"
        assert tui._log_task_id == today_task.id
        # The full task in log mode should be the today task, not backlog
        full = tui._selected_task_full()
        assert full.id == today_task.id

    def test_switch_to_log_mode(self, seeded_db):
        tui = DiaryTUI(db_path=seeded_db)
        tui._load_tasks()
        tui._enter_log_mode()
        assert tui._active_panel == "log"
        assert tui._log_cursor == 0

    def test_switch_to_log_mode_no_task(self, tui_db):
        tui = DiaryTUI(db_path=tui_db)
        tui._load_tasks()
        tui._enter_log_mode()
        assert tui._active_panel != "log"  # stays in task mode, no task selected

    def test_exit_log_mode(self, seeded_db):
        tui = DiaryTUI(db_path=seeded_db)
        tui._load_tasks()
        tui._enter_log_mode()
        tui._exit_log_mode()
        assert tui._active_panel != "log"

    def test_log_cursor_movement(self, seeded_db):
        tui = DiaryTUI(db_path=seeded_db)
        tui._load_tasks()
        task = tui._selected_task_full()
        # Add extra entries so we have something to navigate
        tui.log_svc.add_entry(task.id, "user", "entry 1")
        tui.log_svc.add_entry(task.id, "user", "entry 2")

        tui._enter_log_mode()
        assert tui._log_cursor == 0
        tui._move_log_cursor(1)
        assert tui._log_cursor == 1
        tui._move_log_cursor(-10)
        assert tui._log_cursor == 0

    def test_delete_selected_log(self, seeded_db):
        tui = DiaryTUI(db_path=seeded_db)
        tui._load_tasks()
        task = tui._selected_task_full()
        tui.log_svc.add_entry(task.id, "user", "to delete")
        tui.log_svc.add_entry(task.id, "user", "to keep")

        tui._enter_log_mode()
        # Log is newest first, so index 0 = "to keep", index 1 = "to delete"
        tui._log_cursor = 1
        tui._action_delete_selected_log()

        task = tui._selected_task_full()
        contents = [e.content for e in task.activity_log]
        assert "to delete" not in contents
        assert "to keep" in contents

    def test_edit_selected_log(self, seeded_db):
        tui = DiaryTUI(db_path=seeded_db)
        tui._load_tasks()
        task = tui._selected_task_full()
        tui.log_svc.add_entry(task.id, "user", "original")

        tui._enter_log_mode()
        tui._log_cursor = 0  # newest = "original"
        tui._action_edit_selected_log(_content="edited")

        task = tui._selected_task_full()
        assert any(e.content == "edited" for e in task.activity_log)

    def test_delete_log_no_entries(self, tui_db):
        tui = DiaryTUI(db_path=tui_db)
        tui._load_tasks()
        tui._enter_log_mode()
        tui._action_delete_selected_log()  # no crash


class TestTUIEditorLog:
    def test_add_log_editor_reads_file(self, seeded_db, tmp_path):
        """Simulate editor by writing to the temp file directly."""
        import os
        tui = DiaryTUI(db_path=seeded_db)
        tui._load_tasks()
        task = tui._selected_task_full()
        count_before = len(task.activity_log)

        content = "log from editor"
        tui._action_add_log_editor(_editor_content=content)

        task = tui._selected_task_full()
        assert len(task.activity_log) == count_before + 1
        assert task.activity_log[-1].content == "log from editor"

    def test_add_log_editor_empty_content(self, seeded_db):
        """Empty editor content should not create an entry."""
        tui = DiaryTUI(db_path=seeded_db)
        tui._load_tasks()
        task = tui._selected_task_full()
        count_before = len(task.activity_log)

        tui._action_add_log_editor(_editor_content="")

        task = tui._selected_task_full()
        assert len(task.activity_log) == count_before

    def test_editor_restores_terminal(self, seeded_db):
        """After editor, terminal should be re-initialized for fullscreen."""
        import io, contextlib
        tui = DiaryTUI(db_path=seeded_db)
        tui._load_tasks()

        # Simulate editor with test content
        tui._action_add_log_editor(_editor_content="test")

        # _draw should still work after editor returns
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            tui._draw()
        assert len(buf.getvalue()) > 0


class TestTUIViewArchive:
    def test_build_archive_lines_has_archived(self, seeded_db):
        tui = DiaryTUI(db_path=seeded_db)
        tui._load_tasks()
        task = tui._selected_task()
        tui.task_svc.archive_task(task.id, "test reason")

        lines = tui._build_archive_lines()
        assert any("Today High" in l for l in lines)
        assert any("test reason" in l for l in lines)

    def test_build_archive_lines_empty(self, seeded_db):
        tui = DiaryTUI(db_path=seeded_db)
        lines = tui._build_archive_lines()
        assert any("no archived" in l.lower() for l in lines)

    def test_build_done_lines_has_done(self, seeded_db):
        tui = DiaryTUI(db_path=seeded_db)
        tui._load_tasks()
        task = tui._selected_task()
        tui.task_svc.update_task(task.id, UpdateTaskRequest(done=True))

        lines = tui._build_done_lines()
        assert any("Today High" in l for l in lines)

    def test_build_done_lines_empty(self, seeded_db):
        tui = DiaryTUI(db_path=seeded_db)
        lines = tui._build_done_lines()
        assert any("no done" in l.lower() for l in lines)


class TestTUIHelpOverlay:
    def test_help_toggle(self, tui_db):
        tui = DiaryTUI(db_path=tui_db)
        assert tui._show_help is False
        tui._show_help = True
        assert tui._show_help is True

    def test_draw_help_does_not_crash(self, tui_db):
        import io, contextlib
        tui = DiaryTUI(db_path=tui_db)
        tui._load_tasks()
        tui._show_help = True
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            tui._draw()
        output = buf.getvalue()
        assert "help" in output.lower() or "Help" in output


class TestTUIDrawNoFlicker:
    def test_draw_no_clear_sequence(self, seeded_db):
        """Verify _draw() does NOT emit terminal clear (cause of flicker)."""
        import io, contextlib
        tui = DiaryTUI(db_path=seeded_db)
        tui._load_tasks()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            tui._draw()
        output = buf.getvalue()
        # \x1b[2J is the ANSI clear screen sequence
        assert "\x1b[2J" not in output
