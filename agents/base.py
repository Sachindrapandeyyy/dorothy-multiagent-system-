"""Dorothy OS v2.0 — Abstract Base Agent.

Every agent in the Dorothy ecosystem inherits from ``BaseAgent``.  It
establishes the contract for:

* Identity properties (``agent_id``, ``name``, ``icon``).
* Tool capability declaration (``supported_tools``).
* The async streaming ``process()`` entry-point that the supervisor calls.
* Lifecycle state tracking via ``AgentState``.
"""

from __future__ import annotations

import abc
import logging
from typing import Any, AsyncGenerator, Dict, List

from orchestrator.supervisor import AgentState

logger = logging.getLogger(__name__)


class BaseAgent(abc.ABC):
    """Abstract base class for all Dorothy agents.

    Subclasses must implement :meth:`process` and set the four identity
    attributes either as class variables or via ``__init__``.

    Attributes:
        agent_id:        Unique string identifier (e.g. ``"desktop_agent"``).
        name:            Human-readable display name.
        description:     One-line description shown in the HUD / help.
        icon:            Single emoji used in the HUD.
        supported_tools: List of canonical tool names this agent can invoke.
    """

    agent_id: str = ""
    name: str = ""
    description: str = ""
    icon: str = "🤖"
    supported_tools: List[str] = []

    def __init__(self) -> None:
        """Initialise the agent with an ``IDLE`` state."""
        self._state: AgentState = AgentState.IDLE
        logger.debug("Agent initialised: %s (%s)", self.agent_id, self.name)

    # -----------------------------------------------------------------
    # Abstract interface
    # -----------------------------------------------------------------

    @abc.abstractmethod
    async def process(self, context: Any) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute the agent's logic for the given context.

        This is a streaming interface — the agent yields one or more dicts
        as it progresses.  Typical chunk shapes::

            {"type": "status",  "message": "Opening Chrome…"}
            {"type": "result",  "data": {…}}
            {"type": "error",   "message": "File not found"}

        Args:
            context: An ``ExecutionContext`` instance.

        Yields:
            Progress / result dicts consumed by the supervisor and HUD.
        """
        # Pragma: abstract — yield is required to make this an AsyncGenerator.
        yield {}  # type: ignore[misc]  # pragma: no cover

    # -----------------------------------------------------------------
    # Concrete helpers
    # -----------------------------------------------------------------

    def can_handle(self, tool_name: str) -> bool:
        """Check whether this agent supports *tool_name*.

        Args:
            tool_name: Canonical tool identifier (e.g. ``"open_application"``).

        Returns:
            ``True`` if the tool is in ``supported_tools``, ``False``
            otherwise.
        """
        return tool_name in self.supported_tools

    def get_status(self) -> Dict[str, str]:
        """Return a serialisable snapshot of this agent's identity and state.

        Returns:
            Dict with keys ``agent_id``, ``name``, ``icon``, ``state``.
        """
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "icon": self.icon,
            "state": self._state.value,
        }

    # -----------------------------------------------------------------
    # State helpers
    # -----------------------------------------------------------------

    @property
    def state(self) -> AgentState:
        """Current lifecycle state of this agent."""
        return self._state

    @state.setter
    def state(self, new_state: AgentState) -> None:
        """Transition to *new_state* with a debug log."""
        old = self._state
        self._state = new_state
        logger.debug("Agent %s: %s → %s", self.agent_id, old.value, new_state.value)
