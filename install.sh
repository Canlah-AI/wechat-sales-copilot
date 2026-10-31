#!/bin/bash
# Build the two native helpers and set up the data directory. Safe to rerun.
#   wxctl: synthetic keys and clicks, window lookup, pasteboard (no injection, no access to WeChat's memory or files)
#   ocr:   Apple Vision text recognition of a screenshot, on this Mac
set -euo pipefail
cd "$(dirname "$0")"
[ "$(uname)" = Darwin ] || { echo "macOS only"; exit 1; }
python3 -c 'import sys; sys.exit(sys.version_info < (3, 11))' || { echo "needs Python 3.11+ (brew install python)"; exit 1; }
command -v swiftc >/dev/null || { echo "needs swiftc: xcode-select --install"; exit 1; }
mkdir -p bin
for t in wxctl ocr; do
  swiftc -O -o "bin/$t.new" "native/$t.swift"
  mv "bin/$t.new" "bin/$t"
done
# sending, outreach and inbox need only the standard library; Pillow and openpyxl are for contacts capture and Excel
if ! out=$(python3 -m pip install --quiet --user -r requirements.txt 2>&1); then
  if grep -q externally-managed <<<"$out"; then
    echo "note: this Python (Homebrew's) refuses pip installs. For contacts capture and the Excel export, run"
    echo "      python3 -m pip install --user --break-system-packages -r requirements.txt   (your user folder only)"
  else
    echo "note: pip install -r requirements.txt failed; contacts capture and the Excel export need Pillow and openpyxl"
  fi
fi
DATA="${WSC_DATA_DIR:-$HOME/Library/Application Support/wechat-sales-copilot}"
mkdir -p "$DATA"
chmod 700 "$DATA"
[ -f "$DATA/config.toml" ] || { cp config.example.toml "$DATA/config.toml"; echo "created $DATA/config.toml: fill in [persona]"; }
echo "built bin/wxctl and bin/ocr; data in $DATA"
echo "next: python3 -m wxmac.doctor"
