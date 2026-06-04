"""Dorothy OS v2.0 — Shared Execution Context.

Every user query flows through the system wrapped in an ``ExecutionContext``.
This object is created once at the orchestrator entry-point and passed
through the intent router → supervisor → agent pipeline, accumulating
cognitive logs, tool results, and metadata along the way.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ExecutionContext:
    """Immutable-ish bag of state that travels with a single user request.

    Attributes:
        session_id:           UUID4 string unique to this request.
        user_query:           The raw text the user typed or spoke.
        conversation_history: List of prior ``{"role": …, "content": …}``
                              dicts for the current session.
        intent_match:         Populated by the IntentRouter (may be ``None``
                              if no regex pattern fired).
        routed_agent:         Agent ID selected by the supervisor.
        tool_results:         Ordered list of ``{"tool": …, "result": …}``
                              dicts produced during execution.
        cognitive_logs:       Internal reasoning / chain-of-thought entries
                              used for debugging and the HUD.
        start_time:           ``time.perf_counter()`` snapshot taken at
                              context creation.
        metadata:             Free-form dict for agent-specific extras.
    """

    session_id: str
    user_query: str
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    intent_match: Optional[Any] = None
    routed_agent: Optional[str] = None
    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    cognitive_logs: List[str] = field(default_factory=list)
    start_time: float = field(default_factory=time.perf_counter)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # -----------------------------------------------------------------
    # Factory
    # -----------------------------------------------------------------

    @classmethod
    def create(
        cls,
        user_query: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> ExecutionContext:
        """Build a new context with a fresh UUID and timestamp.

        Args:
            user_query: Raw user input string.
            history:    Optional list of previous conversation turns.  If
                        ``None`` an empty list is used.

        Returns:
            A fully initialised ``ExecutionContext`` ready for the
            orchestrator pipeline.
        """
        ctx = cls(
            session_id=uuid.uuid4().hex,
            user_query=user_query,
            conversation_history=list(history) if history else [],
            start_time=time.perf_counter(),
        )
        logger.debug(
            "ExecutionContext created — session=%s query=%r",
            ctx.session_id,
            ctx.user_query[:80],
        )
        return ctx

    # -----------------------------------------------------------------
    # Mutators
    # -----------------------------------------------------------------

    def add_cognitive_log(self, message: str) -> None:
        """Append a reasoning / chain-of-thought entry.

        Args:
            message: Free-text log line (e.g. ``"Classified intent as open_app"``).
        """
        stamped = f"[{self.elapsed_ms:.1f}ms] {message}"
        self.cognitive_logs.append(stamped)
        logger.debug("CogLog [%s]: %s", self.session_id[:8], stamped)

    def add_tool_result(self, tool_name: str, result: Any) -> None:
        """Record the output of a tool invocation.

        Args:
            tool_name: Canonical tool identifier (e.g. ``"open_application"``).
            result:    Arbitrary result payload — serialised to the audit log
                       later.
        """
        entry: Dict[str, Any] = {
            "tool": tool_name,
            "result": result,
            "elapsed_ms": round(self.elapsed_ms, 2),
        }
        self.tool_results.append(entry)
        logger.debug(
            "ToolResult [%s]: %s → %s",
            self.session_id[:8],
            tool_name,
            str(result)[:120],
        )

    # -----------------------------------------------------------------
    # Properties
    # -----------------------------------------------------------------

    @property
    def elapsed_ms(self) -> float:
        """Milliseconds elapsed since this context was created.

        Returns:
            Wall-clock delta in milliseconds (float).
        """
        return (time.perf_counter() - self.start_time) * 1_000.0
