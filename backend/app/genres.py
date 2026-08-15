"""Genre buttons shown on the guest's first screen.

Static and small on purpose -- this is the very first thing a phone paints
after the QR scan, so it ships with the page rather than waiting on a
request. The key a guest taps is stored on the request as-is (``requests.genre``)
and also used to nudge the iTunes search term -- see ``genre_label``.
"""

from __future__ import annotations

from typing import Optional

from .contracts import Genre

# Interleaved rather than grouped, matching
# frontend/app/components/guest/genres.ts -- the guest grid never clusters
# by region, so the data it's built from shouldn't imply a grouping either.
# "region" is informational only (never rendered) -- "other" covers genres
# that aren't a North/South India regional language at all.
GENRES = [
    Genre(key="punjabi", label="Punjabi", region="north"),
    Genre(key="tamil", label="Tamil", region="south"),
    Genre(key="haryanvi", label="Haryanvi", region="north"),
    Genre(key="telugu", label="Telugu", region="south"),
    Genre(key="marathi", label="Marathi", region="other"),
    Genre(key="bollywood", label="Bollywood", region="north"),
    Genre(key="english", label="English", region="other"),
    Genre(key="edm", label="EDM / Trap", region="other"),
    # Catch-all so a guest whose song doesn't fit any bucket above can still
    # request it, rather than forcing a mistagged pick. Last on purpose --
    # it's the fallback, not a fifth option worth equal billing.
    Genre(key="other", label="Other genre", region="other"),
]

_BY_KEY = {g.key: g.label for g in GENRES}


def genre_label(key: Optional[str]) -> str:
    return _BY_KEY.get(key or "", key or "")
