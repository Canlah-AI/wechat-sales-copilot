"""Scan files for terms from a private denylist (real contact names, your own names, client names).

Usage: python3 -I scripts/scrub_scan.py <denylist> <allowlist> staged|all   (file paths on stdin, one per line)

ASCII terms match as whole words, case-insensitive; other terms (Chinese names...) match as substrings. Both sides
are NFKC-folded, so full-width and half-width forms match. Prints `path:line: term` per hit and exits 1 on any hit.
In `staged` mode the staged blob is read (what would be committed), not the working-tree file.
Binary files cannot be scanned for text: they are listed so a person looks at them (screenshots hold names).
"""
import re, subprocess, sys, unicodedata
from pathlib import Path


def load(path: str) -> list[str]:
    p = Path(path).expanduser()
    if not p.exists():
        return []
    return [unicodedata.normalize("NFKC", t.strip()) for t in p.read_text(encoding="utf-8").splitlines()
            if t.strip() and not t.startswith("#")]


def main() -> int:
    deny, allow, mode = sys.argv[1:4]
    allowed = {t.casefold() for t in load(allow)}  # matching is case-insensitive, so the allowlist is too
    # an allowlist entry is also blanked out of each line before matching, so a phrase such as the repo's own
    # "owner/name" can stay while the owner's name alone is still caught everywhere else
    blank = re.compile("|".join(map(re.escape, sorted(load(allow), key=len, reverse=True))), re.I) if allowed else None
    terms = sorted({t for t in load(deny) if t.casefold() not in allowed}, key=len, reverse=True)
    if not terms:
        print("scrub_scan: empty denylist", file=sys.stderr)
        return 1
    ascii_t = [t for t in terms if t.isascii()]
    other_t = [t for t in terms if not t.isascii()]
    pats = []
    if ascii_t:
        pats.append(re.compile(r"(?<![A-Za-z0-9])(?:" + "|".join(map(re.escape, ascii_t)) + r")(?![A-Za-z0-9])", re.I))
    if other_t:
        pats.append(re.compile("|".join(map(re.escape, other_t))))
    hits, binary = 0, []
    for path in filter(None, sys.stdin.read().splitlines()):
        if mode == "staged":
            raw = subprocess.run(["git", "show", f":{path}"], capture_output=True).stdout
        else:
            p = Path(path)
            if not p.is_file():
                continue
            raw = p.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            binary.append(path)
            continue
        for n, line in enumerate(text.splitlines(), 1):
            line = unicodedata.normalize("NFKC", line)
            if blank:
                line = blank.sub(" ", line)
            for pat in pats:
                for m in pat.finditer(line):
                    print(f"{path}:{n}: {m.group(0)}")
                    hits += 1
    for b in binary:
        print(f"{b}: binary file, not scanned: check it by eye (no screenshots of real chats)")
    print(f"scrub_scan: {hits} hit(s) in {mode} files", file=sys.stderr)
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
