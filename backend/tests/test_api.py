"""Route-level tests against a fake service -- no network, no real Supabase.

The interesting business logic (atomic increment, per-session dedupe) lives
in the ``submit_song_request`` Postgres function and is exercised against the
real database manually; these tests cover the HTTP surface and the
soft-delete contract that the API promises callers.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app import main  # noqa: E402
from app.contracts import (  # noqa: E402
    DashboardState,
    Event,
    EventStats,
    RequestAck,
    Song,
    SongRequest,
)
from app.db import slugify  # noqa: E402
from app.genres import GENRES  # noqa: E402


class FakeService:
    """In-memory stand-in for CueService, same method surface."""

    def __init__(self):
        self.events = []
        self.requests = {}
        self._next = 1

    def _id(self, prefix):
        self._next += 1
        return "%s_%d" % (prefix, self._next)

    def create_event(self, name):
        event = Event(id=self._id("evt"), name=name, slug=slugify(name), status="active")
        self.events.append(event)
        return event

    def list_events(self):
        return list(self.events)

    def resolve_event_id(self, event_id):
        if event_id:
            return event_id
        if not self.events:
            return self.create_event("Untitled event").id
        return self.events[-1].id

    def search_songs(self, query, genre, limit=8):
        return [Song(id="song_1", title="Lover", artist="Diljit Dosanjh", genre="punjabi")]

    def submit_request(self, event_id, session_id, song_title, song_artist, genre, song_id):
        key = (event_id, song_title.strip().lower(), (song_artist or "").strip().lower())
        existing = self.requests.get(key)
        if existing is None or existing.status != "queued":
            req = SongRequest(
                id=self._id("req"),
                event_id=event_id,
                song_title=song_title,
                song_artist=song_artist or "",
                genre=genre,
                request_count=1,
                status="queued",
            )
            self.requests[key] = req
            return RequestAck(
                request_id=req.id, song_title=song_title, request_count=1, message="Added."
            )
        existing.request_count += 1
        return RequestAck(
            request_id=existing.id,
            song_title=song_title,
            request_count=existing.request_count,
            message="Boosted.",
        )

    def build_dashboard(self, event_id):
        rows = [
            r
            for (eid, *_), r in self.requests.items()
            if eid == event_id and r.status == "queued"
        ]
        rows.sort(key=lambda r: -r.request_count)
        return DashboardState(
            event_id=event_id,
            requests=rows,
            stats=EventStats(
                total_requests=sum(r.request_count for r in rows),
                unique_songs=len(rows),
                unique_sessions=0,
            ),
        )

    def set_request_status(self, event_id, request_id, status):
        for r in self.requests.values():
            if r.id == request_id and r.event_id == event_id:
                r.status = status
                return r
        return None


def _client(monkeypatch):
    fake = FakeService()
    monkeypatch.setattr(main, "get_service", lambda: fake)
    return TestClient(main.app), fake


def test_slugify_is_stable_and_never_empty():
    assert slugify("Bellevue Aug 21") == "bellevue-aug-21"
    assert slugify("   ") == "event"


def test_genres_cover_the_required_examples():
    keys = {g.key for g in GENRES}
    assert {"punjabi", "haryanvi", "tamil", "telugu"} <= keys


def test_create_and_list_events(monkeypatch):
    client, _fake = _client(monkeypatch)
    created = client.post("/api/events", json={"name": "Bellevue Aug 21"}).json()
    assert created["slug"] == "bellevue-aug-21"
    listed = client.get("/api/events").json()["events"]
    assert len(listed) == 1


def test_duplicate_requests_increment_count_not_row_count(monkeypatch):
    client, _fake = _client(monkeypatch)
    event = client.post("/api/events", json={"name": "Test Night"}).json()

    body = {
        "event_id": event["id"],
        "session_id": "sess_a",
        "genre": "punjabi",
        "song_title": "Lover",
    }
    first = client.post("/api/requests", json=body).json()
    assert first["request_count"] == 1

    second = client.post("/api/requests", json=dict(body, session_id="sess_b")).json()
    assert second["request_count"] == 2

    dash = client.get("/api/dashboard", params={"event_id": event["id"]}).json()
    assert len(dash["requests"]) == 1
    assert dash["requests"][0]["request_count"] == 2


def test_dashboard_orders_by_request_count_descending(monkeypatch):
    client, _fake = _client(monkeypatch)
    event = client.post("/api/events", json={"name": "Order Test"}).json()

    def req(session, title):
        return client.post(
            "/api/requests",
            json={
                "event_id": event["id"],
                "session_id": session,
                "genre": "tamil",
                "song_title": title,
            },
        ).json()

    req("s1", "Arabic Kuthu")
    req("s1", "Rowdy Baby")
    req("s2", "Rowdy Baby")
    req("s3", "Rowdy Baby")

    dash = client.get("/api/dashboard", params={"event_id": event["id"]}).json()
    titles = [r["song_title"] for r in dash["requests"]]
    assert titles[0] == "Rowdy Baby"
    assert dash["requests"][0]["request_count"] == 3


def test_dismiss_is_a_soft_delete_not_a_row_removal(monkeypatch):
    client, fake = _client(monkeypatch)
    event = client.post("/api/events", json={"name": "Test Night 2"}).json()
    body = {
        "event_id": event["id"],
        "session_id": "sess_a",
        "genre": "tamil",
        "song_title": "Rowdy Baby",
    }
    req = client.post("/api/requests", json=body).json()

    res = client.post(
        "/api/requests/%s/status" % req["request_id"],
        params={"event_id": event["id"]},
        json={"status": "dismissed"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "dismissed"

    dash = client.get("/api/dashboard", params={"event_id": event["id"]}).json()
    assert dash["requests"] == []

    key = (event["id"], "rowdy baby", "")
    assert fake.requests[key].status == "dismissed"  # retained, not deleted


def test_empty_song_title_rejected(monkeypatch):
    client, _fake = _client(monkeypatch)
    event = client.post("/api/events", json={"name": "Validation"}).json()
    res = client.post(
        "/api/requests",
        json={"event_id": event["id"], "session_id": "s1", "genre": "punjabi", "song_title": "  "},
    )
    assert res.status_code == 422
