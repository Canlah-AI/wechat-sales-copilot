"""Check that this Mac can run the copilot, and say how to fix what is missing. Read-only: it never clicks or types.

Usage: python3 -m wxmac.doctor [--ocr]
  --ocr  also screenshot the WeChat window and read it, to check the interface language against [ui] language

Most failures are silent otherwise: without Screen Recording the screenshots are blank and every name "does not
match"; without Accessibility the clicks are dropped. Both grants belong to the app that runs the command
(Terminal, iTerm, the Claude Code host), not to these scripts.
"""
import argparse, json, platform, plistlib, sqlite3, subprocess, sys
from pathlib import Path

from . import config
from .ui_strings import lang

TESTED = {"4.1.13", "4.1.15"}
APP = Path("/Applications/WeChat.app")
NOTIFY_DB = Path.home() / "Library/Group Containers/group.com.apple.usernoted/db2/db"
host = __import__("os").environ.get("TERM_PROGRAM", "your terminal app")
results: list[tuple[bool, str, str]] = []


def check(ok: bool, what: str, fix: str = ""):
    results.append((ok, what, fix))


def run(*a: str) -> str:
    r = subprocess.run(a, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ocr", action="store_true")
    a = ap.parse_args()
    check(sys.version_info >= (3, 11), f"Python {platform.python_version()}", "install Python 3.11+ (brew install python)")
    check(int(platform.mac_ver()[0].split(".")[0] or 0) >= 13, f"macOS {platform.mac_ver()[0]} ({platform.machine()})", "macOS 13 or later")
    wxctl, ocr = config.BIN / "wxctl", config.BIN / "ocr"
    built = wxctl.exists() and ocr.exists()
    check(built, f"native tools in {config.BIN}", "run ./install.sh (needs Xcode Command Line Tools: xcode-select --install)")
    if built:
        perms = json.loads(run(str(wxctl), "perms") or "{}")
        check(perms.get("accessibility", False), "Accessibility",
              f"System Settings > Privacy & Security > Accessibility: turn on {host}, then restart it")
        check(perms.get("screen_recording", False), "Screen Recording",
              f"System Settings > Privacy & Security > Screen Recording: turn on {host}, then restart it")
    try:
        sqlite3.connect(f"file:{NOTIFY_DB}?mode=ro", uri=True).execute("select count(*) from record").fetchone()
        check(True, "Full Disk Access (reading replies from notifications)")
    except sqlite3.Error:
        check(False, "Full Disk Access (reading replies from notifications)",
              f"optional, for wechat-inbox and reply counts: Privacy & Security > Full Disk Access: turn on {host}")
    if APP.exists():
        info = plistlib.load((APP / "Contents/Info.plist").open("rb"))
        v = info.get("CFBundleShortVersionString", "?")
        check(v in TESTED, f"WeChat {v}", f"only {', '.join(sorted(TESTED))} have been used; other versions may need "
                                          f"new UI strings or layout constants (see docs/pitfalls.md)")
    else:
        check(False, "WeChat for Mac installed", "install WeChat from weixin.qq.com or the Mac App Store and log in")
    running = bool(run("pgrep", "-x", "WeChat"))
    check(running, "WeChat running", "open WeChat and log in (scan the QR code with your phone)")
    if running and built:
        win = json.loads(run(str(wxctl), "win") or "{}")
        big = win.get("w", 0) >= 1100 and win.get("h", 0) >= 700
        check(big, f"main window {int(win.get('w', 0))}x{int(win.get('h', 0))}",
              "too small for the search popup and the input box: run bin/wxctl fit")
        check(run(str(wxctl), "locked") == "0", "screen unlocked", "unlock the screen; nothing runs while it is locked")
    idle = run("defaults", "-currentHost", "read", "com.apple.screensaver", "idleTime")
    check(True, f"screen saver after {idle or '?'} s idle (the sender only acts while you are away; a locked "
                f"screen stops it until you unlock)")
    cfg = config.CONFIG_FILE.exists()
    check(cfg, f"config {config.CONFIG_FILE}", "cp config.example.toml to that path and fill in [persona]")
    if cfg:
        try:
            config.persona()
            check(True, "persona filled in")
        except SystemExit as e:
            check(False, "persona filled in", str(e))
    check(lang() in ("en", "zh"), f"[ui] language = {lang()}" + ("  (Chinese interface: contacts capture unverified)" if lang() == "zh" else ""))
    if a.ocr and running and built:
        win = json.loads(run(str(wxctl), "win") or "{}")
        png = config.DATA / "shots" / "doctor.png"
        png.parent.mkdir(parents=True, exist_ok=True)
        rect = ",".join(str(int(win[k])) for k in ("x", "y", "w", "h"))
        subprocess.run(["screencapture", "-x", f"-R{rect}", str(png)])
        text = " ".join(json.loads(l)["text"] for l in run(str(ocr), str(png)).splitlines())
        seen = "zh" if "搜索" in text else "en" if "Search" in text else "?"
        check(seen == lang(), f"interface language on screen: {seen}", f"set [ui] language = \"{seen}\" in config.toml")
        png.unlink(missing_ok=True)  # it shows your chats
    bad = 0
    for ok, what, fix in results:
        print(f"{'OK ' if ok else 'FIX'}  {what}" + ("" if ok or not fix else f"\n     -> {fix}"))
        bad += not ok
    print(f"\n{bad} item(s) to fix" if bad else "\nall good")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
