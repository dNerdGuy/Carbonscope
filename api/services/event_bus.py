"""In-process SSE event bus for real-time push notifications.

Maintains a set of asyncio.Queue per company_id so that SSE connections
scoped to a company receive only their own events.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Map company_id → set of subscriber queues
_subscribers: dict[str, set[asyncio.Queue[dict[str, Any]]]] = {}


@dataclass
class Subscription:
    """Context manager for an SSE subscription scoped to a company."""

    company_id: str
    queue: asyncio.Queue[dict[str, Any]] = field(default_factory=lambda: asyncio.Queue(maxsize=64))

    def __enter__(self) -> asyncio.Queue[dict[str, Any]]:
        subs = _subscribers.setdefault(self.company_id, set())
        subs.add(self.queue)
        return self.queue

    def __exit__(self, *exc: object) -> None:
        self._cleanup()

    async def __aenter__(self) -> asyncio.Queue[dict[str, Any]]:
        subs = _subscribers.setdefault(self.company_id, set())
        subs.add(self.queue)
        return self.queue

    async def __aexit__(self, *exc: object) -> None:
        self._cleanup()

    def _cleanup(self) -> None:
        subs = _subscribers.get(self.company_id)
        if subs:
            subs.discard(self.queue)
            if not subs:
                del _subscribers[self.company_id]


def publish(company_id: str, event_type: str, data: dict[str, Any] | None = None) -> int:
    """Publish an event to all subscribers of a company.

    Returns the number of clients that received the event.
    """
    subs = _subscribers.get(company_id)
    if not subs:
        return 0

    payload = {"event": event_type, "data": data or {}}
    delivered = 0
    for q in list(subs):
        try:
            q.put_nowait(payload)
            delivered += 1
        except asyncio.QueueFull:
            logger.warning("SSE queue full for company %s — dropping event", company_id)
    return delivered
