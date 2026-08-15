"""Live song search via Apple's iTunes Search API.

Free, unauthenticated, no API key, no signup -- this is what lets a guest
search *any* song instead of picking from a small hand-curated list. It's a
public, unofficial-but-stable JSON endpoint Apple has run for over a decade;
no SLA, so every call is short-timeout and fails soft to an empty list
rather than ever taking the guest flow down with it.
"""

from __future__ import annotations

import logging
from typing import List, Optional

import httpx

from .contracts import Song
from .genres import genre_label

log = logging.getLogger("cue.itunes")

_SEARCH_URL = "https://itunes.apple.com/search"
_TIMEOUT_S = 5.0


def search(query: str, genre: Optional[str] = None, limit: int = 8) -> List[Song]:
    query = (query or "").strip()
    if not query:
        return []

    # iTunes search is relevance-ranked, not a strict filter -- there's no
    # "genre=tamil" parameter, so folding the genre's display label into the
    # search term is a cheap relevance nudge, and `country=IN` biases the
    # whole result set toward the Indian storefront's catalog.
    term = f"{query} {genre_label(genre)}" if genre else query

    try:
        res = httpx.get(
            _SEARCH_URL,
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
    except Exception as exc:  # network hiccup, timeout, bad JSON -- never 500 the guest
        log.warning("iTunes search failed for %r: %s", query, exc)
        return []

    songs: List[Song] = []
    for row in payload.get("results", []):
        track_id = row.get("trackId")
        title = row.get("trackName")
        if track_id is None or not title:
            continue
        songs.append(
            Song(
                id=str(track_id),
                title=title,
                artist=row.get("artistName") or "",
                genre=row.get("primaryGenreName") or "",
                artwork_url=row.get("artworkUrl100"),
            )
        )
    return songs
