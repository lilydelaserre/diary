from pathlib import Path
import tomllib
from pydantic import BaseModel


class DiaryConfig(BaseModel):
    morning_notification_time: str = "10:00"
    evening_notification_time: str = "18:00"
    workdays: list[str] = ["mon", "tue", "wed", "thu", "fri"]
    notifications_enabled: bool = True
    data_dir: str = "~/.local/share/diary"
    ai_model: str = "us.anthropic.claude-sonnet-4-20250514-v1:0"
    aws_profile: str | None = None
    aws_region: str | None = None
    terminal_app: str = "Warp"


def load_config(path: Path | str | None = None) -> DiaryConfig:
    """Load config from TOML file, merging with defaults. Returns defaults if file missing."""
    if path is None:
        path = Path("~/.config/diary/config.toml").expanduser()
    else:
        path = Path(path)

    if not path.exists():
        return DiaryConfig()

    with open(path, "rb") as f:
        data = tomllib.load(f)

    return DiaryConfig(**data)
