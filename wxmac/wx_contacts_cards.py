"""Open target contacts' cards one by one in WeChat's Contacts tab and record what each card shows.

Usage: python3 -m wxmac.wx_contacts_cards [--tiers A,B] [--cats customer] [--idle 60]

Read-only and chat-free: the Contacts tab shows a profile card on the right; it never opens a chat, so unread
state is untouched. Before starting it checks that Saved Groups / Official Accounts / WeCom Contacts are collapsed
(so no group or account can be clicked), and after every click it checks that a contact card, not a chat, is shown;
otherwise it stops at once.
  - targets: contacts classified with the given tiers, plus everyone tagged as an existing user
  - scrolls the list like a person and clicks only names that prefix-match a target; the card's nickname and
    remark must match the target before anything is saved
  - acts only while the user has been idle >= --idle seconds, pauses the moment they come back, and stays out
    of the way while the outreach sender is running
Output: <data dir>/contacts/cards.jsonl ({i, display, alias, remark, weixin_id, region, signature, source, added,
shared_groups, channels, labels}); log: cards.log next to it. Resumable: targets already in cards.jsonl are skipped.
"""
import argparse, datetime, difflib, json, random, re, subprocess, sys, time, unicodedata

from . import config
from .ui_strings import UI, both, ui
from .wx_outreach import PID as SENDER_PID
from .wx_send import LIST_RIGHT, WECHAT, Abort, UILock, ctl, idle_seconds, is_send, key, norm, shot

DATA = config.DATA / "contacts"
CONTACTS_TAB = (30, 179)  # sidebar Contacts icon, window points from the top-left
LIST_X = 175  # x of the names in the list column
STEP = 420  # scroll units per page (1.5 pt each), ~10 of the ~16 visible 60-pt rows
ELLIPSIS = "⋯….·•"
FOLDED = tuple(norm(f) for f in ui("folded_sections"))  # the first three must be collapsed before running
BUTTONS = both("card_buttons")
WRAPPED = both("wrapped_labels")
PREFIX = {k: UI["en"]["card_prefixes"][k] + UI["zh"]["card_prefixes"][k] for k in ("alias", "weixin_id", "region")}
MANAGE = norm(ui("manage_contacts"))


def sender_running() -> bool:
    if not SENDER_PID.exists():
        return False
    cmd = subprocess.run(["ps", "-p", SENDER_PID.read_text().strip(), "-o", "command="], capture_output=True, text=True)
    return "wx_outreach send" in cmd.stdout


class Stop(Abort):
    """A safety stop: never retried."""


def log(msg: str):
    line = f"{datetime.datetime.now():%H:%M:%S} {msg}"
    print(line, flush=True)
    with (DATA / "cards.log").open("a") as f:
        f.write(line + "\n")


def similar(a: str, b: str) -> bool:
    a, b = key(a), key(b)
    return a == b or (bool(a) and bool(b) and difflib.SequenceMatcher(None, a, b).ratio() >= 0.8)


def parse_card(win: dict, lines: list[dict]) -> dict | None:
    """Fields of the contact card in the right pane, or None if the pane is not a contact card."""
    pane = [l for l in lines if l["x"] >= LIST_RIGHT + 270 and l["text"]]
    if not any(l["text"].startswith(("Weixin ID", "微信号")) for l in pane):
        return None
    # OCR mixes full- and half-width punctuation ("Name："): fold widths before reading prefixes
    head = sorted(({**l, "text": unicodedata.normalize("NFKC", l["text"])} for l in pane if l["y"] < 180 and l["x"] >= 640),
                  key=lambda l: l["y"])
    # a trailing lone character after a space is the gender icon read as text
    card = {"display": re.sub(r"\s+\S$", "", head[0]["text"]) if head else "", "alias": "", "weixin_id": "", "region": ""}
    for k, l in enumerate(head):
        t = l["text"]
        for key, prefixes in PREFIX.items():
            if t.startswith(prefixes):
                card[key] = t.split(":", 1)[-1].split("：", 1)[-1].strip()
                if key == "region" and k + 1 < len(head) and not head[k + 1]["text"].startswith(("Name", "Weixin")):
                    card[key] += " " + head[k + 1]["text"]
    labels, values = [], []
    for l in sorted((l for l in pane if l["y"] >= 180), key=lambda l: l["y"]):
        if l["text"] in BUTTONS:
            continue
        (labels if l["x"] < 640 else values).append(l)
    blocks = []  # label fragments that wrap ("Shared" / "Groups") form one block
    for l in labels:
        if blocks and l["y"] - blocks[-1]["y1"] < 30 and norm(blocks[-1]["text"] + l["text"]).lower() in WRAPPED:
            blocks[-1]["text"] += l["text"]
            blocks[-1]["y1"] = l["y"] + l["h"]
        else:
            blocks.append({"text": l["text"], "y0": l["y"], "y1": l["y"] + l["h"]})
    fields = {}
    for v in values:
        dist = lambda b: max(b["y0"] - v["y"], v["y"] - b["y1"], 0)
        b = min(blocks, key=dist, default=None)
        if b and dist(b) <= 14:
            k = norm(b["text"]).lower()
            fields[k] = (fields.get(k, "") + " " + v["text"]).strip()
    remark = fields.get("remark", fields.get("备注", ""))
    card.update({
        "remark": "" if remark in ("Add Alias", "添加备注") else remark,
        "signature": fields.get("what'sup", fields.get("个性签名", "")),
        "source": fields.get("source", fields.get("来源", "")),
        "added": fields.get("addtime", fields.get("添加时间", "")),
        "shared_groups": fields.get("sharedgroups", fields.get("共同群聊", "")),
        "channels": fields.get("channels", fields.get("视频号", "")),
        "labels": {k: v for k, v in fields.items() if k not in ("moments", "moment", "朋友圈")},
    })
    if not card["alias"]:  # no remark set: the header is the nickname itself
        card["alias"] = card["display"]
    return card


def list_rows(lines: list[dict]) -> list[dict]:
    """Names in the list column, top to bottom; an emoji splits a name into fragments, which are joined back."""
    rows = []
    for l in sorted((l for l in lines if 120 <= l["x"] < LIST_RIGHT - 10 and l["y"] > 60 and l["text"]),
                    key=lambda l: (round((l["y"] + l["h"] / 2) / 12), l["x"])):
        cy = l["y"] + l["h"] / 2
        if rows and abs(rows[-1]["cy"] - cy) < 10:
            rows[-1]["text"] += l["text"]
        else:
            rows.append({**l, "cy": cy})
    return sorted(rows, key=lambda r: r["y"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tiers", default="A,B")
    ap.add_argument("--cats", default="customer", help="categories opened regardless of tier")
    ap.add_argument("--idle", type=float, default=60)
    a = ap.parse_args()
    contacts = [json.loads(l) for l in (DATA / "all_contacts.jsonl").open()]
    cls = {o["i"]: o for o in map(json.loads, (DATA / "classified.jsonl").open())}
    tiers, cats = set(a.tiers.split(",")), set(a.cats.split(","))
    out = DATA / "cards.jsonl"
    done = {json.loads(l)["i"] for l in out.open()} if out.exists() else set()
    targets = {i: c for i, c in enumerate(contacts)
               if i not in done and (cls.get(i, {}).get("tier") in tiers or cls.get(i, {}).get("cat") in cats)}
    shown = lambda c: c["remark"] if c["remark"] and c["remark"] not in both("no_remark") else c["alias"]
    display = {i: key(shown(c)) for i, c in targets.items()}
    skip_f = DATA / "cards_nonmatch.txt"  # list names whose card turned out not to be a target
    skip = set(skip_f.read_text().split("\n")) if skip_f.exists() else set()
    seen_f = (DATA / "cards_list_names.txt").open("a")  # every list name read, for checking misses later
    log(f"start: {len(targets)} targets left, {len(done)} done")
    shots = config.DATA / "shots" / "cards"
    shots.mkdir(parents=True, exist_ok=True)

    last_action, stage, prev_names, unchanged, misses = 0.0, False, None, 0, 0
    tried = set(skip)  # list names already clicked (target or not), so a row is opened at most once
    lock = UILock()
    while targets:
      try:
          if sender_running():
              # the outreach sender owns the screen while it runs; cards wait for it to stop
              if stage:
                  log("the sender is running; pausing")
              stage = False
              lock.release()
              time.sleep(100)
              continue
          if ctl("locked").strip() == "1":
              log("screen locked; waiting")
              lock.release()
              time.sleep(60)
              continue
          if idle_seconds() < min(a.idle, time.time() - last_action) - 1:
              if stage:
                  log("user is back; pausing")
              stage = False
              lock.release()
              time.sleep(15)
              continue
          lock.acquire()
          if not stage or ctl("front").strip() != WECHAT:
              if idle_seconds() < a.idle:
                  stage = False
                  lock.release()
                  time.sleep(5)
                  continue
              ctl("activate")
              w, lines = shot("tab", shots)
              if not any(MANAGE in norm(l["text"]) for l in lines if l["x"] < LIST_RIGHT):
                  # switch to the Contacts tab only when it is not showing: the click resets the list to the top
                  ctl("click", str(w["x"] + CONTACTS_TAB[0]), str(w["y"] + CONTACTS_TAB[1]))
                  time.sleep(1.2)
              last_action, stage = time.time(), True
              w, lines = shot("tab", shots)
              opened = [norm(l["text"]) for l in lines if l["x"] < LIST_RIGHT and l["text"][:1] in "Vv∨⌄"]  # expanded marker
              if any(f in t for t in opened for f in FOLDED[:3]):
                  raise Stop(f"a group/account section is expanded: {opened}; fold it before running")
              if prev_names is None:  # first time: start from the top of the list (Manage Contacts in view)
                  for k in range(120):
                      ctl("scroll", str(w["x"] + LIST_X), str(w["y"] + w["h"] / 2), "8000")
                      time.sleep(0.4)
                      if k % 5 == 4:
                          _, top = shot("list", shots)
                          if any(MANAGE in norm(l["text"]) for l in top if l["x"] < LIST_RIGHT):
                              break
                  last_action = time.time()
              log("took the stage")

          for old in sorted(shots.glob("*.png"), key=lambda q: q.stat().st_mtime)[:-30]:
              old.unlink()  # screenshots hold private chats' names: keep only the latest few
          w, lines = shot("list", shots)
          # the chat list shows a time on every row (07:38, Yesterday); the contacts list never does.
          # Never click rows there: it would open chats and mark them read.
          stamps = [l for l in lines if l["x"] < LIST_RIGHT and re.search(r"(\b\d{1,2}:\d{2}|Yesterday|昨天|星期.|\d{2}/\d{2})\s*$", l["text"])]
          if len(stamps) >= 3:
              log("the chat list is showing, not contacts; switching back")
              stage = False
              prev_names = None
              continue
          rows = list_rows(lines)
          names = [key(r["text"].rstrip(ELLIPSIS)) for r in rows]
          seen_f.write("\n".join(r["text"] for r in rows) + "\n")
          seen_f.flush()
          clicked = False
          for r, n in zip(rows, names):
              if len(n) < 2 or n in tried:
                  continue
              # the list truncates long names, and OCR reads a few characters differently here than in the table
              cands = [i for i, d in display.items() if d == n or (len(n) >= 3 and d.startswith(n)) or (
                  len(n) >= 4 and difflib.SequenceMatcher(None, d[:len(n)], n).ratio() >= 0.75)]
              if not cands:
                  continue
              tried.add(n)
              ctl("click", str(w["x"] + LIST_X), str(w["y"] + r["y"] + r["h"] / 2))
              last_action = time.time()
              time.sleep(random.uniform(1.3, 2.6))
              w2, lines2 = shot("card", shots)
              card = parse_card(w2, lines2)
              if card is None:
                  if any(is_send(l) for l in lines2):  # a chat pane: should never happen from this tab
                      raise Stop("a chat opened instead of a card; stopping (check unread state)")
                  log(f"no card for {r['text']!r}")
                  continue
              hit = next((i for i in cands if similar(card["alias"], targets[i]["alias"])
                          and (not targets[i]["remark"] or similar(card["remark"], targets[i]["remark"]))), None)
              if hit is None:
                  misses += 1
                  with skip_f.open("a") as f:
                      f.write(n + "\n")
                  continue
              card["i"] = hit
              with out.open("a") as f:
                  f.write(json.dumps(card, ensure_ascii=False) + "\n")
              del targets[hit], display[hit]
              if len(done) % 25 == 0:
                  log(f"{len(targets)} targets left")
              done.add(hit)
              clicked = True
              if random.random() < 0.05:  # now and then a person stops to read
                  time.sleep(random.uniform(5, 12))
          if clicked:
              continue  # re-read the same page before scrolling on

          # scroll on, keeping overlap with the page just read
          if prev_names is not None and names == prev_names:
              unchanged += 1
              if unchanged >= 3:
                  # really the end only if the list still moves up but not down
                  ctl("scroll", str(w["x"] + LIST_X), str(w["y"] + w["h"] / 2), "300")
                  time.sleep(1.0)
                  _, up = shot("list", shots)
                  moved_up = [key(r["text"].rstrip(ELLIPSIS)) for r in list_rows(up)] != names
                  ctl("scroll", str(w["x"] + LIST_X), str(w["y"] + w["h"] / 2), "-900")
                  time.sleep(1.0)
                  _, down = shot("list", shots)
                  last_action = time.time()
                  if moved_up and [key(r["text"].rstrip(ELLIPSIS)) for r in list_rows(down)] == names:
                      log(f"end of list; {len(targets)} targets not found, {misses} non-matching cards")
                      break
                  log("not the end yet; carrying on")
                  unchanged = 0
          else:
              unchanged = 0
          prev_names = names
          ctl("scroll", str(w["x"] + LIST_X), str(w["y"] + w["h"] / 2), str(-STEP))
          last_action = time.time()
          time.sleep(random.uniform(0.8, 2.0))
          w, lines = shot("list", shots)
          after = [key(r["text"].rstrip(ELLIPSIS)) for r in list_rows(lines)]
          if prev_names and after and not set(prev_names[-6:]) & set(after):
              log("scrolled past unseen rows; going back a little")
              ctl("scroll", str(w["x"] + LIST_X), str(w["y"] + w["h"] / 2), str(STEP // 2))
              last_action = time.time()
              time.sleep(1.0)
      except Stop:
        lock.release()
        raise
      except Abort as e:  # a window not on screen yet, a read that failed: wait and retake the stage
        log(f"retrying after: {e}")
        stage = False
        lock.release()
        time.sleep(15)
    log(f"done: {len(done)} cards")
    if idle_seconds() > 300 and ctl("locked").strip() != "1":
        subprocess.run(["open", "-a", "ScreenSaverEngine"])  # finished: let the screen lock again


if __name__ == "__main__":
    try:
        main()
    except Abort as e:
        log(f"aborted: {e}")
        sys.exit(1)
