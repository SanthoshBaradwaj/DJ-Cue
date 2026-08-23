"""Application service layer.

Thin on purpose: the interesting logic (aggregation, per-session dedupe,
atomic increment) lives in the ``submit_song_request`` Postgres function
behind ``Store.submit_request``. This layer's job is to fan out the result to
every connected DJ dashboard over the websocket.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import List, Optional, Tuple

from .. import catalog_search
from ..contracts import (
    DashboardState,
    DBHealth,
    Event,
    EventSettings,
    FirstTimeAnswerAck,
    FlushAck,
    GenreBucketView,
    PulseAck,
    RequestAck,
    Song,
    SongRequest,
    WSMessage,
)
from ..db import DEV_EVENT_SLUG, get_store
from ..events import bus

log = logging.getLogger("cue.service")


def _release_date_ordinal(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10]).toordinal()
    except (ValueError, TypeError):
        return None


def _bucket_sort_key(req: SongRequest, rank_order: List[str]) -> Tuple:
    """Build a tuple sort key implementing the configured rank hierarchy.

    Each field contributes ``(is_missing, -value)`` -- ascending sort on
    that pair puts present values before missing ones (missing always sorts
    last, regardless of direction) and higher values first among the
    present ones. Sorting on the combined tuple applies the fields in
    priority order, each one only breaking ties left by the ones before it.
    An unrecognised field name (a future DJ's typo, or a rank axis this
    build doesn't know yet) is skipped rather than raising, so a bad config
    value degrades to "rank by whatever's left" instead of crashing the
    dashboard.
    """
    parts: List[Tuple[int, float]] = []
    for field in rank_order:
        if field == "votes":
            parts.append((0, -req.request_count))
        elif field == "popularity":
            if req.popularity is None:
                parts.append((1, 0.0))
            else:
                parts.append((0, -req.popularity))
        elif field == "release_date":
            ordinal = _release_date_ordinal(req.release_date)
            if ordinal is None:
                parts.append((1, 0.0))
            else:
                parts.append((0, -ordinal))
    return tuple(parts)


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

    def record_first_time_answer(
        self, event_id: str, session_id: str, answer: str
    ) -> FirstTimeAnswerAck:
        return self.store.record_first_time_answer(event_id, session_id, answer)

    def resolve_event_id(self, event_id: Optional[str]) -> str:
        """An explicit id wins; otherwise fall back to the latest active
        event, creating a first one if none exists yet."""
        if event_id:
            return event_id
        event = self.store.latest_active_event()
        if event is None:
            event = self.store.create_event("DJPrashant-PDX")
        return event.id

    # A fixed slug (not a name lookup) so this is find-or-create rather than
    # create-on-every-call -- create_event() de-dupes slugs by appending
    # -2, -3, so calling it with the same name repeatedly would otherwise
    # spawn a fresh "dev" event on every request. One permanent event to
    # test against, safe to flush as often as needed, never the real one --
    # DEV_EVENT_SLUG lives in db.py because latest_active_event() also
    # needs it, to exclude this event from ordinary guest resolution.
    DEV_EVENT_NAME = "DJ-Cue Dev/Test"

    def get_or_create_dev_event(self) -> Event:
        event = self.store.get_event_by_slug(DEV_EVENT_SLUG)
        if event is not None:
            return event
        return self.store.create_event(self.DEV_EVENT_NAME)

    # -- catalog ----------------------------------------------------------

    def search_songs(self, query: str, genre: Optional[str], limit: int = 8) -> List[Song]:
        return catalog_search.search(query, genre, limit)

    # -- dashboard ----------------------------------------------------------

    def build_dashboard(self, event_id: str) -> DashboardState:
        requests = self.store.queued_requests(event_id)
        event = self.store.get_event(event_id)
        display_requests = requests
        buckets = None
        if event and event.settings.genre_buckets:
            buckets = self._build_buckets(requests, event.settings)
        elif event and event.settings.queue_cap:
            # No bucket chart configured, but a flat display cap is -- e.g. a
            # future DJ who wants "top N" without a genre split. requests is
            # already ranked (highest request_count first), so this is a
            # display truncation, not a re-sort. stats stays computed off the
            # full, uncapped list below -- the cap only trims what's shown.
            display_requests = requests[: event.settings.queue_cap]
        return DashboardState(
            event_id=event_id,
            requests=display_requests,
            stats=self.store.stats(event_id, queued=requests),
            buckets=buckets,
        )

    def _build_buckets(
        self, requests: List[SongRequest], event_settings: EventSettings
    ) -> List[GenreBucketView]:
        """Slot the flat request list into the DJ's configured genre chart.

        Every bucket only draws from requests no earlier bucket has already
        claimed, so a genre listed in two buckets (a future DJ's config,
        never DJ Prashant's) still can't seat the same song twice. Backfill
        is a second pass, strictly after every bucket has had first pick of
        its own genres, so a deliberate genre split never gets crowded out
        by a louder bucket's overflow -- it only reaches into a slot no
        genre-matched song could fill.
        """
        rank_order = event_settings.chart_rank_order or ["votes"]

        def sort_key(req: SongRequest) -> Tuple:
            return _bucket_sort_key(req, rank_order)

        used_ids = set()
        picks: List[List[SongRequest]] = []
        for bucket in event_settings.genre_buckets:
            matched = sorted(
                (r for r in requests if r.genre in bucket.genres and r.id not in used_ids),
                key=sort_key,
            )
            chosen = matched[: bucket.slots]
            used_ids.update(r.id for r in chosen)
            picks.append(chosen)

        if event_settings.allow_cross_genre_backfill:
            leftover = sorted((r for r in requests if r.id not in used_ids), key=sort_key)
            for bucket, chosen in zip(event_settings.genre_buckets, picks):
                need = bucket.slots - len(chosen)
                if need <= 0:
                    continue
                fill, leftover = leftover[:need], leftover[need:]
                chosen.extend(fill)
                used_ids.update(r.id for r in fill)

        return [
            GenreBucketView(
                label=bucket.label,
                requests=chosen + [None] * (bucket.slots - len(chosen)),
            )
            for bucket, chosen in zip(event_settings.genre_buckets, picks)
        ]

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
        album: Optional[str] = None,
        popularity: Optional[int] = None,
        catalog_url: Optional[str] = None,
        duration_seconds: Optional[int] = None,
    ) -> RequestAck:
        # Real BPM, resolved once here rather than at search time. A direct
        # Deezer id gives an exact track; anything else (an iTunes match --
        # the common case, since iTunes usually wins the search merge -- or
        # a typed "request it anyway") falls back to a strict title+artist
        # Deezer lookup so bpm still gets a real shot at resolving instead
        # of being permanently unreachable for the majority of requests.
        #
        # release_date follows the exact same two-path resolution as bpm --
        # always from Deezer, never client-supplied, so both fields share
        # one predictable story instead of iTunes and Deezer dates mixing
        # formats. popularity, by contrast, already travelled with the
        # search result the guest tapped (same trust level as artwork_url)
        # -- only backfilled here when that came back empty, e.g. an
        # iTunes-won pick that never carried a Deezer rank at all.
        if song_id and song_id.startswith("deezer:"):
            deezer_id = song_id.split(":", 1)[1]
            bpm = catalog_search.deezer_track_bpm(deezer_id)
            detail = catalog_search.deezer_track_metadata(deezer_id)
        else:
            bpm = catalog_search.deezer_bpm_by_title_artist(song_title, song_artist)
            detail = catalog_search.deezer_metadata_by_title_artist(song_title, song_artist)
        release_date = detail.get("release_date")
        if popularity is None:
            popularity = detail.get("popularity")
        # catalog_url/duration_seconds: same backfill-only-if-empty rule as
        # popularity -- the search result the guest tapped already carries
        # its own source's values (Apple Music's for an iTunes pick,
        # Deezer's for a Deezer pick); this Deezer lookup only fills the
        # gap for a typed-anyway request or a pick whose source happened
        # not to carry one.
        if not catalog_url:
            catalog_url = detail.get("catalog_url")
        if not duration_seconds:
            duration_seconds = detail.get("duration_seconds")

        ack = self.store.submit_request(
            event_id=event_id,
            session_id=session_id,
            song_title=song_title,
            song_artist=song_artist,
            genre=genre,
            song_id=song_id,
            artwork_url=artwork_url,
            bpm=bpm,
            album=album,
            release_date=release_date,
            popularity=popularity,
            catalog_url=catalog_url,
            duration_seconds=duration_seconds,
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

    def refresh_request_metadata(self, event_id: str, request_id: str) -> Optional[SongRequest]:
        """Re-attempt catalog resolution for whichever of bpm / release_date /
        catalog_url / duration_seconds a request is still missing, called
        when a DJ opens its detail card rather than only once at submit time.

        Submit-time resolution is fail-soft (a slow/flaky Deezer call must
        never block a guest's request), and a row can also simply predate
        whichever deploy first started capturing a given field -- either way
        the gap is otherwise permanent, since nothing ever revisits it. This
        gives every request a second chance, but only when a DJ actually
        looks: it's a no-op (no external calls at all) once every field is
        already filled, so reopening an already-resolved song costs nothing.
        """
        current = self.store.get_request(event_id, request_id)
        if current is None:
            return None
        if (
            current.bpm is not None
            and current.release_date is not None
            and current.catalog_url is not None
            and current.duration_seconds is not None
        ):
            return current

        # Same two-path resolution as submit_request: a direct Deezer id
        # gives an exact track, anything else falls back to a strict
        # title+artist Deezer lookup.
        if current.song_id and current.song_id.startswith("deezer:"):
            deezer_id = current.song_id.split(":", 1)[1]
            bpm = catalog_search.deezer_track_bpm(deezer_id)
            detail = catalog_search.deezer_track_metadata(deezer_id)
        else:
            bpm = catalog_search.deezer_bpm_by_title_artist(current.song_title, current.song_artist)
            detail = catalog_search.deezer_metadata_by_title_artist(
                current.song_title, current.song_artist
            )

        updated = self.store.refresh_request_metadata(
            event_id=event_id,
            request_id=request_id,
            bpm=bpm,
            release_date=detail.get("release_date"),
            popularity=detail.get("popularity"),
            catalog_url=detail.get("catalog_url"),
            duration_seconds=detail.get("duration_seconds"),
        )
        if updated is not None:
            self.broadcast_state(event_id)
        return updated

    def flush_event(self, event_id: str) -> FlushAck:
        """Hard-deletes every queued/played/dismissed request, session tap,
        pulse vote, and first-time-answer for one event -- a true "start
        from zero" for a single gig, not the soft dismiss the rest of this
        app uses (that stays reachable for post-event analysis; this is the
        one path that doesn't). The event row itself and its settings are
        untouched, so nobody has to rescan a QR code after this runs."""
        ack = self.store.flush_event_data(event_id)
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
