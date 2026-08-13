"""Canonical CUE taxonomy.

This module is the single source of truth for every categorical value that
crosses a module boundary. The interpreter (M1) may only emit values from these
lists, the clustering engine (M2) builds its vector space from their ordering,
and the catalog (M3) may only tag tracks with them.

Nothing here may be reordered or removed once agents are running -- the vector
space in ``vectors.py`` is positional. Appending to the end of a list is safe.
"""

from typing import Dict, List, Tuple

# --------------------------------------------------------------------------
# Canonical vocabularies (ORDER IS PART OF THE CONTRACT -- append only)
# --------------------------------------------------------------------------

LANGUAGES: List[str] = [
    "punjabi",
    "hindi",
    "english",
    "tamil",
    "telugu",
    "spanish",
    "afrobeats",
    "arabic",
]

GENRES: List[str] = [
    "bhangra",
    "bollywood",
    "hiphop",
    "rnb",
    "house",
    "techno",
    "edm",
    "pop",
    "rock",
    "reggaeton",
    "afrobeat",
    "desi_hiphop",
    "sufi",
    "disco",
    "amapiano",
    "garage",
]

MOODS: List[str] = [
    "hype",
    "romantic",
    "nostalgic",
    "chill",
    "sad",
    "dark",
    "euphoric",
    "sensual",
    "celebratory",
    "aggressive",
]

ERAS: List[str] = [
    "1980s",
    "1990s",
    "2000s",
    "2010s",
    "2020s",
]

TEMPO_HINTS: List[str] = ["slow", "mid", "fast"]

# Actions a DJ can take on a recommended candidate.
DJ_ACTIONS: List[str] = ["play", "later", "skip"]

# --------------------------------------------------------------------------
# Vector-space layout
# --------------------------------------------------------------------------
# The intent vector is the concatenation of one-hot-ish multi-label blocks
# followed by the continuous features. Both M2 (clustering) and M3 (ranking)
# consume this exact layout, so it lives in the spine rather than in either.

CONTINUOUS_FEATURES: List[str] = [
    "energy_target",
    "danceability",
    "familiarity",
]

# Per-block weights. Language and genre dominate because in practice they are
# what makes two requests feel like "the same ask" to a DJ; mood refines it.
BLOCK_WEIGHTS: Dict[str, float] = {
    "languages": 1.6,
    "genres": 1.5,
    "moods": 0.9,
    "eras": 0.8,
    "continuous": 0.7,
}

VECTOR_BLOCKS: List[Tuple[str, List[str]]] = [
    ("languages", LANGUAGES),
    ("genres", GENRES),
    ("moods", MOODS),
    ("eras", ERAS),
]

VECTOR_DIM: int = (
    len(LANGUAGES) + len(GENRES) + len(MOODS) + len(ERAS) + len(CONTINUOUS_FEATURES)
)


def block_offset(block_name: str) -> int:
    """Return the starting index of a named block in the intent vector."""
    offset = 0
    for name, values in VECTOR_BLOCKS:
        if name == block_name:
            return offset
        offset += len(values)
    if block_name == "continuous":
        return offset
    raise KeyError("unknown vector block: %s" % block_name)


# --------------------------------------------------------------------------
# Display helpers -- used by wave labelling and the UIs
# --------------------------------------------------------------------------

DISPLAY_NAMES: Dict[str, str] = {
    "punjabi": "Punjabi",
    "hindi": "Hindi",
    "english": "English",
    "tamil": "Tamil",
    "telugu": "Telugu",
    "spanish": "Spanish",
    "afrobeats": "Afrobeats",
    "arabic": "Arabic",
    "bhangra": "Bhangra",
    "bollywood": "Bollywood",
    "hiphop": "Hip-Hop",
    "rnb": "R&B",
    "house": "House",
    "techno": "Techno",
    "edm": "EDM",
    "pop": "Pop",
    "rock": "Rock",
    "reggaeton": "Reggaeton",
    "afrobeat": "Afrobeat",
    "desi_hiphop": "Desi Hip-Hop",
    "sufi": "Sufi",
    "disco": "Disco",
    "amapiano": "Amapiano",
    "garage": "Garage",
    "hype": "High-Energy",
    "romantic": "Romantic",
    "nostalgic": "Nostalgia",
    "chill": "Chill",
    "sad": "Melancholy",
    "dark": "Dark",
    "euphoric": "Euphoric",
    "sensual": "Sensual",
    "celebratory": "Celebration",
    "aggressive": "Aggressive",
    "1980s": "80s",
    "1990s": "90s",
    "2000s": "2000s",
    "2010s": "2010s",
    "2020s": "2020s",
}


def display(token: str) -> str:
    """Human-readable form of a taxonomy token."""
    return DISPLAY_NAMES.get(token, token.replace("_", " ").title())


def is_valid(block_name: str, token: str) -> bool:
    """Whether ``token`` is a legal member of the named vocabulary block."""
    lookup = {
        "languages": LANGUAGES,
        "genres": GENRES,
        "moods": MOODS,
        "eras": ERAS,
        "tempo_hints": TEMPO_HINTS,
    }
    return token in lookup.get(block_name, [])


def coerce(block_name: str, tokens: List[str]) -> List[str]:
    """Drop anything outside the canonical vocabulary, preserving order.

    The LLM enhancement layer is free to hallucinate; this is the gate that
    keeps invalid tokens out of the vector space.
    """
    seen = set()
    out = []
    for token in tokens or []:
        norm = str(token).strip().lower().replace(" ", "_").replace("-", "_")
        if is_valid(block_name, norm) and norm not in seen:
            seen.add(norm)
            out.append(norm)
    return out
