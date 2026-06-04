"""
Dorothy OS v2.0 — Head Agent Command Architecture

DESIGN: Military Command Structure
─────────────────────────────────────────────────────────────
HEAD AGENT (General)
  • Always listening — never sleeps
  • First to respond — no waiting
  • Instantly speaks/acknowledges the command
  • Dispatches tasks to Employee Agents in background
  • Receives results and narrates completion

EMPLOYEE AGENTS (Specialists)
  • File Agent    → filesystem operations
  • System Agent  → volume, brightness, power, terminal
  • Desktop Agent → open/close apps, windows
  • Browser Agent → open URLs, web automation
  • Vision Agent  → webcam, screenshot, screen click
  • Research Agent→ public APIs, data fetch
  • Voice Agent   → TTS synthesis
  • Backend Agent → background tasks, maintenance
  • Security Agent→ biometrics, audit
  • Windows Agent → Win32, PyAutoGUI, low-level OS

SPEED PRINCIPLES:
  1. Head Agent NEVER waits for employees to finish before responding
  2. Employee agents run as asyncio background tasks
  3. Head Agent streams response tokens WHILE employees work
  4. Tool results are narrated AFTER execution — non-blocking
─────────────────────────────────────────────────────────────
"""

import asyncio
import json
import logging
import json
import time
from typing import Dict, Any, List, Optional, TypedDict

from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig

from api.llm_service import LLMService
from tools.registry import execute_tool, TOOL_AGENT_MAP, TOOL_SCHEMAS

logger = logging.getLogger("Dorothy.HeadAgent")

# ─── Shared Agent State ───────────────────────────────────────────────────────

class AgentState(TypedDict):
    session_id: str
    user_query: str
    conversation_history: List[Dict[str, str]]
    cognitive_logs: List[str]
    tool_results: List[Dict[str, Any]]
    next_agent: str
    action_result: Optional[Dict[str, Any]]
    response_tokens: str
    pending_tool_calls: List[Dict[str, Any]]
    error: Optional[str]


# ─── Employee Agent Executor ──────────────────────────────────────────────────

class EmployeeAgent:
    """
    A specialist agent that executes tool calls dispatched by the Head Agent.
    Runs as a non-blocking asyncio background task.
    Reports results back via WebSocket when done.
    """

    AGENT_LABELS = {
        "file":     ("📁", "File Agent",     "Filesystem"),
        "system":   ("⚙️", "System Agent",   "System Control"),
        "desktop":  ("🖥️", "Desktop Agent",  "App Control"),
        "browser":  ("🌐", "Browser Agent",  "Web Automation"),
        "vision":   ("👁️", "Vision Agent",   "Screen Perception"),
        "research": ("🔬", "Research Agent", "Data & APIs"),
        "voice":    ("🔊", "Voice Agent",    "Speech Synthesis"),
        "backend":  ("⚙️", "Backend Agent",  "Data Pipeline"),
        "security": ("🛡️", "Security Agent", "Credentials Gate"),
        "windows":  ("🖥️", "Windows Agent",  "OS Controller"),
    }

    @classmethod
    async def execute(
        cls,
        agent_id: str,
        tool_calls: List[Dict[str, Any]],
        history: List[Dict[str, str]],
        websocket: Any,
        manager: Any,
        llm: LLMService,
    ) -> List[Dict[str, Any]]:
        """Execute all tool calls for this agent. Returns list of results."""

        icon, name, role = cls.AGENT_LABELS.get(agent_id, ("🤖", agent_id.title() + " Agent", "Specialist"))
        results = []

        for tool_call in tool_calls:
            tool_name = tool_call.get("name", "")
            tool_args = tool_call.get("args", {})

            logger.info(f"[{name}] Executing: {tool_name}({tool_args})")

            # Broadcast agent activation to HUD
            await cls._broadcast_agent_status(manager, agent_id, "working")
            await cls._send_cognitive_log(
                manager, websocket,
                f"[{icon} {name.upper()}] Executing: {tool_name}"
            )

            try:
                result = await execute_tool(tool_name, tool_args)
                results.append({"tool": tool_name, "result": result, "agent": agent_id})

                # Send tool result to UI
                await manager.send_personal({
                    "type": "chat_response",
                    "data": {
                        "type": "tool_result",
                        "data": {"tool": tool_name, "result": result}
                    }
                }, websocket)

                await cls._send_cognitive_log(
                    manager, websocket,
                    f"[{icon} {name.upper()}] ✓ {tool_name} complete"
                )

            except Exception as e:
                logger.error(f"[{name}] Tool execution failed: {e}")
                results.append({"tool": tool_name, "result": {"success": False, "error": str(e)}, "agent": agent_id})

        # Broadcast agent back to idle
        await cls._broadcast_agent_status(manager, agent_id, "idle")
        return results

    @staticmethod
    async def _broadcast_agent_status(manager: Any, agent_id: str, status: str) -> None:
        try:
            from main import update_agent_status
            await update_agent_status(agent_id, status)
        except Exception:
            pass

    @staticmethod
    async def _send_cognitive_log(manager: Any, websocket: Any, log: str) -> None:
        try:
            await manager.send_personal({"type": "cognitive_log", "content": log}, websocket)
        except Exception:
            pass


# ─── Head Agent Node ──────────────────────────────────────────────────────────

async def head_agent_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """
    THE MAIN BRAIN — Head Agent.

    Always-on command center. Responds instantly. Dispatches to employee
    agents as fire-and-forget background tasks. Never blocks on them.

    Flow:
    1. Check Layer 1 fast-path (already executed actions)
    2. Detect if tools are needed → dispatch employee agents in background
    3. Stream direct response to user WITHOUT waiting for employees
    4. Employees run in parallel, report back independently
    """

    cognitive_logs = list(state.get("cognitive_logs", []))
    history = list(state.get("conversation_history", []))

    configurable = config.get("configurable", {})
    llm: LLMService = configurable.get("llm")
    websocket = configurable.get("websocket")
    manager = configurable.get("manager")

    user_query = state.get("user_query", "")

    # ── FAST PATH: Layer 1 action already executed (or compute it now if None) ──
    action_result = state.get("action_result")
    if not action_result:
        from orchestrator.action_executor import execute_intent
        action_result = await execute_intent(user_query)
        if action_result:
            state["action_result"] = action_result
            # Set the agent status to working
            agent_id = action_result.get("agent_id", "system")
            try:
                from main import update_agent_status
                await update_agent_status(agent_id, "working")
            except Exception:
                pass

    action_result = state.get("action_result")
    if action_result:
        cognitive_logs.append("[HEAD] Layer 1 fast-path executed. Narrating result.")
        # Inject system context for the fast path so LLM knows it is Dorothy!
        history = await _inject_context(llm, history, user_query, cognitive_logs)
        full_response = await _narrate_action(llm, history, action_result, websocket)
        
        # Turn agent status back to idle after narration complete
        agent_id = action_result.get("agent_id", "system")
        try:
            from main import update_agent_status
            await update_agent_status(agent_id, "idle")
        except Exception:
            pass

        return {
            "cognitive_logs": cognitive_logs,
            "next_agent": "end",
            "response_tokens": full_response,
            "action_result": None,
        }

    # ── INJECT SYSTEM CONTEXT ─────────────────────────────────────────────────
    cognitive_logs.append("[HEAD] Loading context and memory...")
    history = await _inject_context(llm, history, user_query, cognitive_logs)

    # ── TOOL DETECTION: Does this need an employee agent? ─────────────────────
    # STEP 2: Use Ollama tool detection (only for complex queries)
    cognitive_logs.append("[HEAD] Scanning command for specialist routing (LLM tool check)...")
    detected_tools = []
    try:
        detected_tools = await llm.detect_tool_calls(history, TOOL_SCHEMAS)
    except Exception as e:
        logger.warning(f"Tool detection error: {e}")

    # ── CASE A: Tools needed → dispatch employees in background ──────────────
    if detected_tools:
        tool_name = detected_tools[0]["name"]
        agent_id = TOOL_AGENT_MAP.get(tool_name, "system")
        icon = EmployeeAgent.AGENT_LABELS.get(agent_id, ("🤖",))[0]
        agent_name = EmployeeAgent.AGENT_LABELS.get(agent_id, ("", tool_name.title() + " Agent"))[1]

        cognitive_logs.append(
            f"[HEAD] Routing '{tool_name}' → dispatching {agent_name.upper()} as background task"
        )

        # Append tool call to history (required for strict LLM chat formats)
        history.append({
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": f"call_{int(time.time())}_{i}",
                "type": "function",
                "function": {"name": tc["name"], "arguments": tc["args"]}
            } for i, tc in enumerate(detected_tools)]
        })

        # ✅ FIRE EMPLOYEE AGENT AS BACKGROUND TASK — HEAD AGENT DOES NOT WAIT
        asyncio.create_task(
            _run_employee_and_narrate(
                agent_id=agent_id,
                tool_calls=detected_tools,
                history=list(history),
                websocket=websocket,
                manager=manager,
                llm=llm,
            )
        )

        # Head Agent immediately acknowledges and streams its own quick response
        ack_history = list(history[:-1])  # exclude the tool_call message
        ack_history.append({
            "role": "system",
            "content": (
                f"The user said: '{user_query}'. "
                f"You have dispatched the {agent_name} to handle this. "
                f"Give a very brief 1-sentence acknowledgement that you are on it. "
                f"Be concise — the agent is already running. Don't say 'I'll' or 'I will' — say it's being done now."
            )
        })

        full_response = ""
        from main import _stream_llm_safe
        events = await _stream_llm_safe(ack_history, websocket)
        for event in events:
            if event.get("type") == "token":
                full_response += event.get("content", "")

        return {
            "cognitive_logs": cognitive_logs,
            "next_agent": "end",
            "response_tokens": full_response,
            "conversation_history": history,
        }

    # ── CASE B: No tools — direct conversation response ───────────────────────
    cognitive_logs.append("[HEAD] Conversational query. Generating direct response.")

    full_response = ""
    from main import _stream_llm_safe
    events = await _stream_llm_safe(history, websocket)
    for event in events:
        if event.get("type") == "token":
            full_response += event.get("content", "")

    return {
        "cognitive_logs": cognitive_logs,
        "next_agent": "end",
        "response_tokens": full_response,
        "conversation_history": history,
    }


# ─── Background Employee Runner ───────────────────────────────────────────────

async def _run_employee_and_narrate(
    agent_id: str,
    tool_calls: List[Dict[str, Any]],
    history: List[Dict[str, str]],
    websocket: Any,
    manager: Any,
    llm: LLMService,
) -> None:
    """
    Runs an employee agent in the background.
    After completion, narrates the result back to the user via streaming TTS.
    The Head Agent has ALREADY replied — this is purely for follow-up narration.
    """
    try:
        icon, agent_name, _ = EmployeeAgent.AGENT_LABELS.get(agent_id, ("🤖", "Agent", ""))
        logger.info(f"[BACKGROUND] {agent_name} starting task execution...")

        # Execute the tools
        results = await EmployeeAgent.execute(
            agent_id=agent_id,
            tool_calls=tool_calls,
            history=history,
            websocket=websocket,
            manager=manager,
            llm=llm,
        )

        # Build result context for narration
        result_summary = []
        for r in results:
            tool = r.get("tool", "unknown")
            res = r.get("result", {})
            success = res.get("success", True)
            msg = res.get("message", res.get("error", str(res)[:80]))
            result_summary.append(f"{tool}: {'✓' if success else '✗'} {msg}")

        # Narrate the result to the user
        narration_history = [
            *history,
            {
                "role": "system",
                "content": (
                    f"BACKGROUND TASK COMPLETE. {agent_name} finished execution. "
                    f"Results: {'; '.join(result_summary)}. "
                    f"Very briefly confirm completion in your Dorothy voice. 1 sentence max."
                )
            }
        ]

        # Stream narration tokens
        full_narration = ""
        from main import _stream_llm_safe, send_tts
        events = await _stream_llm_safe(narration_history, websocket)
        for event in events:
            if event.get("type") == "token":
                full_narration += event.get("content", "")

        # End marker
        await manager.send_personal(
            {"type": "chat_response", "data": {"type": "end"}},
            websocket
        )

        logger.info(f"[BACKGROUND] {agent_name} narration complete: '{full_narration[:60]}...'")

    except Exception as e:
        logger.error(f"[BACKGROUND] Employee agent error: {e}", exc_info=True)
        try:
            await manager.send_personal({
                "type": "cognitive_log",
                "content": f"[{agent_id.upper()} AGENT] ⚠️ Background task failed: {e}"
            }, websocket)
        except Exception:
            pass


# ─── Context Injection Helper ─────────────────────────────────────────────────

async def _inject_context(
    llm: LLMService,
    history: List[Dict[str, str]],
    query: str,
    cognitive_logs: List[str],
) -> List[Dict[str, str]]:
    """Inject system prompt + RAG memory into conversation history."""
    try:
        from memory.vector_store import SemanticMemoryStore
        mem = SemanticMemoryStore()
        results = await mem.search(query, limit=3)

        if results:
            cognitive_logs.append(f"[HEAD] Recalled {len(results)} memory fragment(s).")
            context = "\n".join(
                f"- [{r.get('timestamp','')[:19]}] {r.get('text','')}"
                for r in results
            )
            system_prompt = (
                f"{llm.system_prompt}\n\n"
                f"=== LONG-TERM MEMORY ===\n{context}\n========================"
            )
        else:
            system_prompt = llm.system_prompt

    except Exception as e:
        logger.debug(f"Memory retrieval skipped: {e}")
        system_prompt = llm.system_prompt

    history.insert(0, {"role": "system", "content": system_prompt})
    return history


async def _narrate_action(
    llm: LLMService,
    history: List[Dict[str, str]],
    action_result: Dict[str, Any],
    websocket: Any,
) -> str:
    """Narrate a completed Layer 1 fast-path action."""
    narr_history = list(history)
    narr_history.append({
        "role": "system",
        "content": (
            f"ACTION EXECUTED: {action_result.get('action')}. "
            f"Result: {action_result.get('message', 'Done')}. "
            f"Confirm this in your Dorothy voice. Be brief."
        )
    })
    full_response = ""
    from main import _stream_llm_safe
    events = await _stream_llm_safe(narr_history, websocket)
    for event in events:
        if event.get("type") == "token":
            full_response += event.get("content", "")
    return full_response


# ─── Specialist Agent Nodes (Thin Wrappers → EmployeeAgent) ──────────────────

def _make_agent_node(agent_id: str):
    """Factory: creates a LangGraph node function for any employee agent."""
    async def node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
        configurable = config.get("configurable", {})
        websocket = configurable.get("websocket")
        manager = configurable.get("manager")
        llm = configurable.get("llm")
        history = list(state.get("conversation_history", []))
        pending = state.get("pending_tool_calls", [])
        cognitive_logs = list(state.get("cognitive_logs", []))

        results = await EmployeeAgent.execute(
            agent_id=agent_id,
            tool_calls=pending,
            history=history,
            websocket=websocket,
            manager=manager,
            llm=llm,
        )

        tool_results = list(state.get("tool_results", [])) + results
        return {
            "cognitive_logs": cognitive_logs,
            "tool_results": tool_results,
            "pending_tool_calls": [],
            "next_agent": "head",
        }
    node.__name__ = f"{agent_id}_agent_node"
    return node


# ─── LangGraph Build & Compile ────────────────────────────────────────────────

def build_workflow() -> StateGraph:
    wf = StateGraph(AgentState)

    # Head Agent — the always-on brain
    wf.add_node("head", head_agent_node)

    # Employee Agents — thin tool executors
    agents = ["file", "system", "desktop", "browser", "vision",
              "research", "voice", "backend", "security", "windows"]
    for a in agents:
        wf.add_node(a, _make_agent_node(a))

    # Entry point is always Head Agent
    wf.set_entry_point("head")

    # Head Agent routes to the right employee or terminates
    wf.add_conditional_edges(
        "head",
        lambda s: s.get("next_agent", "end"),
        {a: a for a in agents} | {"end": END}
    )

    # All employees return to Head Agent for narration
    for a in agents:
        wf.add_edge(a, "head")

    return wf


dorothy_graph = build_workflow().compile()
logger.info("✓ Dorothy Head Agent graph compiled. Command structure online.")
