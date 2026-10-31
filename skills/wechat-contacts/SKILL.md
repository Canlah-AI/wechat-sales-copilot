---
name: wechat-contacts
description: Turn the user's WeChat address book into a lead sheet. Captures every contact (nickname, remark, tags) by scrolling the Manage Contacts table and reading it with OCR, labels each one with a category and tier (prospect, customer, partner, investor, peer, friend, consumer, unknown; A/B/C), optionally opens the profile cards of the best leads from the Contacts tab to add region, signature, how and when they were added, and exports an Excel workbook. Read-only - no message is sent, no chat opened. Use for "who in my WeChat could be a customer", "export my WeChat contacts", "微信通讯录整理", "找潜在客户", "wechat leads". Not for messaging them (wechat-outreach).
---

Read `../shared/RULES.md` first.

# From address book to lead sheet

All output goes to `~/Library/Application Support/wechat-sales-copilot/contacts/`.

## 1. Capture (slow, unattended, read-only)

The user opens WeChat → Contacts → **Manage Contacts** and leaves that window open. Then:

```bash
python3 -m wxmac.wx_contacts_dump --idle 60
```

It acts only after 60 s without mouse or keyboard input and pauses the moment the user comes back, resuming from
the same row. It only scrolls: **never click a row in that table** (RULES 5). About 6,000 contacts take a few hours
of idle time. Output `all_contacts.jsonl`; progress in `dump.log`. Chinese interface: unverified (table header names
come from `wxmac/ui_strings.py`); if it stops with "table header not found", check `[ui] language`.

## 2. Label

Default (no API key): you, Claude, do the labelling.

```bash
python3 -m wxmac.wx_contacts_classify --export 120     # writes contacts/classify_todo.txt: instructions + 120 contacts
```

Read `classify_todo.txt`, follow its instructions exactly, write one JSON line per contact to a file, then:

```bash
python3 -m wxmac.wx_contacts_classify --import /path/to/labels.jsonl
```

Repeat until everything is labelled. With `[llm] mode = "api"` and a key, `--api` does it all in one go.

## 3. Cards for the best leads (optional, slow)

```bash
python3 -m wxmac.wx_contacts_cards --tiers A,B --cats customer
```

Opens profile cards from the Contacts tab (never a chat, so unread marks are safe). Before starting, the user folds
Saved Groups / Official Accounts / WeCom Contacts in that list; the script stops if they are expanded. It stays out
of the way while the outreach sender runs.

## 4. Excel

```bash
python3 -m wxmac.wx_contacts_excel --out ~/Desktop/wechat-leads.xlsx
```

Sheets: Read me, Leads A+B, Customers, Investors, Peers & partners, All contacts, Lead mix.

## Report

Counts per category and tier, the top industries and regions among A+B, the file path. Never paste contact names
into anything shared outside this Mac.
