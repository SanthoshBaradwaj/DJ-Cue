"""Anti-manipulation weighting (M2).

The product promise is "the honest signal of the room". One guest hammering the
submit button from a single phone must not be able to out-shout twenty people
who each asked once -- but they must never be *blocked* either, because the
guest experience depends on always feeling heard. So repeat submissions are
heavily discounted rather than rejected: they still show up in their wave, they
just stop moving the needle.

Discounting is strictly *within* a session. Two different devices asking for the
same thing is not manipulation, it is the entire signal we are trying to
measure, and is never penalised.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from .. import vectors
from ..config import settings
from ..contracts import Intent, SongRequest

log = logging.getLogger("cue.clustering.antimanip")

# Reason codes surfaced to the dashboard / guest ack.
REASON_REPEAT = "repeat"
REASON_RAPID_FIRE = "rapid-fire"
REASON_DUPLICATE = "duplicate"

# Multiplier applied on top of the repeat decay when a submission is a
# near-duplicate of something the same session already sent.
DUPLICATE_PENALTY = 0.2

# Only the most recent N prior submissions are checked for duplication; a
# session that has already been discounted into the floor cannot be discounted
# further, so scanning its full history buys nothing but latency.
_DUPLICATE_LOOKBACK = 20


def _is_near_duplicate(prior: List[SongRequest], text: str, intent: Intent) -> bool:
    """Whether this submission repeats something the same session already sent.

    Semantic match first (``vectors.similarity`` -- catches "bhangra pls" after
    "punjabi banger"), lexical match as a backstop (``vectors.text_similarity``
    -- catches re-sends naming an artist the taxonomy does not model).
    """
    for previous in prior[-_DUPLICATE_LOOKBACK:]:
        try:
            if vectors.similarity(previous.intent, intent) > settings.duplicate_similarity:
                return True
            if vectors.text_similarity(previous.text, text) > settings.duplicate_similarity:
                return True
        except Exception:  # pragma: no cover - never let scoring break ingestion
            log.debug("duplicate check failed; treating as non-duplicate")
    return False


def compute_weight(
    prior_requests: List[SongRequest],
    text: str,
    intent: Intent,
    now: float,
) -> Tuple[float, Optional[str]]:
    """Score one incoming submission against its own session's history.

    ``prior_requests`` must be the earlier requests *from the same session*
    (``store.session_requests``). Requests from other sessions are never inputs
    here -- cross-session agreement is genuine demand, not manipulation.

    Returns ``(weight, discount_reason)``; the reason is ``None`` only for a
    session's very first request.
    """
    prior = sorted(
        [r for r in (prior_requests or []) if r is not None],
        key=lambda r: r.created_at,
    )
    if not prior:
        return 1.0, None

    n = len(prior) + 1
    weight = float(settings.repeat_decay ** (n - 1))
    reason = REASON_REPEAT

    # Rapid-fire: the previous submission from this device is still warm.
    latest = prior[-1]
    if abs(float(now) - float(latest.created_at)) <= settings.rapid_fire_window_s:
        weight *= settings.rapid_fire_penalty
        reason = REASON_RAPID_FIRE

    # Near-duplicate outranks rapid-fire as an explanation: it is the more
    # specific thing to tell the DJ (and the guest).
    if _is_near_duplicate(prior, text, intent):
        weight *= DUPLICATE_PENALTY
        reason = REASON_DUPLICATE

    # Floor, never zero: the request still counts, it just barely moves.
    weight = max(settings.session_min_weight, min(1.0, weight))
    return float(weight), reason
