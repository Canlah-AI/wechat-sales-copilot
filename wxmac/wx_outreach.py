"""Personal one-to-one messages to existing WeChat contacts: drafted one by one, approved, sent at a human pace.

Usage:
  python3 -m wxmac.wx_outreach plan [--cats prospect,unknown]   queue classified contacts from the target categories
  python3 -m wxmac.wx_outreach draft --export 20                 write the next 20 for Claude Code to draft (default mode)
  python3 -m wxmac.wx_outreach draft --import drafts.jsonl       take the drafts back ({"i", "lang", "text"} per line)
  python3 -m wxmac.wx_outreach draft --n 20                      draft through the API instead ([llm] mode = "api")
  python3 -m wxmac.wx_outreach review                            list drafts waiting for approval
  python3 -m wxmac.wx_outreach approve --all | <i> [<i> ...]     mark drafts as approved to send
  python3 -m wxmac.wx_outreach reject <i> [<i> ...]              drop drafts (the contact is not messaged)
  python3 -m wxmac.wx_outreach optout "<chat name>"              never message this contact again
  python3 -m wxmac.wx_outreach send                              the paced sender (runs until stopped)
  python3 -m wxmac.wx_outreach status                            queue, today's sends, replies, opt-outs

Guard rails (all in config.toml [pacing] and [outreach]):
  - people only: the chat header must name the person, a group with the same name is refused; contacts whose
    display name is not unique are skipped (search could land on the wrong one), so are skip_tags and anyone who
    messaged you recently (they are mid-conversation, a cold intro would be odd)
  - approved drafts only (require_approval = true by default); a daily cap; sends only inside the time window, with
    random gaps and longer breaks; acts only while you have been away from the keyboard for idle_seconds
  - never the same contact twice: the ledger is checked before every send, also after a crash
  - a reply containing an opt-out word, or `optout`, removes the contact for good
  - any WeChat warning about your account (rate limit, restriction) pauses sending for pause_hours
Files: <data dir>/outreach/ (queue.jsonl, ledger.csv, optout.txt, sender.pid); screenshots in <data dir>/shots/send.
"""
import argparse, csv, datetime, json, os, random, re, sqlite3, subprocess, sys, time
from pathlib import Path

from . import config, llm
from .wx_send import Abort, UILock, ctl, idle_seconds, key, send

CONTACTS = config.DATA / "contacts"
OUT = config.DATA / "outreach"
QUEUE, LEDGER, OPTOUT, PID = OUT / "queue.jsonl", OUT / "ledger.csv", OUT / "optout.txt", OUT / "sender.pid"
SHOTS = config.DATA / "shots" / "send"
NOTIFY_DB = Path.home() / "Library/Group Containers/group.com.apple.usernoted/db2/db"
# WeChat telling you that YOUR account is limited: stop everything
WARNINGS = ("操作频繁", "频繁", "被限制", "功能限制", "限制使用", "restricted", "too frequent", "unable to send", "发送失败")
# the contact removed you: only this contact is affected
NOT_FRIEND = ("朋友验证", "拒收", "friend confirmation", "not his/her friend", "not your friend", "rejected")
# about the recipient's account, not yours: taken out before looking for WARNINGS
THEY_RESTRICTED = ("the user's account is restricted. unable to send message.", "the user's account is restricted",
                   "对方账号异常", "对方账号已被限制", "该用户账号", "对方帐号")


def P(name: str, default=None):
    return config.get("pacing", name, default)


def O(name: str, default=None):
    return config.get("outreach", name, default)


def now() -> datetime.datetime:
    return datetime.datetime.now()


def hm(s: str) -> datetime.time:
    return datetime.time(*map(int, s.split(":")))


def load_queue() -> list[dict]:
    return [json.loads(l) for l in QUEUE.open()] if QUEUE.exists() else []


def save_queue(q: list[dict]):
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = QUEUE.with_suffix(".tmp")
    tmp.write_text("".join(json.dumps(o, ensure_ascii=False) + "\n" for o in q))
    tmp.replace(QUEUE)


def notifications(days: int) -> list[tuple[str, datetime.datetime, str]]:
    """(normalised chat name, time, preview) of WeChat notifications in the last `days` days.
    Needs Full Disk Access for the app running this; without it the list is empty (no recent-chat filter,
    no reply count, no opt-out detection from replies)."""
    if not NOTIFY_DB.exists():
        return []
    import plistlib
    since = (now() - datetime.timedelta(days=days) - datetime.datetime(2001, 1, 1)).total_seconds()
    out = []
    try:
        con = sqlite3.connect(f"file:{NOTIFY_DB}?mode=ro", uri=True)
        found = con.execute("select r.data, r.delivered_date from record r join app a on a.app_id = r.app_id "
                            "where a.identifier = 'com.tencent.xinwechat' and r.delivered_date > ?", (since,)).fetchall()
    except sqlite3.Error:
        return []
    for data, d in found:
        try:
            req = plistlib.loads(data)["req"]
            out.append((key(req.get("titl", "")), datetime.datetime(2001, 1, 1) + datetime.timedelta(seconds=d),
                        req.get("body", "")))
        except Exception:
            pass
    return out


def optouts() -> set[str]:
    """Normalised chat names that must never be messaged again: the optout file, plus anyone whose reply after our
    message contains an opt-out word (those are appended to the file, so they stay after the notification expires)."""
    names = {l.strip() for l in OPTOUT.open()} if OPTOUT.exists() else set()
    words = [w.lower() for w in O("optout_words", [])]
    sent = {key(r["chat"]): datetime.datetime.fromisoformat(r["time"]) for r in ledger_rows() if r["status"].startswith("sent")}
    new = {k for k, t, body in notifications(14) if k in sent and t > sent[k] and any(w in body.lower() for w in words)}
    if new - names:
        OUT.mkdir(parents=True, exist_ok=True)
        with OPTOUT.open("a") as f:
            f.write("".join(k + "\n" for k in sorted(new - names)))
    return names | new


def shown(c: dict) -> str:
    """The name WeChat shows for a contact: your remark if you set one, else their nickname."""
    from .ui_strings import both
    return c["remark"] if c["remark"] and c["remark"] not in both("no_remark") else c["alias"]


def plan(cats: set[str]):
    contacts = [json.loads(l) for l in (CONTACTS / "all_contacts.jsonl").open()]
    cls = {o["i"]: o for o in map(json.loads, (CONTACTS / "classified.jsonl").open())}
    cards_f = CONTACTS / "cards.jsonl"
    cards = {o["i"]: o for o in map(json.loads, cards_f.open())} if cards_f.exists() else {}
    counts = {}
    for c in contacts:
        counts[key(shown(c))] = counts.get(key(shown(c)), 0) + 1
    q = load_queue()
    queued = {o["i"] for o in q}
    busy = {k for k, _, _ in notifications(30)}
    blocked = optouts()
    skip_tags = O("skip_tags", [])
    why = {}
    for i, c in enumerate(contacts):
        k = cls.get(i, {})
        reason = ("queued" if i in queued else "category" if k.get("cat") not in cats
                  else "skip tag" if any(t in c["tags"] for t in skip_tags)
                  else "name too short" if len(key(shown(c))) < 2 else "name not unique" if counts[key(shown(c))] > 1
                  else "opted out" if key(shown(c)) in blocked else "recent chat" if key(shown(c)) in busy else None)
        if reason:
            why[reason] = why.get(reason, 0) + 1
            continue
        card = cards.get(i, {})
        q.append({"i": i, "chat": shown(c), "alias": c["alias"], "remark": c["remark"], "tags": c["tags"],
                  "region": card.get("region", ""), "signature": card.get("signature", ""),
                  "source": card.get("source", ""), "added": card.get("added", ""), "wxid": card.get("weixin_id", ""),
                  "state": "queued"})
    save_queue(q)
    print(f"queue: {sum(1 for o in q if o['state'] == 'queued')} queued; skipped: {why}")


def listing(batch: list[dict]) -> str:
    return "\n".join(f"{o['i']}\t{o['alias']}\t{o['remark']}\t{o['region']}\t{o['signature']}\t"
                     f"{o['source']} {o['added'][:4]}" for o in batch)


def take_drafts(got: dict[int, dict]) -> int:
    q = load_queue()
    n = 0
    for o in q:
        d = got.get(o["i"])
        if d and d.get("text") and o["state"] == "queued":
            o.update(state="drafted", lang=d.get("lang", ""), text=d["text"].strip())
            n += 1
    save_queue(q)
    return n


def draft(n: int, export: bool, imp: Path | None):
    if imp:
        got = {o["i"]: o for o in map(json.loads, filter(str.strip, imp.open())) if "i" in o}
        print(f"took {take_drafts(got)} drafts from {imp}")
        return
    todo = [o for o in load_queue() if o["state"] == "queued"]
    todo = sorted(todo, key=lambda o: not (o["region"] or o["signature"] or o["source"]))[:n]  # card holders first
    if not todo:
        print("nothing queued: run plan first")
        return
    if export or not llm.api_mode():
        path = OUT / "drafts_todo.txt"
        path.write_text(config.prompt("draft") + listing(todo) + "\n", encoding="utf-8")
        print(f"{len(todo)} contacts written to {path}\nwrite one JSON line per contact to a file, then: "
              f"python3 -m wxmac.wx_outreach draft --import <file>")
        return
    client = llm.Client()
    got = {}
    for j in range(0, len(todo), 20):
        try:
            got.update({o["i"]: o for o in llm.json_lines(client.ask(config.prompt("draft") + listing(todo[j:j + 20])))
                        if isinstance(o.get("i"), int)})
        except RuntimeError as e:
            print(f"draft batch failed: {e}")
    print(f"drafted {take_drafts(got)}/{len(todo)}")


def review():
    for o in load_queue():
        if o["state"] == "drafted":
            print(f"[{o['i']}] {o['chat']}  ({o.get('lang', '')})\n    {o['text']}\n")


def mark(ids: list[str], all_: bool, state: str):
    q = load_queue()
    want = {int(i) for i in ids}
    n = 0
    for o in q:
        if o["state"] == "drafted" and (all_ or o["i"] in want):
            o["state"] = state
            n += 1
    save_queue(q)
    print(f"{n} marked {state}")


def ledger_rows() -> list[dict]:
    return list(csv.DictReader(LEDGER.open())) if LEDGER.exists() else []


def log_send(o: dict, status: str, note: str = ""):
    new = not LEDGER.exists()
    with LEDGER.open("a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["time", "i", "chat", "lang", "status", "text", "note"])
        w.writerow([now().isoformat(timespec="seconds"), o["i"], o["chat"], o.get("lang", ""), status, o.get("text", ""), note])


def warning_in(text: str) -> str | None:
    """A WeChat warning about YOUR account in what was read off the chat after sending; notices about the
    recipient's own account are taken out first."""
    text = text.lower()
    for t in THEY_RESTRICTED:
        text = text.replace(t.lower(), " ")
    return next((w for w in WARNINGS if w.lower() in text), None)


def send_loop():
    OUT.mkdir(parents=True, exist_ok=True)
    SHOTS.mkdir(parents=True, exist_ok=True)
    if PID.exists() and subprocess.run(["ps", "-p", PID.read_text().strip(), "-o", "command="],
                                       capture_output=True, text=True).stdout.strip().endswith("send"):
        sys.exit(f"a sender is already running (PID {PID.read_text().strip()}); two would fight over the screen")
    PID.write_text(str(os.getpid()))  # stop_sender stops exactly this process, never by name
    import atexit
    atexit.register(lambda: PID.unlink(missing_ok=True))
    window = tuple(hm(t) for t in P("window", ["09:00", "21:00"]))
    gap, brk, brk_every = P("gap_seconds", [60, 180]), P("break_seconds", [300, 900]), P("break_every", [15, 25])
    cap, idle_need = P("daily_cap", 40), P("idle_seconds", 30)
    want = "approved" if O("require_approval", True) else "drafted"
    card = Path(O("card_image")).expanduser() if O("card_image") else None
    stop_until, idle_msg, done_for, last_action = None, None, set(), 0.0
    run, run_len = 0, random.randint(*brk_every)

    def user_active() -> bool:  # real input since our own last event
        return idle_seconds() < min(idle_need, time.time() - last_action) - 1

    def say(msg: str):
        nonlocal idle_msg
        if msg != idle_msg:
            print(f"{now():%H:%M:%S} {msg}", flush=True)
            idle_msg = msg

    while True:
        t = now()
        today = t.date().isoformat()
        sent_today = sum(1 for r in ledger_rows() if r["time"].startswith(today) and r["status"].startswith("sent"))
        if stop_until and t < stop_until:
            say(f"paused after a WeChat warning until {stop_until:%m-%d %H:%M}")
            time.sleep(300)
            continue
        if not (window[0] <= t.time() <= window[1]) or sent_today >= cap:
            say(f"daily cap {cap} reached" if sent_today >= cap else f"outside {window[0]:%H:%M}-{window[1]:%H:%M}")
            if (P("screensaver_after_window", True) and t.time() > window[1] and today not in done_for
                    and idle_seconds() > 300 and ctl("locked").strip() != "1"):
                subprocess.run(["open", "-a", "ScreenSaverEngine"])  # done for the day: let the screen lock again
                done_for.add(today)
            time.sleep(300)
            continue
        q = load_queue()
        blocked = optouts()
        nxt = next((o for o in q if o["state"] == want and key(o["chat"]) not in blocked), None)
        if nxt is None:
            say(f"no {want} drafts left; draft and approve more (wx_outreach draft / approve)")
            time.sleep(300)
            continue
        if any(r["i"] == str(nxt["i"]) for r in ledger_rows() if r["status"].startswith("sent") or r["status"] == "error"):
            # already went out, or may have (an error can come after Send); aborts all happen before Send
            nxt["state"] = "sent"  # the ledger is the truth if the queue file was overwritten: never twice
            save_queue(q)
            continue
        if ctl("locked").strip() == "1" or (user_active() if last_action else idle_seconds() < idle_need):
            say("waiting for you to leave the keyboard (or for the screen to be unlocked)")
            time.sleep(10)
            continue
        idle_msg = None
        res = {}
        lock = UILock()
        lock.acquire()
        # search by the shown name; a short name drowns in partial matches and emoji break the search, so then try
        # the Weixin ID from the card (search matches it; automatic 'wxid_' ids are not searchable), then the name's
        # longest plain run
        runs = sorted(re.findall(r"[\w一-鿿]{2,}", nxt["chat"]), key=len, reverse=True)
        wxid = (nxt.get("wxid") or "").split("|")[0].strip()
        wxid = "" if wxid.startswith("wxid_") or len(wxid) < 4 else wxid
        for query in [x for x in dict.fromkeys([nxt["chat"], wxid, *runs[:1]]) if x]:
            try:
                res = send(nxt["chat"], nxt["text"], False, SHOTS, query, image=card, person=True)
            except Abort as e:
                res = {"status": "aborted", "reason": str(e)}
            except Exception as e:  # e.g. the window left the screen mid-send: skip this contact, keep the loop
                res = {"status": "error", "reason": f"{type(e).__name__}: {e}"}
            if res["status"] == "sent" or "no result" not in res.get("reason", ""):
                break
        last_action = time.time()
        screen = res.get("screen", "")
        if res["status"].startswith("sent") and any(w.lower() in screen.lower() for w in NOT_FRIEND):
            res["reason"] = "they removed you (friend confirmation shown)"
            res["status"] = "sent-not-friend"
        elif res["status"].startswith("sent") and any(w.lower() in screen.lower() for w in THEY_RESTRICTED):
            res["reason"] = "WeChat restricted the recipient's account; not delivered"
            res["status"] = "sent-not-friend"
        # text that went out but could not be read back still counts as sent: never message anyone twice
        nxt["state"] = "sent" if res["status"].startswith("sent") else "failed"
        log_send(nxt, res["status"], res.get("reason", ""))
        save_queue(q)
        sent_today += res["status"].startswith("sent")
        print(f"{now():%H:%M:%S} {res['status']}: #{nxt['i']} (today {sent_today}/{cap})", flush=True)
        for old in sorted(SHOTS.glob("*.png"), key=lambda p: p.stat().st_mtime)[:-30]:
            old.unlink()  # screenshots show private chats: keep only the latest few
        w = warning_in(screen)
        lock.release()
        if w:
            stop_until = now() + datetime.timedelta(hours=P("pause_hours", 24))
            log_send(nxt, "warning", f"WeChat showed '{w}'; paused")
            print(f"WARNING '{w}' on screen; pausing until {stop_until:%m-%d %H:%M}", flush=True)
            continue
        run += 1
        if run >= run_len:  # a person working through a list stops now and then
            run, run_len = 0, random.randint(*brk_every)
            time.sleep(random.uniform(*brk))
        else:
            time.sleep(random.uniform(*gap))


def status():
    q, rows = load_queue(), ledger_rows()
    by = {}
    for o in q:
        by[o["state"]] = by.get(o["state"], 0) + 1
    today = now().date().isoformat()
    sent = {key(r["chat"]): datetime.datetime.fromisoformat(r["time"]) for r in rows if r["status"].startswith("sent")}
    replied = {k for k, t, _ in notifications(60) if k in sent and t > sent[k]}
    print(f"queue {by}; sent today {sum(1 for r in rows if r['time'].startswith(today) and r['status'].startswith('sent'))}"
          f"/{P('daily_cap', 40)}; sent in all {len(sent)}; replied after our message {len(replied)}; "
          f"opted out {len(optouts())}")
    if not NOTIFY_DB.exists() or not notifications(60):
        print("replies: unreadable or none (needs Full Disk Access for the terminal app running this)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["plan", "draft", "review", "approve", "reject", "optout", "send", "status"])
    ap.add_argument("ids", nargs="*", help="contact numbers for approve / reject; the chat name for optout")
    ap.add_argument("--cats", help="comma-separated categories (default: [outreach] target_categories)")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--export", type=int, metavar="N", help="write N contacts for Claude Code to draft")
    ap.add_argument("--import", dest="imp", type=Path, help="JSON lines {i, lang, text} written by Claude Code")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.cmd == "plan":
        plan(set(a.cats.split(",")) if a.cats else set(O("target_categories", ["unknown"])))
    elif a.cmd == "draft":
        draft(a.export or a.n, a.export is not None, a.imp)
    elif a.cmd == "review":
        review()
    elif a.cmd in ("approve", "reject"):
        mark(a.ids, a.all, "approved" if a.cmd == "approve" else "rejected")
    elif a.cmd == "optout":
        with OPTOUT.open("a") as f:
            f.write("".join(key(n) + "\n" for n in a.ids))
        print(f"{len(a.ids)} added to {OPTOUT}")
    elif a.cmd == "send":
        send_loop()
    else:
        status()


if __name__ == "__main__":
    main()
