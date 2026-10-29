#!/bin/bash
# Privacy guard: refuse a commit when a file contains a term from your private denylist (real contact names,
# your own names, client names), then look for secrets with gitleaks when it is installed.
#
#   scripts/precommit_scrub.sh           scan the staged files (what the pre-commit hook runs)
#   scripts/precommit_scrub.sh --all     scan every tracked and untracked, non-ignored file
#   scripts/precommit_scrub.sh --install install it as .git/hooks/pre-commit
#
# The denylist lives OUTSIDE the repo and is never committed: ${WSC_DENYLIST:-~/.config/wechat-sales-copilot/denylist.txt}
# Build it with `python3 -I scripts/make_denylist.py`. Generic words that are not identifying can be listed in
# ${WSC_ALLOWLIST:-~/.config/wechat-sales-copilot/allowlist.txt}.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
DENY="${WSC_DENYLIST:-$HOME/.config/wechat-sales-copilot/denylist.txt}"
ALLOW="${WSC_ALLOWLIST:-$HOME/.config/wechat-sales-copilot/allowlist.txt}"

if [ "${1:-}" = "--install" ]; then
  printf '#!/bin/bash\nexec "$(git rev-parse --show-toplevel)/scripts/precommit_scrub.sh"\n' > .git/hooks/pre-commit
  chmod +x .git/hooks/pre-commit
  echo "installed .git/hooks/pre-commit"
  exit 0
fi
if [ ! -f "$DENY" ]; then
  echo "precommit_scrub: no denylist at $DENY; build one with scripts/make_denylist.py before committing" >&2
  exit 1
fi
if [ "${1:-}" = "--all" ]; then
  mode=all
  files=$(git ls-files -co --exclude-standard)
else
  mode=staged
  files=$(git diff --cached --name-only --diff-filter=ACMR)
fi
printf '%s\n' "$files" | python3 -I scripts/scrub_scan.py "$DENY" "$ALLOW" "$mode"

if command -v gitleaks >/dev/null; then
  if [ "$mode" = staged ]; then
    gitleaks git --pre-commit --staged --redact --no-banner .
  else
    gitleaks dir --redact --no-banner .
  fi
fi
