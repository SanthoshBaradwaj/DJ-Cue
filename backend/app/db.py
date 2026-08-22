"""Persistence layer: Supabase Postgres via the official client.

DJ-Cue has no in-memory fallback -- request data must survive the DJ's
laptop restarting mid-set, which is the reason this moved off SQLite. If
SUPABASE_URL / SUPABASE_ANON_KEY are missing the server refuses to boot
rather than silently losing every request to a process that dies at 1am.

The heavy lifting for a submission -- find-or-create the row, cap one
contribution per session, increment atomically -- lives in a single Postgres
function (``submit_song_request``, see the migration) so two phones tapping
the same song at the same instant can't race each other across multiple
network round trips.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Callable, Dict, List, Optional

import httpx
from supabase import Client, create_client

from .config import settings
from .contracts import (
    DBHealth,
    Event,
    EventStats,
    FirstTimeAnswerAck,
    PulseAck,
    RequestAck,
    SongRequest,
)

log = logging.getLogger("cue.db")

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    base = _SLUG_RE.sub("-", name.strip().lower()).strip("-")
    return base or "event"


def _exec(build: Callable[[], object]):
    """Run a Supabase query, retrying once on a transient connection drop.

    A warm serverless invocation can hand back a pooled HTTP/2 connection
    that Supabase's edge silently closed between invocations -- the first
    request on it fails with an httpx "Server disconnected" error even
    though nothing about the query itself is wrong (confirmed in production
    logs: the same query succeeds on retry). `build` constructs a fresh
    query object each call so there's no question of reusing state from the
    failed attempt. This deliberately does not catch
    postgrest.exceptions.APIError -- a real SQL/API error would just fail
    the same way again, and swallowing it here would hide real bugs.
    """
    try:
        return build().execute()
    except httpx.TransportError as exc:
        log.info("transient Supabase connection error, retrying once: %s", exc)
        return build().execute()


def _row_to_event(row: Dict) -> Event:
    return Event(
        id=row["id"],
        name=row["name"],
        slug=row["slug"],
        status=row.get("status", "active"),
        dj_status=row.get("dj_status") or "open",
        created_at=_epoch(row.get("created_at")),
        settings=row.get("settings") or {},
    )


def _row_to_request(row: Dict) -> SongRequest:
    return SongRequest(
        id=row["id"],
        event_id=row["event_id"],
        song_id=row.get("song_id"),
        song_title=row["song_title"],
        song_artist=row.get("song_artist") or "",
        genre=row.get("genre") or "",
        request_count=row.get("request_count", 1),
        status=row.get("status", "queued"),
        artwork_url=row.get("artwork_url"),
        bpm=row.get("bpm"),
        album=row.get("album_name"),
        release_date=row.get("release_date"),
        popularity=row.get("popularity"),
        catalog_url=row.get("catalog_url"),
        duration_seconds=row.get("duration_seconds"),
        created_at=_epoch(row.get("created_at")),
        updated_at=_epoch(row.get("updated_at")),
    )


def _epoch(value: object) -> float:
    """Supabase returns ISO timestamps; the rest of the app works in epoch
    seconds so it can sort/compare without parsing dates everywhere."""
    if not value:
        return 0.0
    try:
        import datetime

        return datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


class Store:
    def __init__(self) -> None:
        if not settings.has_supabase:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_ANON_KEY must be set -- DJ-Cue has no "
                "in-memory fallback. Copy .env.example to .env and fill them in, "
                "then restart."
            )
        self.client: Client = create_client(settings.supabase_url, settings.supabase_key)

    # -- events ---------------------------------------------------------

    def create_event(self, name: str) -> Event:
        name = (name or "").strip() or "Untitled event"
        slug = slugify(name)
        existing = _exec(lambda: self.client.table("events").select("slug"))
        taken = {row["slug"] for row in existing.data or []}
        candidate = slug
        suffix = 2
        while candidate in taken:
            candidate = f"{slug}-{suffix}"
            suffix += 1
        res = _exec(
            lambda: self.client.table("events").insert(
                {"name": name, "slug": candidate, "status": "active"}
            )
        )
        return _row_to_event(res.data[0])

    def list_events(self) -> List[Event]:
        res = _exec(
            lambda: self.client.table("events").select("*").order("created_at", desc=True)
        )
        return [_row_to_event(r) for r in res.data or []]

    def get_event(self, event_id: str) -> Optional[Event]:
        res = _exec(
            lambda: self.client.table("events").select("*").eq("id", event_id).limit(1)
        )
        rows = res.data or []
        return _row_to_event(rows[0]) if rows else None

    def latest_active_event(self) -> Optional[Event]:
        res = _exec(
            lambda: self.client.table("events")
            .select("*")
            .eq("status", "active")
            .order("created_at", desc=True)
            .limit(1)
        )
        rows = res.data or []
        return _row_to_event(rows[0]) if rows else None

    def set_event_status(self, event_id: str, status: str) -> Optional[Event]:
        res = _exec(
            lambda: self.client.table("events").update({"status": status}).eq("id", event_id)
        )
        rows = res.data or []
        return _row_to_event(rows[0]) if rows else None

    def set_dj_status(self, event_id: str, dj_status: str) -> Optional[Event]:
        # Same reasoning as set_request_status: RLS grants no direct UPDATE
        # on events.dj_status, so this goes through a validated function.
        res = _exec(
            lambda: self.client.rpc(
                "set_dj_status", {"p_event_id": event_id, "p_status": dj_status}
            )
        )
        rows = res.data or []
        if not rows or rows[0] is None or rows[0].get("id") is None:
            return None
        return self.get_event(event_id)

    # -- requests ---------------------------------------------------------
    # Song search lives in app/catalog_search.py -- there is no local
    # catalog to query.

    def submit_request(
        self,
        event_id: str,
        session_id: str,
        song_title: str,
        song_artist: str = "",
        genre: str = "",
        song_id: Optional[str] = None,
        artwork_url: Optional[str] = None,
        bpm: Optional[int] = None,
        album: Optional[str] = None,
        release_date: Optional[str] = None,
        popularity: Optional[int] = None,
        catalog_url: Optional[str] = None,
        duration_seconds: Optional[int] = None,
    ) -> RequestAck:
        res = _exec(
            lambda: self.client.rpc(
                "submit_song_request",
                {
                    "p_event_id": event_id,
                    "p_session_id": session_id,
                    "p_song_id": song_id,
                    "p_song_title": song_title,
                    "p_song_artist": song_artist,
                    "p_genre": genre,
                    "p_cooldown_seconds": settings.submit_cooldown_s,
                    "p_artwork_url": artwork_url,
                    "p_bpm": bpm,
                    "p_album": album,
                    "p_release_date": release_date,
                    "p_popularity": popularity,
                    "p_catalog_url": catalog_url,
                    "p_duration_seconds": duration_seconds,
                },
            )
        )
        rows = res.data or []
        if not rows:
            return RequestAck(
                request_id=None,
                song_title=song_title,
                request_count=0,
                already_counted=True,
                message="Couldn't reach the queue -- try again.",
            )
        row = rows[0]
        if row.get("dj_closed"):
            return RequestAck(
                request_id=None,
                song_title=song_title,
                request_count=0,
                already_counted=False,
                message="The DJ isn't taking requests right now -- hang tight!",
            )
        if row.get("cooled_down"):
            return RequestAck(
                request_id=None,
                song_title=song_title,
                request_count=0,
                already_counted=True,
                message="Give it a second -- your last request is still landing.",
            )
        if row.get("action_limited"):
            return RequestAck(
                request_id=None,
                song_title=song_title,
                request_count=0,
                already_counted=False,
                action_limited=True,
                message="You've used up your requests for tonight -- thanks for playing along!",
            )
        already = bool(row.get("already_counted"))
        count = row.get("out_request_count", 1)
        message = (
            "Already added — you're on the list, waiting on the DJ."
            if already
            else ("Added to the queue." if count <= 1 else f"Boosted! {count} people want this.")
        )
        return RequestAck(
            request_id=row.get("out_request_id"),
            song_title=row.get("out_song_title") or song_title,
            request_count=count,
            already_counted=already,
            message=message,
        )

    def get_request(self, event_id: str, request_id: str) -> Optional[SongRequest]:
        res = _exec(
            lambda: self.client.table("requests")
            .select("*")
            .eq("event_id", event_id)
            .eq("id", request_id)
            .limit(1)
        )
        rows = res.data or []
        return _row_to_request(rows[0]) if rows else None

    def refresh_request_metadata(
        self,
        event_id: str,
        request_id: str,
        bpm: Optional[int] = None,
        album: Optional[str] = None,
        release_date: Optional[str] = None,
        popularity: Optional[int] = None,
        catalog_url: Optional[str] = None,
        duration_seconds: Optional[int] = None,
    ) -> Optional[SongRequest]:
        # Same COALESCE-only-fills-gaps contract as the submit-time backfill
        # -- this can never clobber a field the row already has, it only
        # ever fills one that's still null.
        res = _exec(
            lambda: self.client.rpc(
                "refresh_request_metadata",
                {
                    "p_event_id": event_id,
                    "p_request_id": request_id,
                    "p_bpm": bpm,
                    "p_album": album,
                    "p_release_date": release_date,
                    "p_popularity": popularity,
                    "p_catalog_url": catalog_url,
                    "p_duration_seconds": duration_seconds,
                },
            )
        )
        rows = res.data or []
        return _row_to_request(rows[0]) if rows else None

    def queued_requests(self, event_id: str) -> List[SongRequest]:
        res = _exec(
            lambda: self.client.table("requests")
            .select("*")
            .eq("event_id", event_id)
            .eq("status", "queued")
            .order("request_count", desc=True)
            .order("created_at")
        )
        return [_row_to_request(r) for r in res.data or []]

    def set_request_status(
        self, event_id: str, request_id: str, status: str
    ) -> Optional[SongRequest]:
        # RLS grants no direct UPDATE on requests -- this goes through a
        # SECURITY DEFINER function so a status change is always a validated
        # transition, not a raw write anyone holding the anon key could fire
        # at any row with any string.
        res = _exec(
            lambda: self.client.rpc(
                "set_request_status",
                {"p_event_id": event_id, "p_request_id": request_id, "p_status": status},
            )
        )
        rows = res.data or []
        if not rows or rows[0] is None or rows[0].get("id") is None:
            return None
        return _row_to_request(rows[0])

    def health(self) -> DBHealth:
        """A real round trip to Postgres, not just process liveness -- and
        proof inserts are actually landing, not just that reads work."""
        started = time.perf_counter()
        try:
            res = _exec(
                lambda: self.client.table("requests")
                .select("created_at", count="exact")
                .order("created_at", desc=True)
                .limit(1)
            )
            latency_ms = (time.perf_counter() - started) * 1000
            rows = res.data or []
            last_insert = _epoch(rows[0]["created_at"]) if rows else None
            return DBHealth(
                ok=True,
                latency_ms=round(latency_ms, 1),
                total_requests_all_time=res.count,
                last_insert_at=last_insert,
            )
        except Exception as exc:  # pragma: no cover - defensive
            log.warning("db health check failed: %s", exc)
            return DBHealth(ok=False, error=str(exc))

    def set_pulse(self, event_id: str, session_id: str, status: str) -> PulseAck:
        # RLS grants no direct write on pulse_votes -- same pattern as every
        # other mutation, routed through a validated SECURITY DEFINER upsert.
        # The 5-toggle cap is enforced inside that function, not here, so it
        # can't be bypassed by calling PostgREST directly.
        res = _exec(
            lambda: self.client.rpc(
                "set_pulse_vote",
                {"p_event_id": event_id, "p_session_id": session_id, "p_status": status},
            )
        )
        rows = res.data or []
        if not rows:
            return PulseAck(message="Couldn't reach the DJ just then.")
        row = rows[0]
        limited = bool(row.get("out_limited"))
        return PulseAck(
            status=row.get("out_status"),
            toggle_count=row.get("out_toggle_count") or 0,
            limited=limited,
            message=(
                "That's five changes -- we hear you, tough crowd. Locking it in for tonight!"
                if limited
                else None
            ),
        )

    def record_first_time_answer(
        self, event_id: str, session_id: str, answer: str
    ) -> FirstTimeAnswerAck:
        # RLS grants no direct write on first_time_answers -- same pattern
        # as every other mutation, routed through a validated SECURITY
        # DEFINER function that also enforces the yes/no answer domain.
        res = _exec(
            lambda: self.client.rpc(
                "record_first_time_answer",
                {"p_event_id": event_id, "p_session_id": session_id, "p_answer": answer},
            )
        )
        rows = res.data or []
        if not rows:
            return FirstTimeAnswerAck()
        row = rows[0]
        return FirstTimeAnswerAck(
            answer=row.get("out_answer"),
            already_answered=bool(row.get("out_already_answered")),
        )

    def stats(self, event_id: str, queued: Optional[List[SongRequest]] = None) -> EventStats:
        # Accepts an already-fetched queued list so a caller that needs both
        # (build_dashboard does) doesn't pay for the same query twice --
        # queued_requests() is a real network round trip, not a cache read.
        if queued is None:
            queued = self.queued_requests(event_id)
        taps = _exec(
            lambda: self.client.table("request_taps").select("session_id").eq("event_id", event_id)
        )
        unique_sessions = len({r["session_id"] for r in (taps.data or [])})
        pulses = _exec(
            lambda: self.client.table("pulse_votes").select("status").eq("event_id", event_id)
        )
        pulse_rows = pulses.data or []
        pulse_single = sum(1 for r in pulse_rows if r.get("status") == "single")
        pulse_committed = sum(1 for r in pulse_rows if r.get("status") == "committed")
        return EventStats(
            total_requests=sum(r.request_count for r in queued),
            unique_songs=len(queued),
            unique_sessions=unique_sessions,
            pulse_single=pulse_single,
            pulse_committed=pulse_committed,
            pulse_total=pulse_single + pulse_committed,
        )


_store: Optional[Store] = None


def get_store() -> Store:
    global _store
    if _store is None:
        _store = Store()
    return _store
