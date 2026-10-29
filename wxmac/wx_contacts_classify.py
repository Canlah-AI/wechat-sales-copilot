"""Sort your WeChat contacts (nickname, your remark, tags) into lead categories and tiers.

Usage:
  python3 -m wxmac.wx_contacts_classify --export 120         write the next 120 for Claude Code to label (default mode)
  python3 -m wxmac.wx_contacts_classify --import labels.jsonl take the labels back (one JSON object per line)
  python3 -m wxmac.wx_contacts_classify --api                 label everything through the API ([llm] mode = "api")

Input <data dir>/contacts/all_contacts.jsonl (from wx_contacts_dump); output classified.jsonl next to it, one
{i, cat, tier, company, role, industry, region, why} per contact. Resumable: rows already labelled are skipped.
The prompt is prompts/classify.md, filled from [persona] and [classify] in config.toml.
Categories: prospect, customer, partner, investor, peer, friend, consumer, unknown. Tiers: A, B, C, '-'.
"""
import argparse, json, sys, threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import config, llm

CONTACTS = config.DATA / "contacts"
BATCH = 120


def the_prompt() -> str:
    return config.prompt("classify", ideal_customers=config.get("classify", "ideal_customers", []),
                         tag_meanings=config.get("classify", "tag_meanings", []))


def listing(rows: list[dict], batch: list[int]) -> str:
    return "\n".join(f"{i}\t{rows[i]['alias']}\t{rows[i]['remark']}\t{rows[i]['tags']}" for i in batch)


def keep(got: list[dict], batch: set[int], out: Path, lock: threading.Lock | None = None) -> int:
    ok = [o for o in got if isinstance(o.get("i"), int) and o["i"] in batch]
    if lock:
        lock.acquire()
    try:
        with out.open("a") as f:
            for o in ok:
                f.write(json.dumps(o, ensure_ascii=False) + "\n")
    finally:
        if lock:
            lock.release()
    return len(ok)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", type=Path, default=CONTACTS / "all_contacts.jsonl")
    ap.add_argument("--out", type=Path, default=CONTACTS / "classified.jsonl")
    ap.add_argument("--export", type=int, metavar="N")
    ap.add_argument("--import", dest="imp", type=Path)
    ap.add_argument("--api", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    rows = [json.loads(l) for l in a.inp.open()]
    done = {json.loads(l)["i"] for l in a.out.open()} if a.out.exists() else set()
    todo = [i for i in range(len(rows)) if i not in done]
    if a.imp:
        got = [json.loads(l) for l in a.imp.open() if l.strip().startswith("{")]
        print(f"kept {keep(got, set(todo), a.out)} labels; {len(todo)} were open")
        return 0
    if a.api and not llm.api_mode():
        raise SystemExit('--api needs [llm] mode = "api" in config.toml and an API key in the environment')
    if not a.api:
        n = a.export or BATCH
        path = CONTACTS / "classify_todo.txt"
        path.write_text(the_prompt() + listing(rows, todo[:n]) + "\n", encoding="utf-8")
        print(f"{min(n, len(todo))} of {len(todo)} open contacts written to {path}\n"
              f"write one JSON line per contact to a file, then: python3 -m wxmac.wx_contacts_classify --import <file>")
        return 0
    client, wlock = llm.Client(), threading.Lock()
    batches = [todo[j:j + BATCH] for j in range(0, len(todo), BATCH)]
    print(f"{len(rows)} rows, {len(done)} done, {len(batches)} batches to run", flush=True)

    def run(batch: list[int]):
        n = keep(llm.json_lines(client.ask(the_prompt() + listing(rows, batch))), set(batch), a.out, wlock)
        print(f"batch {batch[0]}..{batch[-1]}: {n}/{len(batch)}", flush=True)

    with ThreadPoolExecutor(a.workers) as ex:
        for fut in [ex.submit(run, b) for b in batches]:
            try:
                fut.result()
            except Exception as e:  # a failed batch is picked up on the next run (resumable)
                print(f"batch failed: {e}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
