"""M3 -- track catalog and the context-aware ranker.

Public surface::

    from app.catalog import Catalog, get_catalog, Ranker

The catalog is an in-memory, hand-authored library (``library.TRACKS``); the
ranker scores it against a wave in the shared intent vector space from
``app.vectors``.
"""

from __future__ import annotations

import json
import logging
import os
import re
from difflib import SequenceMatcher
from typing import Dict, List, Optional

from ..contracts import Track
from . import audio
from .library import TRACKS
from .ranker import Ranker

log = logging.getLogger("cue.catalog")

_WORD_RE = re.compile(r"[a-z0-9']+")

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_CUSTOM_TRACKS_PATH = os.path.join(_ROOT, "data", "custom_tracks.json")


def _tokens(text: str) -> List[str]:
    return _WORD_RE.findall((text or "").lower())


def _load_custom_tracks() -> List[Track]:
    if not os.path.exists(_CUSTOM_TRACKS_PATH):
        return []
    try:
        with open(_CUSTOM_TRACKS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return [Track(**item) for item in data]
    except Exception as exc:
        log.warning("failed to load custom tracks from %s: %s", _CUSTOM_TRACKS_PATH, exc)
        return []


def _save_custom_tracks(tracks: List[Track]) -> None:
    try:
        os.makedirs(os.path.dirname(_CUSTOM_TRACKS_PATH), exist_ok=True)
        with open(_CUSTOM_TRACKS_PATH, "w", encoding="utf-8") as f:
            json.dump([t.model_dump() for t in tracks], f, indent=2)
    except Exception as exc:
        log.warning("failed to save custom tracks to %s: %s", _CUSTOM_TRACKS_PATH, exc)


class Catalog:
    """Read and write access to the track library, with dynamic custom track support."""

    def __init__(self, tracks: Optional[List[Track]] = None):
        base_tracks = list(TRACKS if tracks is None else tracks)
        custom_tracks = _load_custom_tracks() if tracks is None else []
        self._custom_tracks: List[Track] = custom_tracks
        self._tracks: List[Track] = list(base_tracks) + list(custom_tracks)
        self._by_id: Dict[str, Track] = {t.id: t for t in self._tracks}
        # Anything sitting in audio/ wins over the browser's synth for that
        # track. Idempotent: with an empty directory this is a single stat call
        # and every audio_file stays None.
        self.audio_matched: int = audio.attach(self._tracks)

    def add_track(self, track: Track, persist: bool = True) -> Track:
        """Dynamically add a discovered track to the catalog."""
        if track.id in self._by_id:
            return self._by_id[track.id]
        
        # Check for title/artist duplicate
        for existing in self._tracks:
            if existing.title.lower() == track.title.lower() and existing.artist.lower() == track.artist.lower():
                return existing

        self._tracks.append(track)
        self._by_id[track.id] = track
        if persist:
            self._custom_tracks.append(track)
            _save_custom_tracks(self._custom_tracks)
        log.info("dynamically registered track: %s by %s (%s)", track.title, track.artist, track.id)
        return track

    def __len__(self) -> int:
        return len(self._tracks)

    def all(self) -> List[Track]:
        return list(self._tracks)

    def get(self, track_id: str) -> Optional[Track]:
        return self._by_id.get(track_id)

    def by_language(self, language: str) -> List[Track]:
        lang = (language or "").strip().lower()
        return [t for t in self._tracks if t.language == lang]

    def search(self, query: str, limit: int = 10) -> List[Track]:
        """Fuzzy search over title, artist and tags.

        Guests and DJs type "diljit", "bad bunny", "wedding", "90s bollywood" --
        substring hits win, then token overlap, then a character-level ratio so
        a typo still lands somewhere sensible.
        """
        q = (query or "").strip().lower()
        if not q:
            return []

        q_tokens = set(_tokens(q))
        scored = []

        for track in self._tracks:
            title = track.title.lower()
            artist = track.artist.lower()
            tag_blob = " ".join(track.tags).lower()

            score = 0.0
            if q == title or q == artist:
                score += 6.0
            if q in title:
                score += 3.5
            if q in artist:
                score += 3.0
            if q in tag_blob:
                score += 1.2

            if q_tokens:
                title_tokens = set(_tokens(title))
                artist_tokens = set(_tokens(artist))
                tag_tokens = set(_tokens(tag_blob))
                score += 1.6 * len(q_tokens & title_tokens) / len(q_tokens)
                score += 1.6 * len(q_tokens & artist_tokens) / len(q_tokens)
                score += 0.7 * len(q_tokens & tag_tokens) / len(q_tokens)

            if score == 0.0:
                ratio = max(
                    SequenceMatcher(None, q, title).ratio(),
                    SequenceMatcher(None, q, artist).ratio(),
                )
                if ratio >= 0.62:
                    score = ratio
                else:
                    continue

            # Popularity is a mild tiebreaker, never the reason for a hit.
            scored.append((score + 0.15 * track.popularity, track))

        scored.sort(key=lambda pair: (-pair[0], pair[1].id))
        try:
            limit = max(0, int(limit))
        except (TypeError, ValueError):
            limit = 10
        return [track for _score, track in scored[:limit]]


_CATALOG: Optional[Catalog] = None


def get_catalog() -> Catalog:
    """Module-level singleton -- the library is static, load it once."""
    global _CATALOG
    if _CATALOG is None:
        _CATALOG = Catalog()
    return _CATALOG


__all__ = ["Catalog", "get_catalog", "Ranker", "TRACKS"]
