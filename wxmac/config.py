"""Paths and settings. Nothing here touches WeChat.

Data (contacts, ledger, screenshots, the UI lock) lives outside the repo, in
~/Library/Application Support/wechat-sales-copilot/ (override with WSC_DATA_DIR), so it can never be committed.
Settings come from <data dir>/config.toml (override with WSC_CONFIG); until you create one, config.example.toml is
used, and anything that writes messages refuses to run while the persona still holds {{placeholders}}.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIN = Path(os.environ.get("WSC_BIN_DIR", ROOT / "bin"))  # wxctl and ocr, built by install.sh
DATA = Path(os.environ.get("WSC_DATA_DIR", Path.home() / "Library/Application Support/wechat-sales-copilot"))
CONFIG_FILE = Path(os.environ.get("WSC_CONFIG", DATA / "config.toml"))
EXAMPLE = ROOT / "config.example.toml"
PROMPTS = ROOT / "prompts"

_cache: dict = {}


def load() -> dict:
    """The settings as a dict (Python 3.11+ for tomllib)."""
    if not _cache:
        import tomllib
        with open(CONFIG_FILE if CONFIG_FILE.exists() else EXAMPLE, "rb") as f:
            _cache.update(tomllib.load(f))
    return _cache


def get(section: str, name: str, default=None):
    return load().get(section, {}).get(name, default)


def persona() -> dict:
    """The [persona] table; raises SystemExit while it still has unfilled {{placeholders}}."""
    p = dict(load().get("persona", {}))
    blank = [k for k, v in p.items() if "{{" in str(v)]
    if blank:
        raise SystemExit(f"fill in [persona] {', '.join(blank)} in {CONFIG_FILE} first (copy config.example.toml there)")
    return p


def render(template: str, values: dict) -> str:
    """Replace {{name}} with values[name]; lists become '- item' lines."""
    def fmt(v):
        return "\n".join(f"- {x}" for x in v) if isinstance(v, list) else str(v)
    for k, v in values.items():
        template = template.replace("{{" + k + "}}", fmt(v))
    return template


def prompt(name: str, **extra) -> str:
    """prompts/<name>.md filled with the persona and any extra values."""
    text = render((PROMPTS / f"{name}.md").read_text(encoding="utf-8"), {**persona(), **extra})
    if "{{" in text:
        left = sorted(set(text[i + 2:text.index("}}", i)] for i in range(len(text)) if text.startswith("{{", i)))
        raise SystemExit(f"prompts/{name}.md: fill in {', '.join(left)} in {CONFIG_FILE}")
    return text
