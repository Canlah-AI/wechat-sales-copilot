"""Read new WeChat messages from the macOS notification store without touching WeChat.

Usage: python3 -m wxmac.wx_inbox [--since-file PATH] [--limit N] [--follow SECONDS]
Prints one JSON object per notification: {"ts", "chat", "body", "id"}.
Only messages that raised a banner are visible (chat not focused, notifications on, preview on), and the
terminal app running this needs Full Disk Access (System Settings > Privacy & Security). WeChat is never touched,
so unread marks stay as they are.
"""
import argparse, datetime, json, plistlib, sqlite3, sys, time
from pathlib import Path

DB = Path.home() / "Library/Group Containers/group.com.apple.usernoted/db2/db"
EPOCH = datetime.datetime(2001, 1, 1, tzinfo=datetime.timezone.utc)


def fetch(after: float, limit: int):
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        rows = con.execute(
            """select r.rec_id, r.delivered_date, r.data from record r join app a on a.app_id = r.app_id
               where a.identifier = 'com.tencent.xinwechat' and r.delivered_date > ?
               order by r.delivered_date asc limit ?""",
            (after, limit),
        ).fetchall()
    finally:
        con.close()
    for rec_id, ts, data in rows:
        req = plistlib.loads(data).get("req", {})
        yield ts, {
            "id": rec_id,
            "ts": (EPOCH + datetime.timedelta(seconds=ts)).astimezone().isoformat(timespec="seconds"),
            "chat": req.get("titl", ""),
            "body": req.get("body", ""),
        }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since-file", type=Path, help="remembers the last delivered_date seen")
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--follow", type=float, default=0, help="poll every N seconds")
    a = ap.parse_args()
    after = float(a.since_file.read_text()) if a.since_file and a.since_file.exists() else 0.0
    while True:
        for ts, row in fetch(after, a.limit):
            print(json.dumps(row, ensure_ascii=False), flush=True)
            after = ts
        if a.since_file:
            a.since_file.write_text(str(after))
        if not a.follow:
            break
        time.sleep(a.follow)


if __name__ == "__main__":
    sys.exit(main())
