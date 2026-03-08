"""diary notify — send morning/evening notifications."""
import sys
from pathlib import Path
from diary.config import load_config
from diary.db import get_connection, init_db
from diary.service.notifications import NotificationService


def run(args: list[str]) -> int:
    if not args or args[0] not in ("morning", "evening"):
        print("Usage: diary notify morning|evening", file=sys.stderr)
        return 1

    notify_type = args[0]
    config = load_config()
    db_path = Path(config.data_dir).expanduser() / "diary.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection(str(db_path))
    init_db(conn)

    svc = NotificationService(conn, terminal_app=config.terminal_app)
    sent = svc.check_and_send(notify_type)
    conn.close()

    if sent:
        print(f"{notify_type} notification sent.")
    else:
        print(f"{notify_type} notification already sent today.")
    return 0
