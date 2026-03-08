import argparse
import json
import sys
import os
from diary.config import load_config
from diary.db import get_connection, init_db
from diary.dates import parse_natural_date
from diary.models import CreateTaskRequest, UpdateTaskRequest, TaskListFilters
from diary.service.tasks import TaskService
from diary.service.activity_log import ActivityLogService


def _get_db():
    db_path = os.environ.get("DIARY_DB")
    if db_path is None:
        config = load_config()
        data_dir = os.path.expanduser(config.data_dir)
        os.makedirs(data_dir, exist_ok=True)
        db_path = os.path.join(data_dir, "diary.db")
    conn = get_connection(db_path)
    init_db(conn)
    return conn


def _resolve_date(value: str | None) -> str | None:
    """Resolve a date argument: natural language, ISO, 'today', 'none', or None."""
    if value is None:
        return None
    if value == "none":
        return "none"
    parsed = parse_natural_date(value)
    if parsed is None:
        print(f"Warning: could not parse date '{value}', using as-is", file=sys.stderr)
        return value
    return parsed


def _print_json(data):
    print(json.dumps(data, indent=2, default=str))


def _task_to_dict(task):
    d = task.model_dump()
    if d.get("activity_log") is None:
        d.pop("activity_log", None)
    return d


def _brief_output(tasks):
    if not tasks:
        print("📋 Diary — No tasks found.")
        return
    print(f"📋 Diary — {len(tasks)} task(s):")
    for i, t in enumerate(tasks, 1):
        pri = {"high": "HIGH", "medium": "MED", "low": "LOW"}[t.priority]
        print(f"  {i}. [{pri}] {t.title}")
    print(f"\nRun `diary chat` to review or `diary tui` for full view.")


def handle_list(args):
    conn = _get_db()
    svc = TaskService(conn)
    scheduled = args.scheduled
    if scheduled and scheduled not in ("today", "none"):
        scheduled = _resolve_date(scheduled)
    filters = TaskListFilters(
        scheduled=scheduled,
        done=args.done if hasattr(args, "done") and args.done else None,
        priority=args.priority,
        tag=args.tag,
        search=args.search,
        from_date=getattr(args, "from", None) or getattr(args, "from_date", None),
        to_date=args.to,
        archived=args.archived,
        verbose=args.verbose,
    )
    tasks = svc.list_tasks(filters)
    fmt = getattr(args, "format", "json")
    if fmt == "brief":
        _brief_output(tasks)
    else:
        _print_json([_task_to_dict(t) for t in tasks])


def handle_show(args):
    conn = _get_db()
    svc = TaskService(conn)
    task = svc.get_task(args.task_id)
    _print_json(_task_to_dict(task))


def handle_add(args):
    conn = _get_db()
    svc = TaskService(conn)
    tags = args.tags.split(",") if args.tags else None
    req = CreateTaskRequest(
        title=args.title,
        description=args.description,
        priority=args.priority or "medium",
        tags=tags,
        due_date=_resolve_date(args.due),
        scheduled_date=_resolve_date(args.schedule),
    )
    task = svc.create_task(req)
    _print_json(_task_to_dict(task))


def handle_update(args):
    conn = _get_db()
    svc = TaskService(conn)
    tags = args.tags.split(",") if args.tags else None
    done = None
    if hasattr(args, "done") and args.done:
        done = True
    if hasattr(args, "undone") and args.undone:
        done = False
    req = UpdateTaskRequest(
        title=args.title,
        description=args.description,
        done=done,
        priority=args.priority,
        tags=tags,
        due_date=_resolve_date(args.due),
        scheduled_date=_resolve_date(args.schedule),
    )
    task = svc.update_task(args.task_id, req)
    _print_json(_task_to_dict(task))


def handle_log(args):
    conn = _get_db()
    svc = ActivityLogService(conn)
    entry = svc.add_entry(args.task_id, "user", args.message)
    _print_json(entry.model_dump())


def handle_archive(args):
    conn = _get_db()
    svc = TaskService(conn)
    task = svc.archive_task(args.task_id, args.reason)
    _print_json(_task_to_dict(task))


def handle_unarchive(args):
    conn = _get_db()
    svc = TaskService(conn)
    task = svc.unarchive_task(args.task_id)
    _print_json(_task_to_dict(task))


def build_parser():
    parser = argparse.ArgumentParser(prog="diary api", description="Diary machine-friendly CLI API")
    sub = parser.add_subparsers(dest="api_command")

    # list
    p_list = sub.add_parser("list", help="List tasks with filters")
    p_list.add_argument("--scheduled", help="Filter by scheduled date (today, <date>, none)")
    p_list.add_argument("--done", action="store_true", help="Show only done tasks")
    p_list.add_argument("--priority", help="Filter by priority (high, medium, low)")
    p_list.add_argument("--tag", help="Filter by tag name")
    p_list.add_argument("--search", help="Full-text search across title and description")
    p_list.add_argument("--from", dest="from_date", help="Start date for range filter")
    p_list.add_argument("--to", help="End date for range filter")
    p_list.add_argument("--archived", action="store_true", help="Include archived tasks")
    p_list.add_argument("--verbose", action="store_true", help="Include activity log")
    p_list.add_argument("--format", choices=["json", "brief"], default="json", help="Output format")

    # show
    p_show = sub.add_parser("show", help="Show a single task")
    p_show.add_argument("task_id", help="Task ID")

    # add
    p_add = sub.add_parser("add", help="Create a new task")
    p_add.add_argument("--title", required=True, help="Task title")
    p_add.add_argument("--description", help="Task description")
    p_add.add_argument("--priority", choices=["high", "medium", "low"], help="Priority")
    p_add.add_argument("--tags", help="Comma-separated tags")
    p_add.add_argument("--due", help="Due date")
    p_add.add_argument("--schedule", help="Scheduled date (or 'today')")

    # update
    p_update = sub.add_parser("update", help="Update a task")
    p_update.add_argument("task_id", help="Task ID")
    p_update.add_argument("--title", help="New title")
    p_update.add_argument("--description", help="New description")
    p_update.add_argument("--done", action="store_true", help="Mark as done")
    p_update.add_argument("--undone", action="store_true", help="Mark as not done")
    p_update.add_argument("--priority", choices=["high", "medium", "low"], help="New priority")
    p_update.add_argument("--tags", help="Comma-separated tags")
    p_update.add_argument("--due", help="New due date")
    p_update.add_argument("--schedule", help="New scheduled date (or 'none' for backlog)")

    # log
    p_log = sub.add_parser("log", help="Add activity log entry")
    p_log.add_argument("task_id", help="Task ID")
    p_log.add_argument("message", help="Log message")

    # archive
    p_archive = sub.add_parser("archive", help="Archive a task")
    p_archive.add_argument("task_id", help="Task ID")
    p_archive.add_argument("--reason", required=True, help="Archive reason")

    # unarchive
    p_unarchive = sub.add_parser("unarchive", help="Unarchive a task")
    p_unarchive.add_argument("task_id", help="Task ID")

    return parser


HANDLERS = {
    "list": handle_list,
    "show": handle_show,
    "add": handle_add,
    "update": handle_update,
    "log": handle_log,
    "archive": handle_archive,
    "unarchive": handle_unarchive,
}


def run(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.api_command is None:
        parser.print_help()
        return 0
    handler = HANDLERS.get(args.api_command)
    try:
        handler(args)
        return 0
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1
