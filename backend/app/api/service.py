"""Application service layer.

Thin on purpose: the interesting logic (aggregation, per-session dedupe,
atomic increment) lives in the ``submit_song_request`` Postgres function
behind ``Store.submit_request``. This layer's job is to fan out the result to
every connected DJ dashboard over the websocket.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from .. import catalog_search
from ..contracts import (
    DashboardState,
    DBHealth,
    Event,
    PulseAck,
    RequestAck,
    Song,
    SongRequest,
    WSMessage,
)
from ..db import get_store
from ..events import bus

log = logging.getLogger("cue.service")


class CueService:
    def __init__(self) -> None:
        self.store = get_store()

    # -- events ---------------------------------------------------------

    def create_event(self, name: str) -> Event:
        return self.store.create_event(name)

    def list_events(self) -> List[Event]:
        return self.store.list_events()

    def get_event(self, event_id: str) -> Optional[Event]:
        return self.store.get_event(event_id)

    def set_dj_status(self, event_id: str, status: str) -> Optional[Event]:
        updated = self.store.set_dj_status(event_id, status)
        if updated is not None:
            self.broadcast_state(event_id)
        return updated

    def db_health(self) -> DBHealth:
        return self.store.health()

    def set_pulse(self, event_id: str, session_id: str, status: str) -> PulseAck:
        ack = self.store.set_pulse(event_id, session_id, status)
        if ack.status is not None and not ack.limited:
            self.broadcast_state(event_id)
        return ack

    def resolve_event_id(self, event_id: Optional[str]) -> str:
        """An explicit id wins; otherwise fall back to the latest active
        event, creating a first one if none exists yet."""
        if event_id:
            return event_id
        event = self.store.latest_active_event()
        if event is None:
            event = self.store.create_event("DJPrashant-PDX")
        return event.id

    # -- catalog ----------------------------------------------------------

    def search_songs(self, query: str, genre: Optional[str], limit: int = 8) -> List[Song]:
        return catalog_search.search(query, genre, limit)

    # -- dashboard ----------------------------------------------------------

    def build_dashboard(self, event_id: str) -> DashboardState:
        requests = self.store.queued_requests(event_id)
        return DashboardState(
            event_id=event_id,
            requests=requests,
            stats=self.store.stats(event_id, queued=requests),
        )

    # -- writes -------------------------------------------------------------

    def submit_request(
        self,
        event_id: str,
        session_id: str,
        song_title: str,
        song_artist: str,
        genre: str,
        song_id: Optional[str],
        artwork_url: Optional[str] = None,
    ) -> RequestAck:
        # Real BPM, resolved once here rather than at search time. A direct
        # Deezer id gives an exact track; anything else (an iTunes match --
        # the common case, since iTunes usually wins the search merge -- or
        # a typed "request it anyway") falls back to a strict title+artist
        # Deezer lookup so bpm still gets a real shot at resolving instead
        # of being permanently unreachable for the majority of requests.
        bpm = None
        if song_id and song_id.startswith("deezer:"):
            bpm = catalog_search.deezer_track_bpm(song_id.split(":", 1)[1])
        else:
            bpm = catalog_search.deezer_bpm_by_title_artist(song_title, song_artist)
        ack = self.store.submit_request(
            event_id=event_id,
            session_id=session_id,
            song_title=song_title,
            song_artist=song_artist,
            genre=genre,
            song_id=song_id,
            artwork_url=artwork_url,
            bpm=bpm,
        )
        if ack.request_id:
            bus.publish(
                event_id,
                WSMessage(
                    type="new_request",
                    payload={
                        "song_title": ack.song_title,
                        "request_count": ack.request_count,
                        "already_counted": ack.already_counted,
                    },
                ),
            )
            self.broadcast_state(event_id)
        return ack

    def set_request_status(
        self, event_id: str, request_id: str, status: str
    ) -> Optional[SongRequest]:
        updated = self.store.set_request_status(event_id, request_id, status)
        if updated is not None:
            bus.publish(
                event_id,
                WSMessage(
                    type="status_change",
                    payload={"request_id": request_id, "status": status},
                ),
            )
            self.broadcast_state(event_id)
        return updated

    # -- transport ----------------------------------------------------------

    def broadcast_state(self, event_id: str) -> None:
        try:
            state = self.build_dashboard(event_id)
        except Exception:  # pragma: no cover - defensive
            log.exception("failed to build dashboard state")
            return
        bus.publish(
            event_id, WSMessage(type="state", payload=state.model_dump(mode="json"))
        )


_service: Optional[CueService] = None


def get_service() -> CueService:
    global _service
    if _service is None:
        _service = CueService()
    return _service
