# Privacy: keeping contacts out of git

Everything the scripts collect (your address book, labels, drafts, the ledger, screenshots of your chats) is written
to `~/Library/Application Support/wechat-sales-copilot/`, outside any repo. `.gitignore` also blocks the usual file
types in case something is copied in by hand. Two more guards for contributors:

1. **A private denylist** of names that must never appear in a commit: your contacts' names and remarks, your own
   names, your company and clients. Build it from your own capture and keep it outside the repo:

   ```bash
   python3 -I scripts/make_denylist.py --extra "Your Name" "你的名字" "Your Company" "A Client"
   ```

   It writes `~/.config/wechat-sales-copilot/denylist.txt` (mode 600). Plain English dictionary words are left out
   on purpose: a nickname such as "Happy" is not identifying and would flag ordinary prose. Generic terms that still
   cause false hits go one per line into `~/.config/wechat-sales-copilot/allowlist.txt`.

2. **A pre-commit hook** that scans staged files against the denylist and runs `gitleaks` for secrets when installed:

   ```bash
   scripts/precommit_scrub.sh --install    # once per clone
   scripts/precommit_scrub.sh --all        # scan the whole tree by hand
   ```

Images cannot be scanned for text: the hook lists them so a person looks. Demo screenshots should come from a
test account or File Transfer, with no real name anywhere on screen.

Code comments and tests use invented names only. When documenting an OCR misreading seen on a real contact, invent an
equivalent example.
