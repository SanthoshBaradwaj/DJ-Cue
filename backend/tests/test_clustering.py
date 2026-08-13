"""Contract tests for M2 -- crowd wave clustering + anti-manipulation.

The headline PRD metric lives here: 50 chaotic requests must compress to at most
5 waves the DJ can act on, and the biggest wave must be one real thing rather
than a smear of everything.

Intents are constructed directly -- M2 must be provable without M1.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import random  # noqa: E402
import time  # noqa: E402

import pytest  # noqa: E402

from app import vectors  # noqa: E402
from app.clustering import WaveEngine  # noqa: E402
from app.clustering.antimanip import compute_weight  # noqa: E402
from app.clustering.engine import _dedupe_labels  # noqa: E402
from app.config import settings  # noqa: E402
from app.contracts import Intent, SongRequest, Wave  # noqa: E402
from app.store import reset_store_for_tests  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures / builders
# ---------------------------------------------------------------------------

# Five musical families a real Friday night actually contains.
FAMILIES = {
    "punjabi_hype": {
        "languages": ["punjabi"],
        "genres": ["bhangra"],
        "moods": ["hype"],
        "eras": ["2020s"],
        "energy": 0.90,
        "dance": 0.90,
        "extra_moods": ["celebratory"],
        "keywords": ["bhangra"],
        "texts": [
            "bhangra pls",
            "diljit banger",
            "punjabi hype tune",
            "PLAY SOME BHANGRA",
            "something to jump to, punjabi",
        ],
    },
    "bolly_romance": {
        "languages": ["hindi"],
        "genres": ["bollywood"],
        "moods": ["romantic"],
        "eras": ["2000s"],
        "energy": 0.34,
        "dance": 0.45,
        "extra_moods": ["sensual"],
        "keywords": ["romantic"],
        "texts": [
            "slow bollywood love song",
            "arijit please",
            "something romantic hindi",
            "2000s bollywood romance",
        ],
    },
    "english_hiphop": {
        "languages": ["english"],
        "genres": ["hiphop"],
        "moods": ["hype"],
        "eras": ["2020s"],
        "energy": 0.86,
        "dance": 0.78,
        "extra_moods": ["aggressive"],
        "keywords": ["rap"],
        "texts": [
            "drake",
            "rap bangers",
            "some hip hop please",
            "trap heat",
        ],
    },
    "english_house": {
        "languages": ["english"],
        "genres": ["house"],
        "moods": ["euphoric"],
        "eras": ["2010s"],
        "energy": 0.74,
        "dance": 0.92,
        "extra_moods": ["chill"],
        "keywords": ["house"],
        "texts": [
            "house music",
            "deep house set",
            "give us four to the floor",
            "euphoric house",
        ],
    },
    "bolly_nostalgia": {
        "languages": ["hindi"],
        "genres": ["bollywood"],
        "moods": ["nostalgic"],
        "eras": ["1990s"],
        "energy": 0.52,
        "dance": 0.60,
        "extra_moods": ["celebratory"],
        "keywords": ["retro"],
        "texts": [
            "90s bollywood",
            "old hindi classics",
            "kuch kuch hota hai",
            "throwback hindi",
        ],
    },
}


def family_intent(name, rng):
    """An Intent from a family, with the jitter real requests carry."""
    spec = FAMILIES[name]
    moods = list(spec["moods"])
    roll = rng.random()
    if roll < 0.3:
        moods.append(spec["extra_moods"][0])  # someone adds a mood
    elif roll > 0.9 and len(moods) > 1:
        moods = moods[:1]  # someone drops one
    return Intent(
        languages=list(spec["languages"]),
        genres=list(spec["genres"]),
        moods=moods,
        eras=list(spec["eras"]),
        energy_target=spec["energy"] + rng.uniform(-0.1, 0.1),
        danceability=spec["dance"] + rng.uniform(-0.1, 0.1),
        familiarity=0.5 + rng.uniform(-0.15, 0.15),
        raw_keywords=list(spec["keywords"]),
    )


def family_text(name, rng):
    return rng.choice(FAMILIES[name]["texts"])


def fresh_engine():
    store = reset_store_for_tests()
    return WaveEngine(store), store


PUNJABI = Intent(
    languages=["punjabi"], genres=["bhangra"], moods=["hype"],
    energy_target=0.92, danceability=0.9, eras=["2020s"],
)
BOLLY = Intent(
    languages=["hindi"], genres=["bollywood"], moods=["romantic"],
    energy_target=0.32, danceability=0.42, eras=["2000s"],
)
HOUSE = Intent(
    languages=["english"], genres=["house"], moods=["euphoric"],
    energy_target=0.75, danceability=0.9, eras=["2010s"],
)


# ---------------------------------------------------------------------------
# The headline metric
# ---------------------------------------------------------------------------


def test_fifty_requests_compress_to_at_most_five_waves():
    """50 raw requests -> <= 5 waves, and the biggest wave is one real thing."""
    engine, _ = fresh_engine()
    rng = random.Random(20240513)

    # Deliberately uneven, like a real floor: one family owns the room.
    plan = (
        ["punjabi_hype"] * 18
        + ["bolly_romance"] * 8
        + ["english_hiphop"] * 8
        + ["english_house"] * 8
        + ["bolly_nostalgia"] * 8
    )
    assert len(plan) == 50
    rng.shuffle(plan)

    family_of = {}
    for i, name in enumerate(plan):
        request, _, _ = engine.ingest(
            "gig", "device_%02d" % i, family_text(name, rng), family_intent(name, rng)
        )
        family_of[request.id] = name

    waves = engine.waves("gig")
    assert 1 < len(waves) <= settings.max_waves_shown, [w.label for w in waves]
    assert len(waves) <= 5

    # Every request is accounted for in exactly one wave.
    assigned = [rid for w in waves for rid in w.request_ids]
    assert sorted(assigned) == sorted(family_of)

    dominant = engine.dominant("gig")
    assert dominant is not None
    assert dominant is not None and dominant.id == waves[0].id
    families = {family_of[rid] for rid in dominant.request_ids}
    assert families == {"punjabi_hype"}, families
    assert dominant.raw_count == 18
    assert dominant.unique_sessions == 18
    assert dominant.summary and str(dominant.unique_sessions) in dominant.summary
    assert dominant.sample_texts and len(dominant.sample_texts) <= 3
    assert 0.0 < dominant.share <= 1.0
    assert abs(sum(w.share for w in waves) - 1.0) < 1e-6

    compression = 1.0 - (len(waves) / 50.0)
    assert compression >= 0.85, compression


def test_semantically_different_requests_do_not_merge():
    """Bhangra and slow Bollywood are not the same ask, ever."""
    engine, _ = fresh_engine()
    for i in range(8):
        engine.ingest("gig", "p%d" % i, "bhangra", PUNJABI)
    for i in range(8):
        engine.ingest("gig", "b%d" % i, "slow romantic hindi", BOLLY)

    waves = engine.waves("gig")
    assert len(waves) >= 2, [w.label for w in waves]

    labels = " | ".join(w.label for w in waves)
    assert "Bhangra" in labels
    assert "Bollywood" in labels

    # No wave mixes the two populations.
    for wave in waves:
        prefixes = {rid[:1] for rid in wave.request_ids}
        sessions = {
            r.session_id[0]
            for r in engine.store.requests("gig")
            if r.id in wave.request_ids
        }
        assert len(sessions) == 1, (wave.label, sessions, prefixes)


# ---------------------------------------------------------------------------
# Anti-manipulation
# ---------------------------------------------------------------------------


def test_one_spammer_cannot_outweigh_ten_devices():
    engine, store = fresh_engine()

    # One phone, ten submissions of the same thing.
    for _ in range(10):
        engine.ingest("spam", "one_loud_phone", "bhangra pls", PUNJABI)
    spam_weight = sum(r.weight for r in store.requests("spam"))

    # Ten phones, one submission each.
    for i in range(10):
        engine.ingest("real", "phone_%d" % i, "bhangra pls", PUNJABI)
    real_requests = store.requests("real")
    real_weight = sum(r.weight for r in real_requests)

    # Different devices are never discounted against each other.
    assert all(r.weight == 1.0 for r in real_requests)
    assert all(r.discount_reason is None for r in real_requests)
    assert real_weight == 10.0

    assert real_weight >= 3.0 * spam_weight, (real_weight, spam_weight)

    # Heavily discounted, but never silenced: the guest still lands in a wave.
    assert spam_weight > 1.0
    spam_wave = engine.dominant("spam")
    assert spam_wave is not None
    assert spam_wave.raw_count == 10
    assert spam_wave.unique_sessions == 1
    assert all(r.wave_id == spam_wave.id for r in store.requests("spam"))


def test_rapid_fire_is_discounted_with_reason():
    engine, _ = fresh_engine()

    first, _, _ = engine.ingest("gig", "s1", "bhangra pls", PUNJABI)
    assert first.weight == 1.0
    assert first.discount_reason is None

    # Same device, a different ask, moments later.
    second, _, _ = engine.ingest("gig", "s1", "give us deep house", HOUSE)
    assert second.discount_reason == "rapid-fire"
    assert 0.0 < second.weight < first.weight
    assert second.weight >= settings.session_min_weight


def test_duplicate_from_same_session_is_discounted():
    now = time.time()
    prior = [
        SongRequest(
            event_id="gig", session_id="s1", text="bhangra pls",
            intent=PUNJABI, created_at=now - 600,
        )
    ]
    # Long after the rapid-fire window: the discount is purely for repetition.
    weight, reason = compute_weight(prior, "punjabi banger", PUNJABI, now)
    assert reason == "duplicate"
    assert weight < settings.repeat_decay
    assert weight >= settings.session_min_weight

    # A genuinely different second ask is decayed, but not called a duplicate.
    weight2, reason2 = compute_weight(prior, "some deep house", HOUSE, now)
    assert reason2 == "repeat"
    assert weight2 > weight

    # And a first-ever request is untouched.
    assert compute_weight([], "bhangra pls", PUNJABI, now) == (1.0, None)


def test_weight_never_falls_below_the_floor():
    now = time.time()
    prior = [
        SongRequest(
            event_id="gig", session_id="s1", text="bhangra pls",
            intent=PUNJABI, created_at=now - (i * 0.5),
        )
        for i in range(15)
    ]
    weight, reason = compute_weight(prior, "bhangra pls", PUNJABI, now)
    assert weight == pytest.approx(settings.session_min_weight)
    assert reason == "duplicate"


def test_unique_sessions_counts_devices_not_submissions():
    engine, _ = fresh_engine()
    engine.ingest("gig", "a", "bhangra", PUNJABI)
    engine.ingest("gig", "b", "bhangra pls", PUNJABI)
    engine.ingest("gig", "c", "punjabi banger", PUNJABI)
    engine.ingest("gig", "a", "more bhangra", PUNJABI)  # same device again

    wave = engine.dominant("gig")
    assert wave is not None
    assert wave.raw_count == 4
    assert wave.unique_sessions == 3
    assert wave.weight < 4.0  # the repeat is discounted


# ---------------------------------------------------------------------------
# Wave identity / presentation
# ---------------------------------------------------------------------------


def test_wave_ids_are_stable_across_recomputes():
    engine, _ = fresh_engine()
    rng = random.Random(99)

    plan = ["punjabi_hype"] * 12 + ["bolly_romance"] * 8
    rng.shuffle(plan)
    for i, name in enumerate(plan):
        engine.ingest("gig", "d%02d" % i, family_text(name, rng), family_intent(name, rng))

    before = engine.dominant("gig")
    assert before is not None
    before_id, before_created = before.id, before.created_at

    # A bare recompute changes nothing at all.
    engine.recompute("gig")
    assert engine.dominant("gig").id == before_id

    # Five more of the same families arrive.
    for i in range(5):
        name = "punjabi_hype" if i % 2 == 0 else "bolly_romance"
        engine.ingest(
            "gig", "late%d" % i, family_text(name, rng), family_intent(name, rng)
        )

    after = engine.dominant("gig")
    assert after is not None
    assert after.id == before_id
    assert after.created_at == before_created
    assert after.raw_count > before.raw_count
    assert after.updated_at >= before.updated_at


def test_labels_are_unique_across_waves():
    engine, _ = fresh_engine()
    rng = random.Random(4242)
    plan = [name for name in FAMILIES for _ in range(6)]
    rng.shuffle(plan)
    for i, name in enumerate(plan):
        engine.ingest("gig", "d%02d" % i, family_text(name, rng), family_intent(name, rng))

    labels = [w.label for w in engine.waves("gig")]
    assert all(labels)
    assert len(set(labels)) == len(labels), labels


def test_colliding_labels_are_disambiguated():
    """Two waves that would print the same name get pulled apart."""
    a = Wave(
        label="High-Energy Bhangra",
        centroid=Intent(
            languages=["punjabi"], genres=["bhangra"], moods=["hype"],
            eras=["2020s"], energy_target=0.9,
        ),
    )
    b = Wave(
        label="High-Energy Bhangra",
        centroid=Intent(
            languages=["punjabi"], genres=["bhangra", "desi_hiphop"],
            moods=["celebratory"], eras=["1990s"], energy_target=0.82,
        ),
    )
    _dedupe_labels([a, b])
    assert a.label == "High-Energy Bhangra"
    assert b.label != a.label
    assert b.label.startswith("High-Energy Bhangra")


# ---------------------------------------------------------------------------
# Robustness
# ---------------------------------------------------------------------------


def test_engine_never_raises_on_degenerate_input():
    engine, _ = fresh_engine()

    # Empty event.
    assert engine.recompute("nobody_here") == []
    assert engine.waves("nobody_here") == []
    assert engine.dominant("nobody_here") is None

    # A single request.
    request, wave, joined = engine.ingest("solo", "s1", "bhangra", PUNJABI)
    assert joined is False
    assert wave.raw_count == 1
    assert wave.request_ids == [request.id]
    assert engine.dominant("solo").id == wave.id

    # Three byte-identical requests.
    engine2, _ = fresh_engine()
    ids = []
    for i in range(3):
        r, w, joined = engine2.ingest("dup", "s%d" % i, "same text", PUNJABI)
        ids.append(r.id)
        if i > 0:
            assert joined is True
    waves = engine2.waves("dup")
    assert len(waves) == 1
    assert sorted(waves[0].request_ids) == sorted(ids)
    assert waves[0].unique_sessions == 3

    # A degenerate all-zero intent vector must not take the engine down.
    engine3, _ = fresh_engine()
    blank = Intent(energy_target=0.0, danceability=0.0, familiarity=0.0)
    engine3.ingest("weird", "s1", "", blank)
    engine3.ingest("weird", "s2", "idk something good", blank)
    engine3.ingest("weird", "s3", "bhangra", PUNJABI)
    assert len(engine3.waves("weird")) >= 1


def test_ingest_reports_joining_an_existing_wave():
    engine, _ = fresh_engine()
    _, first_wave, joined_first = engine.ingest("gig", "s1", "bhangra", PUNJABI)
    assert joined_first is False

    _, second_wave, joined_second = engine.ingest("gig", "s2", "bhangra pls", PUNJABI)
    assert joined_second is True
    assert second_wave.id == first_wave.id

    # A genuinely new kind of ask starts its own wave.
    _, third_wave, joined_third = engine.ingest("gig", "s3", "romantic hindi", BOLLY)
    assert third_wave.id != first_wave.id
    assert joined_third is False


def test_greedy_fallback_matches_the_clustering_contract():
    """If sklearn is unavailable the engine still separates the families."""
    engine, _ = fresh_engine()
    rng = random.Random(7)
    for i in range(10):
        name = "punjabi_hype" if i % 2 == 0 else "bolly_romance"
        engine.ingest("gig", "d%d" % i, family_text(name, rng), family_intent(name, rng))

    matrix = None
    import numpy as np

    requests = engine.store.requests("gig")
    matrix = np.vstack([engine._vector_for(r) for r in requests])
    labels = engine._greedy_cluster(matrix)
    assert 2 <= len(set(labels)) <= 4, labels

    # Members sharing a greedy label are genuinely similar.
    for label in set(labels):
        members = [requests[i] for i, l in enumerate(labels) if l == label]
        for other in members[1:]:
            assert vectors.similarity(members[0].intent, other.intent) > 0.5


def test_momentum_and_keywords_are_populated():
    engine, _ = fresh_engine()
    rng = random.Random(3)
    for i in range(6):
        engine.ingest(
            "gig", "d%d" % i, family_text("punjabi_hype", rng),
            family_intent("punjabi_hype", rng),
        )
    wave = engine.dominant("gig")
    assert wave is not None
    assert wave.momentum == pytest.approx(1.0)  # everything just arrived
    assert "bhangra" in wave.top_keywords
    assert wave.centroid.languages == ["punjabi"]


# ---------------------------------------------------------------------------
# Performance
# ---------------------------------------------------------------------------


def test_two_hundred_ingests_stay_fast():
    engine, _ = fresh_engine()  # engine construction warms the sklearn import
    rng = random.Random(11)
    names = list(FAMILIES)

    started = time.time()
    for i in range(200):
        name = names[i % len(names)]
        engine.ingest(
            "load", "d%03d" % i, family_text(name, rng), family_intent(name, rng)
        )
    elapsed = time.time() - started

    assert elapsed < 30.0, elapsed
    assert len(engine.store.requests("load")) == 200
    assert len(engine.waves("load")) <= settings.max_waves_shown
