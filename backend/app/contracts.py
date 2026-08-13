"""Frozen data contracts for CUE.

Every module boundary in the system is expressed here. Agents building M1-M7
import from this module and must not redefine or widen these shapes. Python 3.9
compatible (``typing.Optional`` / ``typing.List``, never ``X | Y``).
"""

from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from . import taxonomy


def new_id(prefix: str) -> str:
    return "%s_%s" % (prefix, uuid.uuid4().hex[:10])


def now_ts() -> float:
    return time.time()


# ---------------------------------------------------------------------------
# M1 -- Intent
# ---------------------------------------------------------------------------


class Intent(BaseModel):
    """Structured musical intent extracted from a free-text request.

    This is the projection that makes clustering work: raw text like "Diljit",
    "bhangra pls" and "punjabi banger" share almost no tokens but collapse onto
    nearly the same Intent, and therefore the same wave.
    """

    languages: List[str] = Field(default_factory=list)
    genres: List[str] = Field(default_factory=list)
    moods: List[str] = Field(default_factory=list)
    artists: List[str] = Field(default_factory=list)
    eras: List[str] = Field(default_factory=list)

    energy_target: float = 0.5  # 0 = ballad, 1 = peak-time
    danceability: float = 0.5
    familiarity: float = 0.5  # 0 = deep cut, 1 = everybody knows it

    tempo_hint: Optional[str] = None  # one of taxonomy.TEMPO_HINTS
    confidence: float = 0.5
    source: str = "rules"  # "rules" | "llm" | "hybrid"

    raw_keywords: List[str] = Field(default_factory=list)
    summary: str = ""  # e.g. "high-energy Punjabi"

    def sanitized(self) -> "Intent":
        """Return a copy with all vocabularies coerced to the taxonomy."""
        return Intent(
            languages=taxonomy.coerce("languages", self.languages),
            genres=taxonomy.coerce("genres", self.genres),
            moods=taxonomy.coerce("moods", self.moods),
            artists=[a.strip() for a in self.artists if str(a).strip()][:5],
            eras=taxonomy.coerce("eras", self.eras),
            energy_target=_clamp(self.energy_target),
            danceability=_clamp(self.danceability),
            familiarity=_clamp(self.familiarity),
            tempo_hint=self.tempo_hint
            if self.tempo_hint in taxonomy.TEMPO_HINTS
            else None,
            confidence=_clamp(self.confidence),
            source=self.source,
            raw_keywords=self.raw_keywords[:12],
            summary=self.summary,
        )


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.5
    return max(low, min(high, v))


# ---------------------------------------------------------------------------
# M2 -- Requests and waves
# ---------------------------------------------------------------------------


class SongRequest(BaseModel):
    """One guest submission, after interpretation."""

    id: str = Field(default_factory=lambda: new_id("req"))
    event_id: str = "default"
    session_id: str = ""
    text: str = ""
    intent: Intent = Field(default_factory=Intent)

    # Anti-manipulation: 1.0 for a first request from a session, decayed for
    # rapid-fire or near-duplicate submissions from the same device.
    weight: float = 1.0
    discount_reason: Optional[str] = None

    wave_id: Optional[str] = None
    created_at: float = Field(default_factory=now_ts)


class Wave(BaseModel):
    """A semantic cluster of requests -- what the DJ actually reads."""

    id: str = Field(default_factory=lambda: new_id("wave"))
    event_id: str = "default"

    label: str = ""  # "High-Energy Punjabi"
    summary: str = ""  # one-line description for the dashboard
    centroid: Intent = Field(default_factory=Intent)

    request_ids: List[str] = Field(default_factory=list)
    raw_count: int = 0  # total requests in the cluster
    unique_sessions: int = 0  # distinct devices -- the honest number
    weight: float = 0.0  # anti-manipulation adjusted demand

    momentum: float = 0.0  # share of weight arriving in the last 120s
    share: float = 0.0  # this wave's weight / total weight, 0..1
    top_keywords: List[str] = Field(default_factory=list)
    sample_texts: List[str] = Field(default_factory=list)

    created_at: float = Field(default_factory=now_ts)
    updated_at: float = Field(default_factory=now_ts)


# ---------------------------------------------------------------------------
# M3 -- Catalog and ranking
# ---------------------------------------------------------------------------


class Track(BaseModel):
    id: str
    title: str
    artist: str
    language: str = "english"
    genres: List[str] = Field(default_factory=list)
    moods: List[str] = Field(default_factory=list)
    era: str = "2010s"

    bpm: int = 120
    energy: float = 0.5
    danceability: float = 0.5
    popularity: float = 0.5  # proxy for familiarity
    duration_sec: int = 210

    audio_file: Optional[str] = None  # relative path under audio/, optional
    tags: List[str] = Field(default_factory=list)


class Candidate(BaseModel):
    """A ranked track recommendation for a wave, with its reasoning."""

    track: Track
    score: float = 0.0

    demand_score: float = 0.0  # how big the wave is
    vibe_score: float = 0.0  # intent match
    bridge_score: float = 0.0  # mixability from the currently playing track

    bpm_delta: Optional[int] = None
    reasons: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# M4 -- DJ state, decisions, transport
# ---------------------------------------------------------------------------


class SetlistEntry(BaseModel):
    """One slot in the DJ's planned set.

    ``position`` is the running order (0 = first). ``played_at`` is set when the
    DJ actually reaches it, so a set can be partly behind and partly ahead --
    which is the whole point: insertion only ever happens ahead of the needle.
    """

    id: str = Field(default_factory=lambda: new_id("slot"))
    position: int = 0
    track: Track
    # Wall-clock offset into the set, as scraped from the DJ's own history
    # ("00:54:53"). Kept as a string because it is display provenance, not
    # something we compute with.
    cue_time: Optional[str] = None
    played_at: Optional[float] = None
    # Set when this slot exists because CUE inserted a crowd request into it,
    # rather than because the DJ planned it.
    inserted_from_wave_id: Optional[str] = None


class TipState(str, Enum):
    """A tip is a promise, not a payment.

    The guest authorises it against one requested track; the DJ only actually
    receives it if that track gets played. Anything still ``pending`` when the
    set ends is released, never captured -- the guest is not charged for a
    request that never landed.
    """

    PENDING = "pending"
    CAPTURED = "captured"
    RELEASED = "released"


class Tip(BaseModel):
    id: str = Field(default_factory=lambda: new_id("tip"))
    event_id: str = "default"
    session_id: str = ""
    track_id: str = ""
    wave_id: Optional[str] = None
    # Minor units (paise/cents) as an int -- never a float, money is not a
    # rounding exercise.
    amount_minor: int = 0
    currency: str = "INR"
    state: TipState = TipState.PENDING
    created_at: float = Field(default_factory=now_ts)
    settled_at: Optional[float] = None

    @property
    def is_live(self) -> bool:
        """Still capable of influencing a queue decision."""
        return self.state == TipState.PENDING


class DJState(BaseModel):
    event_id: str = "default"
    current_track: Optional[Track] = None
    started_at: Optional[float] = None
    queue: List[Track] = Field(default_factory=list)  # the "Later" pile
    history: List[Track] = Field(default_factory=list)
    # The DJ's planned set. Empty for a freestyle event; when present, crowd
    # requests are slotted into it rather than recommended loose.
    setlist: List[SetlistEntry] = Field(default_factory=list)

    @property
    def current_bpm(self) -> Optional[int]:
        return self.current_track.bpm if self.current_track else None

    @property
    def current_energy(self) -> Optional[float]:
        return self.current_track.energy if self.current_track else None

    def upcoming(self, limit: Optional[int] = None) -> List["SetlistEntry"]:
        """Slots still ahead of the needle, in running order."""
        ahead = [e for e in self.setlist if e.played_at is None]
        ahead.sort(key=lambda e: e.position)
        return ahead if limit is None else ahead[:limit]


class SlotProposal(BaseModel):
    """Where a requested track should go in the DJ's planned set.

    The unit of the setlist-aware product: not "play this", but "put this
    *here*, between these two tracks, and here is what it does to the mix".
    """

    track: Track
    wave_id: Optional[str] = None
    wave_label: str = ""

    # Insert *before* the upcoming slot at this position. ``after``/``before``
    # are the neighbours the fit was actually judged against.
    position: int = 0
    after: Optional[Track] = None
    before: Optional[Track] = None

    score: float = 0.0
    demand_score: float = 0.0
    vibe_score: float = 0.0
    # Two-sided mixability: out of ``after`` and into ``before``.
    bridge_in: float = 0.0
    bridge_out: float = 0.0

    bpm_delta_in: Optional[int] = None
    bpm_delta_out: Optional[int] = None

    # Tip money riding on this track, and whether it decided the placement.
    tip_minor: int = 0
    tip_broke_tie: bool = False

    reasons: List[str] = Field(default_factory=list)


class Decision(BaseModel):
    id: str = Field(default_factory=lambda: new_id("dec"))
    event_id: str = "default"
    wave_id: Optional[str] = None
    track_id: str = ""
    action: str = "play"  # one of taxonomy.DJ_ACTIONS
    created_at: float = Field(default_factory=now_ts)


# ---- HTTP payloads --------------------------------------------------------


class RequestCreate(BaseModel):
    text: str
    session_id: Optional[str] = None
    event_id: str = "default"


class RequestAck(BaseModel):
    """Instant validation returned to the guest -- must feel understood."""

    request_id: str
    session_id: str
    message: str  # "Got it. You want high-energy Punjabi..."
    intent_summary: str
    wave_id: Optional[str] = None
    wave_label: str = ""
    wave_size: int = 0
    joined_existing_wave: bool = False


class DecisionCreate(BaseModel):
    track_id: str
    action: str
    wave_id: Optional[str] = None
    event_id: str = "default"


class WaveView(BaseModel):
    """A wave plus its ranked candidates -- the dashboard's unit of display."""

    wave: Wave
    candidates: List[Candidate] = Field(default_factory=list)


class DashboardState(BaseModel):
    event_id: str = "default"
    waves: List[WaveView] = Field(default_factory=list)
    dj: DJState = Field(default_factory=DJState)
    stats: "EventStats" = Field(default_factory=lambda: EventStats())


class EventStats(BaseModel):
    total_requests: int = 0
    unique_sessions: int = 0
    wave_count: int = 0
    compression_ratio: float = 0.0  # 1 - (waves / requests)
    decisions_made: int = 0
    actionability: float = 0.0  # play|later decisions / dominant waves shown
    avg_interpret_ms: float = 0.0
    llm_enabled: bool = False


class WSMessage(BaseModel):
    """Everything pushed over the dashboard socket."""

    type: str  # "state" | "wave_update" | "request" | "decision" | "now_playing"
    payload: Dict[str, Any] = Field(default_factory=dict)
    ts: float = Field(default_factory=now_ts)


DashboardState.model_rebuild()
