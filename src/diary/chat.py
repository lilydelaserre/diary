"""diary chat — conversational AI REPL."""
import sys
from pathlib import Path
from diary.config import load_config
from diary.db import get_connection, init_db
from diary.agent.agent import create_agent


def run():
    """Run the chat REPL. Reads user input, sends to agent, prints response. Exit on 'quit' or 'exit'."""
    config = load_config()
    db_path = Path(config.data_dir).expanduser() / "diary.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection(str(db_path))
    init_db(conn)

    try:
        agent = create_agent(conn, config)
    except Exception as e:
        print(f"Error initializing AI agent: {e}", file=sys.stderr)
        conn.close()
        return 1

    print("Diary AI Chat")
    print("Type 'quit' or 'exit' to leave.\n")

    try:
        while True:
            try:
                user_input = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if user_input.lower() in ("quit", "exit"):
                break
            if not user_input:
                continue

            try:
                result = agent(user_input)
                print()  # newline after streamed response
            except Exception as e:
                print(f"\nError: {e}\n", file=sys.stderr)
    finally:
        conn.close()

    return 0
