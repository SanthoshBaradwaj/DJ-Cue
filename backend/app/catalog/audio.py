"""Optional local audio: match files dropped in ``audio/`` to catalog tracks.

The pitch does not depend on this. The DJ dashboard synthesises a loop per
track in the browser, so the demo makes noise with an empty ``audio/``
directory. But the README promises that dropping an MP3 in gets it picked up
automatically, and a real file beats a synth every time -- so this module makes
that promise true without requiring it.

Matching is deliberately forgiving, because the person dropping files in is
doing it thirty seconds before a pitch and will not rename anything:

* ``trk_patiala_dd.mp3``            -- exact track id
* ``Patiala Peg - Diljit.mp3``      -- title and artist in either order
* ``patiala_peg.m4a``               -- title alone, if unambiguous

Nothing here may raise. A missing directory, an unreadable file, or two files
claiming the same track must all degrade to "no audio for that track" rather
than take the catalog -- and therefore the server -- down at boot.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from ..contracts import Track

log = logging.getLogger("cue.audio")

# Formats every current browser can decode via WebAudio.
AUDIO_SUFFIXES = (".mp3", ".m4a", ".aac", ".ogg", ".oga", ".opus", ".wav", ".flac")

_SLUG_RE = re.compile(r"[^a-z0-9]+")

# Words that carry no identifying signal in a filename and only get in the way
# of a match ("01 - Patiala Peg (Official Video).mp3").
_NOISE = frozenset(
    [
        "official",
        "video",
        "audio",
        "lyrics",
        "lyrical",
        "song",
        "full",
        "hd",
        "hq",
        "remix",
        "mix",
        "extended",
        "radio",
        "edit",
        "version",
        "feat",
        "ft",
        "prod",
        "copy",
        "final",
    ]
)


def audio_dir() -> Path:
    """Where to look for drop-in files. ``CUE_AUDIO_DIR`` overrides."""
    override = os.environ.get("CUE_AUDIO_DIR")
    if override:
        return Path(override).expanduser()
    # app/catalog/audio.py -> app/catalog -> app -> backend -> <project root>
    return Path(__file__).resolve().parents[3] / "audio"


def _slug(text: str) -> str:
    return _SLUG_RE.sub("-", (text or "").lower()).strip("-")


def _tokens(text: str) -> List[str]:
    """Identifying tokens only: noise words and bare track numbers dropped."""
    out = []
    for token in _slug(text).split("-"):
        if not token or token in _NOISE:
            continue
        if token.isdigit() and len(token) <= 2:  # leading "01 "
            continue
        out.append(token)
    return out


def _list_files(directory: Path) -> List[Path]:
    try:
        if not directory.is_dir():
            return []
        return sorted(
            p
            for p in directory.iterdir()
            if p.is_file()
            and not p.name.startswith(".")  # skip .DS_Store and friends
            and p.suffix.lower() in AUDIO_SUFFIXES
        )
    except OSError as exc:
        log.warning("could not read audio dir %s (%s)", directory, exc)
        return []


def _score(track: Track, file_tokens: Sequence[str], stem_slug: str) -> float:
    """How strongly one file names one track. 0.0 means "not this track"."""
    if not file_tokens:
        return 0.0

    # An exact track id in the filename is unambiguous and outranks everything.
    if stem_slug == _slug(track.id):
        return 100.0

    title_tokens = _tokens(track.title)
    artist_tokens = _tokens(track.artist)
    if not title_tokens:
        return 0.0

    present = set(file_tokens)
    title_hits = sum(1 for t in title_tokens if t in present)
    if title_hits < len(title_tokens):
        # The whole title must appear; a partial title match is how "Lover"
        # would steal a file that actually says "Lover Boy".
        return 0.0

    score = 10.0 + len(title_tokens)
    if artist_tokens and any(a in present for a in artist_tokens):
        score += 5.0  # title *and* artist -- much more confident
    # Prefer the file whose name is mostly the track, not a long medley.
    score -= 0.1 * max(0, len(file_tokens) - len(title_tokens) - len(artist_tokens))
    return score


def discover(tracks: Sequence[Track], directory: Optional[Path] = None) -> Dict[str, str]:
    """Map ``track_id -> filename`` for whatever is sitting in ``audio/``.

    Each file claims at most one track and each track takes at most one file;
    ties are resolved by score, then by filename so the result is stable across
    restarts rather than dependent on directory order.
    """
    directory = audio_dir() if directory is None else directory
    files = _list_files(directory)
    if not files:
        return {}

    candidates = []  # (-score, filename, track_id)
    for path in files:
        file_tokens = _tokens(path.stem)
        stem_slug = _slug(path.stem)
        for track in tracks:
            score = _score(track, file_tokens, stem_slug)
            if score > 0.0:
                candidates.append((-score, path.name, track.id))

    candidates.sort()
    mapping: Dict[str, str] = {}
    claimed_files = set()
    for _neg_score, filename, track_id in candidates:
        if track_id in mapping or filename in claimed_files:
            continue
        mapping[track_id] = filename
        claimed_files.add(filename)

    if mapping:
        log.info("matched %d local audio file(s) from %s", len(mapping), directory)
    unmatched = [f.name for f in files if f.name not in claimed_files]
    if unmatched:
        # Worth saying out loud: a file that silently does nothing is the kind
        # of thing you rediscover on stage.
        log.info(
            "%d audio file(s) matched no track and will be ignored: %s",
            len(unmatched),
            ", ".join(unmatched[:5]),
        )
    return mapping


def attach(tracks: Sequence[Track], directory: Optional[Path] = None) -> int:
    """Populate ``Track.audio_file`` in place. Returns how many were matched."""
    try:
        mapping = discover(tracks, directory)
    except Exception:  # pragma: no cover - audio is never worth a boot failure
        log.exception("audio discovery failed; continuing with synth only")
        return 0
    for track in tracks:
        filename = mapping.get(track.id)
        if filename:
            track.audio_file = filename
    return len(mapping)


def resolve(filename: str, directory: Optional[Path] = None) -> Optional[Path]:
    """Resolve a request for ``filename`` to a real file, or ``None``.

    The name is reduced to its basename and the result is confirmed to sit
    directly inside the audio directory, so ``../../etc/passwd`` and absolute
    paths cannot escape regardless of what the route hands us.
    """
    directory = audio_dir() if directory is None else directory
    name = os.path.basename((filename or "").strip())
    if not name or name.startswith("."):
        return None
    if Path(name).suffix.lower() not in AUDIO_SUFFIXES:
        return None
    try:
        base = directory.resolve()
        target = (base / name).resolve()
        if target.parent != base or not target.is_file():
            return None
        return target
    except OSError:
        return None


__all__ = ["AUDIO_SUFFIXES", "attach", "audio_dir", "discover", "resolve"]
