"""
Dorothy OS v2.0 — Main Server Entry Point
FastAPI application with WebSocket streaming, REST endpoints, and system telemetry broadcasting.
"""

import os
import sys
import json
import asyncio
import logging
import httpx
from contextlib import asynccontextmanager
from typing import Dict, Any, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# ─── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-30s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("Dorothy.Main")

# ─── Configuration ────────────────────────────────────────────────────────────

from configs.settings import (
    GEMINI_API_KEY, ANTHROPIC_API_KEY, OLLAMA_BASE_URL, OLLAMA_MODEL,
    Dorothy_SYSTEM_PROMPT, AUDIO_DIR, CAPTURES_DIR,
    TTS_HINDI_VOICE, TTS_ENGLISH_VOICE,
)

# ─── Configure Tool Subsystems ────────────────────────────────────────────────

from tools.tts_tools import configure as configure_tts
from tools.vision_tools import configure as configure_vision

configure_tts(AUDIO_DIR, TTS_HINDI_VOICE, TTS_ENGLISH_VOICE)
configure_vision(CAPTURES_DIR)

# ─── Import Services ──────────────────────────────────────────────────────────

from api.websocket_manager import manager
from api.llm_service import LLMService
from api.event_bus import event_bus
from tools.registry import TOOL_SCHEMAS, execute_tool, TOOL_AGENT_MAP
from tools.system_tools import get_system_stats
from tools.tts_tools import speak
from orchestrator.action_executor import execute_intent
from orchestrator.supervisor import SupervisorAgent
from voice.voice_pipeline import voice_pipeline
from voice.stt_service import stt_service

# ─── Initialize LLM, Supervisor, and Memory Services ──────────────────────────

from memory.vector_store import SemanticMemoryStore
from datetime import datetime

llm = LLMService(
    ollama_base_url=OLLAMA_BASE_URL,
    ollama_model=OLLAMA_MODEL,
    gemini_api_key=GEMINI_API_KEY,
    anthropic_api_key=ANTHROPIC_API_KEY,
    system_prompt=Dorothy_SYSTEM_PROMPT,
)

supervisor = SupervisorAgent(llm)
memory_store = SemanticMemoryStore()


# ─── Gemini Cooldown (skip cloud for 5 min after 429) ────────────────────────

import time as _time
_gemini_cooldown_until: float = 0.0


def is_gemini_cooled_down() -> bool:
    """Check if Gemini API is past its cooldown period."""
    return _time.time() >= _gemini_cooldown_until


def set_gemini_cooldown(seconds: int = 300) -> None:
    """Set a cooldown timer to skip Gemini for the given duration."""
    global _gemini_cooldown_until
    _gemini_cooldown_until = _time.time() + seconds
    logger.warning(f"Gemini cooldown set for {seconds}s (until {_time.strftime('%H:%M:%S', _time.localtime(_gemini_cooldown_until))})")


async def get_openclaw_status() -> str:
    """Check if the OpenClaw service is online."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get("http://127.0.0.1:18789/", timeout=0.5)
            if resp.status_code == 200:
                return "online"
    except Exception:
        pass
    return "offline"


async def monitor_openclaw_loop() -> None:
    """Periodically check OpenClaw gateway status and broadcast updates on change."""
    last_status = None
    while True:
        try:
            status = await get_openclaw_status()
            if status != last_status:
                last_status = status
                await manager.broadcast({
                    "type": "connection_status",
                    "data": {
                        "service": "openclaw",
                        "status": status
                    }
                })
        except Exception as e:
            logger.error(f"OpenClaw monitor error: {e}")
        await asyncio.sleep(5)

# ─── Agent Registry ──────────────────────────────────────────────────────────

AGENTS_LIST: List[Dict[str, Any]] = [
    {"id": "lead", "name": "Dorothy Lead", "role": "Orchestrator", "icon": "🧠", "status": "idle"},
    {"id": "file", "name": "File Agent", "role": "File Operations", "icon": "📁", "status": "idle"},
    {"id": "system", "name": "System Agent", "role": "System Control", "icon": "⚙️", "status": "idle"},
    {"id": "desktop", "name": "Desktop Agent", "role": "App Control", "icon": "🖥️", "status": "idle"},
    {"id": "browser", "name": "Browser Agent", "role": "Web Automation", "icon": "🌐", "status": "idle"},
    {"id": "voice", "name": "Voice Agent", "role": "Speech Synthesis", "icon": "🔊", "status": "idle"},
    {"id": "vision", "name": "Vision Agent", "role": "Object Detection", "icon": "👁️", "status": "idle"},
    {"id": "research", "name": "Research Agent", "role": "Data & APIs", "icon": "🔬", "status": "idle"},
    {"id": "backend", "name": "Backend Agent", "role": "Data & Security", "icon": "⚙️", "status": "idle"},
    {"id": "security", "name": "Security Agent", "role": "Credentials Gate", "icon": "🛡️", "status": "idle"},
    {"id": "windows", "name": "Windows Agent", "role": "OS Controller", "icon": "🖥️", "status": "idle"},
]


async def update_agent_status(agent_id: str, status: str) -> None:
    """Update an agent's status and broadcast to all connected clients."""
    for agent in AGENTS_LIST:
        if agent["id"] == agent_id or agent["role"] == agent_id:
            agent["status"] = status
            await manager.broadcast({
                "type": "agent_status",
                "data": {"agents": AGENTS_LIST},
            })
            break


# ─── Background Tasks ────────────────────────────────────────────────────────

async def broadcast_stats_loop() -> None:
    """Continuously broadcast system telemetry to connected clients."""
    while True:
        try:
            if manager.client_count > 0:
                stats = await get_system_stats()
                await manager.broadcast({"type": "system_stats", "data": stats})
        except Exception as e:
            logger.error(f"Stats broadcast error: {e}")
        await asyncio.sleep(2)


# ─── FastAPI Lifecycle ────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    logger.info("=" * 60)
    logger.info("   Dorothy OS v2.0 — Enterprise AI Operating System")
    logger.info("=" * 60)

    # Health check Ollama
    ollama_ok = await llm.health_check()
    if ollama_ok:
        logger.info(f"✓ Ollama connected at {OLLAMA_BASE_URL} (model: {OLLAMA_MODEL})")
    else:
        logger.warning(f"✗ Ollama not reachable at {OLLAMA_BASE_URL}")

    # Start telemetry broadcast
    stats_task = asyncio.create_task(broadcast_stats_loop())
    logger.info("✓ System telemetry broadcast started (2s interval)")

    # Start OpenClaw status monitor
    openclaw_task = asyncio.create_task(monitor_openclaw_loop())
    logger.info("✓ OpenClaw connection monitor started (5s interval)")
    logger.info("✓ Action executor loaded (Layer 2 agentic)")
    
    # Start Autonomous Workflow Engine
    from workflows.engine import workflow_engine
    
    async def default_maintenance():
        logger.info("[WORKFLOW] Performing background system maintenance check.")
        import gc
        gc.collect()

    workflow_engine.register_task(
        "maintenance", 
        "System Maintenance Check", 
        "interval", 
        60.0, 
        default_maintenance,
        "Cleans up unused memory and prints runtime diagnostic diagnostics."
    )
    workflow_engine.start()
    logger.info("✓ Autonomous Workflow Engine online.")

    # Preload faster-whisper STT model in background (so first voice request is instant)
    asyncio.create_task(_preload_stt())
    logger.info("✓ faster-whisper STT model preloading in background...")
    logger.info("✓ Dorothy OS is online. Awaiting commands.")
    logger.info("=" * 60)

    yield

    stats_task.cancel()
    openclaw_task.cancel()
    workflow_engine.stop()
    logger.info("Dorothy OS shutting down.")


# ─── FastAPI App ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="Dorothy OS v2.0",
    description="Enterprise AI Operating System API",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static directories
ui_dir = os.path.join(os.path.dirname(__file__), "ui")
if os.path.isdir(ui_dir):
    app.mount("/ui", StaticFiles(directory=ui_dir), name="ui")

if os.path.isdir(AUDIO_DIR):
    app.mount("/audio", StaticFiles(directory=AUDIO_DIR), name="audio")

if os.path.isdir(CAPTURES_DIR):
    app.mount("/captures", StaticFiles(directory=CAPTURES_DIR), name="captures")


# ─── REST Endpoints ───────────────────────────────────────────────────────────

@app.get("/")
async def root():
    """Serve the Command Center UI."""
    index_path = os.path.join(ui_dir, "index.html")
    if os.path.isfile(index_path):
        return FileResponse(index_path)
    return {"status": "Dorothy OS v2.0 online", "ui": "UI not found. Place index.html in ui/"}


@app.get("/api/health")
async def health():
    """System health check endpoint."""
    ollama_ok = await llm.health_check()
    return {
        "status": "online",
        "ollama_connected": ollama_ok,
        "model": OLLAMA_MODEL,
        "gemini_configured": bool(GEMINI_API_KEY),
        "gemini_cooled_down": is_gemini_cooled_down(),
        "agents": len(AGENTS_LIST),
        "clients_connected": manager.client_count,
    }


@app.get("/api/agents")
async def get_agents():
    """Get current agent statuses."""
    return {"agents": AGENTS_LIST}


@app.get("/api/models")
async def get_models():
    """List available Ollama models."""
    models = await llm.get_models()
    return {"models": models}


# ─── TTS Helper ───────────────────────────────────────────────────────────────

async def send_tts(text: str, websocket: WebSocket) -> None:
    """Generate TTS for a text chunk and send audio to the client."""
    if len(text.strip()) < 5:
        return
    try:
        audio_path = await speak(text.strip())
        filename = os.path.basename(audio_path)
        await manager.send_personal(
            {"type": "tts_chunk", "data": {"filename": filename, "text": text.strip()}},
            websocket,
        )
    except Exception as e:
        logger.warning(f"TTS failed: {e}")


# ─── WebSocket Handler ────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Main WebSocket handler for real-time bidirectional communication."""
    await manager.connect(websocket)

    # Query OpenClaw status for the initial payload
    openclaw_status = await get_openclaw_status()

    # Send initial state
    await manager.send_personal({
        "type": "init",
        "data": {
            "agents": AGENTS_LIST,
            "model": OLLAMA_MODEL,
            "gemini": bool(GEMINI_API_KEY) and is_gemini_cooled_down(),
            "openclaw_status": openclaw_status,
        },
    }, websocket)

    # Conversation history (per-session)
    conversation_history: List[Dict[str, str]] = []

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                await manager.send_personal(
                    {"type": "error", "message": "Invalid JSON."},
                    websocket,
                )
                continue

            msg_type = message.get("type", "")
            data = message.get("data", {})

            if msg_type == "chat_message":
                user_text = data.get("message", "").strip()
                if not user_text:
                    continue

                conversation_history.append({"role": "user", "content": user_text})
                
                # Auto-save user message to semantic database
                asyncio.create_task(memory_store.add_document(
                    user_text,
                    {"role": "user", "timestamp": datetime.now().isoformat()}
                ))

                # ══════════════════════════════════════════════════════
                # LangGraph Multi-Agent Execution Flow
                # ══════════════════════════════════════════════════════

                # Fast check Layer 1 direct regex actions
                await manager.send_personal(
                    {"type": "cognitive_log", "content": "[COGNITIVE] Fast intent routing checks active..."},
                    websocket,
                )
                action_result = await execute_intent(user_text)

                if action_result:
                    action_name = action_result.get("action", "unknown")
                    agent_id = action_result.get("agent_id", "system")
                    await update_agent_status(agent_id, "working")
                    icon_map = {
                        "browser": "🌐", "desktop": "🖥️", "system": "⚙️", "vision": "👁️",
                        "file": "📁", "research": "🔬", "voice": "🔊", "backend": "⚙️",
                        "security": "🛡️", "windows": "🖥️"
                    }
                    icon = icon_map.get(agent_id, "🤖")
                    await manager.send_personal(
                        {"type": "cognitive_log", "content": f"[{icon} {agent_id.upper()} AGENT] Handing over task to execute direct command: {action_name}"},
                        websocket,
                    )
                else:
                    await manager.send_personal(
                        {"type": "cognitive_log", "content": "[COGNITIVE] Core router fall-through. Entering LangGraph Multi-Agent network."},
                        websocket,
                    )

                # Execute graph using our refactored supervisor
                final_state = await supervisor.execute_graph(
                    query=user_text,
                    history=conversation_history,
                    websocket=websocket,
                    manager=manager,
                    action_result=action_result,
                )

                # Send final cognitive logs
                for log in final_state.get("cognitive_logs", []):
                    await manager.send_personal(
                        {"type": "cognitive_log", "content": log},
                        websocket,
                    )

                # Save generated response to history
                response_tokens = final_state.get("response_tokens", "")
                if response_tokens:
                    conversation_history.append({"role": "assistant", "content": response_tokens})
                    # Auto-save assistant response to semantic database
                    asyncio.create_task(memory_store.add_document(
                        response_tokens,
                        {"role": "assistant", "timestamp": datetime.now().isoformat()}
                    ))

                # Send stream end marker
                await manager.send_personal(
                    {"type": "chat_response", "data": {"type": "end"}},
                    websocket,
                )

            elif msg_type == "command":
                action = data.get("action", "")
                if action == "get_stats":
                    stats = await get_system_stats()
                    await manager.send_personal({"type": "system_stats", "data": stats}, websocket)
                elif action == "get_agents":
                    await manager.send_personal({"type": "agent_status", "data": {"agents": AGENTS_LIST}}, websocket)
                elif action == "execute_sandbox":
                    code = data.get("code", "")
                    from security.sandbox import sandbox_executor
                    res = await sandbox_executor.execute_python(code)
                    await manager.send_personal({
                        "type": "chat_response",
                        "data": {
                            "type": "tool_result",
                            "data": {"tool": "execute_python_sandbox", "result": res}
                        }
                    }, websocket)
                elif action == "switch_model":
                    target_model = data.get("model", "")
                    if target_model in ["claude", "gemini", "ollama", "auto"]:
                        llm.active_provider = target_model
                        content = f"[SYSTEM] Active LLM Router overridden to: {target_model.upper()}"
                    else:
                        llm.ollama_model = target_model
                        content = f"[SYSTEM] Active Ollama model switched to: {target_model}"
                    
                    await manager.send_personal({
                        "type": "cognitive_log",
                        "content": content
                    }, websocket)
                    
                    # Broadcast the new state to all clients
                    await manager.broadcast({
                        "type": "model_status",
                        "data": {
                            "active_provider": getattr(llm, "active_provider", "auto"),
                            "ollama_model": llm.ollama_model
                        }
                    })
                elif action == "trigger_biometrics":
                    from security.gatekeeper import ActionClassifier
                    clf = ActionClassifier()
                    approved = await asyncio.to_thread(clf.verify_windows_hello, "Manual Biometric Challenge")
                    status = "GRANTED" if approved else "REFUSED"
                    
                    clf._log_audit_ledger("biometric_manual_trigger", {}, "ADMIN", "APPROVED" if approved else "DENIED_BY_BIOMETRICS")
                    
                    await manager.send_personal({
                        "type": "biometric_status",
                        "data": {
                            "status": status,
                            "timestamp": datetime.now().isoformat()
                        }
                    }, websocket)
                elif action == "get_processes":
                    from tools.system_tools import get_top_processes
                    procs = await get_top_processes(12)
                    await manager.send_personal({
                        "type": "processes_list",
                        "data": {"processes": procs}
                    }, websocket)
                elif action == "kill_process":
                    pid = data.get("pid")
                    import subprocess
                    try:
                        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, text=True, timeout=5)
                        res = {"success": True, "message": f"Successfully killed process PID {pid}."}
                    except Exception as e:
                        res = {"success": False, "error": str(e)}
                    await manager.send_personal({
                        "type": "kill_process_result",
                        "data": res
                    }, websocket)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        manager.disconnect(websocket)



# ─── Voice WebSocket Handler ──────────────────────────────────────────────────

@app.websocket("/ws/voice")
async def voice_websocket_endpoint(websocket: WebSocket):
    """
    Real-time voice WebSocket endpoint.
    Receives binary WAV audio from the browser, runs faster-whisper STT,
    pipes through Dorothy's brain, and streams TTS responses back.
    """
    await manager.connect(websocket)
    logger.info("Voice WebSocket client connected.")

    # Per-session conversation history (shared feel — voice and text are unified)
    conversation_history: List[Dict[str, str]] = []

    # Send initial state
    openclaw_status = await get_openclaw_status()
    await manager.send_personal({
        "type": "init",
        "data": {
            "agents": AGENTS_LIST,
            "model": OLLAMA_MODEL,
            "gemini": bool(GEMINI_API_KEY) and is_gemini_cooled_down(),
            "openclaw_status": openclaw_status,
            "voice_mode": True,
        },
    }, websocket)

    # Notify STT model is loading in background
    asyncio.create_task(_preload_stt())

    try:
        while True:
            # Receive either binary (audio) or text (control) messages
            message = await websocket.receive()

            if "bytes" in message and message["bytes"]:
                # Binary = raw WAV audio from browser mic
                audio_bytes = message["bytes"]
                logger.info(f"Voice input received: {len(audio_bytes)} bytes")

                await voice_pipeline.process_voice_input(
                    audio_bytes=audio_bytes,
                    session_id=str(id(websocket)),
                    conversation_history=conversation_history,
                    websocket=websocket,
                    manager=manager,
                    supervisor=supervisor,
                    llm=llm,
                    memory_store=memory_store,
                )

            elif "text" in message and message["text"]:
                # Text = JSON control messages (same as /ws)
                try:
                    ctrl = json.loads(message["text"])
                    ctrl_type = ctrl.get("type", "")
                    ctrl_data = ctrl.get("data", {})

                    if ctrl_type == "chat_message":
                        # Allow typing fallback on voice ws too
                        user_text = ctrl_data.get("message", "").strip()
                        if user_text:
                            conversation_history.append({"role": "user", "content": user_text})
                            action_result = await execute_intent(user_text)
                            if action_result:
                                agent_id = action_result.get("agent_id", "system")
                                await update_agent_status(agent_id, "working")
                            final_state = await supervisor.execute_graph(
                                query=user_text,
                                history=conversation_history,
                                websocket=websocket,
                                manager=manager,
                                action_result=action_result,
                            )
                            resp = final_state.get("response_tokens", "")
                            if resp:
                                conversation_history.append({"role": "assistant", "content": resp})
                            await manager.send_personal(
                                {"type": "chat_response", "data": {"type": "end"}},
                                websocket,
                            )
                    elif ctrl_type == "ping":
                        await manager.send_personal({"type": "pong"}, websocket)

                except json.JSONDecodeError:
                    pass

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("Voice WebSocket client disconnected.")
    except RuntimeError as e:
        if "disconnect" in str(e).lower():
            manager.disconnect(websocket)
        else:
            logger.error(f"Voice WebSocket runtime error: {e}", exc_info=True)
            manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Voice WebSocket error: {e}", exc_info=True)
        manager.disconnect(websocket)


async def _preload_stt():
    """Preload faster-whisper model in the background at startup for instant first response."""
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, stt_service.initialize)
    except Exception as e:
        logger.warning(f"STT preload failed: {e}")


async def _stream_llm_safe(

    conversation_history: List[Dict[str, str]],
    websocket: WebSocket,
) -> list:
    """Stream LLM response with Gemini cooldown handling and TTS."""
    events = []
    full_response = ""
    tts_buffer = ""

    # If Gemini is in cooldown, temporarily clear the key so LLM service skips it
    original_key = llm.gemini_api_key
    if not is_gemini_cooled_down():
        llm.gemini_api_key = ""

    try:
        async for event in llm.chat_stream(conversation_history, TOOL_SCHEMAS):
            event_type = event.get("type")

            if event_type == "token":
                token = event.get("content", "")
                full_response += token
                tts_buffer += token
                await manager.send_personal(
                    {"type": "chat_response", "data": {"type": "token", "content": token}},
                    websocket,
                )
                events.append(event)

                # Sentence-level TTS
                while any(sep in tts_buffer for sep in [".", "!", "?", "\n"]):
                    for sep in [".", "!", "?", "\n"]:
                        idx = tts_buffer.find(sep)
                        if idx != -1:
                            sentence = tts_buffer[:idx + 1].strip()
                            tts_buffer = tts_buffer[idx + 1:]
                            await send_tts(sentence, websocket)
                            break

            elif event_type == "thinking":
                await manager.send_personal(
                    {"type": "chat_response", "data": event},
                    websocket,
                )

            elif event_type == "cognitive_log":
                content = event.get("content", "")
                await manager.send_personal(event, websocket)
                # Detect Gemini 429 and set cooldown
                if "429" in content or "quota" in content.lower():
                    set_gemini_cooldown(300)

            elif event_type == "tool_result":
                await manager.send_personal(
                    {"type": "chat_response", "data": event},
                    websocket,
                )

            elif event_type == "error":
                err_msg = event.get("message", "")
                await manager.send_personal(
                    {"type": "chat_response", "data": event},
                    websocket,
                )
                # If error mentions 429 or quota, set cooldown
                if "429" in err_msg:
                    set_gemini_cooldown(300)

        # Flush remaining TTS
        if tts_buffer.strip():
            await send_tts(tts_buffer, websocket)

    finally:
        llm.gemini_api_key = original_key

    return events


# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )
