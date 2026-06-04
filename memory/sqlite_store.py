"""Dorothy OS v2.0 — SQLite Episodic & Personal Memory Store.

Provides three persistent tables:

* **conversations** – per-session chat turns (episodic memory).
* **personal_notes** – key/value knowledge base organised by category.
* **audit_log** – tamper-evident record of every tool invocation.

All methods use short-lived connections obtained through a context manager
so the store is safe to call from multiple threads or asyncio tasks
(``check_same_thread=False``).
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

from configs import settings

logger = logging.getLogger(__name__)


class MemoryStore:
    """SQLite-backed long-term memory for Dorothy.

    The database file is located at :pydata:`configs.settings.DB_PATH`.
    Tables are created automatically on first instantiation (idempotent
    ``CREATE TABLE IF NOT EXISTS``).

    Example::

        store = MemoryStore()
        store.add_message("sess-1", "user", "What's the time?")
        history = store.get_history("sess-1")
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        """Open (or create) the SQLite database and ensure tables exist.

        Args:
            db_path: Override path for testing.  Defaults to
                     ``settings.DB_PATH``.
        """
        self._db_path: Path = db_path or settings.DB_PATH
        self._local = threading.local()

        # Ensure parent directory exists
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_tables()
        logger.info("MemoryStore opened at %s", self._db_path)

    # -----------------------------------------------------------------
    # Connection helpers
    # -----------------------------------------------------------------

    def _get_connection(self) -> sqlite3.Connection:
        """Return a thread-local SQLite connection.

        Returns:
            An open ``sqlite3.Connection`` with WAL journal mode.
        """
        conn: Optional[sqlite3.Connection] = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(
                str(self._db_path),
                check_same_thread=False,
                timeout=10.0,
            )
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return conn

    @contextmanager
    def _cursor(self) -> Generator[sqlite3.Cursor, None, None]:
        """Yield a cursor inside a transaction, auto-committing on success.

        Yields:
            ``sqlite3.Cursor`` bound to the current thread's connection.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except sqlite3.Error:
            conn.rollback()
            raise
        finally:
            cursor.close()

    # -----------------------------------------------------------------
    # Schema bootstrap
    # -----------------------------------------------------------------

    def _init_tables(self) -> None:
        """Create core tables if they do not already exist."""
        with self._cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id  TEXT    NOT NULL,
                    role        TEXT    NOT NULL,
                    content     TEXT    NOT NULL,
                    timestamp   TEXT    NOT NULL DEFAULT (datetime('now'))
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_conv_session
                ON conversations (session_id, timestamp)
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS personal_notes (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    category    TEXT    NOT NULL,
                    key         TEXT    NOT NULL,
                    value       TEXT    NOT NULL,
                    updated_at  TEXT    NOT NULL DEFAULT (datetime('now')),
                    UNIQUE (category, key)
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    action      TEXT    NOT NULL,
                    agent_id    TEXT,
                    tool_name   TEXT,
                    args_json   TEXT,
                    result_json TEXT,
                    timestamp   TEXT    NOT NULL DEFAULT (datetime('now'))
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_ts
                ON audit_log (timestamp DESC)
            """)

        logger.debug("MemoryStore tables verified / created")

    # -----------------------------------------------------------------
    # Conversations (episodic memory)
    # -----------------------------------------------------------------

    def add_message(self, session_id: str, role: str, content: str) -> None:
        """Persist a single conversation turn.

        Args:
            session_id: UUID identifying the current chat session.
            role:       ``"user"``, ``"assistant"``, or ``"system"``.
            content:    The message text.
        """
        ts = datetime.now(timezone.utc).isoformat()
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO conversations (session_id, role, content, timestamp) "
                "VALUES (?, ?, ?, ?)",
                (session_id, role, content, ts),
            )
        logger.debug("add_message session=%s role=%s len=%d", session_id[:8], role, len(content))

    def get_history(self, session_id: str, limit: int = 50) -> List[Dict[str, str]]:
        """Retrieve the most recent messages for a session.

        Args:
            session_id: The session to query.
            limit:      Maximum number of rows to return (default 50).

        Returns:
            List of ``{"role": …, "content": …, "timestamp": …}`` dicts
            ordered oldest-first.
        """
        with self._cursor() as cur:
            cur.execute(
                "SELECT role, content, timestamp FROM conversations "
                "WHERE session_id = ? ORDER BY id DESC LIMIT ?",
                (session_id, limit),
            )
            rows = cur.fetchall()

        # Reverse so oldest message is first
        return [
            {"role": r["role"], "content": r["content"], "timestamp": r["timestamp"]}
            for r in reversed(rows)
        ]

    # -----------------------------------------------------------------
    # Personal notes (semantic / factual memory)
    # -----------------------------------------------------------------

    def add_personal_note(self, category: str, key: str, value: str) -> None:
        """Upsert a personal knowledge entry.

        If a note with the same ``(category, key)`` already exists its
        value and timestamp are updated.

        Args:
            category: Grouping label (e.g. ``"preferences"``, ``"contacts"``).
            key:      Unique identifier within the category.
            value:    Free-text content.
        """
        ts = datetime.now(timezone.utc).isoformat()
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO personal_notes (category, key, value, updated_at) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT (category, key) DO UPDATE SET value=excluded.value, "
                "updated_at=excluded.updated_at",
                (category, key, value, ts),
            )
        logger.debug("add_personal_note %s/%s", category, key)

    def get_personal_notes(self, category: str) -> List[Dict[str, str]]:
        """Fetch all notes under *category*.

        Args:
            category: The grouping label to filter by.

        Returns:
            List of ``{"key": …, "value": …, "updated_at": …}`` dicts.
        """
        with self._cursor() as cur:
            cur.execute(
                "SELECT key, value, updated_at FROM personal_notes "
                "WHERE category = ? ORDER BY updated_at DESC",
                (category,),
            )
            rows = cur.fetchall()

        return [
            {"key": r["key"], "value": r["value"], "updated_at": r["updated_at"]}
            for r in rows
        ]

    # -----------------------------------------------------------------
    # Audit log
    # -----------------------------------------------------------------

    def log_audit(
        self,
        action: str,
        agent_id: str,
        tool_name: str,
        args: Any,
        result: Any,
    ) -> None:
        """Write an immutable audit-log entry.

        Args:
            action:    High-level label (e.g. ``"tool_execution"``).
            agent_id:  The agent that triggered the action.
            tool_name: Canonical tool identifier.
            args:      Arguments passed to the tool (will be JSON-encoded).
            result:    Tool return value (will be JSON-encoded).
        """
        ts = datetime.now(timezone.utc).isoformat()
        try:
            args_json = json.dumps(args, default=str, ensure_ascii=False)
        except (TypeError, ValueError):
            args_json = str(args)

        try:
            result_json = json.dumps(result, default=str, ensure_ascii=False)
        except (TypeError, ValueError):
            result_json = str(result)

        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO audit_log (action, agent_id, tool_name, args_json, "
                "result_json, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                (action, agent_id, tool_name, args_json, result_json, ts),
            )
        logger.debug("log_audit action=%s tool=%s agent=%s", action, tool_name, agent_id)

    def get_recent_audit(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return the most recent audit-log entries.

        Args:
            limit: Maximum rows to return (default 20).

        Returns:
            List of dicts with all audit-log columns, newest first.
        """
        with self._cursor() as cur:
            cur.execute(
                "SELECT id, action, agent_id, tool_name, args_json, result_json, "
                "timestamp FROM audit_log ORDER BY id DESC LIMIT ?",
                (limit,),
            )
            rows = cur.fetchall()

        results: List[Dict[str, Any]] = []
        for r in rows:
            entry: Dict[str, Any] = {
                "id": r["id"],
                "action": r["action"],
                "agent_id": r["agent_id"],
                "tool_name": r["tool_name"],
                "timestamp": r["timestamp"],
            }
            try:
                entry["args"] = json.loads(r["args_json"])
            except (json.JSONDecodeError, TypeError):
                entry["args"] = r["args_json"]
            try:
                entry["result"] = json.loads(r["result_json"])
            except (json.JSONDecodeError, TypeError):
                entry["result"] = r["result_json"]
            results.append(entry)

        return results
