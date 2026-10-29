---
name: wechat-send
description: Send one WeChat message from the user's own WeChat for Mac to one person or one group - text, optionally followed by a picture or any file - or just open a chat to check it is the right one. Every step is verified on screen (search result in a chat section, chat header, text visible after sending) and it aborts before sending on any mismatch; a dry run goes first. Use for "send X a WeChat", "WeChat X that...", "微信发给", "帮我微信跟 X 说", "send this file to X on WeChat", "把这个文件发给", "message the group". Not for many contacts at a pace (wechat-outreach), reading replies (wechat-inbox), or setup problems (wechat-setup).
---

Read `../shared/RULES.md` first.

# Send one message

```bash
python3 -m wxmac.wx_send "<chat name>" "<text>" --person --dry-run        # 1. rehearse: stops before Send, clears the box
python3 -m wxmac.wx_send "<chat name>" "<text>" --person                  # 2. send
python3 -m wxmac.wx_send "<chat name>" "<text>" --person --image card.png # text, then a picture
python3 -m wxmac.wx_send "<chat name>" "<text>" --person --file deck.pdf  # text, then a file (or the file alone: omit the text)
python3 -m wxmac.wx_send "<chat name>" "<text>" --person --search "<Weixin ID>"  # when the name cannot be found
python3 -m wxmac.wx_send "<group name>" "<text>"                          # a group: no --person
python3 -m wxmac.wx_send "<chat name>" --open-only                        # open and check the header only
```

| Flag | Meaning |
|---|---|
| `--person` | 1:1 chat. A header with a member count ("Name (3)") is a group and is refused. Always use it for people. |
| `--dry-run` | Everything up to the Send button, then the input box is cleared. |
| `--image` / `--file` | Sent as their own message after the text. A file counts as sent only when its name shows in the chat. |
| `--search` | What to type into search when it differs from the shown name: a Weixin ID or part of the name. |
| `--open-only` | Opens the chat: **this clears its unread mark** (rule 6). |

Output is one JSON line; every attempt is appended to `sent.jsonl` in the data dir.

| status | meaning | exit |
|---|---|---|
| `sent` | text (and attachments) seen in the chat pane | 0 |
| `dry-run` / `opened` | rehearsal or check passed | 0 |
| `sent-unconfirmed` | Send was pressed but the text was not read back: look at the newest `shots/*-sent.png` before saying anything | 1 |
| `aborted` | stopped before Send; `reason` says why | 1 |

## Steps

1. **The chat name is what WeChat shows**: the user's remark if they set one, else the nickname.
2. **Check for duplicates** when the message is an introduction: `grep -F "<name>" "$HOME/Library/Application Support/wechat-sales-copilot/outreach/ledger.csv"`.
3. **Text**: the user's exact words when given. When you write it: their voice, short, no links unless given.
   Chinese for Chinese speakers unless told otherwise.
4. **Dry run first**, then send. File Transfer is always safe to test with.
5. **Report**: to whom, when, the exact text, the status. `aborted` → follow the reason:
   `no result reads exactly ...` → retry with `--search <Weixin ID>`; `chat header is ...` → wrong chat, check the
   name; `screen locked` → ask the user to unlock; `user is typing` → the user is at the keyboard, try again later.

Never loop this script over a list of people: that is wechat-outreach, which has pacing, a ledger and approval.
