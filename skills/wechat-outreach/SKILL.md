---
name: wechat-outreach
description: Personal one-to-one messages from the user's own WeChat to many existing contacts - each drafted for that person in the user's voice, approved by the user, then sent at a human pace with a daily cap, a ledger that never messages anyone twice, automatic stop on opt-out replies and a pause on any WeChat warning. Also starts, stops and reports on the sender. Use for "reach out to my WeChat contacts", "introduce myself to everyone I never talked to", "微信外联", "给通讯录里的人发介绍", "how is the WeChat outreach going", "stop the WeChat sender". Not for one message (wechat-send) or labelling contacts (wechat-contacts, which must run first).
---

Read `../shared/RULES.md` first. Data: `~/Library/Application Support/wechat-sales-copilot/outreach/`.

# Paced one-to-one outreach

## Before the first campaign

- Contacts captured and labelled (wechat-contacts), `[persona]` filled, File Transfer test passed (wechat-setup).
- Tell the user once, plainly: WeChat's terms forbid automated operation; the risk is to their own account, and it
  grows with volume of similar messages to people who rarely talk to them. The defaults (40 a day, 60–180 s apart,
  09:00–21:00, approval first) are deliberately conservative. Keep them unless the user explicitly decides otherwise.

## 1. Queue

```bash
python3 -m wxmac.wx_outreach plan                      # target_categories from config, e.g. unknown or prospect
python3 -m wxmac.wx_outreach plan --cats prospect
```

Skipped automatically: names shared by several contacts, `skip_tags`, opted-out contacts, anyone who messaged in
the last 30 days (needs Full Disk Access to know).

## 2. Draft (you write them)

```bash
python3 -m wxmac.wx_outreach draft --export 20         # writes outreach/drafts_todo.txt: instructions + 20 contacts
```

Read `drafts_todo.txt` and follow it exactly: only the persona's facts, the contact's private remark never quoted,
varied wording, the length limits. Write one line per contact `{"i": <number>, "lang": "zh"|"en", "text": "..."}`
to a file, then:

```bash
python3 -m wxmac.wx_outreach draft --import /path/to/drafts.jsonl
```

With `[llm] mode = "api"`, `draft --n 20` drafts through the API instead.

## 3. Approve

```bash
python3 -m wxmac.wx_outreach review                    # show drafts
python3 -m wxmac.wx_outreach approve 12 15 31          # or: approve --all
python3 -m wxmac.wx_outreach reject 18
```

Show the user the drafts before approving, unless they told you to approve on their behalf. Before the first
campaign, show 10 and wait for their verdict.

## 4. Send

The sender must run in the user's terminal app (it needs that app's permissions), in its own tab or window:

```bash
python3 -m wxmac.wx_outreach send        # runs until stopped; logs one line per message
python3 -m wxmac.stop_sender             # stops it between two messages (takes the UI lock, kills the recorded PID)
```

Per message: search → the header must name this person (never a group) → paste → Send → read back → optional card
image. It acts only while the user is away from the keyboard, inside the window, under the daily cap.

| Outcome | Ledger status | Effect |
|---|---|---|
| delivered | `sent` | never messaged again |
| "friend confirmation" / rejected | `sent-not-friend` | they removed the user; counted, never retried |
| recipient's account restricted | `sent-not-friend` | about them, not the user |
| stopped before Send | `aborted` | stays failed; fix the cause before re-queueing |
| WeChat warning about the user's account | `warning` | sending paused for `pause_hours`; tell the user, do not resume early |

## 5. Status

```bash
python3 -m wxmac.wx_outreach status
```

Report: sent today vs cap, total sent, removed-by-contact, aborted, replies (or "unreadable" without Full Disk
Access), opt-outs, how many approved drafts are left.

## Opt-outs

Replies containing an `optout_words` entry put the contact on `optout.txt` for good. Add someone by hand with
`python3 -m wxmac.wx_outreach optout "<chat name>"`. Never message an opted-out contact, not even when asked to
re-run a campaign.
