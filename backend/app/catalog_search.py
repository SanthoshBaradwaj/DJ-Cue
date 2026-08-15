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
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

import httpx

from .contracts import Song
from .genres import genre_label

log = logging.getLogger("cue.catalog_search")

_ITUNES_URL = "https://itunes.apple.com/search"
_DEEZER_URL = "https://api.deezer.com/search"
_TIMEOUT_S = 5.0


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


def search(query: str, genre: Optional[str] = None, limit: int = 8) -> List[Song]:
    query = (query or "").strip()
    if not query:
        return []

    # Both APIs rank by relevance rather than filtering strictly -- neither
    # has a "genre=tamil" parameter -- so folding the genre's display label
    # into the search term is a cheap relevance nudge, not a hard filter.
    term = f"{query} {genre_label(genre)}" if genre else query

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
