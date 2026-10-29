---
name: wechat-ops
description: Keep WeChat for Mac in a state the scripts can drive - see what is on screen, list, resize and close WeChat windows, handle a locked screen, a logout or a WeChat update, and use the low-level wxctl primitives. Use for "WeChat window is wrong", "what is on the WeChat screen", "wechat logged out", "close that popped-out chat", "wxctl", or when sends start aborting in a row. Not for first-time setup or permissions (wechat-setup).
---

Read `../shared/RULES.md` first.

# Operations

```bash
bin/wxctl windows                 # every WeChat window and its size (main window: Weixin / 微信 / WeChat)
bin/wxctl win                     # main window position {x, y, w, h, scale}
bin/wxctl fit                     # main window to the top-left, 1300 wide, full height
bin/wxctl close-window "<title>"  # close a popped-out chat window (refuses the main window)
bin/wxctl locked                  # 1 = screen locked
bin/wxctl perms                   # which grants this terminal app has
```

All subcommands are listed at the top of `native/wxctl.swift`. Only window-level Accessibility works on WeChat 4.x;
chat content is invisible to Accessibility, so content is always read from screenshots.

To see the screen: `screencapture -x /tmp/wechat.png` and look at it (it shows private chats: keep it local, delete
it after).

## When sends start failing

| Symptom | Do |
|---|---|
| several `aborted` in a row | `bin/wxctl windows`: a popped-out chat window or a shrunken main window; `close-window`, then `fit` |
| `screen locked` | ask the user to unlock; nothing types into a lock screen |
| QR code or "Log In" on screen | logged out: stop the sender (`python3 -m wxmac.stop_sender`) and ask the user to scan with their phone |
| `main window did not appear` | WeChat not running, or the window is off screen: `bin/wxctl activate`, then `fit`; never reinstall, re-sign or start a second copy |
| a warning in the sender log | the sender already paused; tell the user with the exact words; do not resume early |
| everything "does not match" after a WeChat update | UI words or layout changed: rerun `python3 -m wxmac.doctor --ocr`, compare the screen with `wxmac/ui_strings.py` and the constants in `wx_send.py`, see `docs/pitfalls.md` |

## After changing the Swift sources

```bash
./install.sh                       # rebuilds bin/wxctl and bin/ocr
```

A running sender keeps the old Python code: stop it with `stop_sender` and start it again.
