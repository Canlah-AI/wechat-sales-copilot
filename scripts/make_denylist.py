"""Build the private denylist the pre-commit guard checks against, from your own contacts export.

Usage: python3 -I scripts/make_denylist.py [--extra "Your Name" "Your Company" ...]

Reads <data dir>/contacts/all_contacts.jsonl (written by wx_contacts_dump) and writes
~/.config/wechat-sales-copilot/denylist.txt (mode 600): every contact name and remark of 3+ characters, minus
plain English dictionary words (a nickname like "Happy" is not identifying and would flag ordinary prose),
plus whatever you pass with --extra (your own names, company, clients). The file never goes into the repo.
"""
import argparse, json, re, sys, unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from wxmac.config import DATA  # noqa: E402

OUT = Path.home() / ".config/wechat-sales-copilot/denylist.txt"
UI_WORDS = {"add remarks", "add alias", "file transfer", "weixin", "wechat", "微信", "文件传输助手"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--contacts", type=Path, default=DATA / "contacts" / "all_contacts.jsonl")
    ap.add_argument("--extra", nargs="*", default=[])
    a = ap.parse_args()
    dictionary = Path("/usr/share/dict/words")
    words = {w.strip().lower() for w in dictionary.open()} if dictionary.exists() else set()
    terms = set()
    if a.contacts.exists():
        for line in a.contacts.open():
            c = json.loads(line)
            for f in ("alias", "remark"):
                t = unicodedata.normalize("NFKC", c.get(f) or "").strip()
                if (t and t.lower() not in UI_WORDS and len(re.sub(r"\s", "", t)) >= 3
                        and not (t.isascii() and " " not in t and t.lower() in words)):
                    terms.add(t)
    terms.update(t.strip() for t in a.extra if t.strip())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("# private: never commit\n" + "\n".join(sorted(terms)) + "\n", encoding="utf-8")
    OUT.chmod(0o600)
    print(f"{len(terms)} terms -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
