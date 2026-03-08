"""Tests for agent setup and chat REPL wiring."""
import subprocess
import sys
from pathlib import Path
import pytest
from diary.agent.agent import create_agent, SYSTEM_PROMPT
from diary.config import DiaryConfig


class TestCreateAgent:
    def test_creates_agent_with_tools(self, db):
        agent = create_agent(db)
        tool_names = set(agent.tool_registry.get_all_tools_config().keys())
        expected = {
            "list_tasks", "show_task", "create_task", "update_task",
            "add_log_entry", "archive_task", "unarchive_task",
            "list_tags", "get_summary",
        }
        assert expected == tool_names

    def test_no_delete_edit_tools(self, db):
        agent = create_agent(db)
        tool_names = set(agent.tool_registry.get_all_tools_config().keys())
        assert "delete_entry" not in tool_names
        assert "edit_entry" not in tool_names

    def test_system_prompt_set(self, db):
        agent = create_agent(db)
        assert agent.system_prompt is not None
        # Check it contains key instructions
        prompt_text = str(agent.system_prompt)
        assert "confirmation" in prompt_text.lower()

    def test_uses_config_model(self, db):
        config = DiaryConfig(ai_model="us.anthropic.claude-sonnet-4-20250514-v1:0")
        agent = create_agent(db, config)
        assert agent is not None


class TestChatIntegration:
    def test_chat_starts_and_exits(self, tmp_path):
        """diary chat should start, print banner, and exit on 'quit'.

        This test mocks the agent to avoid needing AWS credentials.
        """
        # Write a small script that patches the agent and runs chat
        script = tmp_path / "run_chat.py"
        script.write_text(
            "import sys; sys.path.insert(0, 'src')\n"
            "from unittest.mock import patch, MagicMock\n"
            "mock_agent = MagicMock()\n"
            "with patch('diary.chat.create_agent', return_value=mock_agent):\n"
            "    from diary.chat import run\n"
            "    sys.exit(run())\n"
        )
        result = subprocess.run(
            [sys.executable, str(script)],
            input="quit\n",
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(Path(__file__).parent.parent),
        )
        assert "Diary AI Chat" in result.stdout
        assert result.returncode == 0
