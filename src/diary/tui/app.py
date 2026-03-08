"""Diary TUI — blessed-based compact lazygit-style interface."""
from datetime import date
from pathlib import Path

from blessed import Terminal

from diary.config import load_config
from diary.dates import parse_natural_date
from diary.db import get_connection, init_db
from diary.models import Task, TaskListFilters, CreateTaskRequest, UpdateTaskRequest
from diary.service.tasks import TaskService
from diary.service.activity_log import ActivityLogService
from diary.service.tags import TagService


class DiaryTUI:
    def __init__(self, db_path: str | None = None):
        config = load_config()
        if db_path:
            self._db_path = db_path
        else:
            self._db_path = str(Path(config.data_dir).expanduser() / "diary.db")

        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = get_connection(self._db_path)
        init_db(self.conn)

        self.task_svc = TaskService(self.conn)
        self.log_svc = ActivityLogService(self.conn)
        self.tag_svc = TagService(self.conn)

        self.t = Terminal()
        self._today_tasks: list[Task] = []
        self._backlog_tasks: list[Task] = []
        self._selected_idx = 0
        self._active_panel = "today"
        self._scroll_offset = 0
        self._show_help = False
        self._log_cursor = 0
        self._log_task_id: str | None = None  # task ID when in log mode

    def _load_tasks(self):
        today = date.today().isoformat()
        # Today = scheduled_date <= today (window still open), not done
        all_tasks = self.task_svc.list_tasks(TaskListFilters())
        self._today_tasks = [t for t in all_tasks if t.scheduled_date and t.scheduled_date <= today and not t.done]
        today_ids = {t.id for t in self._today_tasks}
        # Backlog = everything else that's not done
        self._backlog_tasks = [t for t in all_tasks if t.id not in today_ids and not t.done]

    def _active_list(self) -> list[Task]:
        return self._today_tasks if self._active_panel == "today" else self._backlog_tasks

    def _selected_task(self) -> Task | None:
        tasks = self._active_list()
        if not tasks or self._selected_idx >= len(tasks):
            return None
        return tasks[self._selected_idx]

    def _selected_task_full(self) -> Task | None:
        if self._active_panel == "log" and self._log_task_id:
            try:
                return self.task_svc.get_task(self._log_task_id)
            except ValueError:
                return None
        task = self._selected_task()
        if task:
            try:
                return self.task_svc.get_task(task.id)
            except ValueError:
                pass
        return None

    # --- Drawing helpers ---

    def _styled(self, text: str, *styles) -> str:
        t = self.t
        prefix = "".join(str(s) for s in styles)
        return prefix + text + str(t.normal)

    def _wrap(self, text: str, width: int) -> list[str]:
        """Word-wrap a string to fit within width."""
        if not text:
            return [""]
        if len(text) <= width:
            return [text]
        lines = []
        while text:
            if len(text) <= width:
                lines.append(text)
                break
            # Find last space before width
            idx = text.rfind(" ", 0, width)
            if idx == -1:
                idx = width  # hard break
            lines.append(text[:idx])
            text = text[idx:].lstrip()
        return lines

    def _draw_box(self, x: int, y: int, w: int, h: int, title: str = "", active: bool = False):
        t = self.t
        tl, tr, bl, br = "╭", "╮", "╰", "╯"
        hz, vt = "─", "│"

        if title:
            inner = f" {title} "
            pad = w - 2 - len(inner)
            top = tl + hz + inner + hz * max(0, pad - 1) + tr
        else:
            top = tl + hz * (w - 2) + tr

        style = t.cyan if active else t.white
        print(t.move_xy(x, y) + self._styled(top[:w], style))

        for row in range(1, h - 1):
            print(t.move_xy(x, y + row) + self._styled(vt, style)
                  + " " * (w - 2)
                  + self._styled(vt, style))

        bottom = bl + hz * (w - 2) + br
        print(t.move_xy(x, y + h - 1) + self._styled(bottom[:w], style))

    def _draw(self):
        t = self.t
        w, h = t.width, t.height

        left_w = max(28, int(w * 0.35))
        right_w = w - left_w
        panel_h = h - 1

        today_h = panel_h // 2
        backlog_h = panel_h - today_h

        print(t.home, end="")

        # --- Today panel ---
        active_today = self._active_panel == "today"
        self._draw_box(0, 0, left_w, today_h,
                       f"Today ({len(self._today_tasks)})", active_today)
        for i, task in enumerate(self._today_tasks):
            if i >= today_h - 2:
                break
            line = self._task_line(task)
            padded = line[:left_w - 3].ljust(left_w - 3)
            sel = active_today and i == self._selected_idx
            styled = self._styled(padded, t.reverse) if sel else padded
            print(t.move_xy(1, 1 + i) + styled)

        # --- Backlog panel ---
        active_backlog = self._active_panel == "backlog"
        self._draw_box(0, today_h, left_w, backlog_h,
                       f"Backlog ({len(self._backlog_tasks)})", active_backlog)
        for i, task in enumerate(self._backlog_tasks):
            if i >= backlog_h - 2:
                break
            line = self._task_line(task)
            padded = line[:left_w - 3].ljust(left_w - 3)
            sel = active_backlog and i == self._selected_idx
            styled = self._styled(padded, t.reverse) if sel else padded
            print(t.move_xy(1, today_h + 1 + i) + styled)

        # --- Detail panel ---
        self._draw_box(left_w, 0, right_w, panel_h, "Detail")
        task = self._selected_task_full()
        if task:
            detail_lines = self._detail_lines(task, right_w - 4)
            for i, line in enumerate(detail_lines[self._scroll_offset:]):
                if i >= panel_h - 2:
                    break
                print(t.move_xy(left_w + 2, 1 + i) + line[:right_w - 4].ljust(right_w - 4))
        else:
            print(t.move_xy(left_w + 2, 1) + self._styled("no task selected".ljust(right_w - 4), t.dim))

        # --- Help overlay or hint bar ---
        if self._show_help:
            self._draw_help_overlay()
        else:
            if self._active_panel == "log":
                hints = "j/k:nav d:delete e:edit l:add L:vim Esc:back ?:help q:quit"
            elif self._active_panel == "today":
                hints = "j/k:nav b:backlog x:done p:pri e:edit d:date n:new l:log a:arch 3/Enter:log v:view ?:help q:quit"
            else:
                hints = "j/k:nav t:today p:pri e:edit d:date n:new l:log a:arch 3/Enter:log v:view ?:help q:quit"
            print(t.move_xy(0, h - 1) + self._styled(hints[:w].ljust(w), t.dim), end="", flush=True)

    def _draw_help_overlay(self):
        t = self.t
        lines = [
            "Keybindings",
            "",
            "  j / Down    Move cursor down",
            "  k / Up      Move cursor up",
            "  1           Switch to Today panel",
            "  2           Switch to Backlog panel",
            "",
            "  t           Move task to today",
            "  b           Move task to backlog",
            "  x           Mark task done",
            "  p           Set priority (h/m/l)",
            "  d           Schedule task (prompt for date)",
            "",
            "  n           New task",
            "  e           Edit task (prompt for field)",
            "  l           Add log entry (inline)",
            "  L           Add log entry (open $EDITOR / vim)",
            "  D           Delete newest log entry",
            "  a           Archive task",
            "  u           Unarchive task",
            "  v           View archived tasks",
            "  r           Refresh from DB",
            "",
            "  J / K       Scroll detail panel",
            "  ?           Toggle this help",
            "  q           Quit",
        ]
        # Center the overlay
        box_w = 50
        box_h = len(lines) + 2
        x = (t.width - box_w) // 2
        y = max(0, (t.height - box_h) // 2)

        self._draw_box(x, y, box_w, box_h, "Help", active=True)
        for i, line in enumerate(lines):
            print(t.move_xy(x + 2, y + 1 + i) + line[:box_w - 4].ljust(box_w - 4))

    def _task_line(self, task: Task) -> str:
        pri = {"high": "▲", "medium": "●", "low": "▽"}[task.priority]
        sts = {"todo": "○", "in-progress": "◐", "done": "●"}[task.status]
        return f" {pri} {sts} {task.title}"

    def _detail_lines(self, task: Task, max_w: int) -> list[str]:
        t = self.t
        tags = " ".join(f"#{tg}" for tg in task.tags) if task.tags else "none"
        sched = task.scheduled_date or "backlog"
        due = task.due_date or "none"

        lines = [
            self._styled(task.title, t.bold),
            "",
            f"  Status    {task.status}",
            f"  Priority  {task.priority}",
            f"  Tags      {tags}",
            f"  Due       {due}",
            f"  Sched     {sched}",
        ]
        if task.description:
            lines.append("  Desc:")
            for desc_line in task.description.split("\n"):
                wrapped = self._wrap(desc_line.strip(), max_w - 6)
                for wl in wrapped:
                    lines.append(f"    {wl}")

        lines.append("")
        lines.append(self._styled("--- Log (newest first) ---", t.bold))

        if task.activity_log:
            for idx, entry in enumerate(reversed(task.activity_log)):
                ts = entry.timestamp[5:16]
                src = {"system": "sys", "ai": " ai", "user": "usr"}.get(entry.source, entry.source)
                selected = self._active_panel == "log" and idx == self._log_cursor
                content_lines = entry.content.split("\n")
                # Wrap each content line
                all_content_lines = []
                for cl in content_lines:
                    all_content_lines.extend(self._wrap(cl.strip(), max_w - 18))
                first = all_content_lines[0] if all_content_lines else ""
                rest = all_content_lines[1:]
                if selected:
                    lines.append(self._styled(f" >{ts} {src} {first}", t.reverse))
                    for extra in rest:
                        lines.append(self._styled(f"              {extra}", t.reverse))
                else:
                    prefix = str(t.dim) if entry.source == "system" else ""
                    suffix = str(t.normal) if entry.source == "system" else ""
                    lines.append(f"  {prefix}{ts} {src} {first}{suffix}")
                    for extra in rest:
                        lines.append(f"  {prefix}             {extra}{suffix}")
        else:
            lines.append("  no entries")

        return lines

    # --- Input prompt ---

    def _prompt(self, label: str) -> str | None:
        t = self.t
        y = t.height - 1
        print(t.move_xy(0, y) + t.clear_eol + self._styled(f"{label}: ", t.bold), end="", flush=True)
        buf = ""
        while True:
            key = t.inkey()
            if key.name == "KEY_ESCAPE":
                return None
            if key.name == "KEY_ENTER":
                return buf
            if key.name == "KEY_BACKSPACE" or key.name == "KEY_DELETE":
                buf = buf[:-1]
            elif key and not key.is_sequence:
                buf += str(key)
            print(t.move_xy(0, y) + t.clear_eol + self._styled(f"{label}: ", t.bold) + buf, end="", flush=True)

    # --- Actions ---

    def _action_move_today(self):
        task = self._selected_task()
        if not task:
            return
        today = date.today().isoformat()
        self.task_svc.update_task(task.id, UpdateTaskRequest(scheduled_date=today))
        self._load_tasks()
        self._clamp_cursor()

    def _action_move_backlog(self):
        task = self._selected_task()
        if not task:
            return
        self.task_svc.update_task(task.id, UpdateTaskRequest(scheduled_date="none"))
        self._load_tasks()
        self._clamp_cursor()

    def _action_mark_done(self):
        task = self._selected_task()
        if not task:
            return
        self.task_svc.update_task(task.id, UpdateTaskRequest(done=True))
        self._load_tasks()
        self._clamp_cursor()

    def _action_new_task(self):
        title = self._prompt("Title")
        if not title or not title.strip():
            return
        pri = self._prompt("Priority (h/m/l)") or ""
        pri = {"h": "high", "m": "medium", "l": "low"}.get(pri.strip().lower()[:1], "medium")
        tags_raw = self._prompt("Tags (comma-sep)") or ""
        tags = [tg.strip() for tg in tags_raw.split(",") if tg.strip()] if tags_raw else None
        sched_raw = self._prompt("Schedule (today/tomorrow/date/empty=backlog)") or ""
        sched = parse_natural_date(sched_raw) if sched_raw.strip() else None

        self.task_svc.create_task(CreateTaskRequest(
            title=title.strip(), priority=pri, tags=tags, scheduled_date=sched,
        ))
        self._load_tasks()

    def _action_edit_field(self, field: str | None = None, value: str | None = None):
        """Edit a task field. If field/value not given, prompt for them."""
        task = self._selected_task()
        if not task:
            return
        if field is None:
            field = self._prompt("Field (title/desc/tags/due/sched)")
            if not field:
                return
            field = field.strip().lower()
        if value is None:
            current = {
                "title": task.title,
                "desc": task.description or "",
                "tags": ", ".join(task.tags) if task.tags else "",
                "due": task.due_date or "",
                "sched": task.scheduled_date or "",
            }.get(field, "")
            value = self._prompt(f"{field} [{current}]")
            if value is None:
                return

        value = value.strip()
        req = UpdateTaskRequest()
        if field == "title":
            if not value:
                return
            req.title = value
        elif field in ("desc", "description"):
            req.description = value or "none"
        elif field == "tags":
            req.tags = [t.strip() for t in value.split(",") if t.strip()] if value else []
        elif field == "due":
            req.due_date = (parse_natural_date(value) or value) if value else "none"
        elif field == "sched":
            req.scheduled_date = (parse_natural_date(value) or value) if value else "none"
        else:
            return

        self.task_svc.update_task(task.id, req)
        self._load_tasks()
        self._clamp_cursor()

    def _action_set_priority(self, priority: str | None = None):
        """Set priority directly. If priority not given, prompt for h/m/l."""
        task = self._selected_task()
        if not task:
            return
        if priority is None:
            val = self._prompt("Priority (h/m/l)")
            if not val:
                return
            priority = {"h": "high", "m": "medium", "l": "low"}.get(val.strip().lower()[:1], "")
        if priority not in ("high", "medium", "low"):
            return
        if priority == task.priority:
            return
        self.task_svc.update_task(task.id, UpdateTaskRequest(priority=priority))
        self._load_tasks()

    def _action_schedule(self):
        task = self._selected_task()
        if not task:
            return
        val = self._prompt("Schedule (date/today/empty=backlog)")
        if val is None:
            return
        val = val.strip()
        sched = "none" if val == "" else (parse_natural_date(val) or val)
        self.task_svc.update_task(task.id, UpdateTaskRequest(scheduled_date=sched))
        self._load_tasks()
        self._clamp_cursor()

    def _action_archive(self):
        task = self._selected_task()
        if not task:
            return
        reason = self._prompt("Archive reason")
        if not reason or not reason.strip():
            return
        try:
            self.task_svc.archive_task(task.id, reason.strip())
            self._load_tasks()
            self._clamp_cursor()
        except ValueError:
            pass

    def _action_unarchive(self):
        task = self._selected_task()
        if not task:
            return
        try:
            self.task_svc.unarchive_task(task.id)
            self._load_tasks()
        except ValueError:
            pass

    def _action_add_log(self):
        task = self._selected_task()
        if not task:
            return
        content = self._prompt("Log entry")
        if not content or not content.strip():
            return
        self.log_svc.add_entry(task.id, "user", content.strip())
        self._load_tasks()

    def _action_add_log_editor(self, _editor_content: str | None = None):
        """Open $EDITOR for a longer log entry. _editor_content is for testing only."""
        import os, tempfile, subprocess
        task = self._selected_task()
        if not task:
            return

        if _editor_content is not None:
            content = _editor_content.strip()
        else:
            editor = os.environ.get("EDITOR", "vim")
            with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
                tmp = f.name
            try:
                # Exit fullscreen so editor gets a clean terminal
                t = self.t
                print(t.exit_fullscreen + t.normal_cursor, end="", flush=True)
                subprocess.call([editor, tmp])
                # Re-enter fullscreen
                print(t.enter_fullscreen + t.hide_cursor, end="", flush=True)
                with open(tmp) as f:
                    content = f.read().strip()
            finally:
                os.unlink(tmp)

        if content:
            self.log_svc.add_entry(task.id, "user", content)
            self._load_tasks()

    def _action_delete_newest_log(self):
        """Delete the newest log entry on the selected task."""
        task = self._selected_task_full()
        if not task or not task.activity_log:
            return
        newest = task.activity_log[-1]
        self.log_svc.delete_entry(newest.id)
        self._load_tasks()

    # --- Focus mode methods ---

    def _enter_log_mode(self):
        """Switch to log mode if a task is selected and has entries."""
        task = self._selected_task_full()
        if not task:
            return
        self._log_task_id = task.id
        self._prev_panel = self._active_panel
        self._active_panel = "log"
        self._log_cursor = 0

    def _exit_log_mode(self):
        self._active_panel = getattr(self, "_prev_panel", "today") or "today"
        self._log_cursor = 0
        self._log_task_id = None

    def _get_log_entries_reversed(self) -> list:
        """Get activity log entries newest first."""
        task = self._selected_task_full()
        if not task or not task.activity_log:
            return []
        return list(reversed(task.activity_log))

    def _move_log_cursor(self, delta: int):
        entries = self._get_log_entries_reversed()
        if not entries:
            return
        self._log_cursor = max(0, min(len(entries) - 1, self._log_cursor + delta))

    def _action_delete_selected_log(self):
        entries = self._get_log_entries_reversed()
        if not entries or self._log_cursor >= len(entries):
            return
        entry = entries[self._log_cursor]
        self.log_svc.delete_entry(entry.id)
        self._load_tasks()
        # Clamp cursor
        entries = self._get_log_entries_reversed()
        if entries:
            self._log_cursor = min(self._log_cursor, len(entries) - 1)
        else:
            self._log_cursor = 0

    def _action_edit_selected_log(self, _content: str | None = None):
        entries = self._get_log_entries_reversed()
        if not entries or self._log_cursor >= len(entries):
            return
        entry = entries[self._log_cursor]
        if _content is None:
            _content = self._prompt(f"Edit log [{entry.content[:40]}]")
        if _content is None or not _content.strip():
            return
        self.log_svc.edit_entry(entry.id, _content.strip())
        self._load_tasks()

    def _build_archive_lines(self) -> list[str]:
        tasks = self.task_svc.list_tasks(TaskListFilters(archived=True))
        archived = [t for t in tasks if t.archived]
        lines = ["Archived", ""]
        if not archived:
            lines.append("  no archived tasks")
        else:
            for t in archived:
                reason = t.archive_reason or "(no reason)"
                lines.append(f"  {t.title}")
                lines.append(f"    {reason}")
                lines.append("")
        return lines

    def _build_done_lines(self) -> list[str]:
        tasks = self.task_svc.list_tasks(TaskListFilters(done=True))
        lines = ["Done", ""]
        if not tasks:
            lines.append("  no done tasks")
        else:
            for t in tasks:
                sched = t.scheduled_date or "backlog"
                lines.append(f"  {t.title}  ({sched})")
        return lines

    def _action_view_archive(self):
        """Show done + archived tasks side by side. r=recover, any other key=return."""
        t = self.t
        w, h = t.width, t.height
        half_w = w // 2
        panel_h = h - 1

        done_tasks = self.task_svc.list_tasks(TaskListFilters(done=True))
        arch_tasks = [tk for tk in self.task_svc.list_tasks(TaskListFilters(archived=True)) if tk.archived]
        all_tasks = done_tasks + arch_tasks

        cursor = 0
        panel = "done"  # "done" or "archived"

        while True:
            done_lines = self._build_done_lines()
            arch_lines = self._build_archive_lines()

            print(t.home, end="")

            # Left: done
            self._draw_box(0, 0, half_w, panel_h, f"Done ({len(done_tasks)})", panel == "done")
            for i, task in enumerate(done_tasks):
                if i >= panel_h - 2:
                    break
                line = f"  {task.title}"
                padded = line[:half_w - 4].ljust(half_w - 4)
                sel = panel == "done" and i == cursor
                styled = self._styled(padded, t.reverse) if sel else padded
                print(t.move_xy(1, 1 + i) + styled)

            # Right: archived
            rw = w - half_w
            self._draw_box(half_w, 0, rw, panel_h, f"Archived ({len(arch_tasks)})", panel == "archived")
            for i, task in enumerate(arch_tasks):
                if i >= panel_h - 2:
                    break
                reason = task.archive_reason or ""
                line = f"  {task.title}  {reason}"
                padded = line[:rw - 4].ljust(rw - 4)
                sel = panel == "archived" and i == cursor
                styled = self._styled(padded, t.reverse) if sel else padded
                print(t.move_xy(half_w + 1, 1 + i) + styled)

            hints = "j/k:nav 1:done 2:archived r:recover q:back"
            print(t.move_xy(0, h - 1) + self._styled(hints.ljust(w), t.dim), end="", flush=True)

            key = t.inkey()
            current_list = done_tasks if panel == "done" else arch_tasks

            if key == "q" or key.name == "KEY_ESCAPE":
                break
            elif key == "j" or key.name == "KEY_DOWN":
                if current_list:
                    cursor = min(len(current_list) - 1, cursor + 1)
            elif key == "k" or key.name == "KEY_UP":
                cursor = max(0, cursor - 1)
            elif key == "1":
                panel = "done"
                cursor = 0
            elif key == "2":
                panel = "archived"
                cursor = 0
            elif key == "r":
                if current_list and cursor < len(current_list):
                    task_id = current_list[cursor].id
                    self._action_recover_task(task_id)
                    # Reload lists
                    done_tasks = self.task_svc.list_tasks(TaskListFilters(done=True))
                    arch_tasks = [tk for tk in self.task_svc.list_tasks(TaskListFilters(archived=True)) if tk.archived]
                    current_list = done_tasks if panel == "done" else arch_tasks
                    cursor = min(cursor, max(0, len(current_list) - 1))

        self._load_tasks()
        self._clamp_cursor()

    def _action_recover_task(self, task_id: str, destination: str | None = None):
        """Recover a done or archived task. destination is 'today' or 'backlog'."""
        task = self.task_svc.get_task(task_id)
        if destination is None:
            dest = self._prompt("Recover to (t=today, b=backlog)")
            if not dest:
                return
            destination = {"t": "today", "b": "backlog"}.get(dest.strip().lower()[:1], "")
        if destination not in ("today", "backlog"):
            return

        if task.archived:
            self.task_svc.unarchive_task(task_id)

        sched = date.today().isoformat() if destination == "today" else "none"
        self.task_svc.update_task(task_id, UpdateTaskRequest(done=False, scheduled_date=sched))
        self._load_tasks()
        self._clamp_cursor()

    def _clamp_cursor(self):
        tasks = self._active_list()
        if tasks:
            self._selected_idx = min(self._selected_idx, len(tasks) - 1)
        else:
            self._selected_idx = 0

    # --- Main loop ---

    def run(self):
        t = self.t
        self._load_tasks()

        if self._today_tasks:
            self._active_panel = "today"
        elif self._backlog_tasks:
            self._active_panel = "backlog"
        self._selected_idx = 0

        with t.fullscreen(), t.cbreak(), t.hidden_cursor():
            self._draw()

            while True:
                key = t.inkey()

                if key == "q":
                    break
                elif key == "?" or (key.name == "KEY_ESCAPE" and self._show_help):
                    self._show_help = not self._show_help
                elif self._show_help:
                    if key.name == "KEY_ESCAPE":
                        self._show_help = False
                elif self._active_panel == "log":
                    # --- Log mode ---
                    if key.name == "KEY_ESCAPE" or key == "1" or key == "2":
                        self._exit_log_mode()
                        if key == "1":
                            self._active_panel = "today"
                            self._selected_idx = 0
                        elif key == "2":
                            self._active_panel = "backlog"
                            self._selected_idx = 0
                    elif key == "j" or key.name == "KEY_DOWN":
                        self._move_log_cursor(1)
                    elif key == "k" or key.name == "KEY_UP":
                        self._move_log_cursor(-1)
                    elif key == "d":
                        self._action_delete_selected_log()
                    elif key == "e":
                        self._action_edit_selected_log()
                    elif key == "l":
                        self._action_add_log()
                    elif key == "L":
                        self._action_add_log_editor()
                else:
                    # --- Task mode ---
                    if key.name == "KEY_ESCAPE":
                        self._show_help = False
                    elif key == "j" or key.name == "KEY_DOWN":
                        tasks = self._active_list()
                        if tasks:
                            self._selected_idx = min(len(tasks) - 1, self._selected_idx + 1)
                            self._scroll_offset = 0
                    elif key == "k" or key.name == "KEY_UP":
                        self._selected_idx = max(0, self._selected_idx - 1)
                        self._scroll_offset = 0
                    elif key == "1":
                        self._active_panel = "today"
                        self._selected_idx = 0
                        self._scroll_offset = 0
                    elif key == "2":
                        self._active_panel = "backlog"
                        self._selected_idx = 0
                        self._scroll_offset = 0
                    elif key == "3" or key.name == "KEY_ENTER":
                        self._enter_log_mode()
                    elif key == "t":
                        self._action_move_today()
                    elif key == "b":
                        self._action_move_backlog()
                    elif key == "x":
                        self._action_mark_done()
                    elif key == "n":
                        self._action_new_task()
                    elif key == "e":
                        self._action_edit_field()
                    elif key == "p":
                        self._action_set_priority()
                    elif key == "d":
                        self._action_schedule()
                    elif key == "a":
                        self._action_archive()
                    elif key == "u":
                        self._action_unarchive()
                    elif key == "l":
                        self._action_add_log()
                    elif key == "L":
                        self._action_add_log_editor()
                    elif key == "v":
                        self._action_view_archive()
                    elif key == "r":
                        self._load_tasks()
                    elif key == "J":
                        self._scroll_offset += 1
                    elif key == "K":
                        self._scroll_offset = max(0, self._scroll_offset - 1)

                self._draw()

        self.conn.close()


def run(db_path: str | None = None):
    tui = DiaryTUI(db_path=db_path)
    tui.run()
