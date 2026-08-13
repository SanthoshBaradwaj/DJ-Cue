"""Chaos injector.

Fires the corpus at the live service the same way real guests would -- distinct
anonymous sessions, staggered arrivals -- so the dashboard *animates* into
order rather than blinking into it fully formed. Watching the waves assemble is
the demo.
"""

from __future__ import annotations

import asyncio
import logging
import random
from typing import TYPE_CHECKING

from ..contracts import new_id
from .corpus import sample

if TYPE_CHECKING:  # pragma: no cover
    from ..api.service import CueService

log = logging.getLogger("cue.seeder")


async def seed_event(
    service: "CueService",
    event_id: str = "default",
    count: int = 50,
    delay_ms: int = 120,
    seed: int = None,
) -> int:
    """Submit ``count`` chaotic requests from distinct sessions."""
    rng = random.Random(seed)
    texts = sample(count, seed=seed)
    sent = 0

    for text in texts:
        session_id = new_id("sess")
        # A small share of guests genuinely double-submit -- keeping that in
        # exercises the anti-manipulation path during the live demo instead of
        # only in tests.
        repeats = 2 if rng.random() < 0.08 else 1
        for _ in range(repeats):
            try:
                await service.submit_request(text, session_id, event_id)
                sent += 1
            except Exception as exc:  # one bad request must not stop the demo
                log.warning("seed request failed (%s): %s", text, exc)
        if delay_ms > 0:
            # Jitter so arrivals look human, not like a for-loop.
            await asyncio.sleep(rng.uniform(delay_ms * 0.4, delay_ms * 1.6) / 1000.0)

    log.info("seeded %d requests into %s", sent, event_id)
    return sent
