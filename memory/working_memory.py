"""Dorothy OS v2.0 — Working Memory (In-Process Session State).

``WorkingMemory`` is a lightweight, singleton key-value store that lives
for the duration of the process.  It also maintains a bounded conversation
buffer (last *N* messages) so agents can read recent context without
hitting SQLite.

Thread-safety is provided by a ``threading.Lock`` on every mutation.
"""

from __future__ import annotations

import logging
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional

logger = logging.getLogger(__name__)

_MAX_BUFFER_SIZE: int = 50
"""Maximum number of messages kept in the conversation buffer."""


class WorkingMemory:
    """Singleton in-process key-value store with a conversation buffer.

    Usage::

        mem = WorkingMemory()       # always returns the same instance
        mem.set("current_app", "chrome")
        print(mem.get("current_app"))

        mem.add_to_buffer("user", "Open Chrome")
        print(mem.get_conversation_buffer())
    """

    _instance: Optional[WorkingMemory] = None
    _init_done: bool = False

    # -----------------------------------------------------------------
    # Singleton
    # -----------------------------------------------------------------

    def __new__(cls) -> WorkingMemory:
        """Return the existing singleton instance, or create one."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialise internal stores (runs only once)."""
        if WorkingMemory._init_done:
            return
        WorkingMemory._init_done = True

        self._store: Dict[str, Any] = {}
        self._buffer: Deque[Dict[str, str]] = deque(maxlen=_MAX_BUFFER_SIZE)
        self._lock: threading.Lock = threading.Lock()
        logger.debug("WorkingMemory singleton initialised (buffer max=%d)", _MAX_BUFFER_SIZE)

    # -----------------------------------------------------------------
    # Key-value API
    # -----------------------------------------------------------------

    def set(self, key: str, value: Any) -> None:
        """Store *value* under *key*, overwriting any previous entry.

        Args:
            key:   String key.
            value: Arbitrary Python object.
        """
        with self._lock:
            self._store[key] = value
        logger.debug("WorkingMemory.set %s = %s", key, str(value)[:80])

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve the value for *key*, or *default* if absent.

        Args:
            key:     String key.
            default: Fallback value (default ``None``).

        Returns:
            The stored value, or *default*.
        """
        with self._lock:
            return self._store.get(key, default)

    def delete(self, key: str) -> None:
        """Remove *key* from the store (no-op if absent).

        Args:
            key: String key to remove.
        """
        with self._lock:
            self._store.pop(key, None)
        logger.debug("WorkingMemory.delete %s", key)

    # -----------------------------------------------------------------
    # Conversation buffer
    # -----------------------------------------------------------------

    def add_to_buffer(self, role: str, content: str) -> None:
        """Append a message to the bounded conversation buffer.

        When the buffer exceeds ``_MAX_BUFFER_SIZE`` the oldest message
        is silently dropped.

        Args:
            role:    ``"user"``, ``"assistant"``, or ``"system"``.
            content: Message text.
        """
        entry: Dict[str, str] = {
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            self._buffer.append(entry)
        logger.debug(
            "WorkingMemory.add_to_buffer role=%s len=%d buffer_size=%d",
            role,
            len(content),
            len(self._buffer),
        )

    def get_conversation_buffer(self) -> List[Dict[str, str]]:
        """Return a snapshot of the current conversation buffer.

        Returns:
            List of ``{"role": …, "content": …, "timestamp": …}`` dicts
            ordered oldest-first.
        """
        with self._lock:
            return list(self._buffer)

    # -----------------------------------------------------------------
    # Housekeeping
    # -----------------------------------------------------------------

    def clear(self) -> None:
        """Wipe both the key-value store and the conversation buffer."""
        with self._lock:
            self._store.clear()
            self._buffer.clear()
        logger.info("WorkingMemory cleared")
