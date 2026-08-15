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


class RequestAck(BaseModel):
    request_id: Optional[str]
    song_title: str
    request_count: int
    # True when this device already contributed to this exact song's count
    # (or is inside the submit cooldown) -- the tap still feels acknowledged,
    # it just didn't move the number.
    already_counted: bool = False
    message: str


class StatusUpdate(BaseModel):
    status: str  # "played" | "dismissed"


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


class WSMessage(BaseModel):
    """Everything pushed over the dashboard socket."""

    type: str  # "state" | "new_request" | "status_change"
    payload: Dict[str, Any] = Field(default_factory=dict)
    ts: float = Field(default_factory=now_ts)


DashboardState.model_rebuild()
