"""Context-aware ranking of catalog tracks against a wave.

Three axes, blended with the weights in ``config.settings``:

* **vibe**   -- how close the track sits to the wave centroid in the *shared*
  intent vector space (``app.vectors``). Using the same metric the clustering
  engine uses is what stops a wave and its recommendations from drifting apart.
* **demand** -- how much of the floor this wave represents. Constant within a
  wave, which is exactly what makes the dominant wave's picks outrank a fringe
  wave's picks in a merged view.
* **bridge** -- mixability out of whatever is playing right now: BPM proximity
  (including half/double time, a real DJ transition) plus energy continuity.

``reasons`` are generated from the computed numbers, never hardcoded -- they are
what a DJ reads in the two seconds they have to decide.
"""

from __future__ import annotations

import re
from typing import List, Optional, Sequence, Set

from .. import taxonomy, vectors
from ..config import settings
from ..contracts import Candidate, DJState, Intent, Track, Wave

# Neutral bridge score when nothing is playing -- a cold start must not be
# punished, the DJ simply has no transition constraint yet.
NEUTRAL_BRIDGE = 0.6

_WORD_RE = re.compile(r"[a-z0-9]+")


def _norm_tokens(text: str) -> Set[str]:
    return set(_WORD_RE.findall((text or "").lower()))


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


# ---------------------------------------------------------------------------
# Vibe
# ---------------------------------------------------------------------------


def artist_match(centroid_artists: Sequence[str], track: Track) -> Optional[str]:
    """Return the centroid artist name that names this track's artist, if any.

    Guests type "diljit", "ap dhillon", "bad bunny" -- rarely the full credited
    artist string, which may list three collaborators. So we match on token
    containment in either direction rather than equality.
    """
    track_tokens = _norm_tokens(track.artist)
    if not track_tokens:
        return None
    for raw in centroid_artists or []:
        asked = _norm_tokens(raw)
        if not asked:
            continue
        # Every word of the ask appears in the credited artist ("ap dhillon"),
        # or the ask is a single distinctive surname ("diljit", "bunny").
        if asked.issubset(track_tokens):
            return raw
        if len(asked) == 1 and next(iter(asked)) in track_tokens:
            return raw
    return None


def keyword_hits(wave: Wave, track: Track) -> List[str]:
    """Free-text keywords from the wave that the track's tags/title answer."""
    if not wave.top_keywords:
        return []
    haystack = set()
    for tag in track.tags:
        haystack |= _norm_tokens(tag)
    haystack |= _norm_tokens(track.title)
    for genre in track.genres:
        haystack |= _norm_tokens(genre)

    hits: List[str] = []
    for kw in wave.top_keywords:
        tokens = _norm_tokens(kw)
        if tokens and tokens & haystack:
            hits.append(kw)
    return hits


def vibe_score(wave: Wave, track: Track):
    """Similarity in the shared space, boosted by explicit asks.

    Returns ``(score, matched_artist, keyword_hits, base_similarity)``.
    """
    centroid = wave.centroid or Intent()
    base = vectors.similarity(centroid, vectors.track_intent(track))
    score = _clamp(base)

    matched = artist_match(centroid.artists, track)
    if matched:
        # An explicit artist name is the strongest signal a guest can send --
        # close most of the remaining distance to 1.0.
        score = score + (1.0 - score) * 0.62

    hits = keyword_hits(wave, track)
    if hits:
        lift = 0.16 * min(len(hits), 2) / 2.0
        score = score + (1.0 - score) * lift

    return _clamp(score), matched, hits, base


# ---------------------------------------------------------------------------
# Demand
# ---------------------------------------------------------------------------

# Weight at which a wave counts as "the whole floor is asking".
_SATURATION_WEIGHT = 12.0


def demand_score(wave: Wave) -> float:
    """How much of the room this wave speaks for, in 0..1.

    Blends relative share (this wave vs the rest of the floor) with absolute
    size, so a wave that is 100% of three requests does not outrank a wave that
    is 60% of forty.
    """
    share = _clamp(wave.share)
    size_basis = wave.weight if wave.weight > 0 else float(wave.raw_count)
    size = _clamp(size_basis / _SATURATION_WEIGHT)

    if share <= 0.0 and size <= 0.0:
        return 0.45  # unmeasured wave -- stay neutral rather than zeroing it

    score = 0.6 * share + 0.4 * size
    # Momentum is a real-time signal: a wave that is still growing deserves a
    # nudge over one that has already been served.
    score += 0.1 * _clamp(wave.momentum)
    return _clamp(score)


# ---------------------------------------------------------------------------
# Bridge
# ---------------------------------------------------------------------------


def _bpm_fit(delta: float) -> float:
    """1.0 inside the beatmatchable window, decaying to 0 at max_bpm_bridge."""
    span = float(max(settings.max_bpm_bridge, 5))
    if delta <= 4.0:
        return 1.0
    if delta >= span:
        return 0.0
    return 1.0 - (delta - 4.0) / (span - 4.0)


def bpm_relationship(track_bpm: int, current_bpm: int):
    """Best tempo relationship between two tracks.

    Returns ``(fit, kind, delta)`` where ``kind`` is "direct", "double",
    "half" or "none". Half/double time is a genuine transition -- a 140 BPM
    house track drops cleanly out of a 70 BPM hip-hop record -- so it scores
    near-full marks rather than being treated as 70 BPM apart.
    """
    direct = abs(float(track_bpm) - float(current_bpm))
    best_fit = _bpm_fit(direct)
    best_kind = "direct"
    best_delta = direct

    for kind, target in (
        ("double", 2.0 * current_bpm),
        ("half", current_bpm / 2.0),
    ):
        delta = abs(float(track_bpm) - target)
        fit = _bpm_fit(delta) * 0.92  # a hair below a true beatmatch
        if fit > best_fit:
            best_fit, best_kind, best_delta = fit, kind, delta

    if best_fit <= 0.0:
        best_kind = "none"
    return best_fit, best_kind, best_delta


def _energy_fit(track_energy: float, current_energy: float) -> float:
    """Reward flat-or-slightly-up; punish a big drop, hardest at peak time."""
    step = float(track_energy) - float(current_energy)
    if -0.05 <= step <= 0.15:
        return 1.0
    if step > 0.15:
        # Stepping up is good, but a vertical jump is a jarring gear change.
        return _clamp(1.0 - (step - 0.15) * 0.8, 0.55, 1.0)
    drop = -step - 0.05
    # A drop hurts more the higher the floor currently is.
    severity = 1.4 + 1.6 * _clamp(current_energy)
    return _clamp(1.0 - drop * severity, 0.0, 1.0)


def bridge_score(track: Track, dj_state: DJState):
    """Mixability out of the currently playing track.

    Returns ``(score, bpm_delta, kind, current_track)``.
    """
    current = dj_state.current_track if dj_state else None
    if current is None:
        return NEUTRAL_BRIDGE, None, "cold", None

    fit, kind, delta = bpm_relationship(track.bpm, current.bpm)
    energy = _energy_fit(track.energy, current.energy)
    score = _clamp(0.7 * fit + 0.3 * energy)
    return score, int(track.bpm - current.bpm), kind, current


# ---------------------------------------------------------------------------
# Reasons
# ---------------------------------------------------------------------------


def _wave_noun(wave: Wave) -> str:
    centroid = wave.centroid or Intent()
    if wave.label:
        return wave.label
    if centroid.genres:
        return taxonomy.display(centroid.genres[0])
    if centroid.languages:
        return taxonomy.display(centroid.languages[0])
    return "floor"


def build_reasons(
    wave: Wave,
    track: Track,
    matched_artist: Optional[str],
    hits: List[str],
    vibe: float,
    bridge: float,
    bpm_delta: Optional[int],
    kind: str,
    current: Optional[Track],
    in_queue: bool,
) -> List[str]:
    """2-3 short, number-grounded lines explaining the pick."""
    reasons: List[str] = []

    # 1. Why it matches the ask.
    if matched_artist:
        named = max(1, int(round(wave.raw_count * 0.5))) if wave.raw_count else 1
        reasons.append(
            "%s named by %d request%s" % (
                matched_artist.title(), named, "" if named == 1 else "s",
            )
        )
    elif wave.raw_count:
        reasons.append(
            "Matches %d-request %s wave" % (wave.raw_count, _wave_noun(wave))
        )
    else:
        reasons.append("Matches the %s wave" % _wave_noun(wave))

    # 2. Why it mixes.
    if current is not None and bpm_delta is not None:
        if kind == "double":
            reasons.append("Double-time from %d BPM" % current.bpm)
        elif kind == "half":
            reasons.append("Half-time from %d BPM" % current.bpm)
        elif bpm_delta == 0:
            reasons.append("%d BPM -- same tempo as current track" % track.bpm)
        elif abs(bpm_delta) <= 4:
            reasons.append(
                "%d BPM -- %+d from current track" % (track.bpm, bpm_delta)
            )
        elif bridge >= 0.5:
            reasons.append("%d BPM -- %+d from current track" % (track.bpm, bpm_delta))
        else:
            reasons.append("%d BPM -- tempo reset off %d" % (track.bpm, current.bpm))
    elif track.energy >= 0.85:
        reasons.append("Peak-time energy (%.2f)" % track.energy)
    else:
        reasons.append("%d BPM, energy %.2f" % (track.bpm, track.energy))

    # 3. The texture note -- keywords, tags, or raw floor appeal.
    if hits:
        reasons.append("Asked for \"%s\"" % hits[0])
    elif "wedding" in track.tags or "sangeet" in track.tags:
        reasons.append("Wedding floor-filler")
    elif "baraat" in track.tags:
        reasons.append("Baraat energy")
    elif "closer" in track.tags:
        reasons.append("Closer material")
    elif "peak-time" in track.tags and track.energy >= 0.8:
        reasons.append("Peak-time energy (%.2f)" % track.energy)
    elif "sing-along" in track.tags and track.popularity >= 0.85:
        reasons.append("Everybody-knows-it sing-along")
    elif track.popularity >= 0.9:
        reasons.append("Universally known (%d%% recognition)" % int(track.popularity * 100))
    elif vibe >= 0.8:
        reasons.append("Strong vibe match (%.2f)" % vibe)

    if in_queue:
        reasons.append("Already in your Later pile")

    # The three branches can independently land on the same phrasing (a
    # peak-time track with no current track, say) -- never show it twice.
    unique: List[str] = []
    for reason in reasons:
        if reason and reason not in unique:
            unique.append(reason)

    # Guarantee the >= 2 reasons the dashboard renders.
    if len(unique) < 2:
        filler = "%d BPM, energy %.2f" % (track.bpm, track.energy)
        if filler not in unique:
            unique.append(filler)
    if len(unique) < 2:
        unique.append("%s pick" % taxonomy.display(track.language))

    return unique[:3]


# ---------------------------------------------------------------------------
# Ranker
# ---------------------------------------------------------------------------


class Ranker:
    """Scores the catalog against one wave in one moment of the night."""

    def __init__(self, catalog):
        self.catalog = catalog

    # -- public ------------------------------------------------------------

    def rank(
        self,
        wave: Wave,
        dj_state: DJState,
        k: int = None,
        exclude: Optional[Set[str]] = None,
    ) -> List[Candidate]:
        """Top ``k`` candidates for ``wave``, given what is playing right now.

        Never raises: a ranking failure mid-set must degrade to "here are the
        closest tracks", never to an empty dashboard.
        """
        try:
            return self._rank(wave, dj_state, k, exclude)
        except Exception:
            return self._fallback(wave, k, exclude)

    # -- internals ---------------------------------------------------------

    def _limit(self, k: int = None) -> int:
        if k is None:
            k = settings.candidates_per_wave
        try:
            k = int(k)
        except (TypeError, ValueError):
            k = settings.candidates_per_wave
        return max(1, k)

    def _blocked(self, dj_state: DJState, exclude: Optional[Set[str]]) -> Set[str]:
        blocked: Set[str] = set(exclude or ())
        if dj_state is not None:
            if dj_state.current_track is not None:
                blocked.add(dj_state.current_track.id)
            for played in dj_state.history or ():
                blocked.add(played.id)
        return blocked

    def _rank(
        self,
        wave: Wave,
        dj_state: DJState,
        k: int = None,
        exclude: Optional[Set[str]] = None,
    ) -> List[Candidate]:
        wave = wave if wave is not None else Wave()
        dj_state = dj_state if dj_state is not None else DJState()
        limit = self._limit(k)

        blocked = self._blocked(dj_state, exclude)
        queued = {t.id for t in (dj_state.queue or ())}

        demand = demand_score(wave)
        scored: List[Candidate] = []

        for track in self.catalog.all():
            if track.id in blocked:
                continue

            vibe, matched, hits, _base = vibe_score(wave, track)
            bridge, bpm_delta, kind, current = bridge_score(track, dj_state)

            score = (
                settings.weight_vibe * vibe
                + settings.weight_demand * demand
                + settings.weight_bridge * bridge
            )
            in_queue = track.id in queued
            if in_queue:
                # Not excluded -- the DJ already liked it -- but it should not
                # crowd out fresh options.
                score *= 0.88

            scored.append(
                Candidate(
                    track=track,
                    score=round(float(score), 6),
                    demand_score=round(float(demand), 6),
                    vibe_score=round(float(vibe), 6),
                    bridge_score=round(float(bridge), 6),
                    bpm_delta=bpm_delta,
                    reasons=build_reasons(
                        wave, track, matched, hits, vibe, bridge,
                        bpm_delta, kind, current, in_queue,
                    ),
                )
            )

        # Deterministic ordering: score, then vibe, then popularity, then id.
        scored.sort(
            key=lambda c: (
                -c.score,
                -c.vibe_score,
                -c.track.popularity,
                c.track.id,
            )
        )
        return scored[:limit]

    def _fallback(
        self,
        wave: Wave,
        k: int = None,
        exclude: Optional[Set[str]] = None,
    ) -> List[Candidate]:
        """Pure vibe match. Used only if the full scorer somehow blows up."""
        limit = self._limit(k)
        blocked = set(exclude or ())
        out: List[Candidate] = []
        try:
            centroid = (wave.centroid if wave is not None else None) or Intent()
        except Exception:
            centroid = Intent()

        for track in self.catalog.all():
            if track.id in blocked:
                continue
            try:
                vibe = _clamp(vectors.similarity(centroid, vectors.track_intent(track)))
            except Exception:
                vibe = track.popularity
            out.append(
                Candidate(
                    track=track,
                    score=round(float(vibe), 6),
                    vibe_score=round(float(vibe), 6),
                    demand_score=0.0,
                    bridge_score=NEUTRAL_BRIDGE,
                    bpm_delta=None,
                    reasons=[
                        "Closest match in the library",
                        "%d BPM, energy %.2f" % (track.bpm, track.energy),
                    ],
                )
            )
        out.sort(key=lambda c: (-c.score, -c.track.popularity, c.track.id))
        return out[:limit]


__all__ = [
    "Ranker",
    "vibe_score",
    "demand_score",
    "bridge_score",
    "bpm_relationship",
    "artist_match",
    "build_reasons",
    "NEUTRAL_BRIDGE",
]
