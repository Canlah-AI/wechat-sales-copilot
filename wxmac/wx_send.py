"""Send one WeChat message as the logged-in user by driving the unmodified Mac client the way a person would.

Usage: python3 -m wxmac.wx_send "<chat name>" ["<text>"] [--image PNG] [--file PATH] [--person] [--search Q]
                                [--dry-run | --open-only]

Never touches the app bundle, the process memory or the database: only activation, Cmd+F, paste, clicks, and
screenshots read by local OCR. Every step is checked on screen; any mismatch aborts before the text is sent.
  1. refuse if the screen is locked; wait until the user has been idle >= 3 s
  2. remember the front app and the clipboard
  3. bring WeChat forward, Cmd+F, paste the chat name, click the result whose OCR text equals the name exactly
     (only under a chat section of the search popup, never under web search or chat history)
  4. the chat header must read the chat name (with --person: never a group of the same name), else Esc and abort
  5. paste the text, click the input box's Send button, and confirm the text shows in the chat pane;
     then each attachment (--image, --file) as its own message; a file must show its name in the chat pane
  6. restore the clipboard and the front app; log the result to <data dir>/sent.jsonl
"""
import argparse, datetime, difflib, fcntl, json, random, re, subprocess, sys, time, unicodedata
from pathlib import Path

from . import config
from .ui_strings import both

WXCTL, OCR = str(config.BIN / "wxctl"), str(config.BIN / "ocr")
LOG = config.DATA / "sent.jsonl"
HEADER_BAND = 80  # points from the window top that hold the search box and the chat header
SEARCH_BOX_BOTTOM = 50  # points from the window top to the bottom of the search box; results start below it
# search popup section headings (whitespace removed); their order varies, so a result counts only when the
# nearest heading above it is a chat section. Unknown or missing headings mean no click.
# 4.1.15 shows recent chats under "Most used"; without it in the list every recent chat is refused.
CHAT_SECTIONS = both("chat_sections")
OTHER_SECTIONS = both("other_sections")
LIST_RIGHT = 270  # points from the window's left edge to the end of the sidebar + chat list column
INPUT_TOP = 230  # points from the window bottom to the top of the input box (default WeChat 4.1 layout)
PHONE_ICON = (30, 89)  # sidebar phone icon, points from the window's left / bottom edge; its menu holds File Transfer
FILE_TRANSFER = both("file_transfer")
WECHAT = "com.tencent.xinWeChat"


class Abort(Exception):
    pass


class UILock:
    """One script at a time drives WeChat (sender, card reader, a single send): an exclusive lock on ui.lock."""
    def __init__(self):
        self.f = None

    def acquire(self):
        if not self.f:
            config.DATA.mkdir(parents=True, exist_ok=True)
            self.f = open(config.DATA / "ui.lock", "w")
            fcntl.flock(self.f, fcntl.LOCK_EX)

    def release(self):
        if self.f:
            fcntl.flock(self.f, fcntl.LOCK_UN)
            self.f.close()
            self.f = None

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *exc):
        self.release()


def ctl(*a: str) -> str:
    r = subprocess.run([WXCTL, *a], capture_output=True, text=True)
    if r.returncode:
        raise Abort(f"wxctl {a[0]}: {r.stderr.strip()}")
    return r.stdout


def pause(lo=0.35, hi=0.8):
    time.sleep(random.uniform(lo, hi))


def idle_seconds() -> float:
    out = subprocess.run(["ioreg", "-c", "IOHIDSystem"], capture_output=True, text=True).stdout
    for line in out.splitlines():
        if "HIDIdleTime" in line:
            return int(line.split("=")[-1]) / 1e9
    return 0.0


def shot(tag: str, shots: Path) -> tuple[dict, list[dict]]:
    """Screenshot the screen area of WeChat's main window; return (window, OCR lines in window points).

    Captures the area rather than the window id: search results live in a separate popup window on top of it."""
    win = json.loads(ctl("win"))
    png = shots / f"{datetime.datetime.now():%H%M%S}-{tag}.png"
    rect = ",".join(str(int(win[k])) for k in ("x", "y", "w", "h"))
    subprocess.run(["screencapture", "-x", f"-R{rect}", str(png)], check=True)
    lines = []
    for raw in subprocess.run([OCR, str(png)], capture_output=True, text=True, check=True).stdout.splitlines():
        r = json.loads(raw)
        s = win["scale"]
        lines.append({"text": r["text"].strip(), "x": r["x"] / s, "y": r["y"] / s, "w": r["w"] / s, "h": r["h"] / s})
    return win, lines


def norm(s: str) -> str:
    return "".join(s.split())


def key(s: str) -> str:
    """Comparable form of a name as OCR reads it in different places: width-folded, lower case, letters and digits only."""
    return "".join(ch for ch in unicodedata.normalize("NFKC", s).lower() if ch.isalnum())


def pieces(text: str, n: int = 6) -> list[str]:
    """The text cut into n-character pieces. OCR garbles a few characters of a line (the greeting 'Hi 小雨' read as
    '旧小面'), so the text counts as shown when at least two pieces are on screen, wherever the garbling falls."""
    k = key(text)
    return [k[i:i + n] for i in range(0, len(k) - n + 1, n)] or [k]


def is_send(line: dict) -> bool:
    """The input box's Send button; OCR sometimes glues the voice icon on ('① Send')."""
    t = norm(line["text"])
    return len(t) <= 6 and (t.endswith("Send") or t.endswith("发送"))


def section(line: dict) -> str | None:
    """'other' / 'chat' if the line is a search popup heading (OCR may prefix the heading's icon), else None."""
    t = norm(line["text"])
    if any(o in t for o in OTHER_SECTIONS):
        return "other"
    if any(t.endswith(c) and len(t) <= len(c) + 2 for c in CHAT_SECTIONS):
        return "chat"
    return None


def same_chat(header: str, chat: str) -> bool:
    """Header equals the chat name, allowing the member count a group header carries: 'Name (377)'."""
    if key(header) == key(chat):
        return True
    return re.fullmatch(re.escape(norm(chat)) + r"([（(]\d+[）)])?", norm(header)) is not None


def same_person(header: str, chat: str) -> bool:
    """A 1:1 chat header for this name: never a group ('Name (3)'); one or two characters may differ, because the
    header's larger font is read differently from the search popup that already matched the name exactly
    ('Wren 张小両' for 'Wren 张小雨')."""
    if re.search(r"[（(]\d+[）)]\s*$", header.strip()):
        return False
    a, b = key(header), key(chat)
    return a == b or (len(b) >= 4 and difflib.SequenceMatcher(None, a, b).ratio() >= 0.8)


def search_hits(lines: list[dict], chat: str, query: str) -> list[dict]:
    """The search-popup rows to click for this chat, top first; empty means do not click anything.

    A row counts only when it names the chat (exactly, or a long name the popup cut off with an ellipsis) and the
    nearest heading above it is a chat section: an 'Internet search results' row can read exactly like the name.
    When searching by Weixin ID the row reads 'Weixin ID: <id>' even if OCR garbles the name ('Lu）' for 'Luna'):
    exactly one such row counts, and the chat header is still checked against the name after the click."""
    headings = [l for l in lines if section(l)]

    def in_chat_section(l: dict) -> bool:
        above = [h for h in headings if h["y"] < l["y"]]
        return bool(above) and section(max(above, key=lambda h: h["y"])) == "chat"

    def names_it(l: dict) -> bool:
        t = l["text"].rstrip("⋯….")
        return key(l["text"]) == key(chat) or (t != l["text"] and len(key(t)) >= 5 and key(chat).startswith(key(t)))

    hits = sorted((l for l in lines if names_it(l) and l["y"] > SEARCH_BOX_BOTTOM and in_chat_section(l)),
                  key=lambda l: l["y"])
    if not hits and query != chat:
        ids = [l for l in lines if l["y"] > SEARCH_BOX_BOTTOM and in_chat_section(l)
               and (m := re.fullmatch(r"(?:Weixin ID|WeChat ID|微信号)\s*[:：]\s*(\S+)", l["text"].strip()))
               and key(m.group(1)) == key(query)]
        hits = ids if len(ids) == 1 else []
    return hits


def send(chat: str, text: str, dry_run: bool, shots: Path, query: str, open_only: bool = False,
         image: Path | None = None, person: bool = False, file: Path | None = None) -> dict:
    """person=True: the header must name this person, so a group with the same name (header 'Name (3)') is refused."""
    if ctl("locked").strip() == "1":
        raise Abort("screen locked")
    for _ in range(40):
        if idle_seconds() >= 3:
            break
        time.sleep(0.5)
    else:
        raise Abort("user is typing; not stealing focus")

    front = ctl("front").strip()
    clip = ctl("clip-get")
    try:
        ctl("activate")
        pause()
        if norm(chat) in FILE_TRANSFER:
            # search does not return File Transfer in WeChat 4.1: click its chat-list row when one shows, else take it
            # from the sidebar phone icon's menu. Never the row while that menu is open: the click only closes the menu
            ctl("key", "esc")  # close a menu left open, or the click below would toggle it shut
            pause()
            is_ft = lambda l: norm(l["text"]) == norm(chat) and l["x"] < LIST_RIGHT and l["y"] > HEADER_BAND
            win, lines = shot("list", shots)
            hits = [l for l in lines if is_ft(l)]
            if any(same_chat(l["text"], chat) for l in lines if l["y"] < HEADER_BAND and l["x"] > LIST_RIGHT):
                hits = None  # already open: a click on the selected row closes the chat in 4.1.15
            elif not hits:
                ctl("click", str(win["x"] + PHONE_ICON[0]), str(win["y"] + win["h"] - PHONE_ICON[1]))
                time.sleep(1.0)
                win, lines = shot("phone", shots)
                hits = [l for l in lines if is_ft(l)]
        else:
            ctl("key", "cmd+f")
            pause()
            ctl("clip-set", query)
            ctl("key", "cmd+v")
            time.sleep(1.6)  # search results render asynchronously
            win, lines = shot("search", shots)
            hits = search_hits(lines, chat, query)
        if hits is not None:
            if not hits:
                ctl("key", "esc")
                raise Abort(f"no result reads exactly {chat!r}")
            h = hits[0]
            ctl("click", str(win["x"] + h["x"] + h["w"] / 2), str(win["y"] + h["y"] + h["h"] / 2))
            time.sleep(1.0)

        win, lines = shot("opened", shots)
        header = [l for l in lines if l["y"] < HEADER_BAND and l["x"] > LIST_RIGHT]
        if not any(same_person(l["text"], chat) if person else same_chat(l["text"], chat) for l in header):
            ctl("key", "esc")
            raise Abort(f"chat header is {[l['text'] for l in header]}, not {chat!r}")
        if open_only:
            return {"status": "opened", "chat": chat}

        # focus the input box just above its icon row (the box is shorter in a smaller window) and paste
        ctl("click", str(win["x"] + (LIST_RIGHT + win["w"]) / 2), str(win["y"] + win["h"] - 95))
        pause()
        box_top = win["h"] - INPUT_TOP  # default layout; set below from where the pasted text shows up
        b = None  # the input box's Send button, once seen

        def press_send():
            # click the input box's Send button: Enter can land on the chat list, and WeChat 4.1.15 then pops the chat
            # out into a window of its own and leaves the text behind as a draft
            if b:
                ctl("click", str(win["x"] + b["x"] + b["w"] / 2), str(win["y"] + b["y"] + b["h"] / 2))
            else:
                ctl("key", "enter")

        # the chat pane as read while WeChat is still in front (not the chat list's previews): callers scan it for warnings
        pane_text = lambda ls: " ".join(l["text"] for l in ls if l["x"] > LIST_RIGHT)
        screen = ""
        if text:
            ctl("clip-set", text)
            ctl("key", "cmd+v")
            pause()
            ps = pieces(text)
            need = min(2, len(ps))

            def hits_in(ls: list[dict]) -> int:
                return sum(1 for p in ps if any(p in key(l["text"]) for l in ls))

            def where(lines: list[dict]) -> tuple[int, int]:
                """(pieces of the text seen in the message pane, pieces seen in the input box)"""
                # chat column only: the chat list's '[Draft] ...' preview carries the text too
                pane = hits_in([l for l in lines if l["x"] > LIST_RIGHT and HEADER_BAND < l["y"] and l["y"] + l["h"] < box_top])
                box = hits_in([l for l in lines if l["x"] > LIST_RIGHT and l["y"] >= box_top])
                return pane, box

            win, lines = shot("typed", shots)
            # the box starts at the first line of the pasted text (a smaller window has a shorter box than INPUT_TOP)
            typed = [l for l in lines if any(p in key(l["text"]) for p in ps) and l["x"] > LIST_RIGHT and l["y"] > win["h"] / 2]
            if typed:
                box_top = min(l["y"] for l in typed) - 8
            if not typed or where(lines)[1] < need:
                ctl("key", "cmd+a")
                ctl("key", "backspace")
                raise Abort("pasted text is not visible in the input box")
            if dry_run:
                ctl("key", "cmd+a")
                ctl("key", "backspace")
                return {"status": "dry-run", "chat": chat}
            btn = [l for l in lines if is_send(l) and l["x"] > LIST_RIGHT and l["y"] > box_top]
            b = max(btn, key=lambda l: l["y"]) if btn else None
            press_send()
            time.sleep(1.2)

            win, lines = shot("sent", shots)
            pane, box = where(lines)
            screen = pane_text(lines)
            if pane < need or box:
                return {"status": "sent-unconfirmed", "chat": chat, "screen": screen}
        seen = lines  # the latest look at the chat before an attachment is pasted
        for kind, path in (("image", image), ("file", file)):
            if not path:
                continue
            # each attachment goes as its own message after the text, like a person dropping in a card or a document

            def named(ls: list[dict], top: float = 0, bottom: float = 1e9) -> int:
                """lines in the chat column showing a piece of the file name (bubbles cut long names in the middle)"""
                return sum(1 for l in ls if l["x"] > LIST_RIGHT and top < l["y"] < bottom
                           and any(p in key(l["text"]) for p in pieces(path.name, 4)))
            pause(0.8, 1.6)
            ctl("clip-image" if kind == "image" else "clip-file", str(path))
            ctl("key", "cmd+v")
            pause(0.9, 1.4)
            if kind == "file" or not text:
                win, lines = shot(f"{kind}-pasted", shots)
            if kind == "file" and named(lines) <= named(seen):
                # nothing new carries the file name: the paste did not take, so pressing Send would send nothing
                ctl("key", "cmd+a")
                ctl("key", "backspace")
                raise Abort(("text sent; " if text else "") + "pasted file is not visible in WeChat")
            if not text:
                # nothing was typed, so the Send button has not been seen yet (and a dry run ends here)
                btn = [l for l in lines if is_send(l) and l["x"] > LIST_RIGHT and l["y"] > box_top]
                b = max(btn, key=lambda l: l["y"]) if btn else None
                if dry_run:
                    ctl("key", "cmd+a")
                    ctl("key", "backspace")
                    return {"status": "dry-run", "chat": chat}
            press_send()
            time.sleep(1.5)
            win, lines = shot(kind, shots)
            if any(is_send(l) for l in lines if l["y"] < box_top):
                # a send-confirmation sheet: confirm it once
                ctl("key", "enter")
                time.sleep(1.2)
                win, lines = shot(f"{kind}-sent", shots)
            screen += " " + pane_text(lines)
            if kind == "file" and named(lines, HEADER_BAND, box_top) <= named(seen, HEADER_BAND, box_top):
                return {"status": "sent-unconfirmed", "chat": chat, "screen": screen, "file": path.name}
            seen = lines
        return {"status": "sent", "chat": chat, "screen": screen,
                **({"image": image.name} if image else {}), **({"file": file.name} if file else {})}
    finally:
        ctl("clip-set", clip)
        if front and front not in (WECHAT, "com.apple.loginwindow"):
            subprocess.run([WXCTL, "activate", front], capture_output=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("chat")
    ap.add_argument("text", nargs="?", default="")
    ap.add_argument("--search", help="text to type into search when it differs from the shown chat name (e.g. a Weixin ID)")
    ap.add_argument("--image", type=Path, help="a picture (e.g. your business card) sent right after the text")
    ap.add_argument("--file", type=Path, help="any file (PDF, deck, zip...) sent as an attachment after the text, or alone")
    ap.add_argument("--open-only", action="store_true", help="open the chat and check its header, type nothing")
    ap.add_argument("--dry-run", action="store_true", help="do everything except pressing Send, then clear the box")
    ap.add_argument("--person", action="store_true", help="a 1:1 chat: refuse a group with the same name")
    ap.add_argument("--shots", type=Path, default=config.DATA / "shots")
    a = ap.parse_args()
    a.shots.mkdir(parents=True, exist_ok=True)
    try:
        if not (a.text or a.open_only or a.file):
            raise Abort("no text")
        if a.file and not a.file.is_file():
            raise Abort(f"no such file: {a.file}")
        with UILock():  # waits for the outreach sender to finish its current message instead of fighting it for the screen
            res = send(a.chat, a.text, a.dry_run, a.shots, a.search or a.chat, a.open_only, a.image, a.person,
                       a.file.resolve() if a.file else None)
    except Abort as e:
        res = {"status": "aborted", "chat": a.chat, "reason": str(e)}
    res["ts"] = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    res["chars"] = len(a.text)
    with LOG.open("a") as f:
        f.write(json.dumps(res, ensure_ascii=False) + "\n")
    print(json.dumps(res, ensure_ascii=False))
    return 0 if res["status"] in ("sent", "dry-run", "opened") else 1


if __name__ == "__main__":
    sys.exit(main())
