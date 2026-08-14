"""Dynamic track discovery and automatic catalog ingest.

When a guest requests a specific song that does not exist in the seeded catalog
(e.g., "Raga of Revenge by Anirudh" or "Bloody Sweet from Leo"), this module
resolves the track metadata via LLM or heuristics and dynamically registers it
into the Catalog so that:
  1. The song is immediately scored and ranked for the wave.
  2. The guest can select and tip on that exact song.
  3. The DJ sees it on the booth dashboard with realistic BPM/energy.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.request
from typing import Optional

from ..config import settings
from ..contracts import Intent, Track
from ..catalog import Catalog

log = logging.getLogger("cue.discovery")

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(text: str) -> str:
    cleaned = _SLUG_RE.sub("", (text or "").lower())
    return cleaned[:24] or "track"


async def discover_and_add_track(
    text: str, intent: Intent, catalog: Catalog
) -> Optional[Track]:
    """Check if ``text`` names a specific song missing from ``catalog``.

    If missing, resolves full track metadata and registers it into the catalog.
    """
    cleaned = (text or "").strip()
    if len(cleaned) < 3:
        return None

    # Check if there is already a confident match in the catalog
    matches = catalog.search(cleaned, limit=1)
    if matches:
        top = matches[0]
        # If the query strongly matches existing track title
        if top.title.lower() in cleaned.lower() or cleaned.lower() in top.title.lower():
            return top

    # Query LLM to check if this is a specific song request
    track_info = await _resolve_song_metadata(cleaned, intent)
    if not track_info or not track_info.get("is_specific_song"):
        return None

    title = str(track_info.get("title", "")).strip()
    artist = str(track_info.get("artist", "")).strip() or (intent.artists[0] if intent.artists else "Unknown Artist")
    if not title or len(title) < 2:
        return None

    # Double-check search with the resolved title
    existing_hits = catalog.search(title, limit=1)
    if existing_hits and (
        existing_hits[0].title.lower() == title.lower()
        or (title.lower() in existing_hits[0].title.lower() and len(title) > 4)
    ):
        return existing_hits[0]

    lang = str(track_info.get("language", "")).lower() or (intent.languages[0] if intent.languages else "hindi")
    genre = str(track_info.get("genre", "")).lower() or (intent.genres[0] if intent.genres else "pop")
    bpm = int(track_info.get("bpm", 120))
    energy = float(track_info.get("energy", intent.energy_target or 0.85))
    danceability = float(track_info.get("danceability", intent.danceability or 0.85))
    era = str(track_info.get("era", "2020s"))

    track_id = f"trk_{_slugify(title)}_{_slugify(artist)[:8]}"
    
    tags = [
        _slugify(title),
        _slugify(artist),
        lang,
        genre,
        "web-discovered",
    ]
    if artist:
        tags.extend([_slugify(a) for a in artist.split()])

    new_track = Track(
        id=track_id,
        title=title,
        artist=artist,
        language=lang,
        genres=[genre, "pop"],
        moods=intent.moods or ["hype", "celebratory"],
        era=era,
        bpm=max(60, min(180, bpm)),
        energy=max(0.1, min(1.0, energy)),
        danceability=max(0.1, min(1.0, danceability)),
        popularity=0.85,
        duration_sec=210,
        audio_file=None,
        tags=tags,
    )

    registered = catalog.add_track(new_track, persist=True)
    log.info("Discovered new song from prompt '%s' -> %s by %s (%d BPM)", text, title, artist, bpm)
    return registered


async def _resolve_song_metadata(text: str, intent: Intent) -> Optional[dict]:
    """Call LLM to extract specific song metadata from the guest text."""
    if not settings.has_llm:
        return _heuristic_extract(text, intent)

    prompt = (
        "The user requested a song at a DJ party: '%s'.\n"
        "Your task is to identify if the user is asking for a specific song or track name.\n"
        "- If it is purely a generic vibe (e.g. 'play some slow songs' or 'punjabi party music' or 'romantic vibes'), return {\"is_specific_song\": false}.\n"
        "- If the request mentions or suggests a specific song title or track (even if new, unreleased, movie track, background score, remix, or indie e.g. 'Raga of Revenge', 'Bloody Sweet', 'Naa Ready', 'Chaleya', 'Coolie Disco'), extract and format the title and artist cleanly, and provide estimated DJ metadata.\n\n"
        "Return STRICT JSON only:\n"
        "{\n"
        '  "is_specific_song": true,\n'
        '  "title": "Clean Song Title (e.g. Raga of Revenge)",\n'
        '  "artist": "Artist Name (e.g. Anirudh Ravichander)",\n'
        '  "language": "tamil" | "hindi" | "punjabi" | "english" | "telugu" | "spanish" | "arabic",\n'
        '  "genre": "pop" | "bollywood" | "bhangra" | "hiphop" | "edm" | "house" | "rnb",\n'
        '  "era": "2020s" | "2010s" | "2000s" | "1990s",\n'
        '  "bpm": integer tempo 70-160 (e.g. 125),\n'
        '  "energy": float 0.1 to 1.0 (e.g. 0.88),\n'
        '  "danceability": float 0.1 to 1.0 (e.g. 0.85)\n'
        "}"
    ) % text.replace("'", "\\'")

    try:
        if settings.llm_provider == "anthropic":
            return await _call_anthropic_discovery(prompt)
        elif settings.llm_provider == "openai":
            return await _call_openai_discovery(prompt)
    except Exception as exc:
        log.warning("LLM discovery failed: %s", exc)

    return _heuristic_extract(text, intent)


async def _call_anthropic_discovery(prompt: str) -> Optional[dict]:
    import httpx
    api_key = settings.anthropic_api_key
    if not api_key:
        return None

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": "claude-haiku-4-5",
        "max_tokens": 300,
        "messages": [{"role": "user", "content": prompt}],
    }

    async with httpx.AsyncClient(timeout=4.0) as client:
        res = await client.post("https://api.anthropic.com/v1/messages", json=payload, headers=headers)
        if res.status_code == 200:
            content = res.json()["content"][0]["text"]
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                return json.loads(match.group(0))
    return None


async def _call_openai_discovery(prompt: str) -> Optional[dict]:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=4.0)
    res = await client.chat.completions.create(
        model=settings.llm_model or "gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        max_tokens=300,
    )
    text = res.choices[0].message.content or ""
    return json.loads(text) if text else None


def _heuristic_extract(text: str, intent: Intent) -> Optional[dict]:
    """Fallback heuristic when LLM is unavailable or offline."""
    raw = (text or "").lower()
    for drop in ["play", "song", "songs", "pls", "please", "can you", "track", "music"]:
        raw = re.sub(r"\b" + drop + r"\b", "", raw).strip()

    if len(raw) < 3:
        return None

    artist = intent.artists[0] if intent.artists else ""
    return {
        "is_specific_song": True,
        "title": raw.title(),
        "artist": artist or "Guest Request",
        "language": intent.languages[0] if intent.languages else "hindi",
        "genre": intent.genres[0] if intent.genres else "pop",
        "era": "2020s",
        "bpm": 124,
        "energy": intent.energy_target or 0.85,
        "danceability": intent.danceability or 0.85,
    }
