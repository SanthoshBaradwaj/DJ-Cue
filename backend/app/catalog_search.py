"""Live song search: Apple's iTunes Search API, with Deezer as a fallback.

Both are free, unauthenticated, no signup -- there is no local song catalog
and no paid search API anywhere in this path. iTunes is queried first; when
it comes up thin, Deezer fills in the rest. This exists because iTunes'
India-storefront coverage is uneven across the genres this app serves --
excellent for Hindi/Bollywood, Punjabi and Telugu, thinner for Marathi, and
noticeably weak for Haryanvi (a fast-moving, YouTube-first folk-pop scene
many small labels never bring to Apple Music at all). Every call is
short-timeout and fails soft to an empty list -- a flaky external API must
never take the guest flow down with it.
"""

from __future__ import annotations

import logging
from typing import List, Optional

import httpx

from .contracts import Song
from .genres import genre_label

log = logging.getLogger("cue.catalog_search")

_ITUNES_URL = "https://itunes.apple.com/search"
_DEEZER_URL = "https://api.deezer.com/search"
_TIMEOUT_S = 5.0
# Below this many iTunes hits, also try Deezer.
_FALLBACK_THRESHOLD = 3


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
    # into the search term is a cheap relevance nudge.
    term = f"{query} {genre_label(genre)}" if genre else query

    songs = _search_itunes(term, limit)
    if len(songs) < _FALLBACK_THRESHOLD:
        seen = {(s.title.strip().lower(), s.artist.strip().lower()) for s in songs}
        for song in _search_deezer(term, limit - len(songs)):
            key = (song.title.strip().lower(), song.artist.strip().lower())
            if key in seen:
                continue
            seen.add(key)
            songs.append(song)
            if len(songs) >= limit:
                break
    return songs
