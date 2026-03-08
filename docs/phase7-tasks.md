# Phase 7 — Tasks: Notifications + Zsh Hook + Install

## Tasks

### 1. NotificationService (`service/notifications.py`)
- check_and_send(type: "morning"|"evening") → checks notification_state table, sends if not already sent today
- Uses `terminal-notifier` for macOS notifications
- Click action: `open -a <terminal_app>` (from config)

### 2. Notify command (`notify.py`)
- `diary notify morning` / `diary notify evening`
- Calls NotificationService

### 3. Install command
- `diary install` prints:
  - Two launchd plist XMLs (morning + evening) with times from config
  - Zsh snippet for `.zshrc`
  - Instructions for the user

### 4. Wire into CLI
- `diary notify` and `diary install` call their implementations

### 5. Tests
- notification_state idempotency (send twice → only one record)
- install prints valid plist XML
- install prints zsh snippet

## Verification
- [x] `diary notify morning` sends notification (or no-ops if already sent)
- [x] `diary notify evening` same
- [x] notification_state prevents duplicates
- [x] `diary install` prints valid plists and zsh snippet
- [x] All tests pass (224 passed)
