"""The chaos corpus.

These are the requests the demo fires at the engine. They are deliberately
messy -- slang, Hinglish, typos, emoji, artist names, vague vibes, and a few
that are barely coherent -- because the pitch only lands if the input visibly
looks like real crowd noise and the output still snaps into clean waves.

Grouped by the family each request *should* land in. The groupings are the
expected answer, not an input to the engine: nothing downstream reads the keys
except the verifier, which uses them to check that clustering actually
separates the families it should.
"""

from __future__ import annotations

import random
from typing import Dict, List, Tuple

FAMILIES: Dict[str, List[str]] = {
    "punjabi_hype": [
        "PUNJABI WEDDING CHAOS",
        "diljit please 🔥",
        "bhangra bhangra bhangra",
        "we need dhol RIGHT NOW",
        "ap dhillon anything",
        "karan aujla banger pls",
        "something to do bhangra to",
        "punjabi high energy stuff",
        "sidhu moose wala 🙏",
        "balle balle time",
        "desi banger that goes crazy",
        "play shubh",
        "punjabi hype pleaseee",
        "bhangra paake floor todna hai",
        "gimme that dhol drop",
        "panjabi mc mundian to bach ke!!",
        "baraat energy songs",
        "honey singh throwback party track",
    ],
    "bollywood_romance": [
        "2010s Bollywood romance",
        "something romantic but people can still dance to it",
        "arijit singh pls 🥺",
        "slow bollywood love song",
        "romantic hindi gaana",
        "couple dance song for sangeet",
        "dil wala gaana",
        "soft romantic hindi",
        "something for the couples",
        "atif aslam vibes",
        "romantic but not too slow",
        "pyaar wala song jisme naach bhi sakein",
    ],
    "bollywood_nostalgia": [
        "2000s bollywood nostalgia",
        "90s hindi throwback",
        "that hrithik song where everyone dances",
        "old school bollywood please",
        "kishore kumar classic",
        "purane gaane bajao",
        "chaiyya chaiyya!!!",
        "srk era songs",
        "govinda dance number lol",
        "y2k bollywood bangers",
        "childhood hindi songs",
        "retro filmi vibes",
    ],
    "hiphop": [
        "drake",
        "some hip hop pls",
        "rap bangers only",
        "travis scott 🔥🔥",
        "trap music",
        "kendrick anything",
        "hip hop to turn up to",
        "throw on some rap",
        "doja cat",
        "aggressive rap for the gym crowd lol",
        "cardi b!!",
    ],
    "house": [
        "peak time house",
        "fred again please",
        "deep house vibes",
        "techno!!!",
        "edm drop pls",
        "something euphoric and electronic",
        "peggy gou",
        "house music all night",
        "big room anthem",
        "calvin harris type stuff",
        "underground techno pls not commercial",
    ],
    "latin_afro": [
        "bad bunny",
        "reggaeton pls",
        "afrobeats!!",
        "burna boy",
        "amapiano vibes",
        "karol g 💃",
        "latin party music",
        "wizkid or rema",
    ],
    "retro_western": [
        "ABBA dancing queen",
        "80s throwback",
        "michael jackson pls",
        "disco classics",
        "queen - dont stop me now!!",
        "sing along classics everyone knows",
    ],
    "chill": [
        "cool it down for a bit",
        "something chill",
        "we need a breather song",
        "slow it down pls",
        "mellow vibes",
    ],
    "noise": [
        "asdkjhasd",
        "play something good",
        "idk surprise me",
        "anything but techno",
        "🔥🔥🔥🔥",
        "MUSIC",
        "whatever the dj wants tbh",
    ],
}

# Families that must remain distinguishable from one another for the demo to
# read as intelligent. The verifier asserts these do not collapse together.
MUST_SEPARATE: List[Tuple[str, str]] = [
    ("punjabi_hype", "bollywood_romance"),
    ("punjabi_hype", "house"),
    ("bollywood_romance", "hiphop"),
    ("house", "bollywood_nostalgia"),
    ("chill", "punjabi_hype"),
]


def all_requests() -> List[str]:
    out: List[str] = []
    for texts in FAMILIES.values():
        out.extend(texts)
    return out


def labelled_requests() -> List[Tuple[str, str]]:
    """[(family, text), ...] -- used by the verifier to score cluster purity."""
    out: List[Tuple[str, str]] = []
    for family, texts in FAMILIES.items():
        for text in texts:
            out.append((family, text))
    return out


def sample(count: int = 50, seed: int = None) -> List[str]:
    """A shuffled sample skewed to look like a real floor.

    Real crowds are not uniform: a wedding has a dominant Punjabi contingent and
    a long tail of everything else. A flat sample would make the dominant-wave
    story look artificial, so we weight the draw.
    """
    rng = random.Random(seed)
    weights = {
        "punjabi_hype": 3.0,
        "bollywood_nostalgia": 2.2,
        "bollywood_romance": 2.0,
        "hiphop": 1.5,
        "house": 1.4,
        "latin_afro": 0.9,
        "retro_western": 0.8,
        "chill": 0.6,
        "noise": 0.7,
    }
    pool: List[str] = []
    for family, texts in FAMILIES.items():
        repeats = max(1, int(round(weights.get(family, 1.0) * 2)))
        for _ in range(repeats):
            pool.extend(texts)

    rng.shuffle(pool)
    picked: List[str] = []
    seen: Dict[str, int] = {}
    for text in pool:
        # Allow a few genuine repeats (different people do ask for the same
        # thing) but not so many that the corpus looks copy-pasted.
        if seen.get(text, 0) >= 2:
            continue
        seen[text] = seen.get(text, 0) + 1
        picked.append(text)
        if len(picked) >= count:
            break

    while len(picked) < count:
        picked.append(rng.choice(all_requests()))
    return picked[:count]
