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
from typing import Dict, List, Optional

from supabase import Client, create_client

from .config import settings
from .contracts import Event, EventStats, RequestAck, SongRequest

log = logging.getLogger("cue.db")

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    base = _SLUG_RE.sub("-", name.strip().lower()).strip("-")
    return base or "event"


def _row_to_event(row: Dict) -> Event:
    return Event(
        id=row["id"],
        name=row["name"],
        slug=row["slug"],
        status=row.get("status", "active"),
        created_at=_epoch(row.get("created_at")),
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
        existing = self.client.table("events").select("slug").execute()
        taken = {row["slug"] for row in existing.data or []}
        candidate = slug
        suffix = 2
        while candidate in taken:
            candidate = f"{slug}-{suffix}"
            suffix += 1
        res = (
            self.client.table("events")
            .insert({"name": name, "slug": candidate, "status": "active"})
            .execute()
        )
        return _row_to_event(res.data[0])

    def list_events(self) -> List[Event]:
        res = self.client.table("events").select("*").order("created_at", desc=True).execute()
        return [_row_to_event(r) for r in res.data or []]

    def get_event(self, event_id: str) -> Optional[Event]:
        res = self.client.table("events").select("*").eq("id", event_id).limit(1).execute()
        rows = res.data or []
        return _row_to_event(rows[0]) if rows else None

    def latest_active_event(self) -> Optional[Event]:
        res = (
            self.client.table("events")
            .select("*")
            .eq("status", "active")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        return _row_to_event(rows[0]) if rows else None

    def set_event_status(self, event_id: str, status: str) -> Optional[Event]:
        res = self.client.table("events").update({"status": status}).eq("id", event_id).execute()
        rows = res.data or []
        return _row_to_event(rows[0]) if rows else None

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
    ) -> RequestAck:
        res = self.client.rpc(
            "submit_song_request",
            {
                "p_event_id": event_id,
                "p_session_id": session_id,
                "p_song_id": song_id,
                "p_song_title": song_title,
                "p_song_artist": song_artist,
                "p_genre": genre,
                "p_cooldown_seconds": settings.submit_cooldown_s,
            },
        ).execute()
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
        if row.get("cooled_down"):
            return RequestAck(
                request_id=None,
                song_title=song_title,
                request_count=0,
                already_counted=True,
                message="Give it a second -- your last request is still landing.",
            )
        already = bool(row.get("already_counted"))
        count = row.get("out_request_count", 1)
        message = (
            "You've already got this one queued."
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

    def queued_requests(self, event_id: str) -> List[SongRequest]:
        res = (
            self.client.table("requests")
            .select("*")
            .eq("event_id", event_id)
            .eq("status", "queued")
            .order("request_count", desc=True)
            .order("created_at")
            .execute()
        )
        return [_row_to_request(r) for r in res.data or []]

    def set_request_status(
        self, event_id: str, request_id: str, status: str
    ) -> Optional[SongRequest]:
        # RLS grants no direct UPDATE on requests -- this goes through a
        # SECURITY DEFINER function so a status change is always a validated
        # transition, not a raw write anyone holding the anon key could fire
        # at any row with any string.
        res = self.client.rpc(
            "set_request_status",
            {"p_event_id": event_id, "p_request_id": request_id, "p_status": status},
        ).execute()
        rows = res.data or []
        if not rows or rows[0] is None or rows[0].get("id") is None:
            return None
        return _row_to_request(rows[0])

    def stats(self, event_id: str) -> EventStats:
        queued = self.queued_requests(event_id)
        taps = (
            self.client.table("request_taps")
            .select("session_id")
            .eq("event_id", event_id)
            .execute()
        )
        unique_sessions = len({r["session_id"] for r in (taps.data or [])})
        return EventStats(
            total_requests=sum(r.request_count for r in queued),
            unique_songs=len(queued),
            unique_sessions=unique_sessions,
        )


_store: Optional[Store] = None


def get_store() -> Store:
    global _store
    if _store is None:
        _store = Store()
    return _store
