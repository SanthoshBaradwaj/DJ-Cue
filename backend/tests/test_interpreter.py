"""Tests for M1 -- the intent interpreter.

The bar these encode: the deterministic path alone must be good enough to run a
live demo with no API key, and it must never emit a token outside the frozen
taxonomy or blow up on garbage.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncio  # noqa: E402
import time  # noqa: E402

from app import taxonomy  # noqa: E402
from app.contracts import Intent  # noqa: E402
from app.interpreter import interpret, interpret_async, phrase_ack  # noqa: E402
from app.interpreter import lexicon, llm, rules  # noqa: E402


# ---------------------------------------------------------------------------
# Corpus reused by the invariant tests
# ---------------------------------------------------------------------------

VARIED_INPUTS = [
    "Punjabi wedding chaos",
    "2010s Bollywood romance",
    "That Hrithik song where everyone dances",
    "Something romantic but people can still dance to it",
    "play some diljit",
    "bad bunny pls",
    "arijit singh sad songs",
    "something to turn up to \U0001F525",
    "anything but techno",
    "no rap please",
    "asdkjhasd",
    "",
    "   ",
    "chill r&b slow jams",
    "deep house underground vibes \U0001F60E",
    "nachne wala gaana chahiye",
    "balle balle dhol bhangra paake",
    "90s throwback bollywood classics everyone knows",
    "michael jackson or abba, retro disco",
    "sad breakup songs \U0001F494 dard bhare gaane",
    "burna boy amapiano \U0001F57A",
    "gym workout aggressive hard hitting rap",
    "slow it down, ballad, cool down please",
    "sufi qawwali nusrat fateh ali khan",
    "\U0001F525\U0001F525\U0001F525",
    "peak time techno warehouse",
    "shah rukh khan romantic classic",
    "karol g reggaeton perreo \U0001F483",
]


# ---------------------------------------------------------------------------
# The four PRD user-flow examples
# ---------------------------------------------------------------------------


def test_prd_punjabi_wedding_chaos():
    intent = interpret("Punjabi wedding chaos")
    assert "punjabi" in intent.languages
    assert {"celebratory", "hype"} & set(intent.moods)
    assert intent.energy_target >= 0.7, intent.energy_target
    assert intent.summary


def test_prd_2010s_bollywood_romance():
    intent = interpret("2010s Bollywood romance")
    assert "hindi" in intent.languages
    assert "bollywood" in intent.genres
    assert "romantic" in intent.moods
    assert "2010s" in intent.eras


def test_prd_hrithik_song_everyone_dances():
    intent = interpret("That Hrithik song where everyone dances")
    assert "hindi" in intent.languages
    assert "bollywood" in intent.genres
    assert intent.danceability >= 0.65, intent.danceability
    assert intent.familiarity >= 0.65, intent.familiarity
    assert "Hrithik Roshan" in intent.artists


def test_prd_romantic_but_danceable():
    intent = interpret("Something romantic but people can still dance to it")
    assert "romantic" in intent.moods
    assert intent.danceability >= 0.65, intent.danceability
    assert 0.45 <= intent.energy_target <= 0.8, intent.energy_target


# ---------------------------------------------------------------------------
# Artist recognition
# ---------------------------------------------------------------------------


def test_artist_diljit_is_punjabi():
    intent = interpret("play some diljit")
    assert "punjabi" in intent.languages
    assert intent.energy_target >= 0.6
    assert "Diljit Dosanjh" in intent.artists


def test_artist_bad_bunny_is_spanish_reggaeton():
    intent = interpret("bad bunny pls")
    assert "spanish" in intent.languages
    assert "reggaeton" in intent.genres


def test_artist_arijit_singh_sad():
    intent = interpret("arijit singh sad songs")
    assert "hindi" in intent.languages
    assert "sad" in intent.moods
    assert intent.energy_target <= 0.45


def test_artist_house_and_afrobeats_priors():
    house = interpret("fred again peggy gou set")
    assert "house" in house.genres

    afro = interpret("burna boy and wizkid")
    assert "afrobeats" in afro.languages
    assert "afrobeat" in afro.genres


def test_two_phrasings_of_the_same_ask_converge():
    """The whole product rests on this: different words, same Intent region."""
    a = interpret("diljit")
    b = interpret("punjabi bhangra banger")
    assert "punjabi" in a.languages and "punjabi" in b.languages
    assert a.energy_target > 0.6 and b.energy_target > 0.6


# ---------------------------------------------------------------------------
# Slang, emoji, eras, energy
# ---------------------------------------------------------------------------


def test_slang_turn_up_with_emoji():
    intent = interpret("something to turn up to \U0001F525")
    assert "hype" in intent.moods
    assert intent.energy_target >= 0.75, intent.energy_target


def test_emoji_only_still_reads_as_hype():
    intent = interpret("\U0001F525\U0001F483\U0001F389")
    assert set(intent.moods) & {"hype", "celebratory"}
    assert intent.energy_target >= 0.7


def test_romantic_emoji():
    intent = interpret("❤️\U0001F60D slow one for us")
    assert "romantic" in intent.moods


def test_hinglish_slang():
    intent = interpret("nachne wala gaana chahiye, thoda dhinchak")
    assert set(intent.languages) & {"hindi", "punjabi"}
    assert intent.danceability >= 0.7


def test_era_slang_maps_to_taxonomy():
    assert "1990s" in interpret("90s hits").eras
    assert "2000s" in interpret("y2k vibes").eras
    assert "2020s" in interpret("play something new and current").eras
    old = interpret("some old school oldies")
    assert "1990s" in old.eras
    assert "nostalgic" in old.moods


def test_energy_modifiers():
    hot = interpret("high energy peak time please")
    assert hot.energy_target >= 0.85, hot.energy_target
    assert hot.tempo_hint == "fast"

    cold = interpret("slow it down, we need a breather")
    assert cold.energy_target <= 0.35, cold.energy_target
    assert cold.tempo_hint == "slow"

    mid = interpret("something groovy and mid tempo")
    assert 0.35 < mid.energy_target < 0.7, mid.energy_target


def test_familiarity_cues():
    known = interpret("a classic everyone knows")
    assert known.familiarity >= 0.75, known.familiarity

    deep = interpret("deep cuts and obscure b sides")
    assert deep.familiarity <= 0.35, deep.familiarity


def test_genre_slang_lands_on_taxonomy_tokens():
    assert "rnb" in interpret("some r&b").genres
    assert "house" in interpret("deep house set").genres
    assert "techno" in interpret("hard techno").genres
    assert "amapiano" in interpret("amapiano log drum").genres
    assert "sufi" in interpret("qawwali night").genres
    assert "disco" in interpret("disco night").genres
    assert "desi_hiphop" in interpret("punjabi rap").genres


# ---------------------------------------------------------------------------
# Negation
# ---------------------------------------------------------------------------


def test_negation_excludes_genre():
    intent = interpret("anything but techno")
    assert "techno" not in intent.genres


def test_negation_no_rap_and_not_bollywood():
    assert "hiphop" not in interpret("no rap, just house").genres
    assert "house" in interpret("no rap, just house").genres

    intent = interpret("not bollywood please, punjabi instead")
    assert "bollywood" not in intent.genres
    assert "punjabi" in intent.languages


def test_negation_scope_does_not_leak_past_a_clause_break():
    intent = interpret("not sure, maybe bhangra")
    assert "bhangra" in intent.genres


# ---------------------------------------------------------------------------
# Robustness
# ---------------------------------------------------------------------------


def test_garbage_input_returns_valid_low_confidence_intent():
    for text in ("asdkjhasd", "", "   ", "!!!???", "12345"):
        intent = interpret(text)
        assert isinstance(intent, Intent)
        assert intent.confidence <= 0.35, (text, intent.confidence)
        assert intent.summary
        assert 0.0 <= intent.energy_target <= 1.0


def test_interpret_never_raises_on_hostile_input():
    hostile = [
        None,
        "\x00\x01\x02",
        "a" * 5000,
        "\U0001F525" * 200,
        "; DROP TABLE requests; --",
        "{\"json\": true}",
        "\n\t\r",
        "ＰＵＮＪＡＢＩ",
    ]
    for text in hostile:
        intent = interpret(text)  # type: ignore[arg-type]
        assert isinstance(intent, Intent)
        assert intent == intent.sanitized()


def test_every_intent_survives_sanitization_unchanged():
    """We must never emit a token the vector space cannot represent."""
    for text in VARIED_INPUTS:
        intent = interpret(text)
        assert intent == intent.sanitized(), text
        for token in intent.languages:
            assert token in taxonomy.LANGUAGES, (text, token)
        for token in intent.genres:
            assert token in taxonomy.GENRES, (text, token)
        for token in intent.moods:
            assert token in taxonomy.MOODS, (text, token)
        for token in intent.eras:
            assert token in taxonomy.ERAS, (text, token)
        assert intent.tempo_hint in taxonomy.TEMPO_HINTS
        assert intent.source == "rules"
        assert len(intent.raw_keywords) <= 12


def test_lexicon_contains_no_illegal_tokens():
    assert lexicon.audit() == []
    assert lexicon.size() > 400


def test_confidence_tracks_signal_density():
    rich = interpret("2000s bollywood romantic arijit singh slow songs")
    poor = interpret("qwertyuiop")
    assert rich.confidence > poor.confidence + 0.3
    assert poor.confidence <= 0.35


def test_interpret_is_fast():
    corpus = VARIED_INPUTS * 2
    start = time.perf_counter()
    for i in range(200):
        interpret(corpus[i % len(corpus)])
    elapsed = time.perf_counter() - start
    assert elapsed < 0.5, "200 interpretations took %.3fs" % elapsed


# ---------------------------------------------------------------------------
# Async / LLM layer
# ---------------------------------------------------------------------------


def test_interpret_async_matches_rules_without_llm(monkeypatch):
    monkeypatch.setattr(llm.settings, "llm_enabled", False, raising=False)
    text = "Punjabi wedding chaos"
    assert asyncio.get_event_loop_policy() is not None
    result = asyncio.new_event_loop().run_until_complete(interpret_async(text))
    assert result == interpret(text)


def test_interpret_async_survives_a_broken_llm(monkeypatch):
    async def boom(_text):
        raise RuntimeError("provider exploded")

    monkeypatch.setattr("app.interpreter._llm_interpret", boom)
    result = asyncio.new_event_loop().run_until_complete(
        interpret_async("play some diljit")
    )
    assert "punjabi" in result.languages
    assert result.source == "rules"


def test_llm_interpret_returns_none_without_a_key(monkeypatch):
    monkeypatch.setattr(llm.settings, "llm_enabled", False, raising=False)
    out = asyncio.new_event_loop().run_until_complete(llm.llm_interpret("hi"))
    assert out is None


def test_llm_parse_rejects_malformed_and_hallucinated_output():
    assert llm.parse_intent(None) is None
    assert llm.parse_intent("") is None
    assert llm.parse_intent("not json at all") is None
    assert llm.parse_intent("{broken json") is None

    parsed = llm.parse_intent(
        '```json\n{"languages": ["punjabi", "klingon"], '
        '"genres": ["bhangra", "trap-metal"], "moods": ["hype"], '
        '"eras": ["1990s", "1600s"], "artists": ["Diljit"], '
        '"energy_target": 4.2, "danceability": 0.9, "familiarity": 0.8, '
        '"tempo_hint": "warp", "confidence": 0.9, "summary": "hype punjabi"}\n```'
    )
    assert parsed is not None
    assert parsed.languages == ["punjabi"]
    assert parsed.genres == ["bhangra"]
    assert parsed.eras == ["1990s"]
    assert parsed.energy_target == 1.0
    assert parsed.tempo_hint is None
    assert parsed.source == "llm"


def test_llm_merge_produces_hybrid():
    base = interpret("play some diljit")
    enhanced = Intent(
        languages=["punjabi"], genres=["desi_hiphop"], moods=["celebratory"],
        energy_target=0.91, danceability=0.93, familiarity=0.7,
        tempo_hint="fast", confidence=0.88, source="llm",
        summary="peak-time Punjabi",
    )
    merged = llm.merge(base, enhanced)
    assert merged.source == "hybrid"
    assert "punjabi" in merged.languages
    assert "desi_hiphop" in merged.genres
    assert "bhangra" in merged.genres  # base's contribution survives
    assert merged.energy_target == 0.91
    assert merged.summary == "peak-time Punjabi"
    assert merged.confidence == max(base.confidence, 0.88)
    assert merged == merged.sanitized()


def test_llm_merge_with_none_is_identity():
    base = interpret("bad bunny pls")
    assert llm.merge(base, None) == base


def test_llm_prompt_injects_the_taxonomy():
    prompt = llm.build_prompt("punjabi banger")
    for token in ("punjabi", "desi_hiphop", "celebratory", "2020s", "mid"):
        assert token in prompt


# ---------------------------------------------------------------------------
# phrase_ack
# ---------------------------------------------------------------------------


def test_phrase_ack_includes_wave_size_when_positive():
    intent = interpret("Punjabi wedding chaos")
    message = phrase_ack(intent, "High-Energy Punjabi", 14)
    assert "14" in message
    assert intent.summary in message

    single = phrase_ack(intent, "High-Energy Punjabi", 1)
    assert "1" in single


def test_phrase_ack_handles_a_brand_new_wave():
    intent = interpret("Punjabi wedding chaos")
    message = phrase_ack(intent, "High-Energy Punjabi", 0)
    assert "new wave" in message.lower()
    assert "0" not in message


def test_phrase_ack_is_deterministic_but_varied():
    intent = interpret("Punjabi wedding chaos")
    assert phrase_ack(intent, "x", 5) == phrase_ack(intent, "x", 5)

    messages = {
        phrase_ack(interpret(text), "", 7) for text in VARIED_INPUTS if text.strip()
    }
    assert len(messages) > 3


def test_phrase_ack_survives_an_empty_intent():
    message = phrase_ack(Intent(), "", 0)
    assert isinstance(message, str) and message
    assert phrase_ack(Intent(), "Chill R&B", 4).count("4") == 1


# ---------------------------------------------------------------------------
# Internals worth pinning
# ---------------------------------------------------------------------------


def test_normalisation_handles_emoji_punctuation_and_case():
    assert lexicon.normalize("R&B, please!") == ["rnb", ",", "please", ","]
    assert "\U0001F525" in lexicon.normalize("turn up\U0001F525")
    assert lexicon.normalize("don't") == ["dont"]
    assert lexicon.normalize("") == []


def test_longest_match_wins():
    intent = interpret("deep house")
    assert "house" in intent.genres
    assert "deep house" in intent.raw_keywords
    assert intent.familiarity > 0.3  # not read as "deep cut"


def test_fallback_intent_is_valid():
    intent = rules._fallback("weird ☃ request")
    assert isinstance(intent, Intent)
    assert intent == intent.sanitized()
    assert intent.summary
