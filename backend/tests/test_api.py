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
    FirstTimeAnswerAck,
    PulseAck,
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
        self.pulse_votes = {}
        self.first_time_answers = {}
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
            return self.create_event("DJPrashant-PDX").id
        return self.events[-1].id

    def get_event(self, event_id):
        return next((e for e in self.events if e.id == event_id), None)

    def set_pulse(self, event_id, session_id, status):
        if not any(e.id == event_id for e in self.events):
            return PulseAck(message="event not found")
        key = (event_id, session_id)
        prev_status, count = self.pulse_votes.get(key, (None, 0))
        if prev_status == status:
            return PulseAck(status=status, toggle_count=count, limited=False)
        if count >= 5:
            return PulseAck(status=prev_status, toggle_count=count, limited=True, message="slow down")
        count += 1
        self.pulse_votes[key] = (status, count)
        return PulseAck(status=status, toggle_count=count, limited=False)

    def search_songs(self, query, genre, limit=8):
        return [
            Song(
                id="song_1",
                title="Lover",
                artist="Diljit Dosanjh",
                genre="punjabi",
                artwork_url="https://example.com/art.jpg",
            )
        ]

    def submit_request(
        self,
        event_id,
        session_id,
        song_title,
        song_artist,
        genre,
        song_id,
        artwork_url=None,
        album=None,
        popularity=None,
    ):
        event = self.get_event(event_id)
        if event is not None and event.dj_status == "closed":
            return RequestAck(
                request_id=None,
                song_title=song_title,
                request_count=0,
                already_counted=False,
                message="The DJ isn't taking requests right now -- hang tight!",
            )
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
                artwork_url=artwork_url,
                album=album,
                popularity=popularity,
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

    def set_dj_status(self, event_id, status):
        for e in self.events:
            if e.id == event_id:
                updated = e.model_copy(update={"dj_status": status})
                self.events[self.events.index(e)] = updated
                return updated
        return None

    def db_health(self):
        from app.contracts import DBHealth

        return DBHealth(ok=True, latency_ms=1.0, total_requests_all_time=len(self.requests))

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

    def record_first_time_answer(self, event_id, session_id, answer):
        key = (event_id, session_id)
        existing = self.first_time_answers.get(key)
        if existing is not None:
            return FirstTimeAnswerAck(answer=existing, already_answered=True)
        self.first_time_answers[key] = answer
        return FirstTimeAnswerAck(answer=answer, already_answered=False)

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
    assert {"punjabi", "haryanvi", "tamil", "telugu", "marathi", "english", "edm", "other"} <= keys


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


def test_artwork_url_is_persisted_on_the_request(monkeypatch):
    client, _fake = _client(monkeypatch)
    event = client.post("/api/events", json={"name": "Artwork Test"}).json()
    res = client.post(
        "/api/requests",
        json={
            "event_id": event["id"],
            "session_id": "s1",
            "genre": "telugu",
            "song_title": "Oo Antava",
            "artwork_url": "https://example.com/art.jpg",
        },
    ).json()
    dash = client.get("/api/dashboard", params={"event_id": event["id"]}).json()
    assert dash["requests"][0]["artwork_url"] == "https://example.com/art.jpg"
    assert res["request_id"] == dash["requests"][0]["id"]


def test_dj_status_toggle(monkeypatch):
    client, _fake = _client(monkeypatch)
    event = client.post("/api/events", json={"name": "Status Test"}).json()
    assert event["dj_status"] == "open"

    res = client.post(f"/api/events/{event['id']}/status", json={"status": "closed"})
    assert res.status_code == 200
    assert res.json()["dj_status"] == "closed"

    # "busy" was a real status once -- removing it must actually reject it,
    # not silently accept it as a no-op.
    bad = client.post(f"/api/events/{event['id']}/status", json={"status": "busy"})
    assert bad.status_code == 422


def test_closed_dj_status_blocks_requests_with_a_polite_message(monkeypatch):
    client, _fake = _client(monkeypatch)
    event = client.post("/api/events", json={"name": "Closed Test"}).json()
    client.post(f"/api/events/{event['id']}/status", json={"status": "closed"})

    res = client.post(
        "/api/requests",
        json={
            "event_id": event["id"],
            "session_id": "s1",
            "genre": "punjabi",
            "song_title": "Lover",
        },
    ).json()
    assert res["request_id"] is None
    assert "taking requests" in res["message"].lower()

    dash = client.get("/api/dashboard", params={"event_id": event["id"]}).json()
    assert dash["requests"] == []


def test_pulse_vote_accepted_and_validated(monkeypatch):
    client, _fake = _client(monkeypatch)
    event = client.post("/api/events", json={"name": "Pulse Test"}).json()

    ok = client.post(
        f"/api/events/{event['id']}/pulse", json={"session_id": "s1", "status": "single"}
    )
    assert ok.status_code == 200
    body = ok.json()
    assert body["status"] == "single"
    assert body["toggle_count"] == 1
    assert body["limited"] is False

    bad = client.post(
        f"/api/events/{event['id']}/pulse", json={"session_id": "s1", "status": "married"}
    )
    assert bad.status_code == 422


def test_pulse_vote_capped_at_five_toggles(monkeypatch):
    client, _fake = _client(monkeypatch)
    event = client.post("/api/events", json={"name": "Pulse Limit Test"}).json()

    def vote(status):
        return client.post(
            f"/api/events/{event['id']}/pulse", json={"session_id": "s1", "status": status}
        ).json()

    # Alternate five times -- each one is a genuine change, so all count.
    for i in range(5):
        body = vote("single" if i % 2 == 0 else "committed")
        assert body["limited"] is False
    assert body["toggle_count"] == 5
    assert body["status"] == "single"

    # A 6th real change (to the opposite status) is over the cap.
    limited = vote("committed")
    assert limited["limited"] is True
    assert limited["status"] == "single"  # unchanged
    assert limited["message"]

    # But re-selecting the status you're already on is never a "change" --
    # always allowed, never counted against the cap.
    noop = vote("single")
    assert noop["limited"] is False
    assert noop["toggle_count"] == 5


def test_health_reports_db_status(monkeypatch):
    client, _fake = _client(monkeypatch)
    res = client.get("/api/health").json()
    assert res["ok"] is True
    assert res["db"]["ok"] is True


def test_config_exposes_event_settings_with_defaults(monkeypatch):
    client, _fake = _client(monkeypatch)
    res = client.get("/api/config").json()
    # An event that never configured anything ships the all-defaults shape --
    # no special-casing needed on the frontend for "unconfigured".
    assert res["settings"]["genre_buckets"] == []
    assert res["settings"]["max_actions_per_session"] is None
    assert res["settings"]["allow_cross_genre_backfill"] is False


def test_first_time_answer_rejects_anything_but_yes_or_no(monkeypatch):
    client, _fake = _client(monkeypatch)
    event = client.post("/api/events", json={"name": "FTA Test"}).json()
    res = client.post(
        "/api/first-time-answer",
        json={"event_id": event["id"], "session_id": "s1", "answer": "already_answered"},
    )
    assert res.status_code == 422


def test_first_time_answer_is_idempotent_per_session(monkeypatch):
    client, _fake = _client(monkeypatch)
    event = client.post("/api/events", json={"name": "FTA Idempotent Test"}).json()
    body = {"event_id": event["id"], "session_id": "s1", "answer": "yes"}

    first = client.post("/api/first-time-answer", json=body).json()
    assert first == {"answer": "yes", "already_answered": False}

    # Same session answering again (e.g. the modal firing twice) doesn't
    # overwrite the original answer, even with a different choice.
    second = client.post("/api/first-time-answer", json=dict(body, answer="no")).json()
    assert second == {"answer": "yes", "already_answered": True}
