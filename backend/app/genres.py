"""Genre buttons shown on the guest's first screen.

Static and small on purpose -- this is the very first thing a phone paints
after the QR scan, so it ships with the page rather than waiting on a
request. Keys must match the ``genre`` column values seeded into ``songs``.
"""

from __future__ import annotations

from .contracts import Genre

GENRES = [
    Genre(key="punjabi", label="Punjabi", region="north"),
    Genre(key="haryanvi", label="Haryanvi", region="north"),
    Genre(key="bollywood", label="Bollywood", region="north"),
    Genre(key="tamil", label="Tamil", region="south"),
    Genre(key="telugu", label="Telugu", region="south"),
]
