"""Data contracts for DJ-Cue.

Every module boundary in the system is expressed here. The shapes mirror the
Supabase schema closely on purpose -- there is no separate domain model to
keep in sync with the database, because the database *is* the authority.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


def now_ts() -> float:
    return time.time()


# ---------------------------------------------------------------------------
# Events -- one per gig, so requests can be collected and analysed in
# isolation across different venues/nights.
# ---------------------------------------------------------------------------


class GenreBucket(BaseModel):
    """One column of a DJ's genre-quota chart -- e.g. 5 Punjabi slots. The
    `genres` list maps to this app's own genre keys (see genres.py); a
    request's genre must match one of them to belong in this bucket."""

    label: str
    genres: List[str]
    slots: int


class EventSettings(BaseModel):
    """Per-event configuration, entirely opt-in. Every field defaults to
    "off" -- an event that never sets any of this behaves exactly like the
    app always has. These are customizations a DJ turns on, never a second
    set of rules every event has to actively opt out of."""

    queue_cap: Optional[int] = None
    genre_buckets: List[GenreBucket] = Field(default_factory=list)
    # Shared budget across both a fresh request and an upvote on an
    # existing one -- None means unlimited (today's behavior).
    max_actions_per_session: Optional[int] = None
    # If a bucket's backlog runs dry, may another genre's backlog fill the
    # empty slot? Off by default -- a bucket runs short rather than a DJ's
    # deliberate genre split getting silently overridden.
    allow_cross_genre_backfill: bool = False
    chart_rank_order: List[str] = Field(default_factory=lambda: ["votes"])
    show_public_queue: bool = False
    first_time_prompt_enabled: bool = False
    instagram_handle: Optional[str] = None
    venue_name: Optional[str] = None
    start_time: Optional[str] = None
    confirmation_toast_copy: Optional[str] = None


class Event(BaseModel):
    id: str
    name: str
    slug: str
    status: str = "active"  # "active" | "ended"
    # The DJ's own availability signal, shown to guests before they spend
    # time searching: "open" (taking requests) or "closed" (not taking
    # requests -- enforced server-side, not just a display label).
    dj_status: str = "open"
    created_at: float = 0.0
    settings: EventSettings = Field(default_factory=EventSettings)


class EventCreate(BaseModel):
    name: str


class DJStatusUpdate(BaseModel):
    status: str  # "open" | "closed"


class PulseUpdate(BaseModel):
    """Optional, guest-set crowd-pulse signal -- purely informational, never
    gates anything. One vote per session per event; a repeat call overwrites
    the guest's own prior vote rather than accumulating."""

    session_id: str
    status: str  # "single" | "committed"


class FirstTimeAnswerCreate(BaseModel):
    """Guest's reply to the config-gated "Is this your first time?" modal.
    Only "yes"/"no" ever reach the backend -- the modal's third button,
    "Already Answered", is a pure client-side dismiss for a guest who
    remembers answering earlier, and never calls this at all."""

    event_id: str
    session_id: str
    answer: str  # "yes" | "no"


class FirstTimeAnswerAck(BaseModel):
    answer: Optional[str] = None
    # True when this session had already recorded an answer before this
    # call -- the original answer is returned either way, unchanged, so a
    # repeat call (the modal firing twice on a slow reconnect, say) is
    # always safe to make and never double-counts in analysis.
    already_answered: bool = False


class PulseAck(BaseModel):
    # None only when the event/session round trip itself failed -- the
    # guest's own vote never gets silently dropped otherwise.
    status: Optional[str] = None
    # Real changes only -- re-selecting the already-active status doesn't
    # count. Capped at 5 (enforced in the set_pulse_vote Postgres function).
    toggle_count: int = 0
    limited: bool = False
    message: Optional[str] = None


# ---------------------------------------------------------------------------
# Catalog -- the songs a guest can pick from once they've tapped a genre.
# ---------------------------------------------------------------------------


class Genre(BaseModel):
    key: str
    label: str
    region: str  # "north" | "south" | "other"


class Song(BaseModel):
    """A search result from the iTunes Search API -- ``id`` is an iTunes
    track id, not a row in our own database. There is no local catalog
    anymore; this is whatever Apple's music catalog returns in real time."""

    id: str
    title: str
    artist: str = ""
    genre: str = ""
    artwork_url: Optional[str] = None
    # Straight from the same iTunes/Deezer response already fetched for
    # the fields above -- no second call, no new integration.
    album: Optional[str] = None
    release_date: Optional[str] = None
    # Deezer's own catalog rank -- a relative popularity score, not a
    # literal stream count (Deezer's public API doesn't expose that).
    # Always null for an iTunes-sourced result.
    popularity: Optional[int] = None
    # A direct link to the track on its source catalog (Apple Music's own
    # trackViewUrl, or Deezer's link) -- lets the DJ open/preview the exact
    # recording in one tap to confirm it's the right one. Same provenance
    # as album/artwork: whichever source matched, verbatim, never built or
    # guessed from a title/artist string.
    catalog_url: Optional[str] = None
    # Track length in seconds, straight off the same search result -- a
    # DJ-relevant fact (mix planning) that's also a near-universal
    # identifying detail, unlike bpm which only Deezer's catalog measures.
    duration_seconds: Optional[int] = None


# ---------------------------------------------------------------------------
# Requests -- one row per distinct song per event. Duplicate submissions
# increment request_count on this row rather than creating a new one.
# ---------------------------------------------------------------------------


class SongRequest(BaseModel):
    id: str
    event_id: str
    song_id: Optional[str] = None
    song_title: str
    song_artist: str = ""
    genre: str = ""
    request_count: int = 1
    # "queued" | "played" | "dismissed". The DJ's Clear/Dismiss action is a
    # soft delete -- it flips this field, never removes the row -- so the
    # full lifecycle survives for post-event analysis.
    status: str = "queued"
    artwork_url: Optional[str] = None
    # Real, measured tempo from Deezer's own catalog metadata -- never AI
    # estimated, never client-supplied. Only present for songs picked from
    # a live Deezer search result; null otherwise (iTunes-sourced picks,
    # typed-anyway requests, and the static "popular right now" seed).
    bpm: Optional[int] = None
    # Same provenance rule as bpm: real catalog metadata, resolved once at
    # submit time, never AI-guessed. Null wherever the source lookup came
    # up empty.
    album: Optional[str] = None
    release_date: Optional[str] = None
    popularity: Optional[int] = None
    # Same provenance as Song.catalog_url/duration_seconds -- see there.
    catalog_url: Optional[str] = None
    duration_seconds: Optional[int] = None
    created_at: float = 0.0
    updated_at: float = 0.0


class RequestCreate(BaseModel):
    event_id: str
    session_id: str
    genre: str = ""
    song_title: str
    song_artist: str = ""
    song_id: Optional[str] = None
    artwork_url: Optional[str] = None
    # Same trust level as artwork_url -- display data straight from the
    # search result the guest tapped, not security-sensitive. release_date
    # is deliberately not accepted from the client; it's always resolved
    # server-side, same as bpm.
    album: Optional[str] = None
    popularity: Optional[int] = None
    catalog_url: Optional[str] = None
    duration_seconds: Optional[int] = None


class RequestAck(BaseModel):
    request_id: Optional[str]
    song_title: str
    request_count: int
    # True when this device already contributed to this exact song's count
    # (or is inside the submit cooldown) -- the tap still feels acknowledged,
    # it just didn't move the number.
    already_counted: bool = False
    # True when this session has spent its configured request/upvote budget
    # (events.settings.max_actions_per_session) -- always False for an event
    # that hasn't set one. Broken out like PulseAck.limited so the guest UI
    # can gate further taps instead of just reading the message string.
    action_limited: bool = False
    message: str


class StatusUpdate(BaseModel):
    status: str  # "played" | "dismissed"


class PinVerify(BaseModel):
    pin: str
    role: str  # "dj" | "present" -- which of the two operator PINs this is checked against


class FlushAck(BaseModel):
    """Confirms a `/flush` actually deleted something, and how much --
    the operator sees this as the toast, so a flush that silently matched
    zero rows (wrong event, already clean) reads differently from one that
    genuinely cleared a live queue."""

    event_id: str
    requests_removed: int = 0
    taps_removed: int = 0
    pulse_votes_removed: int = 0
    first_time_answers_removed: int = 0


# ---------------------------------------------------------------------------
# Health -- /api/health reports whether the database is actually reachable
# and taking writes, not just whether the process is up.
# ---------------------------------------------------------------------------


class DBHealth(BaseModel):
    ok: bool
    latency_ms: Optional[float] = None
    total_requests_all_time: Optional[int] = None
    last_insert_at: Optional[float] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


class GenreBucketView(BaseModel):
    """One rendered column of a DJ's genre-quota chart. `requests` is
    always exactly `slots` long -- a `None` entry is an explicitly empty
    slot (that genre's backlog ran dry), never just omitted, so the
    dashboard can show the gap instead of silently collapsing it."""

    label: str
    requests: List[Optional[SongRequest]]


class EventStats(BaseModel):
    total_requests: int = 0  # sum of request_count across queued rows
    unique_songs: int = 0  # queued rows
    unique_sessions: int = 0  # distinct devices that have tapped in
    # Aggregate of the optional guest-set crowd-pulse slider. Never
    # per-person -- only ever shown as a count/ratio.
    pulse_single: int = 0
    pulse_committed: int = 0
    pulse_total: int = 0


class DashboardState(BaseModel):
    event_id: str
    requests: List[SongRequest] = Field(default_factory=list)
    stats: EventStats = Field(default_factory=EventStats)
    # Only populated when the event has genre_buckets configured -- the flat
    # `requests` list above stays fully populated regardless, so a request
    # whose genre matches no configured bucket is never invisible on any
    # surface. None (not []) means "this event has no bucket chart" -- an
    # unconfigured event renders exactly like the app always has.
    buckets: Optional[List[GenreBucketView]] = None


class WSMessage(BaseModel):
    """Everything pushed over the dashboard socket."""

    type: str  # "state" | "new_request" | "status_change"
    payload: Dict[str, Any] = Field(default_factory=dict)
    ts: float = Field(default_factory=now_ts)


DashboardState.model_rebuild()
