"""Genre buttons shown on the guest's first screen.

Static and small on purpose -- this is the very first thing a phone paints
after the QR scan, so it ships with the page rather than waiting on a
request. The key a guest taps is stored on the request as-is (``requests.genre``)
and also used to nudge the iTunes search term -- see ``genre_label``.
"""

from __future__ import annotations

from typing import Optional

from .contracts import Genre

# Interleaved north/south, matching frontend/app/components/guest/genres.ts
# -- the guest grid never groups by region, so the data it's built from
# shouldn't imply a grouping either.
GENRES = [
    Genre(key="punjabi", label="Punjabi", region="north"),
    Genre(key="tamil", label="Tamil", region="south"),
    Genre(key="haryanvi", label="Haryanvi", region="north"),
    Genre(key="telugu", label="Telugu", region="south"),
    Genre(key="bollywood", label="Bollywood", region="north"),
]

_BY_KEY = {g.key: g.label for g in GENRES}


def genre_label(key: Optional[str]) -> str:
    return _BY_KEY.get(key or "", key or "")
