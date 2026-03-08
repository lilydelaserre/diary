"""diary install — print launchd plists and zsh snippet."""
import sys
from diary.config import load_config


PLIST_TEMPLATE = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.diary.notify.{notify_type}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{diary_path}</string>
        <string>notify</string>
        <string>{notify_type}</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>{hour}</integer>
        <key>Minute</key>
        <integer>{minute}</integer>
    </dict>
</dict>
</plist>"""

ZSH_SNIPPET = """\
# Diary — daily task summary on new terminal
if command -v diary &> /dev/null; then
  diary api list --scheduled today --format brief 2>/dev/null
fi"""


def run() -> int:
    config = load_config()

    # Find diary executable
    import shutil
    diary_path = shutil.which("diary") or "diary"

    morning_h, morning_m = config.morning_notification_time.split(":")
    evening_h, evening_m = config.evening_notification_time.split(":")

    print("=" * 60)
    print("DIARY INSTALL INSTRUCTIONS")
    print("=" * 60)

    print("\n--- Morning launchd plist ---")
    print(f"Save to: ~/Library/LaunchAgents/com.diary.notify.morning.plist\n")
    print(PLIST_TEMPLATE.format(
        notify_type="morning", diary_path=diary_path,
        hour=int(morning_h), minute=int(morning_m),
    ))

    print(f"\n--- Evening launchd plist ---")
    print(f"Save to: ~/Library/LaunchAgents/com.diary.notify.evening.plist\n")
    print(PLIST_TEMPLATE.format(
        notify_type="evening", diary_path=diary_path,
        hour=int(evening_h), minute=int(evening_m),
    ))

    print("\nLoad them with:")
    print("  launchctl load ~/Library/LaunchAgents/com.diary.notify.morning.plist")
    print("  launchctl load ~/Library/LaunchAgents/com.diary.notify.evening.plist")

    print("\n--- Zsh snippet ---")
    print(f"Add to ~/.zshrc:\n")
    print(ZSH_SNIPPET)

    print("\n" + "=" * 60)
    return 0
