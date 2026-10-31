---
name: wechat-setup
description: First-time setup and health check for driving WeChat for Mac. Builds the native helpers, walks the user through the macOS permissions (Accessibility, Screen Recording, optional Full Disk Access), creates config.toml with their persona, sizes the WeChat window and runs a dry-run send to File Transfer. Use when the user installs the plugin, says "set up wechat", "wechat doctor", "why doesn't the wechat skill work", "permissions for wechat", or when any wechat-* command fails with blank screenshots, dropped clicks, "screen locked" or "main window did not appear". Not for sending (wechat-send) or campaigns (wechat-outreach).
---

Read `../shared/RULES.md` first.

# Set up and check

## 1. Build and run the doctor

```bash
./install.sh                 # builds bin/wxctl and bin/ocr, installs Pillow + openpyxl, creates config.toml
python3 -m wxmac.doctor      # read-only checklist with the fix for each failing item
```

Fix items top to bottom; rerun the doctor after each.

## 2. Permissions (only the user can grant these)

Grants belong to the app that runs the commands (Terminal, iTerm, or the app hosting Claude Code), not to the scripts.
Tell the user exactly where to click; you cannot do it for them:

| Permission | Where | Needed for |
|---|---|---|
| Accessibility | System Settings → Privacy & Security → Accessibility → turn on the terminal app | keys and clicks |
| Screen Recording | System Settings → Privacy & Security → Screen Recording → turn on the terminal app | reading the screen |
| Full Disk Access (optional) | System Settings → Privacy & Security → Full Disk Access → turn on the terminal app | replies, opt-outs from replies |

After granting, the terminal app must be restarted. Without Screen Recording, screenshots come back as the desktop
only and every name "does not match": that is the commonest first failure.

## 3. Config

`~/Library/Application Support/wechat-sales-copilot/config.toml` (created from `config.example.toml`).
Ask the user for: their name as contacts know them, company, one-line description, a few facts drafts may use, who
buys from them, what their WeChat tags mean. Fill `[persona]` and `[classify]`. Set `[ui] language` to the WeChat
interface language: `en` is tested; with `zh`, sending is tested but contacts capture is **unverified** (say so; run
`python3 -m wxmac.doctor --ocr` to confirm the language on screen). Leave `[pacing]` at the defaults unless the user insists.

## 4. Calibrate the window

```bash
bin/wxctl fit                # main window to the top-left, 1300 wide, full height
bin/wxctl windows            # any extra window titles are popped-out chats: bin/wxctl close-window "<title>"
```

The layout constants in `wxmac/wx_send.py` (`LIST_RIGHT`, `INPUT_TOP`, `PHONE_ICON`) assume this default layout.

## 5. First send, to yourself

```bash
python3 -m wxmac.wx_send "File Transfer" "setup test" --dry-run
python3 -m wxmac.wx_send "File Transfer" "setup test"
```

Both must print `dry-run` then `sent`. On a Chinese interface the chat is "文件传输助手". If it aborts, read the
`reason` and `docs/pitfalls.md`, and look at the newest screenshot in the data dir's `shots/`.

## Keeping it healthy

- The screen must stay unlocked while sending. The sender acts only when the user is away from the keyboard, so a
  short screen-saver delay plus "require password immediately" will lock it mid-run. Tell the user the trade-off;
  changing lock settings is their call.
- After a WeChat update, rerun the doctor and the File Transfer test before any campaign.
