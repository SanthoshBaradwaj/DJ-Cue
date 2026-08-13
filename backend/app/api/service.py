"""Application service layer.

Wires the four engines together and owns the one operation that matters:
ingest a guest request, re-cluster, re-rank, and push the new world to every
dashboard. Kept separate from the HTTP routes so the demo seeder and the
verifier can drive the exact same code path the API does.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Dict, List, Optional, Set, Tuple

from ..catalog import Ranker, get_catalog
from ..catalog import insertion
from ..clustering import WaveEngine
from ..config import settings
from ..contracts import (
    DashboardState,
    Decision,
    DJState,
    RequestAck,
    SetlistEntry,
    SlotProposal,
    SongRequest,
    Tip,
    TipState,
    Track,
    Wave,
    WaveView,
    WSMessage,
    now_ts,
)
from ..events import bus
from ..interpreter import interpret_async, phrase_ack
from ..store import get_store

log = logging.getLogger("cue.service")

# A DJ's exported history carries extra words the catalog title does not
# ("JAWAN Chaleya", "Tauba Tauba Bad Newz"), so the match has to tolerate
# noise around the title -- but not tolerate a single incidental word carrying
# the whole match. Requiring most of the *matched title* to appear in the
# queried string gets both: "JAWAN Chaleya" covers "Chaleya" completely, while
# "Zzzz Not A Real Song" covers only 1 of the 3 words in "Not Like Us".
_TITLE_COVERAGE = 0.6

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> Set[str]:
    return set(_TOKEN_RE.findall((text or "").lower()))


def _is_confident_match(query: str, track: Track) -> bool:
    """Is ``track`` really the song ``query`` names, or just a shared word?"""
    q = _tokens(query)
    title = _tokens(track.title)
    if not q or not title:
        return False
    covered = len(title & q) / float(len(title))
    if covered >= _TITLE_COVERAGE:
        return True
    # An exact substring is decisive even when tokenisation disagrees.
    return track.title.lower() in query.lower() or query.lower() in track.title.lower()


class CueService:
    def __init__(self) -> None:
        self.store = get_store()
        self.catalog = get_catalog()
        self.ranker = Ranker(self.catalog)
        self.engine = WaveEngine(self.store)
        # Tracks the DJ has explicitly skipped, per event -- never recommend
        # them again in this set. A DJ who has to say no twice loses trust.
        self._skipped: Dict[str, Set[str]] = {}
        # Tips, per event. Deliberately alongside _skipped rather than in the
        # store: same lifetime as an event, and it keeps store.py untouched.
        self._tips: Dict[str, List[Tip]] = {}

    # -- reads --------------------------------------------------------------

    def skipped(self, event_id: str) -> Set[str]:
        return self._skipped.setdefault(event_id, set())

    def tips(self, event_id: str) -> List[Tip]:
        return self._tips.setdefault(event_id, [])

    def live_tips(self, event_id: str) -> List[Tip]:
        """Tips still capable of influencing a placement."""
        return [t for t in self.tips(event_id) if t.is_live]

    def tip_totals(self, event_id: str) -> Dict[str, int]:
        """``{state: minor units}`` -- what is promised, earned, and released."""
        totals = {s.value: 0 for s in TipState}
        for tip in self.tips(event_id):
            totals[tip.state.value] += int(tip.amount_minor)
        return totals

    def propose_insertions(
        self, event_id: str, horizon: int = insertion.DEFAULT_HORIZON
    ) -> List[SlotProposal]:
        """Where each wave's best tracks belong in the DJ's planned set.

        Returns the strongest proposal per wave, so the DJ reads one row per
        thing the room wants rather than a wall of permutations.
        """
        dj = self.store.dj_state(event_id)
        if not dj.upcoming():
            return []  # freestyle event -- nothing to insert into

        exclude = set(self.skipped(event_id))
        # Never propose something already scheduled ahead.
        exclude |= {e.track.id for e in dj.upcoming()}

        tips = self.live_tips(event_id)
        out: List[SlotProposal] = []
        for wave in self.engine.waves(event_id)[: settings.max_waves_shown]:
            try:
                candidates = self.ranker.rank(wave, dj, exclude=exclude)
                proposals = insertion.propose_slots(
                    wave,
                    [c.track for c in candidates],
                    dj,
                    tips=tips,
                    horizon=horizon,
                    limit=1,
                )
            except Exception:  # a scoring bug must not blank the booth screen
                log.exception("insertion failed for wave %s", wave.id)
                continue
            if proposals:
                out.append(proposals[0])
                exclude.add(proposals[0].track.id)

        out.sort(key=lambda p: -p.score)
        return out

    def build_dashboard(self, event_id: str) -> DashboardState:
        waves: List[Wave] = self.engine.waves(event_id)
        dj: DJState = self.store.dj_state(event_id)
        exclude = set(self.skipped(event_id))

        views: List[WaveView] = []
        for wave in waves[: settings.max_waves_shown]:
            try:
                candidates = self.ranker.rank(wave, dj, exclude=exclude)
            except Exception as exc:  # a ranking bug must not blank the screen
                log.exception("ranking failed for wave %s: %s", wave.id, exc)
                candidates = []
            # Don't offer the same track twice across two waves on one screen;
            # it makes the recommendations look thin.
            for candidate in candidates:
                exclude.add(candidate.track.id)
            views.append(WaveView(wave=wave, candidates=candidates))

        return DashboardState(
            event_id=event_id,
            waves=views,
            dj=dj,
            stats=self.store.stats(event_id),
        )

    # -- writes -------------------------------------------------------------

    async def submit_request(
        self, text: str, session_id: str, event_id: str
    ) -> RequestAck:
        started = time.perf_counter()
        intent = await interpret_async(text)
        self.store.record_interpret_ms(event_id, (time.perf_counter() - started) * 1000)

        request, wave, joined = self.engine.ingest(event_id, session_id, text, intent)

        # The guest's own request counts toward the wave they see, so report
        # unique people rather than raw submissions -- it's the honest number
        # and it's the one that makes them feel part of something.
        others = max(0, wave.unique_sessions - 1)
        ack = RequestAck(
            request_id=request.id,
            session_id=session_id,
            message=phrase_ack(intent, wave.label, others),
            intent_summary=intent.summary or wave.label,
            wave_id=wave.id,
            wave_label=wave.label,
            wave_size=others,
            joined_existing_wave=joined,
        )

        bus.publish(
            event_id,
            WSMessage(
                type="request",
                payload={
                    "text": text,
                    "wave_label": wave.label,
                    "wave_id": wave.id,
                    "session_id": session_id,
                    "summary": intent.summary,
                },
            ),
        )
        self.broadcast_state(event_id)
        return ack

    def record_decision(
        self, track_id: str, action: str, wave_id: Optional[str], event_id: str
    ) -> DJState:
        track = self.catalog.get(track_id)
        dj = self.store.dj_state(event_id)

        if action == "play":
            if track is not None:
                dj = self.store.set_current_track(event_id, track)
                # Playing something that was queued removes it from the queue.
                dj.queue = [t for t in dj.queue if t.id != track_id]
                # If this track was a planned slot, it is no longer upcoming.
                for entry in dj.setlist:
                    if entry.played_at is None and entry.track.id == track_id:
                        entry.played_at = now_ts()
                        break
                # The guest's request is satisfied the moment it actually plays.
                self._capture_tips(event_id, track_id)
                bus.publish(
                    event_id,
                    WSMessage(
                        type="now_playing", payload={"track": track.model_dump()}
                    ),
                )
        elif action == "later":
            if track is not None and all(t.id != track_id for t in dj.queue):
                dj.queue.append(track)
        elif action == "skip":
            self.skipped(event_id).add(track_id)
            dj.queue = [t for t in dj.queue if t.id != track_id]

        self.store.add_decision(
            Decision(
                event_id=event_id, wave_id=wave_id, track_id=track_id, action=action
            )
        )
        bus.publish(
            event_id,
            WSMessage(
                type="decision",
                payload={
                    "action": action,
                    "wave_id": wave_id,
                    "track": track.model_dump() if track else None,
                },
            ),
        )
        self.broadcast_state(event_id)
        return dj

    # -- setlist ------------------------------------------------------------

    def load_setlist(
        self, event_id: str, entries: List[Dict[str, str]]
    ) -> Tuple[DJState, List[str]]:
        """Import the DJ's planned set from ``[{cue_time, title}, ...]``.

        Titles are resolved against the catalog by fuzzy search, because a DJ's
        exported history says "JAWAN Chaleya", not ``trk_chaleya``. Anything
        that cannot be resolved is returned as an unmatched list rather than
        silently dropped -- a set with a hole in it would score insertions
        against the wrong neighbours.
        """
        dj = self.store.dj_state(event_id)
        slots: List[SetlistEntry] = []
        unmatched: List[str] = []

        for index, raw in enumerate(entries):
            title = str(raw.get("title", "")).strip()
            if not title:
                continue
            hits = self.catalog.search(title, limit=1)
            if not hits or not _is_confident_match(title, hits[0]):
                # Reported, never guessed. The catalog's fuzzy search is tuned
                # for a guest typing "diljit" and will cheerfully match
                # "Zzzz Not A Real Song" to "Not Like Us" on the shared word
                # "not". Accepting that would put a song the DJ is not playing
                # into the set, and then every insertion either side of it is
                # scored against the wrong neighbours -- silently wrong data is
                # worse than an honest miss.
                unmatched.append(title)
                continue
            slots.append(
                SetlistEntry(
                    position=len(slots),
                    track=hits[0],
                    cue_time=(str(raw.get("cue_time")).strip() or None)
                    if raw.get("cue_time")
                    else None,
                )
            )

        dj.setlist = slots
        # The set has a plan but nothing has played yet; the first slot is what
        # the DJ is about to drop, not what is already on the decks.
        self.store.set_dj_state(dj)
        self.broadcast_state(event_id)
        return dj, unmatched

    def advance_setlist(self, event_id: str) -> DJState:
        """The DJ moved on: play the next planned slot.

        Marks it played, promotes it to ``current_track`` (which is what every
        bridge score is measured against), and settles any tips riding on it --
        this is the moment a guest's request counts as satisfied.
        """
        dj = self.store.dj_state(event_id)
        upcoming = dj.upcoming(limit=1)
        if not upcoming:
            return dj

        slot = upcoming[0]
        slot.played_at = now_ts()
        dj = self.store.set_current_track(event_id, slot.track)
        dj.queue = [t for t in dj.queue if t.id != slot.track.id]
        self._capture_tips(event_id, slot.track.id)

        bus.publish(
            event_id,
            WSMessage(type="now_playing", payload={"track": slot.track.model_dump()}),
        )
        self.broadcast_state(event_id)
        return dj

    def insert_into_setlist(
        self, event_id: str, track_id: str, position: int, wave_id: Optional[str] = None
    ) -> DJState:
        """Accept a crowd request into the planned set at ``position``.

        Inserting does **not** settle the tip. The guest's request is satisfied
        when the track actually plays, not when the DJ agrees to play it -- a
        set can always change before the needle gets there.
        """
        track = self.catalog.get(track_id)
        dj = self.store.dj_state(event_id)
        if track is None:
            return dj

        upcoming = dj.upcoming()
        clamped = max(0, min(int(position), len(upcoming)))
        anchor = upcoming[clamped].position if clamped < len(upcoming) else None

        new_slot = SetlistEntry(
            track=track,
            position=anchor if anchor is not None else (len(dj.setlist)),
            inserted_from_wave_id=wave_id,
        )
        # Shift everything at or after the anchor down one place.
        if anchor is not None:
            for entry in dj.setlist:
                if entry.played_at is None and entry.position >= anchor:
                    entry.position += 1
        dj.setlist.append(new_slot)
        dj.setlist.sort(key=lambda e: e.position)

        self.store.set_dj_state(dj)
        self.store.add_decision(
            Decision(
                event_id=event_id, wave_id=wave_id, track_id=track_id, action="later"
            )
        )
        self.broadcast_state(event_id)
        return dj

    # -- tips ---------------------------------------------------------------

    def create_tip(
        self,
        event_id: str,
        session_id: str,
        track_id: str,
        amount_minor: int,
        wave_id: Optional[str] = None,
        currency: str = "INR",
    ) -> Optional[Tip]:
        """Authorise a tip against one track. Nothing is charged yet."""
        if self.catalog.get(track_id) is None or int(amount_minor) <= 0:
            return None
        tip = Tip(
            event_id=event_id,
            session_id=session_id or "",
            track_id=track_id,
            wave_id=wave_id,
            amount_minor=int(amount_minor),
            currency=currency,
        )
        self.tips(event_id).append(tip)
        self.broadcast_state(event_id)
        return tip

    def _capture_tips(self, event_id: str, track_id: str) -> List[Tip]:
        """The track played, so the promise is now earned."""
        captured = []
        for tip in self.tips(event_id):
            if tip.is_live and tip.track_id == track_id:
                tip.state = TipState.CAPTURED
                tip.settled_at = now_ts()
                captured.append(tip)
        if captured:
            log.info(
                "captured %d tip(s) for %s in event %s", len(captured), track_id, event_id
            )
        return captured

    def release_pending_tips(self, event_id: str) -> List[Tip]:
        """Set over. Anything unplayed is released -- the guest is not charged."""
        released = []
        for tip in self.tips(event_id):
            if tip.is_live:
                tip.state = TipState.RELEASED
                tip.settled_at = now_ts()
                released.append(tip)
        if released:
            self.broadcast_state(event_id)
        return released

    def reset(self, event_id: str) -> None:
        self.store.reset(event_id)
        self._skipped.pop(event_id, None)
        self._tips.pop(event_id, None)
        self.engine.recompute(event_id)
        self.broadcast_state(event_id)

    # -- transport ----------------------------------------------------------

    def broadcast_state(self, event_id: str) -> None:
        try:
            state = self.build_dashboard(event_id)
        except Exception as exc:  # pragma: no cover - defensive
            log.exception("failed to build dashboard state: %s", exc)
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


def reset_service_for_tests() -> CueService:
    global _service
    _service = CueService()
    return _service
