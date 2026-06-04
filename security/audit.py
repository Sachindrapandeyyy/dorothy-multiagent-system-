"""Dorothy OS v2.0 — Persistent Audit Logger.

Thin convenience layer over ``MemoryStore.log_audit`` that adds
security-level tagging and a dedicated ``log_security_event`` method
for non-tool events (e.g. login attempts, blocked commands).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from memory.sqlite_store import MemoryStore
from security.gatekeeper import SecurityLevel

logger = logging.getLogger(__name__)


class AuditLogger:
    """High-level audit facade backed by :class:`MemoryStore`.

    Example::

        audit = AuditLogger()
        audit.log_tool_execution(
            agent_id="desktop_agent",
            tool_name="open_application",
            args={"app": "chrome"},
            result={"status": "ok"},
            security_level=SecurityLevel.CONFIRM,
        )
    """

    def __init__(self, store: Optional[MemoryStore] = None) -> None:
        """Initialise with an optional pre-existing store.

        Args:
            store: Shared ``MemoryStore`` instance.  If ``None`` a new
                   one is created (which is fine — SQLite handles
                   concurrent writers via WAL).
        """
        self._store: MemoryStore = store or MemoryStore()
        logger.debug("AuditLogger initialised")

    # -----------------------------------------------------------------
    # Tool execution logging
    # -----------------------------------------------------------------

    def log_tool_execution(
        self,
        agent_id: str,
        tool_name: str,
        args: Any,
        result: Any,
        security_level: SecurityLevel,
    ) -> None:
        """Record a tool invocation in the audit trail.

        Args:
            agent_id:       Agent that triggered the tool.
            tool_name:      Canonical tool identifier.
            args:           Arguments passed to the tool.
            result:         Return value of the tool.
            security_level: Classification assigned by the gatekeeper.
        """
        enriched_args: Dict[str, Any] = {
            "tool_args": args,
            "security_level": security_level.name,
            "security_value": security_level.value,
        }

        self._store.log_audit(
            action="tool_execution",
            agent_id=agent_id,
            tool_name=tool_name,
            args=enriched_args,
            result=result,
        )
        logger.info(
            "Audit ▸ tool_execution: agent=%s tool=%s level=%s",
            agent_id,
            tool_name,
            security_level.name,
        )

    # -----------------------------------------------------------------
    # Security event logging
    # -----------------------------------------------------------------

    def log_security_event(self, event_type: str, details: Any) -> None:
        """Log a security-related event that is *not* a tool execution.

        Examples of security events:

        * ``blocked_command`` — a command matched the deny-list.
        * ``auth_failure``   — a password / biometric check failed.
        * ``escalation``     — an action was escalated from CONFIRM to ADMIN.

        Args:
            event_type: Short label describing the event category.
            details:    Arbitrary payload with contextual information.
        """
        self._store.log_audit(
            action=f"security_event:{event_type}",
            agent_id="gatekeeper",
            tool_name="",
            args={"event_type": event_type},
            result=details,
        )
        logger.warning("Audit ▸ security_event: type=%s details=%s", event_type, str(details)[:200])

    # -----------------------------------------------------------------
    # Retrieval
    # -----------------------------------------------------------------

    def get_recent_events(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return the *limit* most recent audit entries.

        Args:
            limit: Maximum number of entries (default 20).

        Returns:
            List of audit dicts, newest first.
        """
        return self._store.get_recent_audit(limit=limit)
