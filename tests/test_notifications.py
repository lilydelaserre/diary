"""Tests for notification service, notify command, and install command."""
import subprocess
import sys
from datetime import date
from pathlib import Path
from unittest.mock import patch
import pytest

from diary.service.notifications import NotificationService


class TestNotificationService:
    def test_morning_not_sent_yet(self, db):
        svc = NotificationService(db, terminal_app="Warp")
        today = date.today().isoformat()
        assert svc.should_send("morning") is True

    def test_morning_marks_sent(self, db):
        svc = NotificationService(db, terminal_app="Warp")
        with patch("diary.service.notifications.subprocess.run"):
            svc.check_and_send("morning")
        assert svc.should_send("morning") is False

    def test_morning_idempotent(self, db):
        svc = NotificationService(db, terminal_app="Warp")
        with patch("diary.service.notifications.subprocess.run") as mock_run:
            svc.check_and_send("morning")
            svc.check_and_send("morning")
        # terminal-notifier called only once
        assert mock_run.call_count == 1

    def test_evening_independent(self, db):
        svc = NotificationService(db, terminal_app="Warp")
        with patch("diary.service.notifications.subprocess.run"):
            svc.check_and_send("morning")
        assert svc.should_send("evening") is True

    def test_sends_notification(self, db):
        svc = NotificationService(db, terminal_app="Warp")
        with patch("diary.service.notifications.subprocess.run") as mock_run:
            svc.check_and_send("morning")
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "terminal-notifier" in args
        assert "Diary" in args


class TestInstallCommand:
    def test_prints_plist(self):
        result = subprocess.run(
            [sys.executable, "-m", "diary.cli", "install"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "com.diary.notify.morning" in result.stdout
        assert "com.diary.notify.evening" in result.stdout
        assert "<?xml" in result.stdout

    def test_prints_zsh_snippet(self):
        result = subprocess.run(
            [sys.executable, "-m", "diary.cli", "install"],
            capture_output=True, text=True,
        )
        assert "diary api list" in result.stdout
        assert ".zshrc" in result.stdout
