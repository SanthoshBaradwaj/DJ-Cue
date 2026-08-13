"""Optional LLM enhancement layer for M1.

Strictly an upgrade path: the deterministic engine in ``rules.py`` is the
product. Everything here is wrapped so that a missing key, a missing package, a
timeout, a rate limit or a hallucinated JSON blob degrades to ``None`` and the
caller silently keeps the rules result. This module must never raise.

Python 3.9 compatible: no ``X | Y`` annotations.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Dict, List, Optional

from .. import taxonomy
from ..config import settings
from ..contracts import Intent

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

# Interpretation sits on the ingest path with a hard ``llm_timeout_s`` budget
# (2.5s by default), and every guest submission pays it. That makes latency the
# binding constraint here, not capability -- the task is a short, well-specified
# extraction into a fixed vocabulary, which is exactly what the fastest tier is
# for. A model that thinks before answering will simply blow the deadline and
# fall back to the rules engine, so the LLM layer would cost money and change
# nothing.
#
# Override with ``CUE_LLM_MODEL`` (e.g. claude-sonnet-5 or claude-opus-5 for
# more nuance on messy Hinglish) -- but raise ``CUE_LLM_TIMEOUT`` with it.
ANTHROPIC_MODEL = "claude-haiku-4-5"


def anthropic_model() -> str:
    """The Claude model to call.

    ``settings.llm_model`` is shared with the OpenAI path and defaults to an
    OpenAI model name, so it is only honoured here when it actually names a
    Claude model -- otherwise a key-only setup would send ``gpt-4o-mini`` to
    Anthropic and 404 on every request.
    """
    configured = (settings.llm_model or "").strip()
    if configured.lower().startswith("claude"):
        return configured
    return ANTHROPIC_MODEL

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def build_prompt(text: str) -> str:
    """System/instruction prompt with the legal vocabularies inlined.

    Injecting the taxonomy is what keeps the model inside the vector space --
    ``Intent.sanitized()`` is the hard gate, but a model that knows the
    vocabulary produces far fewer dropped tokens.
    """
    return (
        "You interpret song requests shouted at a live DJ. Convert the request "
        "into structured musical intent.\n"
        "Reply with STRICT JSON only -- no prose, no markdown fences.\n\n"
        "Schema (all keys required):\n"
        "{\n"
        '  "languages": [str],   // subset of: %s\n'
        '  "genres": [str],      // subset of: %s\n'
        '  "moods": [str],       // subset of: %s\n'
        '  "eras": [str],        // subset of: %s\n'
        '  "artists": [str],     // real artist names mentioned or implied, max 5\n'
        '  "energy_target": float,  // 0.0 ballad .. 1.0 peak-time\n'
        '  "danceability": float,   // 0.0 .. 1.0\n'
        '  "familiarity": float,    // 0.0 deep cut .. 1.0 everybody knows it\n'
        '  "tempo_hint": str,       // one of: %s\n'
        '  "confidence": float,     // 0.0 .. 1.0, how sure you are\n'
        '  "summary": str           // 2-4 words, e.g. "high-energy Punjabi"\n'
        "}\n\n"
        "Rules: use ONLY tokens from the lists above; omit a list rather than "
        "invent a token. Respect negation (\"no rap\" means exclude hiphop). "
        "Map artists to their language/genre. Hinglish and emoji are common.\n\n"
        "Request: %s"
    ) % (
        ", ".join(taxonomy.LANGUAGES),
        ", ".join(taxonomy.GENRES),
        ", ".join(taxonomy.MOODS),
        ", ".join(taxonomy.ERAS),
        ", ".join(taxonomy.TEMPO_HINTS),
        json.dumps(text[:400]),
    )


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------


async def _call_openai(text: str) -> Optional[str]:
    from openai import AsyncOpenAI  # imported lazily; optional dependency

    client = AsyncOpenAI(
        api_key=settings.openai_api_key, timeout=settings.llm_timeout_s
    )
    response = await client.chat.completions.create(
        model=settings.llm_model,
        temperature=0,
        max_tokens=400,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": "You output strict JSON describing musical intent.",
            },
            {"role": "user", "content": build_prompt(text)},
        ],
    )
    return response.choices[0].message.content


async def _call_anthropic(text: str) -> Optional[str]:
    import httpx  # imported lazily; optional dependency

    # No ``temperature``: it is rejected outright by current Claude models, so
    # sending it would break the moment someone points CUE_LLM_MODEL at one.
    # The prompt already pins the output shape.
    payload = {
        "model": anthropic_model(),
        "max_tokens": 500,
        "messages": [{"role": "user", "content": build_prompt(text)}],
    }
    headers = {
        "x-api-key": settings.anthropic_api_key or "",
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }
    async with httpx.AsyncClient(timeout=settings.llm_timeout_s) as client:
        response = await client.post(ANTHROPIC_URL, json=payload, headers=headers)
        response.raise_for_status()
        body = response.json()
    chunks = [
        block.get("text", "")
        for block in body.get("content", [])
        if isinstance(block, dict) and block.get("type") == "text"
    ]
    return "".join(chunks)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def parse_intent(raw: Optional[str]) -> Optional[Intent]:
    """Parse a model response into a sanitized Intent, or ``None``."""
    if not raw:
        return None
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"```\s*$", "", text).strip()
    match = _JSON_BLOCK.search(text)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None

    def strings(key: str) -> List[str]:
        value = data.get(key)
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, list):
            return []
        return [str(v) for v in value if isinstance(v, (str, int, float))]

    def number(key: str, default: float) -> float:
        try:
            return float(data.get(key, default))
        except (TypeError, ValueError):
            return default

    tempo = data.get("tempo_hint")
    summary = data.get("summary")

    return Intent(
        languages=strings("languages"),
        genres=strings("genres"),
        moods=strings("moods"),
        artists=strings("artists"),
        eras=strings("eras"),
        energy_target=number("energy_target", 0.55),
        danceability=number("danceability", 0.6),
        familiarity=number("familiarity", 0.55),
        tempo_hint=tempo if isinstance(tempo, str) else None,
        confidence=number("confidence", 0.6),
        source="llm",
        raw_keywords=strings("raw_keywords"),
        summary=str(summary).strip() if isinstance(summary, str) else "",
    ).sanitized()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def llm_interpret(text: str) -> Optional[Intent]:
    """LLM-derived Intent, or ``None`` on any failure. Never raises."""
    try:
        if not (text or "").strip():
            return None
        if not settings.has_llm:
            return None
        provider = settings.llm_provider
        if provider == "openai":
            coroutine = _call_openai(text)
        elif provider == "anthropic":
            coroutine = _call_anthropic(text)
        else:
            return None
        raw = await asyncio.wait_for(coroutine, timeout=settings.llm_timeout_s)
        return parse_intent(raw)
    except asyncio.TimeoutError:
        return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------


def merge(base: Intent, enhanced: Optional[Intent]) -> Intent:
    """Union the categorical fields, trust the LLM on the continuous ones."""
    if enhanced is None:
        return base

    def union(a: List[str], b: List[str], limit: int) -> List[str]:
        out: List[str] = []
        for token in list(a) + list(b):
            if token and token not in out:
                out.append(token)
        return out[:limit]

    merged = Intent(
        languages=union(base.languages, enhanced.languages, 3),
        genres=union(base.genres, enhanced.genres, 4),
        moods=union(base.moods, enhanced.moods, 3),
        artists=union(base.artists, enhanced.artists, 5),
        eras=union(base.eras, enhanced.eras, 2),
        energy_target=enhanced.energy_target,
        danceability=enhanced.danceability,
        familiarity=enhanced.familiarity,
        tempo_hint=enhanced.tempo_hint or base.tempo_hint,
        confidence=max(base.confidence, enhanced.confidence),
        source="hybrid",
        raw_keywords=union(base.raw_keywords, enhanced.raw_keywords, 12),
        summary=(enhanced.summary or base.summary),
    )
    return merged.sanitized()


def describe() -> Dict[str, Any]:
    """Small introspection helper for the dashboard / health endpoint."""
    return {
        "enabled": bool(settings.has_llm),
        "provider": settings.llm_provider,
        "model": (
            settings.llm_model
            if settings.llm_provider == "openai"
            else anthropic_model()
        ),
        "timeout_s": settings.llm_timeout_s,
    }
