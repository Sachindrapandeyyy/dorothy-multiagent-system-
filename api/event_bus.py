"""
Dorothy OS v2.0 — Event Bus
Lightweight async pub/sub event system for inter-module communication.
"""

import asyncio
import logging
from typing import Dict, Set, Callable, Any, Awaitable

logger = logging.getLogger("Dorothy.EventBus")


class EventBus:
    """Asynchronous publish/subscribe event bus for decoupled module communication."""

    def __init__(self):
        self._subscribers: Dict[str, Set[Callable[[Any], Awaitable[None]]]] = {}

    def subscribe(self, topic: str, callback: Callable[[Any], Awaitable[None]]) -> None:
        """Register a callback for a topic."""
        if topic not in self._subscribers:
            self._subscribers[topic] = set()
        self._subscribers[topic].add(callback)
        logger.debug(f"Subscribed to topic: {topic}")

    def unsubscribe(self, topic: str, callback: Callable[[Any], Awaitable[None]]) -> None:
        """Remove a callback from a topic."""
        if topic in self._subscribers:
            self._subscribers[topic].discard(callback)
            if not self._subscribers[topic]:
                del self._subscribers[topic]
            logger.debug(f"Unsubscribed from topic: {topic}")

    async def publish(self, topic: str, data: Any) -> None:
        """Publish data to all subscribers of a topic."""
        if topic not in self._subscribers:
            return
        tasks = []
        for callback in list(self._subscribers[topic]):
            async def safe_call(cb=callback, payload=data):
                try:
                    await cb(payload)
                except Exception as e:
                    logger.error(f"Error in subscriber for '{topic}': {e}", exc_info=True)
            tasks.append(asyncio.create_task(safe_call()))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    @property
    def topics(self) -> list:
        """List all active topics."""
        return list(self._subscribers.keys())


# Global singleton
event_bus = EventBus()
