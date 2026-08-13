#!/usr/bin/env python3
"""Drive a realistic multi-guest party against the DJ's real setlist.

Unlike ``/api/demo/seed`` (which fires a fixed corpus from synthetic sessions),
this walks the whole product loop the way a real room does it:

  1. Import the DJ's planned set from his exported history.
  2. Many *distinct* phones submit, in their own words, at their own pace --
     including one repeat offender, so the anti-manipulation weighting is
     visible rather than claimed.
  3. CUE proposes where each crowd wave belongs *inside* that planned set,
     scored against both neighbours.
  4. Two guests tip specific songs.
  5. The DJ accepts a proposal, plays it, and the tip settles -- and the tip
     on the song he never plays is released, not charged.

Usage:
    python3 scripts/demo_party.py            # against a running backend
    python3 scripts/demo_party.py --fast      # no pauses
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"
EVENT = "default"

# The DJ's set lives in a data file, not in this script, so demoing a different
# night means pasting a new export -- no code change.
SETLIST_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "setlist.txt"
)

# "00:54:53  Buzz - Badshah - Aastha Gill" -> ("00:54:53", "Buzz - Badshah ...")
_LINE_RE = re.compile(r"^\s*(\d{1,2}:\d{2}:\d{2})\s+(.+?)\s*$")


def load_setlist(path: str):
    """Parse the DJ's exported history. Comments and blank lines ignored."""
    if not os.path.exists(path):
        sys.exit("No setlist at %s — see data/setlist.txt" % path)
    entries = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            match = _LINE_RE.match(line)
            if match:
                entries.append({"cue_time": match.group(1), "title": match.group(2)})
            else:
                print("   ! could not parse line: %s" % line.strip())
    if not entries:
        sys.exit("Setlist at %s parsed to zero entries." % path)
    return entries

# One phone, one person, their own phrasing. Deliberately messy: Hinglish,
# emoji, negation, vagueness, and typos are the actual input distribution.
GUESTS = [
    ("Aarav",   "bhangra bhangra bhangra"),
    ("Priya",   "kuch romantic bajao yaar"),
    ("Rohan",   "diljit please 🙏"),
    ("Sneha",   "something we can all sing along to"),
    ("Kabir",   "TAUBA TAUBA!!!"),
    ("Ananya",  "slow it down for a bit"),
    ("Vikram",  "punjabi hits only"),
    ("Meera",   "arijit singh vibes"),
    ("Dev",     "anything but techno"),
    ("Isha",    "badshah 🔥"),
    ("Arjun",   "bhangra paake floor todna hai"),
    ("Zoya",    "couple dance song for sangeet"),
    ("Nikhil",  "peak time banger pls"),
    ("Riya",    "90s bollywood nostalgia"),
    ("Sameer",  "karan aujla"),
    ("Tara",    "idk surprise me"),
    ("Yash",    "dhol dhol dhol"),
    ("Nisha",   "romantic but not too slow"),
    ("Omkar",   "garmi type energy"),
    ("Diya",    "wedding baraat songs"),
]

# One person hammering the same ask from one device. Should NOT out-vote the room.
SPAMMER_TEXT = "play techno"
SPAMMER_COUNT = 10


def call(method: str, path: str, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        BASE + path, data=data, method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.load(r)
    except urllib.error.HTTPError as exc:
        print("   ! %s %s -> %s %s" % (method, path, exc.code, exc.read()[:200]))
        return None
    except urllib.error.URLError as exc:
        sys.exit("Cannot reach %s (%s). Start ./scripts/dev.sh first." % (BASE, exc.reason))


def rule(title: str) -> None:
    print("\n" + title)
    print("─" * max(48, len(title)))


def money(minor: int) -> str:
    return "₹%s" % ("%.2f" % (minor / 100.0)).rstrip("0").rstrip(".")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true", help="no pauses between guests")
    args = ap.parse_args()
    pause = (lambda s: None) if args.fast else time.sleep
    rng = random.Random(7)  # reproducible demo

    call("POST", "/api/demo/reset", {"event_id": EVENT})

    # ---- 1. the DJ's plan --------------------------------------------------
    rule("1. The DJ already has a set planned")
    setlist = load_setlist(SETLIST_PATH)
    print("   from %s\n" % os.path.relpath(SETLIST_PATH))
    loaded = call("POST", "/api/setlist", {"event_id": EVENT, "entries": setlist})
    if loaded is None:
        sys.exit(1)
    if loaded["unmatched"]:
        print("   unmatched (not guessed at): %s" % ", ".join(loaded["unmatched"]))
    for e in loaded["upcoming"]:
        t = e["track"]
        print("   %s  %-20s %3d bpm  energy %.2f" % (e["cue_time"], t["title"], t["bpm"], t["energy"]))

    # ---- 2. the room ------------------------------------------------------
    rule("2. %d phones, %d different ways of asking" % (len(GUESTS), len(GUESTS)))
    for name, text in GUESTS:
        ack = call("POST", "/api/requests", {
            "text": text, "session_id": "sess_%s" % name.lower(), "event_id": EVENT,
        })
        if ack:
            joined = "joined %d others in" % ack["wave_size"] if ack["joined_existing_wave"] else "started"
            print("   %-8s %-38s -> %s %s" % (name, '"%s"' % text, joined, ack["wave_label"]))
        pause(rng.uniform(0.05, 0.2))

    rule("3. One guy spamming from one phone, %dx" % SPAMMER_COUNT)
    for _ in range(SPAMMER_COUNT):
        call("POST", "/api/requests", {
            "text": SPAMMER_TEXT, "session_id": "sess_spammer", "event_id": EVENT,
        })
    board = call("GET", "/api/dashboard?event_id=%s" % EVENT)
    top = board["waves"][0]["wave"]
    print('   dominant wave is still "%s" (%d unique devices)' % (top["label"], top["unique_sessions"]))
    print("   techno in the top wave? %s" % ("YES — antimanip failed" if "techno" in top["label"].lower() else "no"))

    # ---- 4. insertion -----------------------------------------------------
    rule("4. Where do those requests go in HIS set?")
    ins = call("GET", "/api/insertions?event_id=%s" % EVENT)
    proposals = (ins or {}).get("proposals", [])
    if not proposals:
        print("   (no proposals — is the setlist loaded?)")
        return
    for p in proposals:
        after = p["after"]["title"] if p["after"] else "now"
        before = p["before"]["title"] if p["before"] else "end of set"
        print("   %-18s -> slot %d, between %s and %s" % (p["track"]["title"], p["position"], after, before))
        print("      %-22s score %.2f   out %.2f / in %.2f" % (p["wave_label"], p["score"], p["bridge_out"], p["bridge_in"]))
        print("      %s" % " · ".join(p["reasons"]))

    # ---- 5. tips ----------------------------------------------------------
    rule("5. Two guests put money on it")
    will_play = proposals[0]["track"]
    never_plays = call("GET", "/api/catalog/search?q=Kesariya&limit=1")["tracks"][0]

    call("POST", "/api/tips", {
        "event_id": EVENT, "session_id": "sess_priya",
        "track_id": will_play["id"], "amount_minor": 20000, "wave_id": proposals[0]["wave_id"],
    })
    call("POST", "/api/tips", {
        "event_id": EVENT, "session_id": "sess_dev",
        "track_id": never_plays["id"], "amount_minor": 50000,
    })
    print("   Priya tipped %s on %s   (the DJ will play this)" % (money(20000), will_play["title"]))
    print("   Dev   tipped %s on %s   (the DJ never plays it)" % (money(50000), never_plays["title"]))
    print("   totals now: %s" % call("GET", "/api/tips?event_id=%s" % EVENT)["totals"])

    # ---- 6. the DJ acts --------------------------------------------------
    rule("6. DJ accepts the slot, then actually plays it")
    call("POST", "/api/insertions/accept", {
        "event_id": EVENT, "track_id": will_play["id"],
        "position": proposals[0]["position"], "wave_id": proposals[0]["wave_id"],
    })
    print("   accepted into the set — tip still PENDING (a set can change):")
    print("      %s" % call("GET", "/api/tips?event_id=%s" % EVENT)["totals"])

    call("POST", "/api/decisions", {
        "event_id": EVENT, "track_id": will_play["id"],
        "action": "play", "wave_id": proposals[0]["wave_id"],
    })
    print("   played it — Priya's tip is now earned:")
    print("      %s" % call("GET", "/api/tips?event_id=%s" % EVENT)["totals"])

    rule("7. Set ends — unplayed tips are released, not charged")
    rel = call("POST", "/api/tips/release", {"event_id": EVENT})
    print("   released %d tip(s): %s" % (rel["released"], rel["totals"]))
    print("   Dev is not charged for a request that never landed.")

    stats = call("GET", "/api/stats?event_id=%s" % EVENT)
    rule("Summary")
    print("   %d requests from %d devices -> %d waves (%.0f%% compression)"
          % (stats["total_requests"], stats["unique_sessions"],
             stats["wave_count"], stats["compression_ratio"] * 100))
    print("   interpretation: %.1f ms avg" % stats["avg_interpret_ms"])


if __name__ == "__main__":
    main()
