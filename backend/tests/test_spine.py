"""Contract tests for the spine (M0).

If these fail, every downstream module is built on sand. Run first.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import taxonomy, vectors  # noqa: E402
from app.contracts import Intent, SongRequest, Track  # noqa: E402
from app.store import reset_store_for_tests  # noqa: E402


PUNJABI_HYPE = Intent(
    languages=["punjabi"], genres=["bhangra"], moods=["hype"],
    energy_target=0.92, danceability=0.9,
)
PUNJABI_HYPE_2 = Intent(
    languages=["punjabi"], genres=["bhangra"], moods=["hype", "celebratory"],
    energy_target=0.85, danceability=0.88,
)
BOLLY_ROMANCE = Intent(
    languages=["hindi"], genres=["bollywood"], moods=["romantic"],
    energy_target=0.3, danceability=0.4, eras=["2000s"],
)


def test_vector_dim_matches_taxonomy():
    assert vectors.intent_vector(PUNJABI_HYPE).shape == (taxonomy.VECTOR_DIM,)


def test_similar_intents_cluster_apart_from_dissimilar():
    near = vectors.similarity(PUNJABI_HYPE, PUNJABI_HYPE_2)
    far = vectors.similarity(PUNJABI_HYPE, BOLLY_ROMANCE)
    assert near > 0.85, near
    assert far < 0.35, far
    assert near - far > 0.5


def test_taxonomy_coercion_rejects_hallucinated_tokens():
    dirty = Intent(
        languages=["punjabi", "klingon"],
        genres=["Bhangra", "trap-metal"],
        moods=["hype"],
        energy_target=5.0,
        familiarity=-2.0,
    )
    clean = dirty.sanitized()
    assert clean.languages == ["punjabi"]
    assert clean.genres == ["bhangra"]
    assert clean.energy_target == 1.0
    assert clean.familiarity == 0.0


def test_centroid_summarizes_a_cluster():
    c = vectors.centroid([PUNJABI_HYPE, PUNJABI_HYPE_2, PUNJABI_HYPE])
    assert "punjabi" in c.languages
    assert "bhangra" in c.genres
    assert 0.8 < c.energy_target < 1.0


def test_labels_are_dj_readable():
    assert vectors.label_for(PUNJABI_HYPE) == "High-Energy Bhangra"
    assert "Bollywood" in vectors.label_for(BOLLY_ROMANCE)


def test_track_projects_into_same_space_as_intent():
    track = Track(
        id="t1", title="Test", artist="A", language="punjabi",
        genres=["bhangra"], moods=["hype"], era="2020s",
        bpm=140, energy=0.9, danceability=0.9,
    )
    assert vectors.similarity(PUNJABI_HYPE, vectors.track_intent(track)) > 0.8
    assert vectors.similarity(BOLLY_ROMANCE, vectors.track_intent(track)) < 0.35


def test_store_roundtrip_and_stats():
    store = reset_store_for_tests()
    for i in range(3):
        store.add_request(
            SongRequest(event_id="e", session_id="s%d" % i,
                        text="bhangra", intent=PUNJABI_HYPE)
        )
    assert len(store.requests("e")) == 3
    stats = store.stats("e")
    assert stats.total_requests == 3
    assert stats.unique_sessions == 3
    store.reset("e")
    assert store.requests("e") == []
