"""Contract tests for M3 -- track catalog + context-aware ranker.

These deliberately construct ``Intent``/``Wave``/``DJState`` by hand rather
than importing the interpreter or clustering modules: M3 must be correct
independently of how a wave got built.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import taxonomy  # noqa: E402
from app.catalog import Catalog, Ranker, get_catalog  # noqa: E402
from app.catalog.ranker import bpm_relationship  # noqa: E402
from app.config import settings  # noqa: E402
from app.contracts import DJState, Intent, Track, Wave  # noqa: E402


CATALOG = get_catalog()
RANKER = Ranker(CATALOG)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_wave(label, languages=None, genres=None, moods=None, eras=None,
              artists=None, energy=0.7, dance=0.7, familiarity=0.7,
              raw_count=10, weight=9.0, share=0.35, keywords=None):
    return Wave(
        label=label,
        raw_count=raw_count,
        unique_sessions=raw_count,
        weight=weight,
        share=share,
        top_keywords=list(keywords or []),
        centroid=Intent(
            languages=list(languages or []),
            genres=list(genres or []),
            moods=list(moods or []),
            eras=list(eras or []),
            artists=list(artists or []),
            energy_target=energy,
            danceability=dance,
            familiarity=familiarity,
        ),
    )


PUNJABI_WAVE = make_wave(
    "High-Energy Punjabi",
    languages=["punjabi"], genres=["bhangra"], moods=["hype", "celebratory"],
    energy=0.9, dance=0.9, familiarity=0.75, raw_count=18, weight=16.0, share=0.45,
)

BOLLY_ROMANCE_WAVE = make_wave(
    "2000s Bollywood Nostalgia",
    languages=["hindi"], genres=["bollywood"], moods=["romantic", "nostalgic"],
    eras=["2000s"], energy=0.35, dance=0.45, familiarity=0.85,
    raw_count=9, weight=8.0, share=0.22,
)

HOUSE_WAVE = make_wave(
    "Euphoric House",
    languages=["english"], genres=["house"], moods=["euphoric"],
    energy=0.85, dance=0.85, familiarity=0.6,
    raw_count=12, weight=11.0, share=0.3,
)


# ---------------------------------------------------------------------------
# Catalog integrity -- guards the shared vector space
# ---------------------------------------------------------------------------


def test_catalog_is_substantial():
    assert len(CATALOG.all()) >= 120, len(CATALOG.all())


def test_track_ids_are_unique():
    ids = [t.id for t in CATALOG.all()]
    assert len(ids) == len(set(ids))
    assert all(t.id for t in CATALOG.all())


def test_every_track_uses_only_taxonomy_tokens():
    """An off-vocabulary token is silently invisible in the vector space."""
    offenders = []
    for track in CATALOG.all():
        if not taxonomy.is_valid("languages", track.language):
            offenders.append((track.id, "language", track.language))
        if not taxonomy.is_valid("eras", track.era):
            offenders.append((track.id, "era", track.era))
        for genre in track.genres:
            if not taxonomy.is_valid("genres", genre):
                offenders.append((track.id, "genre", genre))
        for mood in track.moods:
            if not taxonomy.is_valid("moods", mood):
                offenders.append((track.id, "mood", mood))
    assert offenders == [], offenders


def test_every_track_has_genres_and_moods():
    for track in CATALOG.all():
        assert track.genres, track.id
        assert track.moods, track.id
        assert track.title and track.artist, track.id


def test_numeric_fields_are_in_range():
    for track in CATALOG.all():
        assert 60 <= track.bpm <= 200, (track.id, track.bpm)
        assert 0.0 <= track.energy <= 1.0, (track.id, track.energy)
        assert 0.0 <= track.danceability <= 1.0, (track.id, track.danceability)
        assert 0.0 <= track.popularity <= 1.0, (track.id, track.popularity)
        assert 60 <= track.duration_sec <= 900, (track.id, track.duration_sec)
        assert track.audio_file is None


def test_language_coverage():
    assert len(CATALOG.by_language("punjabi")) >= 15
    assert len(CATALOG.by_language("hindi")) >= 25
    assert len(CATALOG.by_language("english")) >= 40


def test_genre_coverage_spans_the_night():
    genres = set()
    for track in CATALOG.all():
        genres.update(track.genres)
    for required in ("bhangra", "bollywood", "hiphop", "house", "edm",
                     "disco", "reggaeton", "afrobeat", "desi_hiphop", "amapiano"):
        assert required in genres, required


def test_get_and_all():
    first = CATALOG.all()[0]
    assert CATALOG.get(first.id) is not None
    assert CATALOG.get(first.id).id == first.id
    assert CATALOG.get("trk_does_not_exist") is None


def test_get_catalog_is_a_singleton():
    assert get_catalog() is get_catalog()
    assert isinstance(get_catalog(), Catalog)


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


def test_search_by_artist_diljit():
    hits = CATALOG.search("diljit")
    assert hits
    assert all("diljit" in t.artist.lower() or "diljit" in " ".join(t.tags).lower()
               for t in hits[:3])


def test_search_by_artist_bad_bunny():
    hits = CATALOG.search("bad bunny")
    assert hits
    assert any("Bad Bunny" in t.artist for t in hits[:3])


def test_search_by_title_and_tag():
    assert any(t.title == "Kala Chashma" for t in CATALOG.search("kala chashma"))
    assert CATALOG.search("wedding")
    assert CATALOG.search("") == []


def test_search_respects_limit():
    assert len(CATALOG.search("a", limit=4)) <= 4


# ---------------------------------------------------------------------------
# Relevance
# ---------------------------------------------------------------------------


def test_punjabi_wave_returns_punjabi_or_bhangra():
    cands = RANKER.rank(PUNJABI_WAVE, DJState(), k=3)
    assert len(cands) == 3
    for cand in cands:
        track = cand.track
        assert track.language == "punjabi" or "bhangra" in track.genres, (
            track.title, track.language, track.genres,
        )


def test_bollywood_romance_wave_is_not_bhangra():
    cands = RANKER.rank(BOLLY_ROMANCE_WAVE, DJState(), k=3)
    assert len(cands) == 3
    for cand in cands:
        track = cand.track
        assert track.language == "hindi", (track.title, track.language)
        assert "bollywood" in track.genres, (track.title, track.genres)
        assert "bhangra" not in track.genres, (track.title, track.genres)
    # The floor asked for a slow, romantic room -- do not hand back bangers.
    assert all(c.track.energy <= 0.7 for c in cands), [
        (c.track.title, c.track.energy) for c in cands
    ]


def test_house_wave_returns_dance_music():
    cands = RANKER.rank(HOUSE_WAVE, DJState(), k=3)
    assert len(cands) == 3
    for cand in cands:
        assert set(cand.track.genres) & {"house", "techno", "edm"}, (
            cand.track.title, cand.track.genres,
        )


def test_named_artist_beats_a_generic_match():
    """An explicit artist ask is the strongest signal a guest can send."""
    wave = make_wave(
        "Punjabi -- Diljit",
        languages=["punjabi"], genres=["bhangra"], moods=["hype"],
        artists=["Diljit Dosanjh"], energy=0.85, dance=0.85,
    )
    cands = RANKER.rank(wave, DJState(), k=3)
    assert all("Diljit" in c.track.artist for c in cands), [
        c.track.artist for c in cands
    ]


# ---------------------------------------------------------------------------
# Bridge logic
# ---------------------------------------------------------------------------


def _bridges(track_bpm, current_bpm):
    """Whether a tempo pair is mixable directly or at half/double time."""
    span = settings.max_bpm_bridge
    if abs(track_bpm - current_bpm) <= span:
        return True
    if abs(track_bpm - 2 * current_bpm) <= span:
        return True
    if abs(track_bpm - current_bpm / 2.0) <= span:
        return True
    return False


def test_candidates_bridge_from_the_current_track():
    current = Track(
        id="trk_current_house", title="Current", artist="Resident",
        language="english", genres=["house"], moods=["euphoric"], era="2020s",
        bpm=128, energy=0.85, danceability=0.85, popularity=0.6,
        duration_sec=240, tags=["peak-time"],
    )
    cands = RANKER.rank(HOUSE_WAVE, DJState(current_track=current), k=3)
    assert len(cands) == 3
    for cand in cands:
        assert _bridges(cand.track.bpm, 128), (cand.track.title, cand.track.bpm)
        assert cand.bpm_delta == cand.track.bpm - 128
        assert cand.bridge_score > 0.0


def test_half_and_double_time_are_recognised():
    fit_direct, kind_direct, _ = bpm_relationship(128, 126)
    assert kind_direct == "direct"
    assert fit_direct == 1.0

    fit_double, kind_double, _ = bpm_relationship(142, 71)
    assert kind_double == "double", kind_double
    assert fit_double > 0.85, fit_double

    fit_half, kind_half, _ = bpm_relationship(70, 140)
    assert kind_half == "half", kind_half
    assert fit_half > 0.85, fit_half

    fit_none, _, _ = bpm_relationship(128, 100)
    assert fit_none == 0.0, fit_none


def test_cold_start_is_not_punished():
    cands = RANKER.rank(HOUSE_WAVE, DJState(), k=3)
    assert len(cands) == 3
    for cand in cands:
        assert cand.bpm_delta is None
        assert cand.bridge_score == 0.6


def test_big_energy_drop_at_peak_is_penalised():
    from app.catalog.ranker import bridge_score as bridge

    peak = Track(
        id="trk_peak", title="Peak", artist="Resident", language="english",
        genres=["house"], moods=["hype"], era="2020s", bpm=128, energy=0.95,
        danceability=0.9, popularity=0.6, duration_sec=240, tags=["peak-time"],
    )
    ballad = Track(
        id="trk_ballad", title="Ballad", artist="Someone", language="english",
        genres=["pop"], moods=["sad"], era="2020s", bpm=128, energy=0.25,
        danceability=0.3, popularity=0.6, duration_sec=240, tags=["closer"],
    )
    steady = Track(
        id="trk_steady", title="Steady", artist="Someone", language="english",
        genres=["house"], moods=["hype"], era="2020s", bpm=128, energy=0.95,
        danceability=0.9, popularity=0.6, duration_sec=240, tags=["peak-time"],
    )
    state = DJState(current_track=peak)
    assert bridge(ballad, state)[0] < bridge(steady, state)[0]


# ---------------------------------------------------------------------------
# Exclusions and repeats
# ---------------------------------------------------------------------------


def test_current_track_and_history_are_excluded():
    top = RANKER.rank(PUNJABI_WAVE, DJState(), k=4)
    current = top[0].track
    played = top[1].track
    state = DJState(current_track=current, history=[played])

    cands = RANKER.rank(PUNJABI_WAVE, state, k=5)
    ids = {c.track.id for c in cands}
    assert current.id not in ids
    assert played.id not in ids


def test_explicit_exclude_set_is_honoured():
    top = RANKER.rank(PUNJABI_WAVE, DJState(), k=3)
    blocked = {c.track.id for c in top}
    cands = RANKER.rank(PUNJABI_WAVE, DJState(), k=3, exclude=blocked)
    assert blocked & {c.track.id for c in cands} == set()


def test_queued_tracks_are_downranked_not_removed():
    baseline = RANKER.rank(PUNJABI_WAVE, DJState(), k=5)
    queued_track = baseline[0].track

    state = DJState(queue=[queued_track])
    cands = RANKER.rank(PUNJABI_WAVE, state, k=len(CATALOG.all()))
    by_id = {c.track.id: c for c in cands}
    assert queued_track.id in by_id  # still available, just less attractive
    assert by_id[queued_track.id].score < baseline[0].score


# ---------------------------------------------------------------------------
# Candidate shape
# ---------------------------------------------------------------------------


def test_every_candidate_has_reasons():
    current = Track(
        id="trk_current_bhangra", title="Current", artist="Resident",
        language="punjabi", genres=["bhangra"], moods=["hype"], era="2020s",
        bpm=100, energy=0.8, danceability=0.85, popularity=0.6,
        duration_sec=240, tags=["dhol"],
    )
    for wave in (PUNJABI_WAVE, BOLLY_ROMANCE_WAVE, HOUSE_WAVE):
        for state in (DJState(), DJState(current_track=current)):
            for cand in RANKER.rank(wave, state, k=3):
                assert len(cand.reasons) >= 2, (cand.track.title, cand.reasons)
                assert all(r and r.strip() for r in cand.reasons)
                assert len(set(cand.reasons)) == len(cand.reasons)
                if state.current_track is not None:
                    assert cand.bpm_delta is not None


def test_scores_are_bounded_and_sorted():
    cands = RANKER.rank(PUNJABI_WAVE, DJState(), k=10)
    scores = [c.score for c in cands]
    assert scores == sorted(scores, reverse=True)
    for cand in cands:
        assert 0.0 <= cand.vibe_score <= 1.0
        assert 0.0 <= cand.demand_score <= 1.0
        assert 0.0 <= cand.bridge_score <= 1.0
        assert 0.0 <= cand.score <= 1.0


def test_demand_is_constant_within_a_wave_and_tracks_size():
    small = make_wave("Fringe", languages=["punjabi"], genres=["bhangra"],
                      raw_count=2, weight=2.0, share=0.05)
    big = make_wave("Dominant", languages=["punjabi"], genres=["bhangra"],
                    raw_count=30, weight=28.0, share=0.7)

    small_cands = RANKER.rank(small, DJState(), k=3)
    big_cands = RANKER.rank(big, DJState(), k=3)

    assert len({c.demand_score for c in small_cands}) == 1
    assert big_cands[0].demand_score > small_cands[0].demand_score
    assert big_cands[0].score > small_cands[0].score


# ---------------------------------------------------------------------------
# Robustness
# ---------------------------------------------------------------------------


def test_default_k_is_candidates_per_wave():
    cands = RANKER.rank(PUNJABI_WAVE, DJState())
    assert len(cands) == settings.candidates_per_wave


def test_empty_wave_does_not_raise():
    cands = RANKER.rank(Wave(), DJState())
    assert len(cands) == settings.candidates_per_wave
    for cand in cands:
        assert len(cand.reasons) >= 2


def test_ranker_survives_a_hostile_catalog():
    """Must degrade to a best-effort list, never raise, never return empty."""

    class ExplodingCatalog(Catalog):
        def __init__(self):
            Catalog.__init__(self)
            self._calls = 0

        def all(self):
            self._calls += 1
            if self._calls == 1:
                raise RuntimeError("catalog unavailable")
            return Catalog.all(self)

    cands = Ranker(ExplodingCatalog()).rank(PUNJABI_WAVE, DJState(), k=3)
    assert len(cands) == 3
    for cand in cands:
        assert len(cand.reasons) >= 2


def test_ranker_handles_missing_dj_state_and_odd_k():
    assert RANKER.rank(PUNJABI_WAVE, None, k=None)
    assert len(RANKER.rank(PUNJABI_WAVE, DJState(), k=0)) == 1
    assert len(RANKER.rank(PUNJABI_WAVE, DJState(), k=99999)) == len(CATALOG.all())
