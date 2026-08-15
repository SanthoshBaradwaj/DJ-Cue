"""Live song search: Apple's iTunes Search API and Deezer, combined.

Both are free, unauthenticated, no signup -- there is no local song catalog
and no paid search API anywhere in this path. Earlier this queried Deezer
only when iTunes came up thin (fewer than 3 hits), but that undercounts the
common case where iTunes returns a full page of *mediocre* matches -- full
enough to skip Deezer, but not necessarily the best available results. Both
sources are now queried on every search, in parallel, and merged -- so a
better Deezer hit for Haryanvi/Marathi can surface even when iTunes wasn't
literally empty. Every call is short-timeout and fails soft to an empty
list -- a flaky external API must never take the guest flow down with it.
"""

from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional, Set

import httpx

from .contracts import Song
from .genres import genre_label

log = logging.getLogger("cue.catalog_search")

_ITUNES_URL = "https://itunes.apple.com/search"
_DEEZER_URL = "https://api.deezer.com/search"
_DEEZER_TRACK_URL = "https://api.deezer.com/track"
_TIMEOUT_S = 5.0
_BPM_TIMEOUT_S = 3.0


def _search_itunes(term: str, limit: int) -> List[Song]:
    try:
        res = httpx.get(
            _ITUNES_URL,
            params={
                "term": term,
                "media": "music",
                "entity": "song",
                "limit": max(1, min(int(limit), 25)),
                "country": "IN",
            },
            timeout=_TIMEOUT_S,
        )
        res.raise_for_status()
        payload = res.json()
    except Exception as exc:  # network hiccup, timeout, bad JSON
        log.warning("iTunes search failed for %r: %s", term, exc)
        return []

    songs: List[Song] = []
    for row in payload.get("results", []):
        track_id = row.get("trackId")
        title = row.get("trackName")
        if track_id is None or not title:
            continue
        songs.append(
            Song(
                id="itunes:%s" % track_id,
                title=title,
                artist=row.get("artistName") or "",
                genre=row.get("primaryGenreName") or "",
                artwork_url=row.get("artworkUrl100"),
            )
        )
    return songs


def _search_deezer(term: str, limit: int) -> List[Song]:
    try:
        res = httpx.get(
            _DEEZER_URL,
            params={"q": term, "limit": max(1, min(int(limit), 25))},
            timeout=_TIMEOUT_S,
        )
        res.raise_for_status()
        payload = res.json()
    except Exception as exc:
        log.warning("Deezer search failed for %r: %s", term, exc)
        return []

    songs: List[Song] = []
    for row in payload.get("data", []):
        track_id = row.get("id")
        title = row.get("title")
        if track_id is None or not title:
            continue
        album = row.get("album") or {}
        songs.append(
            Song(
                id="deezer:%s" % track_id,
                title=title,
                artist=(row.get("artist") or {}).get("name") or "",
                genre="",
                artwork_url=album.get("cover_medium") or album.get("cover"),
            )
        )
    return songs


def deezer_track_bpm(deezer_track_id: str) -> Optional[int]:
    """Real, measured tempo from Deezer's own catalog -- never estimated.

    Deezer's *search* endpoint doesn't include bpm (confirmed by its own
    docs), only the per-track detail endpoint does, so this is a second,
    deliberate call made once at submit time -- not per search result. Short
    timeout and fail-soft: a slow or missing bpm must never block or fail a
    guest's request, it just means no label shows on the DJ dashboard.
    """
    try:
        res = httpx.get(f"{_DEEZER_TRACK_URL}/{deezer_track_id}", timeout=_BPM_TIMEOUT_S)
        res.raise_for_status()
        bpm = res.json().get("bpm")
    except Exception as exc:
        log.info("Deezer bpm lookup failed for track %s: %s", deezer_track_id, exc)
        return None
    # Deezer returns 0 (not null) when it simply has no tempo data for a
    # track -- that's "unknown", not "zero BPM", so treat it as absent.
    if not bpm:
        return None
    try:
        return round(float(bpm))
    except (TypeError, ValueError):
        return None


_ARTIST_SPLIT_RE = re.compile(r"[,&/]|\bfeat\.?\b|\bfeaturing\b|\bft\.?\b|\band\b", re.IGNORECASE)


def _artist_tokens(artist: str) -> Set[str]:
    """Split a multi-credit artist string into individual names, so 'A &
    B' and 'A, B' (or a search result crediting only 'A') can be compared
    on overlap rather than needing byte-for-byte equality -- real catalogs
    don't agree on separator punctuation for the exact same recording."""
    return {p.strip() for p in _ARTIST_SPLIT_RE.split(artist.lower()) if p.strip()}


def deezer_bpm_by_title_artist(title: str, artist: str) -> Optional[int]:
    """Fallback bpm lookup for a song picked from iTunes (or typed by hand)
    rather than matched to a Deezer id directly.

    In practice iTunes wins the search merge for most popular tracks (its
    top hit and Deezer's often normalise to the same title/artist, so
    Deezer's duplicate gets deduped out) -- restricting bpm lookups to
    `song_id` starting with "deezer:" left real coverage far thinner than
    it needs to be. This still only ever returns Deezer's own measured
    field: the title must match the request exactly (case-insensitively --
    this is the real safeguard against attaching the wrong recording's
    tempo), and the artist only needs to share at least one credited name
    with the request, since "A & B" vs "A, B" vs a search result crediting
    only "A" are all the same recording, just formatted differently.
    """
    title = (title or "").strip()
    artist = (artist or "").strip()
    if not title:
        return None
    term = f"{title} {artist}".strip()
    try:
        res = httpx.get(
            _DEEZER_URL, params={"q": term, "limit": 5}, timeout=_BPM_TIMEOUT_S
        )
        res.raise_for_status()
        rows = res.json().get("data", [])
    except Exception as exc:
        log.info("Deezer bpm-by-title lookup failed for %r: %s", term, exc)
        return None

    norm_title = title.lower()
    requested_artists = _artist_tokens(artist) if artist else set()
    for row in rows:
        row_title = (row.get("title") or "").strip().lower()
        if row_title != norm_title:
            continue
        if requested_artists:
            row_artists = _artist_tokens((row.get("artist") or {}).get("name") or "")
            if not (requested_artists & row_artists):
                continue
        track_id = row.get("id")
        if track_id is None:
            continue
        return deezer_track_bpm(str(track_id))
    return None


def search(query: str, genre: Optional[str] = None, limit: int = 8) -> List[Song]:
    query = (query or "").strip()
    if not query:
        return []

    # Both APIs rank by relevance rather than filtering strictly -- neither
    # has a "genre=tamil" parameter -- so folding the genre's display label
    # into the search term is a cheap relevance nudge, not a hard filter.
    # "other" has no genre of its own to bias toward -- appending its label
    # ("Other genre") would just add noise to the query -- so it searches
    # unbiased, same as no genre at all.
    term = f"{query} {genre_label(genre)}" if genre and genre != "other" else query

    # Run both requests in parallel rather than doubling latency -- FastAPI
    # already runs this sync route in a worker thread, so a small nested
    # pool is cheap and doesn't need an async rewrite of the whole path.
    with ThreadPoolExecutor(max_workers=2) as pool:
        itunes_future = pool.submit(_search_itunes, term, limit)
        deezer_future = pool.submit(_search_deezer, term, limit)
        itunes_songs = itunes_future.result()
        deezer_songs = deezer_future.result()

    # Interleave rather than "all of A then all of B" -- a strong Deezer hit
    # for a thin-on-iTunes genre should be able to land above a weak iTunes
    # match, not get buried after a full page of it.
    merged: List[Song] = []
    seen = set()
    for a, b in zip(itunes_songs, deezer_songs):
        for song in (a, b):
            key = (song.title.strip().lower(), song.artist.strip().lower())
            if key in seen:
                continue
            seen.add(key)
            merged.append(song)
    for song in itunes_songs[len(deezer_songs):] + deezer_songs[len(itunes_songs):]:
        key = (song.title.strip().lower(), song.artist.strip().lower())
        if key in seen:
            continue
        seen.add(key)
        merged.append(song)

    return merged[:limit]
