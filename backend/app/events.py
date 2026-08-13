"""Async pub/sub bus backing the live dashboard.

Producers (request ingestion, DJ decisions) never touch WebSockets directly --
they publish a WSMessage and the API layer fans it out. Slow or dead sockets are
dropped rather than allowed to block ingestion, because on a live floor a stalled
tablet must never delay the next guest's request.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Dict, List, Set

from .contracts import WSMessage

log = logging.getLogger("cue.events")

# Bounded so a disconnected-but-not-yet-reaped client cannot grow without limit.
_QUEUE_MAX = 128


class EventBus:
    def __init__(self) -> None:
        self._subscribers: Dict[str, Set[asyncio.Queue]] = {}

    def subscribe(self, event_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=_QUEUE_MAX)
        self._subscribers.setdefault(event_id, set()).add(queue)
        return queue

    def unsubscribe(self, event_id: str, queue: asyncio.Queue) -> None:
        subs = self._subscribers.get(event_id)
        if subs:
            subs.discard(queue)
            if not subs:
                self._subscribers.pop(event_id, None)

    def subscriber_count(self, event_id: str) -> int:
        return len(self._subscribers.get(event_id, ()))

    def publish(self, event_id: str, message: WSMessage) -> None:
        """Fan a message out to every subscriber. Never raises, never blocks."""
        for queue in list(self._subscribers.get(event_id, ())):
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                # Drop the oldest frame and retry once: a laggy client should
                # see the newest state, not a backlog of stale ones.
                try:
                    queue.get_nowait()
                    queue.put_nowait(message)
                except Exception:  # pragma: no cover - defensive
                    log.debug("dropping frame for saturated subscriber")

    def publish_many(self, event_id: str, messages: List[WSMessage]) -> None:
        for message in messages:
            self.publish(event_id, message)


bus = EventBus()
