"""Shared intent vector space.

Both the clustering engine (M2) and the ranker (M3) need to measure "how close
are these two musical desires". If they each rolled their own embedding, a wave
and its recommendations would drift apart. So the projection lives here, in the
spine, and both import it.

Design note: we deliberately embed *structured intent*, not raw text. Requests
like "Diljit", "bhangra pls" and "punjabi banger" have near-zero lexical
overlap but land in almost the same place here -- which is exactly the
compression the product promises. Raw-text similarity is available separately
as a tiebreaker via ``text_similarity``.
"""

from __future__ import annotations

import math
import re
from typing import List, Optional, Sequence

import numpy as np

from . import taxonomy
from .contracts import Intent, Track


def _multi_hot(values: Sequence[str], vocabulary: Sequence[str]) -> np.ndarray:
    vec = np.zeros(len(vocabulary), dtype=np.float32)
    if not values:
        return vec
    hits = [vocabulary.index(v) for v in values if v in vocabulary]
    if not hits:
        return vec
    # L2-normalise within the block so a request naming three genres does not
    # outweigh one naming a single genre.
    magnitude = math.sqrt(len(hits))
    for index in hits:
        vec[index] = 1.0 / magnitude
    return vec


def intent_vector(intent: Intent) -> np.ndarray:
    """Project an Intent into the canonical vector space."""
    blocks: List[np.ndarray] = []
    values_by_block = {
        "languages": intent.languages,
        "genres": intent.genres,
        "moods": intent.moods,
        "eras": intent.eras,
    }
    for name, vocabulary in taxonomy.VECTOR_BLOCKS:
        block = _multi_hot(values_by_block[name], vocabulary)
        blocks.append(block * taxonomy.BLOCK_WEIGHTS[name])

    continuous = np.array(
        [intent.energy_target, intent.danceability, intent.familiarity],
        dtype=np.float32,
    )
    blocks.append(continuous * taxonomy.BLOCK_WEIGHTS["continuous"])
    return np.concatenate(blocks)


def track_intent(track: Track) -> Intent:
    """Express a catalog track as the Intent that would perfectly ask for it.

    This is what lets us score a track against a wave centroid with the same
    metric the clustering uses -- no second, divergent similarity function.
    """
    era = track.era if track.era in taxonomy.ERAS else "2010s"
    return Intent(
        languages=taxonomy.coerce("languages", [track.language]),
        genres=taxonomy.coerce("genres", track.genres),
        moods=taxonomy.coerce("moods", track.moods),
        eras=[era],
        energy_target=track.energy,
        danceability=track.danceability,
        familiarity=track.popularity,
    )


def track_vector(track: Track) -> np.ndarray:
    return intent_vector(track_intent(track))


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity, safe on zero vectors."""
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def similarity(a: Intent, b: Intent) -> float:
    """Similarity between two intents in 0..1."""
    return max(0.0, cosine(intent_vector(a), intent_vector(b)))


def centroid(intents: Sequence[Intent]) -> Intent:
    """Average a set of intents back into a representative Intent.

    Categorical blocks keep any token held by at least a third of members (so a
    wave centroid stays legible), continuous features are averaged.
    """
    if not intents:
        return Intent()

    n = len(intents)
    threshold = max(1, math.ceil(n / 3.0))

    def majority(attr: str, vocabulary: Sequence[str]) -> List[str]:
        counts = {}
        for intent in intents:
            for token in getattr(intent, attr):
                counts[token] = counts.get(token, 0) + 1
        kept = [t for t, c in counts.items() if c >= threshold and t in vocabulary]
        kept.sort(key=lambda t: -counts[t])
        return kept[:4]

    artists = {}
    for intent in intents:
        for artist in intent.artists:
            artists[artist] = artists.get(artist, 0) + 1
    top_artists = sorted(artists, key=lambda a: -artists[a])[:3]

    keywords = {}
    for intent in intents:
        for kw in intent.raw_keywords:
            keywords[kw] = keywords.get(kw, 0) + 1
    top_keywords = sorted(keywords, key=lambda k: -keywords[k])[:8]

    return Intent(
        languages=majority("languages", taxonomy.LANGUAGES),
        genres=majority("genres", taxonomy.GENRES),
        moods=majority("moods", taxonomy.MOODS),
        eras=majority("eras", taxonomy.ERAS),
        artists=top_artists,
        energy_target=float(np.mean([i.energy_target for i in intents])),
        danceability=float(np.mean([i.danceability for i in intents])),
        familiarity=float(np.mean([i.familiarity for i in intents])),
        confidence=float(np.mean([i.confidence for i in intents])),
        raw_keywords=top_keywords,
        source="centroid",
    )


# ---------------------------------------------------------------------------
# Lexical tiebreaker
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[a-z0-9']+")


def tokenize(text: str) -> List[str]:
    return _TOKEN_RE.findall((text or "").lower())


def text_similarity(a: str, b: str) -> float:
    """Jaccard over word tokens plus 3-gram overlap.

    Used only to break ties between intents that are already close -- e.g. two
    requests naming the same artist that the taxonomy does not model.
    """
    ta, tb = set(tokenize(a)), set(tokenize(b))
    if not ta or not tb:
        return 0.0
    word_j = len(ta & tb) / float(len(ta | tb))

    def grams(s: str) -> set:
        s = re.sub(r"\s+", " ", (s or "").lower()).strip()
        return {s[i : i + 3] for i in range(max(0, len(s) - 2))}

    ga, gb = grams(a), grams(b)
    gram_j = len(ga & gb) / float(len(ga | gb)) if (ga and gb) else 0.0
    return 0.6 * word_j + 0.4 * gram_j


def label_for(intent: Intent) -> str:
    """Generate a DJ-readable wave label from a centroid intent.

    "High-Energy Punjabi", "2000s Bollywood Nostalgia", "Upbeat Romantic".
    """
    parts: List[str] = []

    if intent.eras and intent.eras[0] in ("1980s", "1990s", "2000s", "2010s"):
        parts.append(taxonomy.display(intent.eras[0]))

    mood: Optional[str] = intent.moods[0] if intent.moods else None
    if mood == "hype" or (mood is None and intent.energy_target >= 0.75):
        parts.append("High-Energy")
    elif mood and mood != "nostalgic":
        parts.append(taxonomy.display(mood))

    if intent.genres:
        parts.append(taxonomy.display(intent.genres[0]))
    elif intent.languages:
        parts.append(taxonomy.display(intent.languages[0]))

    if mood == "nostalgic":
        parts.append("Nostalgia")

    if not parts:
        if intent.energy_target >= 0.7:
            parts = ["High-Energy", "Floor Fillers"]
        elif intent.energy_target <= 0.35:
            parts = ["Slow", "Burners"]
        else:
            parts = ["Mixed", "Requests"]

    # De-duplicate while preserving order (e.g. Punjabi language + Bhangra genre)
    seen = set()
    unique = []
    for part in parts:
        if part.lower() not in seen:
            seen.add(part.lower())
            unique.append(part)
    return " ".join(unique[:3])
