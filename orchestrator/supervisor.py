"""
Dorothy OS v2.0 — Supervisor: Head Agent Lifecycle Manager

The Supervisor wraps the Head Agent's LangGraph execution.
Head Agent = always-on general. Employee agents = background specialists.
"""

from __future__ import annotations

import asyncio
import enum
import logging
from typing import Any, Dict, List, Optional

from orchestrator.graph import dorothy_graph, AgentState
from orchestrator.intent_router import IntentRouter

_intent_router = IntentRouter()  # singleton — compiled once at import

logger = logging.getLogger("Dorothy.Supervisor")


class AgentStateEnum(enum.Enum):
    IDLE     = "idle"
    THINKING = "thinking"
    WORKING  = "working"
    ERROR    = "error"
    OFFLINE  = "offline"


class SupervisorAgent:
    """
    Manages Head Agent lifecycle and state telemetry for the front-end HUD.
    Head Agent is always first to respond — employees run in background.
    """

    EMPLOYEE_AGENTS = [
        "file", "system", "desktop", "browser",
        "vision", "research", "voice", "backend", "security", "windows"
    ]

    def __init__(self, llm: Any) -> None:
        self.llm = llm
        self._states: Dict[str, AgentStateEnum] = {
            "lead": AgentStateEnum.IDLE,
            **{a: AgentStateEnum.IDLE for a in self.EMPLOYEE_AGENTS}
        }
        logger.info("✓ SupervisorAgent ready. Head Agent online, employees standing by.")

    def update_agent_status(self, agent_id: str, status: AgentStateEnum) -> None:
        if agent_id in self._states:
            self._states[agent_id] = status

    async def execute_graph(
        self,
        query: str,
        history: List[Dict[str, str]],
        websocket: Any,
        manager: Any,
        action_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Runs the Head Agent. Head Agent responds immediately, dispatches
        employee agents as fire-and-forget background tasks.
        """

        initial_state: AgentState = {
            "session_id":            getattr(websocket, "id", "ws_session"),
            "user_query":            query,
            "conversation_history":  history,
            "cognitive_logs":        [f"[HEAD] Command received: '{query}'"],
            "tool_results":          [],
            "next_agent":            "head",
            "action_result":         action_result,
            "response_tokens":       "",
            "pending_tool_calls":    [],
            "error":                 None,
        }

        config = {
            "configurable": {
                "llm":       self.llm,
                "websocket": websocket,
                "manager":   manager,
            }
        }

        # Head Agent is now THINKING
        self.update_agent_status("lead", AgentStateEnum.THINKING)

        try:
            final_state = await dorothy_graph.ainvoke(initial_state, config)
            self.update_agent_status("lead", AgentStateEnum.IDLE)
            return final_state
        except Exception as exc:
            logger.exception("Head Agent graph execution failed")
            self.update_agent_status("lead", AgentStateEnum.ERROR)
            return {
                **initial_state,
                "error": str(exc),
                "cognitive_logs": initial_state["cognitive_logs"] + [f"[ERROR] {exc}"],
            }
        finally:
            # Head Agent always returns to IDLE — employees manage their own state
            self.update_agent_status("lead", AgentStateEnum.IDLE)

    def get_status_report(self) -> Dict[str, Any]:
        return {
            "head_agent": self._states.get("lead", AgentStateEnum.IDLE).value,
            "employees":  {a: self._states[a].value for a in self.EMPLOYEE_AGENTS},
        }
