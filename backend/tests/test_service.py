"""Unit tests for CueService.build_dashboard's bucket/cap logic.

This is real business logic (ranking, backfill, blank slots, the flat-list
display cap) that route-level tests can't reach -- those replace the whole
service with FakeService. Here the persistence layer is stubbed instead, so
CueService's own code is what's actually under test.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.service import CueService  # noqa: E402
from app.contracts import Event, EventSettings, GenreBucket, EventStats, SongRequest  # noqa: E402


class FakeStore:
    def __init__(self, event, requests):
        self.event = event
        self.requests = requests

    def queued_requests(self, event_id):
        return self.requests

    def get_event(self, event_id):
        return self.event

    def stats(self, event_id, queued=None):
        return EventStats(total_requests=len(self.requests), unique_songs=len(self.requests))


def _service(event, requests) -> CueService:
    svc = object.__new__(CueService)
    svc.store = FakeStore(event, requests)
    return svc


def _req(id, genre, title, votes=1):
    return SongRequest(id=id, event_id="e1", song_title=title, genre=genre, request_count=votes)


def _event(settings=None):
    return Event(id="e1", name="Test", slug="test", settings=settings or EventSettings())


def test_no_settings_keeps_todays_flat_list_behaviour():
    requests = [_req("1", "punjabi", "A"), _req("2", "tamil", "B")]
    svc = _service(_event(), requests)
    state = svc.build_dashboard("e1")
    assert state.requests == requests
    assert state.buckets is None


def test_genre_buckets_produce_a_ranked_padded_chart():
    requests = [_req("1", "punjabi", "A", votes=1), _req("2", "punjabi", "B", votes=5)]
    settings = EventSettings(genre_buckets=[GenreBucket(label="Punjabi", genres=["punjabi"], slots=3)])
    svc = _service(_event(settings), requests)
    state = svc.build_dashboard("e1")
    assert state.buckets is not None
    assert len(state.buckets) == 1
    titles = [r.song_title if r else None for r in state.buckets[0].requests]
    # Highest votes first, exhausted slot renders as an explicit None.
    assert titles == ["B", "A", None]
    # The flat list stays fully populated regardless -- never hidden just
    # because a bucket chart exists.
    assert len(state.requests) == 2


def test_queue_cap_truncates_the_flat_list_when_no_buckets_configured():
    requests = [_req(str(i), "punjabi", f"Song {i}", votes=10 - i) for i in range(5)]
    settings = EventSettings(queue_cap=2)
    svc = _service(_event(settings), requests)
    state = svc.build_dashboard("e1")
    assert state.buckets is None
    assert [r.song_title for r in state.requests] == ["Song 0", "Song 1"]


def test_queue_cap_is_ignored_when_genre_buckets_are_also_configured():
    requests = [_req("1", "punjabi", "A")]
    settings = EventSettings(
        queue_cap=0,
        genre_buckets=[GenreBucket(label="Punjabi", genres=["punjabi"], slots=1)],
    )
    svc = _service(_event(settings), requests)
    state = svc.build_dashboard("e1")
    # queue_cap=0 would zero out the flat list if it applied here -- bucket
    # config takes priority, and the flat list stays a full safety net.
    assert len(state.requests) == 1
    assert state.buckets is not None
