"""Optional direct LLM calls, for unattended runs (drafting and classifying while no Claude Code session is open).

The default is no API at all: the scripts export work files, Claude Code (the host) writes the drafts or labels,
and the scripts import them. Set [llm] mode = "api" and an API key in the environment to call the Anthropic
Messages API directly instead:
  WSC_ANTHROPIC_API_KEY (preferred, so a key meant for this tool does not switch other tools to API billing)
  or ANTHROPIC_API_KEY
"""
import json, os, threading, time, urllib.error, urllib.request

from . import config


def api_mode() -> bool:
    return config.get("llm", "mode", "host") == "api"


class Client:
    def __init__(self):
        self.key = os.environ.get("WSC_ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
        if not self.key:
            raise SystemExit('[llm] mode = "api" needs WSC_ANTHROPIC_API_KEY (or ANTHROPIC_API_KEY) in the environment')
        self.model = config.get("llm", "model", "claude-sonnet-5-5")
        self.lock = threading.Lock()

    def ask(self, text: str, max_tokens: int = 16000) -> str:
        for attempt in range(8):
            body = json.dumps({"model": self.model, "max_tokens": max_tokens,
                               "messages": [{"role": "user", "content": text}]}).encode()
            req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
                "x-api-key": self.key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=600) as r:
                    data = json.load(r)
                return "".join(b.get("text", "") for b in data["content"] if b.get("type") == "text")
            except urllib.error.HTTPError as e:
                msg = e.read().decode(errors="replace")[:300]
                if e.code in (429, 500, 502, 503, 529):
                    time.sleep(10 * (attempt + 1))
                    continue
                raise RuntimeError(f"HTTP {e.code}: {msg}")
            except (urllib.error.URLError, TimeoutError):
                time.sleep(10 * (attempt + 1))
        raise RuntimeError("gave up after retries")


def json_lines(reply: str) -> list[dict]:
    """The JSON objects in a reply that puts one per line (anything else is ignored)."""
    out = []
    for line in reply.splitlines():
        line = line.strip().strip(",")
        if line.startswith("{"):
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out
