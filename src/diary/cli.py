import argparse
import sys
from diary import api_cli


def main():
    parser = argparse.ArgumentParser(prog="diary", description="AI-powered daily task management")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("tui", help="Launch the TUI")
    subparsers.add_parser("chat", help="Launch conversational AI chat")
    subparsers.add_parser("api", help="Machine-friendly CLI API")
    subparsers.add_parser("notify", help="Send notification")
    subparsers.add_parser("install", help="Print setup instructions")

    args, remaining = parser.parse_known_args()

    if args.command is None:
        parser.print_help()
        return

    if args.command == "api":
        sys.exit(api_cli.run(remaining))
    elif args.command == "chat":
        from diary import chat
        sys.exit(chat.run())
    elif args.command == "tui":
        from diary.tui.app import run as run_tui
        run_tui()
    elif args.command == "notify":
        from diary import notify
        sys.exit(notify.run(remaining))
    elif args.command == "install":
        from diary import install
        sys.exit(install.run())


if __name__ == "__main__":
    main()
