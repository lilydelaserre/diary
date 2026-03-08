import subprocess
import sys
import pytest


def run_diary(*args):
    """Run diary CLI and return the result."""
    return subprocess.run(
        [sys.executable, "-m", "diary.cli", *args],
        capture_output=True,
        text=True,
    )


class TestCliHelp:
    def test_help_exits_0(self):
        result = run_diary("--help")
        assert result.returncode == 0

    @pytest.mark.parametrize("subcommand", ["tui", "chat", "api", "notify", "install"])
    def test_subcommand_in_help(self, subcommand):
        result = run_diary("--help")
        assert subcommand in result.stdout

    def test_no_args_prints_help(self):
        result = run_diary()
        # Should print help or usage info
        assert result.returncode == 0 or "usage" in result.stderr.lower() or "usage" in result.stdout.lower()


class TestCliImplemented:
    def test_notify_no_args_shows_usage(self):
        result = run_diary("notify")
        assert result.returncode == 1
        assert "usage" in result.stderr.lower()

    def test_install_prints_instructions(self):
        result = run_diary("install")
        assert result.returncode == 0
        assert "diary" in result.stdout.lower()
