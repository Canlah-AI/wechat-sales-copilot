# wechat-sales-copilot

A sales copilot for **your own personal WeChat on macOS**, packaged as Claude Code skills.

It turns your address book into a lead sheet, drafts one-to-one messages in your voice, sends only what you approve at a
human pace, and tells you who replied. It drives the official WeChat for Mac app **from the outside**, the way a person
would: screenshots read with Apple's on-device OCR, synthetic keystrokes and clicks. No hooking, no injection, no
re-signing, no protocol emulation, no decryption of WeChat's database.

[中文说明](README.zh-CN.md)

> **Status: v0.1, early.** Used on WeChat for Mac 4.1.13 and 4.1.15 with an **English** interface. The Chinese
> interface is **untested** (the labels are in `wxmac/ui_strings.py`; please report what you see). macOS 13+ only.

## What it does

| Skill | What you say | What happens |
|---|---|---|
| `wechat-setup` | "set up WeChat", "wechat doctor" | builds the helpers, checks permissions, writes your persona, sizes the window, test-sends to File Transfer |
| `wechat-contacts` | "who in my WeChat could be a customer?" | scrolls Manage Contacts and reads every row, labels each contact (prospect, customer, investor... tier A/B/C), opens profile cards of the best leads, exports Excel. Read-only. |
| `wechat-outreach` | "introduce myself to the people I never talked to" | queues the right contacts, drafts a personal message for each, you approve, a paced sender delivers them one by one |
| `wechat-send` | "send Wren the deck" | one message, picture or file to one chat, verified on screen, dry run first |
| `wechat-inbox` | "who replied?" | reads WeChat notifications from macOS's notification store; never opens a chat, so unread marks stay |
| `wechat-ops` | "the WeChat window is wrong" | windows, lock screen, logout, after a WeChat update |

Drafting and labelling are done by Claude Code itself by default (no API key): the scripts write a work file, Claude
writes the drafts, the scripts read them back. For unattended runs you can switch to the Anthropic API in `config.toml`.

## How a message is sent

1. Wait until you have been away from the keyboard for 30 s; refuse if the screen is locked.
2. Bring WeChat forward, search the name, click a result **only under a chat section** (never web results).
3. The chat header must name **this person**: a group with the same name is refused.
4. Paste the text, click Send, and read the chat back to confirm the text is there; then the optional picture or file.
5. Restore your clipboard and the app you were using; append the result to the ledger.

Any mismatch aborts before Send. The details that make this work on a real account (OCR misreadings, popped-out chat
windows, a Send button read as "① Send", look-alike web results...) are in [docs/pitfalls.md](docs/pitfalls.md).

## Conservative by default

| Setting | Default |
|---|---|
| Messages per day | 40 |
| Gap between messages | 60–180 s, plus a 5–15 min break every 15–25 |
| Hours | 09:00–21:00 |
| Approval | every draft approved before it can be sent |
| Recipients | people only, one at a time; never groups |
| Never twice | the ledger is checked before every send, also after a crash |
| Opt-outs | a reply with "stop", "别再发"... removes the contact for good |
| WeChat warning | any warning about your account pauses sending for 24 h |

All of it is in `config.example.toml`.

## Install

In Claude Code (2.1.275+), one step:

```
/plugin install wechat-sales-copilot --marketplace Canlah-AI/wechat-sales-copilot
```

then ask Claude to "set up WeChat". By hand:

```bash
git clone https://github.com/Canlah-AI/wechat-sales-copilot && cd wechat-sales-copilot
./install.sh                 # builds bin/wxctl and bin/ocr (needs Xcode Command Line Tools), Python 3.11+
python3 -m wxmac.doctor      # tells you exactly which permission or setting is missing
```

Then give your terminal app **Accessibility** and **Screen Recording** (System Settings → Privacy & Security), and
optionally **Full Disk Access** for reading replies. Fill in `[persona]` in
`~/Library/Application Support/wechat-sales-copilot/config.toml`.


## Use it right

- **Your own account, people who know you.** This is for following up with your existing contacts, not for messaging
  strangers or buying lists.
- **WeChat's terms forbid automated operation of the app**, modified or not. The risk falls on your account, and it
  grows with the volume of similar messages to people who rarely talk to you. Keep the daily cap low.
- **Respect opt-outs** and say who you are in the first message.
- **Local laws apply to you.** For example, Singapore's Spam Control Act covers instant messages and treats 100+
  similar messages a day as bulk; personal-data laws (PDPA, PIPL) apply to profiling contacts. Not legal advice.
- **Your data stays on your Mac.** Contacts, drafts, the ledger and screenshots live in
  `~/Library/Application Support/wechat-sales-copilot/`. Drafting through the API sends the listed contact fields to
  Anthropic; host mode sends them to your Claude Code session. See [docs/privacy.md](docs/privacy.md).

## Prior art

Driving WeChat for Mac without injection is not new, and this project owes ideas to others working on it:

- [zbvxbb622-code/wechat-mcp-friend-automation](https://github.com/zbvxbb622-code/wechat-mcp-friend-automation): an
  MCP for Mac that adds friends from an Excel list with work hours, cool-downs, dedupe, a single-instance lock and a
  circuit breaker.
- [harrylabsj/wechat-social-assistant](https://github.com/harrylabsj/wechat-social-assistant): captures contacts by
  screenshot OCR, tags them with an LLM and writes personalised drafts per segment for a human to approve.
- [BiboyQG/WeChat-MCP](https://github.com/BiboyQG/WeChat-MCP): read and reply through macOS Accessibility.
- [cluic/wxauto](https://github.com/cluic/wxauto): UI Automation for WeChat on Windows.

What this project adds: the full path from the whole address book to labelled leads, approved one-to-one drafts, a
paced sender with a never-twice ledger and opt-out handling, and replies matched back to that ledger; all as skills.

## Roadmap

1. **Reply copilot**: sort replies by intent, draft answers in your voice from your own sent messages, approve on
   your phone, send through the same checks.
2. **Follow-ups**: one short nudge after N days without a reply, at most two or three, stop on any reply or opt-out.
3. **Contact cards and a daily "who to follow up today" list**, with a booking link when someone is interested.

Not planned: Moments auto-likes or comments, reading WeChat's database, fine-tuned "clones".

## Layout

```
skills/        six skills + shared/RULES.md
wxmac/         Python 3.11+: send, outreach, inbox, contacts capture / labels / cards / Excel, doctor
native/        wxctl.swift (keys, clicks, windows, pasteboard), ocr.swift (Apple Vision)
prompts/       draft.md, classify.md, filled from [persona] in config.toml
docs/          pitfalls, privacy, optional two-Mac setup
tests/         pure helpers over synthetic OCR fixtures: python3 -m unittest
```

## Disclaimer

Not affiliated with, endorsed by, or connected to Tencent. "WeChat" and "Weixin" are Tencent's trademarks.
Provided as-is under the Apache License 2.0; you are responsible for how you use it.
