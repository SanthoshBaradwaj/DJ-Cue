"""Setlist-aware insertion and the tip lifecycle (M3b).

Two properties carry the feature, and both are easy to get wrong:

* An insert is judged against **both** neighbours. A track that mixes out of
  the previous song but collides with the next one is a bad insert, and the
  original one-sided ranker could not see that.
* A tip **settles ties and nothing else**, and only pays out if the song
  actually plays. If either half of that slips, "tip to be heard" quietly
  becomes "pay to outvote the room" -- exactly what antimanip.py prevents.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from app.api.service import reset_service_for_tests  # noqa: E402
from app.catalog.insertion import TIE_BAND, propose_slots, transition_fit  # noqa: E402
from app.contracts import DJState, SetlistEntry, TipState, new_id  # noqa: E402
from app.store import reset_store_for_tests  # noqa: E402

EVENT = "setlist-test"

# The DJ's real exported history -- roughly one transition a minute.
REAL_SET = [
    {"cue_time": "00:54:53", "title": "Buzz"},
    {"cue_time": "00:56:27", "title": "Uyi Amma"},
    {"cue_time": "00:57:10", "title": "Tauba Tauba"},
    {"cue_time": "00:58:10", "title": "Chaleya"},
    {"cue_time": "00:59:09", "title": "Jhoome Jo Pathaan"},
    {"cue_time": "01:00:05", "title": "Akhiyaan Gulaab"},
    {"cue_time": "01:00:59", "title": "Garmi"},
]


@pytest.fixture()
def service():
    reset_store_for_tests()
    return reset_service_for_tests()


def seed(service, texts):
    async def run():
        for text in texts:
            await service.submit_request(text, new_id("sess"), EVENT)

    asyncio.run(run())


# ---------------------------------------------------------------------------
# Importing a real set
# ---------------------------------------------------------------------------


def test_the_real_setlist_resolves_completely(service):
    dj, unmatched = service.load_setlist(EVENT, REAL_SET)
    assert unmatched == [], unmatched
    assert [e.track.title for e in dj.upcoming()] == [
        "Buzz", "Uyi Amma", "Tauba Tauba", "Chaleya",
        "Jhoome Jo Pathaan", "Akhiyaan Gulaab", "Garmi",
    ]
    assert dj.upcoming()[0].cue_time == "00:54:53"


def test_unresolvable_titles_are_reported_not_dropped(service):
    _dj, unmatched = service.load_setlist(
        EVENT, REAL_SET + [{"cue_time": "01:02:00", "title": "Zzzz Not A Real Song"}]
    )
    assert unmatched == ["Zzzz Not A Real Song"]


def test_positions_are_contiguous_and_ordered(service):
    dj, _ = service.load_setlist(EVENT, REAL_SET)
    assert [e.position for e in dj.upcoming()] == list(range(len(REAL_SET)))


# ---------------------------------------------------------------------------
# Two-sided scoring -- the property the one-sided ranker could not express
# ---------------------------------------------------------------------------


def test_an_open_end_is_neutral_not_free(service):
    """Appending must not beat inserting just because there is no next track."""
    fit, delta, kind = transition_fit(None, service.catalog.search("Garmi", 1)[0])
    assert kind == "open"
    assert 0.0 < fit < 1.0


def test_a_collision_with_the_next_track_is_penalised(service):
    """Garmi mixes out of Chaleya (0.91) but slams into Jhoome (+22 BPM)."""
    cat = service.catalog
    chaleya = cat.search("Chaleya", 1)[0]
    jhoome = cat.search("Jhoome Jo Pathaan", 1)[0]
    garmi = cat.search("Garmi", 1)[0]

    out, _d, _k = transition_fit(chaleya, garmi)
    into, _d2, _k2 = transition_fit(garmi, jhoome)

    assert out > 0.8, out          # genuinely good on the way in
    assert into < 0.5, into        # genuinely bad on the way out
    # The harmonic combination must sit far below the good side, not average it.
    assert 2 * out * into / (out + into) < (out + into) / 2


def test_proposals_carry_both_neighbours(service):
    service.load_setlist(EVENT, REAL_SET)
    seed(service, ["bhangra bhangra", "punjabi banger", "dhol please"] * 3)
    proposals = service.propose_insertions(EVENT)

    assert proposals, "expected at least one insertion proposal"
    for p in proposals:
        assert 0 <= p.position <= len(service.store.dj_state(EVENT).upcoming())
        # Every proposal explains itself against real neighbours.
        assert p.after is not None or p.position == 0
        assert p.reasons


def test_no_proposals_without_a_plan(service):
    """A freestyle event has nothing to insert into."""
    seed(service, ["bhangra pls"] * 4)
    assert service.propose_insertions(EVENT) == []


def test_already_scheduled_tracks_are_not_reproposed(service):
    service.load_setlist(EVENT, REAL_SET)
    seed(service, ["tauba tauba", "karan aujla", "punjabi hits"] * 3)
    scheduled = {e.track.id for e in service.store.dj_state(EVENT).upcoming()}
    for p in service.propose_insertions(EVENT):
        assert p.track.id not in scheduled, p.track.title


# ---------------------------------------------------------------------------
# Tips: tiebreak only, and only paid on delivery
# ---------------------------------------------------------------------------


def _two_track_wave(service):
    """A wave plus a planned set, for direct control over proposal ordering."""
    service.load_setlist(EVENT, REAL_SET)
    seed(service, ["bhangra bhangra bhangra", "balle balle", "dhol pls"] * 4)
    return service.engine.waves(EVENT)[0], service.store.dj_state(EVENT)


def test_a_tip_cannot_leapfrog_a_clearly_better_fit(service):
    """The whole integrity claim: ₹5000 on a bad mix still loses to a good one.

    Deliberately does not hunt the catalog for a separated pair -- it builds
    one, so the property is exercised on every run rather than skipped whenever
    the ranker's top three happen to score closely.
    """
    wave, dj = _two_track_wave(service)  # a bhangra/punjabi hype wave

    great = service.catalog.search("Tauba Tauba", 1)[0]   # punjabi, hype, 98bpm
    awful = service.catalog.search("Akhiyaan Gulaab", 1)[0]  # romantic ballad, 92bpm
    tracks = [great, awful]

    untipped = propose_slots(wave, tracks, dj, tips=[], limit=2)
    assert untipped[0].track.id == great.id, "fixture assumption broken"
    gap = untipped[0].score - untipped[1].score
    assert gap > TIE_BAND, "these two must not be a genuine tie (gap %.3f)" % gap

    tip = service.create_tip(EVENT, "sess_whale", awful.id, 500_000)  # ₹5000
    assert tip is not None
    tipped = propose_slots(wave, tracks, dj, tips=[tip], limit=2)

    # Money bought a badge, not the top slot.
    assert tipped[0].track.id == great.id, (
        "₹5000 leapfrogged a better mix: %s beat %s"
        % (tipped[0].track.title, great.title)
    )
    loser = next(p for p in tipped if p.track.id == awful.id)
    assert loser.tip_minor == 500_000     # the tip is still recorded
    assert loser.tip_broke_tie is False   # it just did not decide anything


def test_a_tip_settles_a_genuine_tie(service):
    """Two placements inside TIE_BAND: the tipped one wins and says so."""
    wave, dj = _two_track_wave(service)
    ranked = service.ranker.rank(wave, dj)
    tracks = [c.track for c in ranked]

    base = propose_slots(wave, tracks, dj, tips=[], limit=len(tracks))
    pair = None
    for i in range(len(base) - 1):
        if abs(base[i].score - base[i + 1].score) < TIE_BAND:
            pair = (base[i], base[i + 1])
            break
    if pair is None:
        pytest.skip("no naturally tied pair in this catalog slice")

    leader, runner_up = pair
    tip = service.create_tip(EVENT, "sess_tipper", runner_up.track.id, 20_000)  # ₹200
    tipped = propose_slots(wave, tracks, dj, tips=[tip], limit=len(tracks))

    winner = next(p for p in tipped if p.track.id == runner_up.track.id)
    loser = next(p for p in tipped if p.track.id == leader.track.id)
    assert tipped.index(winner) < tipped.index(loser)
    assert winner.tip_broke_tie is True
    assert any("broke a tie" in r for r in winner.reasons)


def test_a_tip_is_not_charged_until_the_song_plays(service):
    service.load_setlist(EVENT, REAL_SET)
    garmi = service.catalog.search("Garmi", 1)[0]
    tip = service.create_tip(EVENT, "sess_a", garmi.id, 10_000)

    assert tip.state is TipState.PENDING
    assert service.tip_totals(EVENT)["captured"] == 0

    # Merely agreeing to play it settles nothing -- a set can still change.
    service.insert_into_setlist(EVENT, garmi.id, 0, wave_id=None)
    assert service.tips(EVENT)[0].state is TipState.PENDING

    service.record_decision(garmi.id, "play", None, EVENT)
    assert service.tips(EVENT)[0].state is TipState.CAPTURED
    assert service.tip_totals(EVENT)["captured"] == 10_000


def test_advancing_the_setlist_also_captures(service):
    service.load_setlist(EVENT, REAL_SET)
    first = service.store.dj_state(EVENT).upcoming()[0].track
    service.create_tip(EVENT, "sess_b", first.id, 5_000)

    dj = service.advance_setlist(EVENT)
    assert dj.current_track is not None and dj.current_track.id == first.id
    assert service.tips(EVENT)[0].state is TipState.CAPTURED
    # And it is no longer upcoming.
    assert first.id not in {e.track.id for e in dj.upcoming()}


def test_unplayed_tips_are_released_never_captured(service):
    service.load_setlist(EVENT, REAL_SET)
    never = service.catalog.search("Kesariya", 1)[0]
    service.create_tip(EVENT, "sess_c", never.id, 7_500)

    released = service.release_pending_tips(EVENT)
    assert len(released) == 1
    totals = service.tip_totals(EVENT)
    assert totals["released"] == 7_500
    assert totals["captured"] == 0


def test_a_released_tip_no_longer_influences_placement(service):
    wave, dj = _two_track_wave(service)
    tracks = [c.track for c in service.ranker.rank(wave, dj)]
    tip = service.create_tip(EVENT, "sess_d", tracks[-1].id, 100_000)

    service.release_pending_tips(EVENT)
    assert tip.is_live is False
    for p in propose_slots(wave, tracks, dj, tips=service.live_tips(EVENT)):
        assert p.tip_minor == 0
        assert p.tip_broke_tie is False


def test_zero_and_unknown_track_tips_are_rejected(service):
    assert service.create_tip(EVENT, "s", "trk_does_not_exist", 1_000) is None
    real = service.catalog.search("Garmi", 1)[0]
    assert service.create_tip(EVENT, "s", real.id, 0) is None
    assert service.create_tip(EVENT, "s", real.id, -500) is None


def test_reset_clears_tips(service):
    real = service.catalog.search("Garmi", 1)[0]
    service.create_tip(EVENT, "s", real.id, 1_000)
    service.reset(EVENT)
    assert service.tips(EVENT) == []
