import asyncio
import logging
from typing import Dict, Set, Callable, Any, Awaitable

logger = logging.getLogger("JARVIS.EventBus")

class EventBus:
    def __init__(self):
        self._subscribers: Dict[str, Set[Callable[[Any], Awaitable[None]]]] = {}

    def subscribe(self, topic: str, callback: Callable[[Any], Awaitable[None]]):
        if topic not in self._subscribers:
            self._subscribers[topic] = set()
        self._subscribers[topic].add(callback)
        logger.debug(f"Subscribed callback to topic: {topic}")

    def unsubscribe(self, topic: str, callback: Callable[[Any], Awaitable[None]]):
        if topic in self._subscribers:
            self._subscribers[topic].discard(callback)
            if not self._subscribers[topic]:
                del self._subscribers[topic]
            logger.debug(f"Unsubscribed callback from topic: {topic}")

    async def publish(self, topic: str, data: Any):
        if topic not in self._subscribers:
            return
        
        # Wrap execution in try-except so a single failing subscriber does not break others
        tasks = []
        for callback in list(self._subscribers[topic]):
            async def safe_cb(cb=callback, payload=data):
                try:
                    await cb(payload)
                except Exception as e:
                    logger.error(f"Error executing callback for topic '{topic}': {e}", exc_info=True)
            tasks.append(asyncio.create_task(safe_cb()))
            
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

# Global singleton event bus
event_bus = EventBus()
