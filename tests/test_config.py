import pytest
from diary.config import DiaryConfig, load_config


class TestDiaryConfigDefaults:
    def test_all_defaults(self):
        config = DiaryConfig()
        assert config.morning_notification_time == "10:00"
        assert config.evening_notification_time == "18:00"
        assert config.workdays == ["mon", "tue", "wed", "thu", "fri"]
        assert config.notifications_enabled is True
        assert config.data_dir == "~/.local/share/diary"
        assert config.ai_model == "us.anthropic.claude-sonnet-4-20250514-v1:0"
        assert config.terminal_app == "Warp"

    @pytest.mark.parametrize(
        "field,default_value",
        [
            ("morning_notification_time", "10:00"),
            ("evening_notification_time", "18:00"),
            ("workdays", ["mon", "tue", "wed", "thu", "fri"]),
            ("notifications_enabled", True),
            ("data_dir", "~/.local/share/diary"),
            ("ai_model", "us.anthropic.claude-sonnet-4-20250514-v1:0"),
            ("terminal_app", "Warp"),
        ],
    )
    def test_individual_defaults(self, field, default_value):
        config = DiaryConfig()
        assert getattr(config, field) == default_value


class TestLoadConfig:
    def test_no_file_returns_defaults(self, tmp_path):
        config = load_config(tmp_path / "nonexistent.toml")
        assert config == DiaryConfig()

    def test_partial_toml_merges_with_defaults(self, tmp_config):
        tmp_config.write_text('morning_notification_time = "09:00"\n')
        config = load_config(tmp_config)
        assert config.morning_notification_time == "09:00"
        assert config.evening_notification_time == "18:00"  # default preserved

    def test_full_toml_overrides_all(self, tmp_config):
        tmp_config.write_text(
            'morning_notification_time = "08:00"\n'
            'evening_notification_time = "17:00"\n'
            'workdays = ["mon", "tue", "wed"]\n'
            "notifications_enabled = false\n"
            'data_dir = "/tmp/diary"\n'
            'ai_model = "some-other-model"\n'
            'terminal_app = "iTerm"\n'
        )
        config = load_config(tmp_config)
        assert config.morning_notification_time == "08:00"
        assert config.evening_notification_time == "17:00"
        assert config.workdays == ["mon", "tue", "wed"]
        assert config.notifications_enabled is False
        assert config.data_dir == "/tmp/diary"
        assert config.ai_model == "some-other-model"
        assert config.terminal_app == "iTerm"
