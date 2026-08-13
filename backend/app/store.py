"""State layer: in-memory authority, SQLite mirror.

Clustering re-reads the full request set on every ingest, so the authoritative
copy lives in memory (a dict lookup, not a query). SQLite is written through for
durability and post-event analytics -- if the laptop dies mid-set, the DJ
reloads and the floor's requests are still there.

Scoped to a single event by design; the PRD targets a 24-48 hour event.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from typing import Dict, List, Optional

from .config import settings
from .contracts import (
    Decision,
    DJState,
    EventStats,
    SongRequest,
    Track,
    Wave,
)

log = logging.getLogger("cue.store")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS requests (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    text TEXT NOT NULL,
    intent_json TEXT NOT NULL,
    weight REAL NOT NULL,
    discount_reason TEXT,
    wave_id TEXT,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_requests_event ON requests(event_id, created_at);

CREATE TABLE IF NOT EXISTS waves (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL,
    label TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS decisions (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL,
    wave_id TEXT,
    track_id TEXT NOT NULL,
    action TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS metrics (
    event_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value REAL NOT NULL,
    PRIMARY KEY (event_id, key)
);
"""


class Store:
    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path or settings.db_path
        self._lock = threading.RLock()

        self._requests: Dict[str, List[SongRequest]] = {}
        self._waves: Dict[str, List[Wave]] = {}
        self._dj: Dict[str, DJState] = {}
        self._decisions: Dict[str, List[Decision]] = {}
        self._interpret_times: Dict[str, List[float]] = {}

        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()
        self._load()

    # -- persistence --------------------------------------------------------

    def _load(self) -> None:
        """Rehydrate in-memory state from disk on boot."""
        try:
            cur = self._conn.execute(
                "SELECT id, event_id, session_id, text, intent_json, weight,"
                " discount_reason, wave_id, created_at FROM requests"
                " ORDER BY created_at ASC"
            )
            for row in cur.fetchall():
                request = SongRequest(
                    id=row[0],
                    event_id=row[1],
                    session_id=row[2],
                    text=row[3],
                    intent=json.loads(row[4]),
                    weight=row[5],
                    discount_reason=row[6],
                    wave_id=row[7],
                    created_at=row[8],
                )
                self._requests.setdefault(request.event_id, []).append(request)

            cur = self._conn.execute(
                "SELECT event_id, wave_id, track_id, action, id, created_at"
                " FROM decisions ORDER BY created_at ASC"
            )
            for row in cur.fetchall():
                decision = Decision(
                    event_id=row[0],
                    wave_id=row[1],
                    track_id=row[2],
                    action=row[3],
                    id=row[4],
                    created_at=row[5],
                )
                self._decisions.setdefault(decision.event_id, []).append(decision)
        except Exception as exc:  # pragma: no cover - corrupt db shouldn't brick boot
            log.warning("could not rehydrate store (%s); starting empty", exc)

    # -- requests -----------------------------------------------------------

    def add_request(self, request: SongRequest) -> SongRequest:
        with self._lock:
            self._requests.setdefault(request.event_id, []).append(request)
            self._conn.execute(
                "INSERT OR REPLACE INTO requests VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    request.id,
                    request.event_id,
                    request.session_id,
                    request.text,
                    request.intent.model_dump_json(),
                    request.weight,
                    request.discount_reason,
                    request.wave_id,
                    request.created_at,
                ),
            )
            self._conn.commit()
        return request

    def requests(self, event_id: str) -> List[SongRequest]:
        with self._lock:
            return list(self._requests.get(event_id, []))

    def session_requests(self, event_id: str, session_id: str) -> List[SongRequest]:
        return [r for r in self.requests(event_id) if r.session_id == session_id]

    def update_request_waves(self, event_id: str, mapping: Dict[str, str]) -> None:
        """Persist which wave each request landed in."""
        with self._lock:
            for request in self._requests.get(event_id, []):
                if request.id in mapping:
                    request.wave_id = mapping[request.id]
            self._conn.executemany(
                "UPDATE requests SET wave_id = ? WHERE id = ?",
                [(wave_id, rid) for rid, wave_id in mapping.items()],
            )
            self._conn.commit()

    # -- waves --------------------------------------------------------------

    def set_waves(self, event_id: str, waves: List[Wave]) -> None:
        with self._lock:
            self._waves[event_id] = list(waves)
            self._conn.execute("DELETE FROM waves WHERE event_id = ?", (event_id,))
            self._conn.executemany(
                "INSERT INTO waves VALUES (?,?,?,?,?)",
                [
                    (w.id, w.event_id, w.label, w.model_dump_json(), w.updated_at)
                    for w in waves
                ],
            )
            self._conn.commit()

    def waves(self, event_id: str) -> List[Wave]:
        with self._lock:
            return list(self._waves.get(event_id, []))

    # -- DJ state -----------------------------------------------------------

    def dj_state(self, event_id: str) -> DJState:
        with self._lock:
            if event_id not in self._dj:
                self._dj[event_id] = DJState(event_id=event_id)
            return self._dj[event_id]

    def set_dj_state(self, state: DJState) -> DJState:
        with self._lock:
            self._dj[state.event_id] = state
            return state

    def set_current_track(self, event_id: str, track: Optional[Track]) -> DJState:
        import time

        with self._lock:
            state = self.dj_state(event_id)
            if state.current_track is not None:
                state.history.append(state.current_track)
                state.history = state.history[-25:]
            state.current_track = track
            state.started_at = time.time() if track else None
            return state

    # -- decisions ----------------------------------------------------------

    def add_decision(self, decision: Decision) -> Decision:
        with self._lock:
            self._decisions.setdefault(decision.event_id, []).append(decision)
            self._conn.execute(
                "INSERT OR REPLACE INTO decisions VALUES (?,?,?,?,?,?)",
                (
                    decision.id,
                    decision.event_id,
                    decision.wave_id,
                    decision.track_id,
                    decision.action,
                    decision.created_at,
                ),
            )
            self._conn.commit()
        return decision

    def decisions(self, event_id: str) -> List[Decision]:
        with self._lock:
            return list(self._decisions.get(event_id, []))

    # -- metrics ------------------------------------------------------------

    def record_interpret_ms(self, event_id: str, ms: float) -> None:
        with self._lock:
            samples = self._interpret_times.setdefault(event_id, [])
            samples.append(ms)
            del samples[:-200]

    def stats(self, event_id: str) -> EventStats:
        requests = self.requests(event_id)
        waves = self.waves(event_id)
        decisions = self.decisions(event_id)
        samples = self._interpret_times.get(event_id, [])

        acted = [d for d in decisions if d.action in ("play", "later")]
        return EventStats(
            total_requests=len(requests),
            unique_sessions=len({r.session_id for r in requests if r.session_id}),
            wave_count=len(waves),
            compression_ratio=(
                1.0 - (len(waves) / float(len(requests))) if requests else 0.0
            ),
            decisions_made=len(decisions),
            actionability=(len(acted) / float(len(decisions)) if decisions else 0.0),
            avg_interpret_ms=(sum(samples) / len(samples) if samples else 0.0),
            llm_enabled=settings.has_llm,
        )

    # -- lifecycle ----------------------------------------------------------

    def reset(self, event_id: str) -> None:
        """Wipe an event clean -- used between demo runs."""
        with self._lock:
            self._requests.pop(event_id, None)
            self._waves.pop(event_id, None)
            self._decisions.pop(event_id, None)
            self._interpret_times.pop(event_id, None)
            self._dj[event_id] = DJState(event_id=event_id)
            for table in ("requests", "waves", "decisions"):
                self._conn.execute(
                    "DELETE FROM %s WHERE event_id = ?" % table, (event_id,)
                )
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()


_store: Optional[Store] = None


def get_store() -> Store:
    global _store
    if _store is None:
        _store = Store()
    return _store


def reset_store_for_tests(db_path: str = ":memory:") -> Store:
    """Fresh isolated store -- used by module contract tests."""
    global _store
    if _store is not None:
        try:
            _store.close()
        except Exception:
            pass
    if db_path != ":memory:" and os.path.exists(db_path):
        os.remove(db_path)
    _store = Store(db_path)
    return _store
