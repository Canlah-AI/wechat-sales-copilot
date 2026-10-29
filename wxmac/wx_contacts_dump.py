"""Read every row of WeChat's Manage Contacts table (alias, remark, tags) by scrolling and OCR, like a person paging through.

Usage: python3 -m wxmac.wx_contacts_dump [--out <data dir>/contacts/all_contacts.jsonl] [--idle 60]

Before running, open WeChat > Contacts > Manage Contacts (the table window) and leave it open.
Read-only: never clicks a row (a click in that table SELECTS the contact and offers Delete), never opens a chat,
never types. Only scroll-wheel events over the table.
  - runs only while the user has been idle >= --idle seconds; the moment they touch the mouse or keyboard it
    stops acting, leaves their window alone, and resumes from the same row once they are idle again
  - rows are found by their avatar, so a row whose name OCR cannot read (one letter, emoji only) still counts
  - each page must overlap rows already collected; if it does not, it works out whether it is behind or ahead
    of the collected rows and scrolls that way, so no row is skipped or counted twice
  - stops when two scrolls in a row add nothing (end of list)
Progress is appended to the output file and logged to dump.log next to it; rerunning resumes from the last rows.
"""
import argparse, datetime, difflib, json, random, subprocess, sys, time
from pathlib import Path

from PIL import Image

from . import config
from .ui_strings import ui
from .wx_send import WECHAT, Abort, ctl, idle_seconds, norm

TITLE = ui("manage_contacts")
HEAD = ui("table")  # column headers: remark, tags, privacy, and the 'All (N)' filter
STEP = 460  # scroll units per page turn; one unit moves 1.5 pt, so ~12 of the ~20 visible 58-pt rows
AVATAR_X = (266, 296)  # avatar column in window points
FIELDS = ("alias", "remark", "tags")


def log(msg: str, logf: Path):
    line = f"{datetime.datetime.now():%H:%M:%S} {msg}"
    print(line, flush=True)
    with logf.open("a") as f:
        f.write(line + "\n")


def avatar_rows(png: Path, scale: float, text_ys: list[float]) -> list[float]:
    """Centre y (window points) of every fully visible row: avatars and name text anchor a fixed row grid."""
    im = Image.open(png).convert("RGB")
    bg = im.getpixel((im.width - int(60 * scale), im.height // 2))
    x0, x1 = (int(v * scale) for v in AVATAR_X)

    def ink(y: int) -> bool:
        return any(sum(abs(a - b) for a, b in zip(im.getpixel((x, y)), bg)) > 40 for x in range(x0, x1, 2))

    centres, start = [], None
    for y in range(int(95 * scale), im.height - 2):
        if ink(y):
            start = y if start is None else start
        elif start is not None:
            if 20 * scale <= y - start <= 40 * scale:
                centres.append((start + y) / 2 / scale)
            start = None
    # avatars further down load lazily and can still be blank; the name text marks those rows
    for t in text_ys:
        if all(abs(t - c) > 12 for c in centres):
            centres.append(t)
    centres.sort()
    if len(centres) < 2:
        return centres
    # rows sit on a fixed grid; an avatar that is mostly white can be missed, so fill every slot of the grid
    # between the first and last avatar, plus slots beyond them that still show some ink (a partial page end)
    gaps = sorted(b - a for a, b in zip(centres, centres[1:]) if 50 < b - a < 66)
    pitch = gaps[len(gaps) // 2] if gaps else 58.0
    slots, y = [], centres[0]
    while y - pitch >= 95 + 24:
        y -= pitch
    while y <= im.height / scale - 26:
        near = min(centres, key=lambda c: abs(c - y))
        y = near if abs(near - y) < 8 else y  # follow the detected avatars so rounding does not drift
        lo, hi = int((y - 14) * scale), int((y + 14) * scale)
        if centres[0] - 1 <= y <= centres[-1] + 1 or any(ink(v) for v in range(lo, hi, 2)):
            slots.append(y)
        y += pitch
    return slots


TOTAL = [0]  # contact count from the 'All (N)' filter, read off the first page


def page(shots: Path) -> tuple[dict, list[dict]]:
    """OCR the table; return (window, fully visible rows top to bottom as {y, alias, remark, tags})."""
    w = json.loads(ctl("win", TITLE))
    png = shots / "page.png"
    subprocess.run(["screencapture", "-x", f"-R{int(w['x'])},{int(w['y'])},{int(w['w'])},{int(w['h'])}", str(png)],
                   check=True)
    s = w["scale"]
    lines = []
    for raw in subprocess.run([str(config.BIN / "ocr"), str(png)], capture_output=True, text=True, check=True).stdout.splitlines():
        r = json.loads(raw)
        lines.append({"t": r["text"].strip(), "x": r["x"] / s, "y": (r["y"] + r["h"] / 2) / s})
    head = {norm(l["t"]): l for l in lines if l["y"] < 90}
    for k in head:
        if k.startswith(HEAD["all"]) and any(ch.isdigit() for ch in k):
            TOTAL[0] = int("".join(ch for ch in k if ch.isdigit()))
    if not all(HEAD[k] in head for k in ("remark", "tags")):
        raise Abort(f"table header not found: {sorted(head)[:8]} (is [ui] language right?)")
    remark_x, tags_x = head[HEAD["remark"]]["x"] - 10, head[HEAD["tags"]]["x"] - 10
    privacy_x = head[HEAD["privacy"]]["x"] - 30 if HEAD["privacy"] in head else w["w"] - 120
    text_ys = [l["y"] for l in lines if 95 + 20 < l["y"] < w["h"] - 20 and AVATAR_X[1] <= l["x"] < remark_x]
    rows = [{"y": y, "alias": "", "remark": "", "tags": ""} for y in avatar_rows(png, s, text_ys)]
    for l in sorted(lines, key=lambda l: l["x"]):
        if l["y"] < 95 or l["x"] < AVATAR_X[1] or l["x"] >= privacy_x:
            continue
        near = min(rows, key=lambda r: abs(r["y"] - l["y"]), default=None)
        if near and abs(near["y"] - l["y"]) < 22:
            col = "alias" if l["x"] < remark_x else "remark" if l["x"] < tags_x else "tags"
            near[col] = (near[col] + " " + l["t"]).strip()
    return w, rows


def same(a: dict, b: dict) -> bool:
    ka, kb = (norm("|".join(r[k] for k in FIELDS)) for r in (a, b))
    return ka == kb or difflib.SequenceMatcher(None, ka, kb).ratio() >= 0.85


def blank(r: dict) -> bool:
    return not any(r[k] for k in FIELDS)


def align(collected: list[dict], rows: list[dict]) -> tuple[str, int]:
    """('ok', i): rows[i:] are new. ('behind', 0): page is above the collected end. ('ahead', 0): rows were skipped."""
    tail = collected[-300:]
    for back in range(min(8, len(tail) - 1)):  # anchor on a collected row and its predecessor, both readable
        t0, t1 = tail[-2 - back], tail[-1 - back]
        if blank(t0) or blank(t1):
            continue
        for i in range(len(rows) - 1, 0, -1):
            if same(rows[i], t1) and same(rows[i - 1], t0):
                return "ok", i + 1 + back
    known = sum(1 for r in rows if not blank(r) and any(same(r, t) for t in tail))
    return ("behind", 0) if known >= max(2, len([r for r in rows if not blank(r)]) // 2) else ("ahead", 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=config.DATA / "contacts" / "all_contacts.jsonl")
    ap.add_argument("--idle", type=float, default=60, help="seconds of user idleness before acting")
    a = ap.parse_args()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    logf = a.out.parent / "dump.log"
    collected = [json.loads(l) for l in a.out.open()] if a.out.exists() else []
    log(f"start, {len(collected)} rows already collected", logf)

    last_action, empty_pages, prev_front = 0.0, 0, None
    at_top = bool(collected)  # a fresh run starts from the top of the list
    while True:
        if ctl("locked").strip() == "1":
            log("screen locked; waiting", logf)
            time.sleep(60)
            continue
        # the user is active if their idle time is shorter than the time since our own last event
        if idle_seconds() < min(a.idle, time.time() - last_action) - 1:
            if prev_front is not None:
                log("user is back; pausing", logf)
                prev_front = None
            time.sleep(15)
            continue
        if prev_front is None or ctl("front").strip() != WECHAT:
            if idle_seconds() < a.idle:  # (re)take the stage only once the user has been idle long enough
                prev_front = None
                time.sleep(5)
                continue
            prev_front = ctl("front").strip()
            ctl("activate")
            subprocess.run(["osascript", "-e", f'tell application "System Events" to tell process "WeChat" to '
                            f'perform action "AXRaise" of window "{TITLE}"'], capture_output=True)
            time.sleep(1.0)
            last_action = time.time()
            log("took the stage", logf)

        try:
            w, rows = page(a.out.parent)
        except Abort as e:  # something covers the table: wait for the next idle stretch
            log(f"table not readable ({e}); retaking the stage later", logf)
            prev_front = None
            time.sleep(10)
            continue
        cx, cy = str(w["x"] + w["w"] / 2), str(w["y"] + w["h"] / 2)

        def scroll(units: int):
            nonlocal last_action
            ctl("scroll", cx, cy, str(units))
            last_action = time.time()

        if not at_top:
            first = rows[0] if rows else None
            scroll(4000)
            time.sleep(1.2)
            _, again = page(a.out.parent)
            at_top = bool(again) and first is not None and same(again[0], first)
            continue
        if collected:
            state, i = align(collected, rows)
            if state != "ok":
                log(f"page is {state} of the collected rows; scrolling {'down' if state == 'behind' else 'back up'}", logf)
                scroll(-STEP if state == "behind" else STEP)
                time.sleep(1.0)
                continue
            new = rows[i:]
        else:
            new = rows
        fresh = [{k: r[k] for k in FIELDS} for r in new]
        with a.out.open("a") as f:
            for r in fresh:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        if len(collected) // 250 != (len(collected) + len(fresh)) // 250:
            log(f"{len(collected) + len(fresh)} rows", logf)
        collected += fresh
        empty_pages = 0 if fresh else empty_pages + 1
        if empty_pages >= 2 and len(collected) >= 0.98 * TOTAL[0]:
            log(f"end of list: {len(collected)} rows of {TOTAL[0]}", logf)
            break
        if empty_pages >= 2:  # not at the end yet: give lazy-loading rows time, then keep going
            log(f"no new rows at {len(collected)} of {TOTAL[0]}; waiting for the table to load", logf)
            time.sleep(4)
        if empty_pages >= 12:
            log(f"stuck at {len(collected)} of {TOTAL[0]}; stopping", logf)
            break

        scroll(-STEP)
        # a person skims a page, now and then stops to look at something
        time.sleep(random.uniform(1.0, 2.6) + (random.uniform(6, 15) if random.random() < 0.04 else 0))

    if prev_front and prev_front not in (WECHAT, "com.apple.loginwindow"):
        subprocess.run([str(config.BIN / "wxctl"), "activate", prev_front], capture_output=True)


if __name__ == "__main__":
    try:
        main()
    except Abort as e:
        print(f"aborted: {e}", file=sys.stderr)
        sys.exit(1)
