"""M1 -- Intent Interpreter.

Public surface:

    interpret(text) -> Intent                 deterministic, <5ms, never raises
    interpret_async(text) -> Intent           LLM-enhanced when a key exists
    phrase_ack(intent, wave_label, wave_size) -> str   guest-facing validation

The deterministic path is the product; the LLM is an optional upgrade that can
fail freely. See ``rules.py`` and ``llm.py``.

Python 3.9 compatible: no ``X | Y`` annotations.
"""

from __future__ import annotations

import hashlib
from typing import List

from ..contracts import Intent
from . import lexicon as _lexicon
from .llm import llm_interpret as _llm_interpret
from .llm import merge as _merge
from .rules import interpret

__all__ = ["interpret", "interpret_async", "phrase_ack"]


async def interpret_async(text: str) -> Intent:
    """Rules first, then optionally refined by an LLM. Never raises."""
    base = interpret(text)
    try:
        enhanced = await _llm_interpret(text)
    except Exception:  # pragma: no cover -- llm_interpret already swallows
        return base
    if enhanced is None:
        return base
    try:
        return _merge(base, enhanced)
    except Exception:  # pragma: no cover
        return base


# ---------------------------------------------------------------------------
# Guest-facing acknowledgement
# ---------------------------------------------------------------------------

_NEW_WAVE: List[str] = [
    "Got it. You want {desc}. You're starting a new wave - the DJ sees it now.",
    "Heard you: {desc}. You're starting a new wave - the DJ sees it now.",
    "Locked in - {desc}. You're starting a new wave - the DJ sees it now.",
]

_ONE_OTHER: List[str] = [
    "Got it. You want {desc}. Your request just joined 1 other person asking "
    "for the same thing.",
    "Heard you: {desc}. 1 other person is already on this wave.",
    "Locked in - {desc}. You and 1 other person want the same thing right now.",
]

_MANY: List[str] = [
    "Got it. You want {desc}. Your request just joined a wave of {n} other "
    "people.",
    "Heard you: {desc}. That's {n} other people asking for the same energy.",
    "Locked in - {desc}. You're riding a wave with {n} others right now.",
    "Got it - {desc}. {n} other people want this too, and the DJ can see the "
    "wave building.",
]


def _descriptor(intent: Intent, wave_label: str) -> str:
    summary = (intent.summary or "").strip() if intent else ""
    if summary:
        return summary
    label = (wave_label or "").strip()
    if label:
        return label
    return "something for the floor"


def _pick(templates: List[str], seed: str) -> str:
    """Deterministic template choice -- stable across processes, unlike hash()."""
    digest = hashlib.md5(seed.encode("utf-8", "ignore")).hexdigest()
    return templates[int(digest[:8], 16) % len(templates)]


def phrase_ack(intent: Intent, wave_label: str = "", wave_size: int = 0) -> str:
    """Warm confirmation that the guest was actually understood.

    ``wave_size`` is the number of *other* people already in the wave.
    """
    try:
        desc = _descriptor(intent, wave_label)
        try:
            size = int(wave_size)
        except (TypeError, ValueError):
            size = 0
        size = max(0, size)

        seed = "%s|%s|%d" % (desc, wave_label or "", size)
        if size <= 0:
            template = _pick(_NEW_WAVE, seed)
        elif size == 1:
            template = _pick(_ONE_OTHER, seed)
        else:
            template = _pick(_MANY, seed)
        return template.format(desc=desc, n=size)
    except Exception:  # pragma: no cover -- an ack must never break a request
        return "Got it - your request is in. The DJ can see it now."


def lexicon_size() -> int:
    """Number of distinct surface forms the deterministic engine knows."""
    return _lexicon.size()
