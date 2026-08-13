"""Deterministic intent engine -- the primary interpretation path.

CUE must work with no API key: the live demo cannot depend on a network
round-trip. So this module, not the LLM, is the product. It projects free-text
song requests onto the frozen taxonomy using a music-domain lexicon, a
longest-match n-gram scanner, weighted evidence pooling and a small set of
post-rules that encode how people actually phrase requests at a party.

Contract: ``interpret`` is synchronous, sub-millisecond, never raises, never
returns ``None``, and always returns ``Intent.sanitized()``.

Python 3.9 compatible: no ``X | Y`` annotations.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Set, Tuple

from .. import taxonomy
from ..contracts import Intent
from . import lexicon
from .lexicon import LEXICON, MAX_NGRAM, SEP, Signal

# --- defaults for a request that told us nothing -------------------------
DEFAULT_ENERGY = 0.55
DEFAULT_DANCE = 0.60
DEFAULT_FAMILIARITY = 0.55
_PRIOR_WEIGHT = 0.5  # pull of the defaults against real evidence

# --- caps so a rambling request cannot flood the vector space ------------
MAX_LANGUAGES = 3
MAX_GENRES = 4
MAX_MOODS = 3
MAX_ERAS = 2
MAX_ARTISTS = 5
MAX_KEYWORDS = 12

# --- negation ------------------------------------------------------------
NEGATION_TRIGGERS: Set[str] = {
    "no", "not", "dont", "doesnt", "cant", "never", "without", "except",
    "avoid", "hate", "skip", "nothing", "anti", "nope", "minus",
}
NEGATION_PHRASES: Set[str] = {
    "anything but", "everything but", "other than", "do not", "no more",
    "cant stand", "dont want", "sick of", "tired of", "enough of",
    "please no", "not into", "less of",
}
# Words that close a negation scope, so "not sure, maybe bhangra" does not
# accidentally veto bhangra.
NEGATION_STOP: Set[str] = {
    SEP, "but", "maybe", "instead", "just", "actually", "however", "though",
    "please", "pls", "plz", "prefer", "want", "rather",
}
NEGATION_SCOPE = 3  # tokens

_SLOW_MOODS = ("romantic", "sensual", "chill", "sad")


class _Match(object):
    __slots__ = ("start", "span", "key", "sig", "negated")

    def __init__(self, start: int, span: int, key: str, sig: Signal) -> None:
        self.start = start
        self.span = span
        self.key = key
        self.sig = sig
        self.negated = False


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def interpret(text: str) -> Intent:
    """Free text -> structured Intent. Deterministic, fast, never raises."""
    try:
        return _interpret(text)
    except Exception:  # pragma: no cover -- belt and braces, must never raise
        return _fallback(text)


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------


def _scan(tokens: Sequence[str]) -> List[_Match]:
    """Longest-match-first n-gram scan over the lexicon."""
    n_tokens = len(tokens)
    consumed = [False] * n_tokens
    matches: List[_Match] = []

    for span in range(min(MAX_NGRAM, n_tokens), 0, -1):
        for start in range(0, n_tokens - span + 1):
            if any(consumed[start:start + span]):
                continue
            key = " ".join(tokens[start:start + span])
            sig = LEXICON.get(key)
            if sig is None:
                continue
            for i in range(start, start + span):
                consumed[i] = True
            matches.append(_Match(start, span, key, sig))

    matches.sort(key=lambda m: m.start)
    return matches


def _negation_spans(tokens: Sequence[str]) -> List[Tuple[int, int]]:
    """Token index ranges [start, end) that sit under a negation."""
    spans: List[Tuple[int, int]] = []
    n_tokens = len(tokens)
    i = 0
    while i < n_tokens:
        trigger_len = 0
        if i + 1 < n_tokens and " ".join(tokens[i:i + 2]) in NEGATION_PHRASES:
            trigger_len = 2
        elif tokens[i] in NEGATION_TRIGGERS:
            trigger_len = 1
        if trigger_len:
            start = i + trigger_len
            end = start
            while end < n_tokens and end - start < NEGATION_SCOPE:
                if tokens[end] in NEGATION_STOP:
                    break
                end += 1
            if end > start:
                spans.append((start, end))
            i = start
            continue
        i += 1
    return spans


def _is_negated(match: _Match, spans: Sequence[Tuple[int, int]]) -> bool:
    for start, end in spans:
        if start <= match.start < end:
            return True
    return False


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------


def _interpret(text: str) -> Intent:
    raw = (text or "")[:400]
    tokens = lexicon.normalize(raw)
    if not tokens:
        return _fallback(raw)

    matches = _scan(tokens)
    spans = _negation_spans(tokens)
    for match in matches:
        match.negated = _is_negated(match, spans)

    lang_scores: Dict[str, float] = {}
    genre_scores: Dict[str, float] = {}
    mood_scores: Dict[str, float] = {}
    era_scores: Dict[str, float] = {}
    banned: Set[str] = set()

    energy_votes: List[Tuple[float, float]] = [(DEFAULT_ENERGY, _PRIOR_WEIGHT)]
    dance_votes: List[Tuple[float, float]] = [(DEFAULT_DANCE, _PRIOR_WEIGHT)]
    fam_votes: List[Tuple[float, float]] = [
        (DEFAULT_FAMILIARITY, _PRIOR_WEIGHT)
    ]

    artists: List[str] = []
    keywords: List[str] = []
    tempo_votes: List[Tuple[str, float]] = []
    dance_cue = False
    positive_hits = 0

    scores_by_block = {
        "languages": lang_scores,
        "genres": genre_scores,
        "moods": mood_scores,
        "eras": era_scores,
    }

    for match in matches:
        sig = match.sig
        values_by_block = (
            ("languages", sig.languages),
            ("genres", sig.genres),
            ("moods", sig.moods),
            ("eras", sig.eras),
        )

        if match.negated:
            # Veto the tokens, and flip any energy hint ("nothing slow").
            for block, values in values_by_block:
                for value in values:
                    if taxonomy.is_valid(block, value):
                        banned.add(value)
            if sig.energy is not None:
                energy_votes.append((1.0 - sig.energy, 1.0))
            continue

        positive_hits += 1
        keywords.append(match.key)

        for block, values in values_by_block:
            bucket = scores_by_block[block]
            for value in values:
                if taxonomy.is_valid(block, value):
                    bucket[value] = bucket.get(value, 0.0) + sig.weight

        if sig.energy is not None:
            energy_votes.append((sig.energy, sig.weight))
        if sig.dance is not None:
            dance_votes.append((sig.dance, sig.weight))
        if sig.familiarity is not None:
            fam_votes.append((sig.familiarity, sig.weight))
        if sig.tempo in taxonomy.TEMPO_HINTS:
            tempo_votes.append((sig.tempo, sig.weight))
        if sig.artist and sig.artist not in artists:
            artists.append(sig.artist)
        if match.key in lexicon.DANCE_CUES:
            dance_cue = True

    languages = _top(lang_scores, banned, MAX_LANGUAGES)
    genres = _top(genre_scores, banned, MAX_GENRES)
    moods = _top(mood_scores, banned, MAX_MOODS)
    eras = _top(era_scores, banned, MAX_ERAS)

    energy = _weighted(energy_votes, DEFAULT_ENERGY)
    dance = _weighted(dance_votes, DEFAULT_DANCE)
    familiarity = _weighted(fam_votes, DEFAULT_FAMILIARITY)

    # ---- post-rules: how requests actually behave ----------------------
    mood_set = set(moods)

    if "hype" in mood_set or "aggressive" in mood_set:
        energy = max(energy, 0.75)
    if "celebratory" in mood_set:
        energy = max(energy, 0.70)
        dance = max(dance, 0.78)
    if "euphoric" in mood_set:
        energy = max(energy, 0.68)
    if "chill" in mood_set and "hype" not in mood_set:
        energy = min(energy, 0.48)
    if "sad" in mood_set and "hype" not in mood_set:
        energy = min(energy, 0.42)
    if "romantic" in mood_set and not dance_cue:
        energy = min(energy, 0.50)
    if genres and set(genres) & {"bhangra", "reggaeton", "amapiano", "disco"}:
        dance = max(dance, 0.80)

    # "romantic but people can still dance to it" -- the PRD's canonical
    # ambivalent request. Keep the mood, lift the floor, keep it mixable.
    if dance_cue and (mood_set & set(_SLOW_MOODS)):
        energy = min(max(energy, 0.60), 0.72)
        dance = max(dance, 0.80)

    if not artists and languages == [] and genres == [] and moods == []:
        # nothing categorical landed -- stay neutral rather than guessing loud
        energy = min(max(energy, 0.35), 0.75)

    tempo_hint = _tempo(tempo_votes, energy)
    confidence = _confidence(positive_hits, languages, genres, moods, eras,
                             artists, tempo_votes)
    summary = _summary(languages, genres, moods, eras, energy, dance, raw,
                       positive_hits > 0)

    return Intent(
        languages=languages,
        genres=genres,
        moods=moods,
        artists=artists[:MAX_ARTISTS],
        eras=eras,
        energy_target=_clamp(energy),
        danceability=_clamp(dance),
        familiarity=_clamp(familiarity),
        tempo_hint=tempo_hint,
        confidence=confidence,
        source="rules",
        raw_keywords=_dedupe(keywords)[:MAX_KEYWORDS],
        summary=summary,
    ).sanitized()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def _dedupe(items: Sequence[str]) -> List[str]:
    seen: Set[str] = set()
    out: List[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _top(scores: Dict[str, float], banned: Set[str], limit: int) -> List[str]:
    """Highest-scoring tokens, ties broken by first-mention order."""
    order = {token: i for i, token in enumerate(scores)}
    kept = [t for t in scores if t not in banned]
    kept.sort(key=lambda t: (-scores[t], order[t]))
    return kept[:limit]


def _weighted(votes: Sequence[Tuple[float, float]], default: float) -> float:
    total = sum(w for _, w in votes)
    if total <= 0:
        return default
    return sum(v * w for v, w in votes) / total


def _tempo(votes: Sequence[Tuple[str, float]], energy: float) -> str:
    if votes:
        pooled: Dict[str, float] = {}
        for hint, weight in votes:
            pooled[hint] = pooled.get(hint, 0.0) + weight
        return max(pooled, key=lambda k: pooled[k])
    if energy >= 0.72:
        return "fast"
    if energy <= 0.35:
        return "slow"
    return "mid"


def _confidence(
    hits: int,
    languages: List[str],
    genres: List[str],
    moods: List[str],
    eras: List[str],
    artists: List[str],
    tempo_votes: Sequence[Tuple[str, float]],
) -> float:
    """More independent signals -> more confidence. Never certain, never zero."""
    filled = sum(
        1 for block in (languages, genres, moods, eras, artists) if block
    )
    score = 0.28 + 0.085 * min(hits, 4) + 0.07 * filled
    if tempo_votes:
        score += 0.03
    return round(_clamp(score, 0.15, 0.95), 3)


def _summary(
    languages: List[str],
    genres: List[str],
    moods: List[str],
    eras: List[str],
    energy: float,
    dance: float,
    raw: str,
    has_signal: bool,
) -> str:
    """A short human phrase: 'high-energy Punjabi', '2000s Bollywood romance'."""
    snippet = " ".join((raw or "").split())[:44].strip()
    if not has_signal:
        # Nothing in the lexicon fired -- echo the guest rather than invent.
        return snippet if snippet else "open to anything"

    parts: List[str] = []
    mood_set = set(moods)

    if eras:
        parts.append(taxonomy.display(eras[0]))

    lead: Optional[str] = None
    if "hype" in mood_set or energy >= 0.78:
        lead = "high-energy"
    elif "aggressive" in mood_set:
        lead = "hard-hitting"
    elif "euphoric" in mood_set:
        lead = "euphoric"
    elif "dark" in mood_set:
        lead = "dark"
    elif "chill" in mood_set:
        lead = "chill"
    elif "sensual" in mood_set:
        lead = "sensual"
    elif "sad" in mood_set:
        lead = "melancholy"
    elif "nostalgic" in mood_set and not (eras and (genres or languages)):
        lead = "throwback"
    elif energy <= 0.38:
        lead = "slow"
    if lead:
        parts.append(lead)

    core: Optional[str] = None
    if genres:
        core = taxonomy.display(genres[0])
    elif languages:
        core = taxonomy.display(languages[0])

    tail: Optional[str] = None
    if "romantic" in mood_set:
        tail = "romance"
    elif "celebratory" in mood_set and lead is None:
        tail = "celebration"

    if core is None:
        # No language or genre landed -- give the phrase something to stand on
        # so the guest reads a description rather than a lone adjective.
        if tail == "romance":
            parts.append("danceable" if dance >= 0.75 else "slow")
        elif lead is not None:
            core = "floor fillers" if energy >= 0.68 else "vibes"

    if core:
        parts.append(core)
    if tail:
        parts.append(tail)

    if not parts:
        return snippet if snippet else "open to anything"

    # de-duplicate ("Punjabi Bhangra" -> "Bhangra") while keeping order
    seen: Set[str] = set()
    unique: List[str] = []
    for part in parts:
        if part.lower() not in seen:
            seen.add(part.lower())
            unique.append(part)
    return " ".join(unique[:4])


def _fallback(text: str) -> Intent:
    """Valid, honest, low-confidence Intent for input we could not read."""
    snippet = " ".join((text or "").split())[:44].strip()
    return Intent(
        energy_target=DEFAULT_ENERGY,
        danceability=DEFAULT_DANCE,
        familiarity=DEFAULT_FAMILIARITY,
        tempo_hint="mid",
        confidence=0.2 if snippet else 0.15,
        source="rules",
        raw_keywords=[],
        summary=snippet if snippet else "open to anything",
    ).sanitized()
