import os
import sys
import json
import logging
import asyncio

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from contextlib import asynccontextmanager
from typing import Dict, Any, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from backend.config import OLLAMA_MODEL, TTS_OUTPUT_DIR
from backend.models.schemas import HealthResponse, ModelListResponse, ModelInfo
from backend.services.websocket_manager import manager
from backend.services.ollama_service import OllamaService, execute_tool
from backend.tools.system_tools import get_system_stats, set_system_volume, set_system_brightness, toggle_wifi
from backend.tools.app_tools import trigger_media_control
from backend.tools.tts_tools import speak, detect_language

# Setup logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("JARVIS.Main")

# Global instances
from backend.agents.lead_agent import LeadAgent
ollama_service = OllamaService()
lead_agent = LeadAgent()

# Agent Status default list
AGENTS_LIST = [
    {"name": "JARVIS Lead", "role": "Orchestrator", "status": "idle", "icon": "🎯"},
    {"name": "File Agent", "role": "File Operations", "status": "idle", "icon": "📁"},
    {"name": "System Agent", "role": "System Control", "status": "idle", "icon": "⚙️"},
    {"name": "Code Agent", "role": "Code Generation", "status": "idle", "icon": "💻"},
    {"name": "Web Agent", "role": "Web Search", "status": "idle", "icon": "🌐"},
    {"name": "Comms Agent", "role": "Messaging", "status": "idle", "icon": "📱"}
]

# Map specific tools to agent roles for interactive status updates
TOOL_AGENT_MAP = {
    "read_file": "File Operations",
    "write_file": "File Operations",
    "create_file": "File Operations",
    "list_directory": "File Operations",
    "delete_file": "File Operations",
    "move_file": "File Operations",
    "copy_file": "File Operations",
    "search_files": "File Operations",
    
    "get_system_stats": "System Control",
    "get_top_processes": "System Control",
    "execute_terminal": "System Control",
    "open_application": "System Control",
    "close_application": "System Control",
    "list_running_apps": "System Control",
    
    "tts_speak": "Messaging"
}

def get_agent_role_for_tool(tool_name: str) -> str:
    return TOOL_AGENT_MAP.get(tool_name, "Orchestrator")

async def update_agent_status_and_broadcast(role: str, status: str):
    """Update status of a sub-agent and broadcast the update to all clients."""
    for agent in AGENTS_LIST:
        if agent["role"] == role:
            agent["status"] = status
            break
    await manager.broadcast({
        "type": "agent_status",
        "data": {"agents": AGENTS_LIST}
    })

async def broadcast_stats_loop():
    """Background loop to broadcast system statistics every 2 seconds."""
    logger.info("System stats broadcast loop started.")
    while True:
        try:
            stats = await get_system_stats()
            await manager.broadcast({
                "type": "system_stats",
                "data": stats
            })
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in broadcast stats loop: {e}", exc_info=True)
        await asyncio.sleep(2.0)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    logger.info("Initializing JARVIS core subsystems...")
    
    # Verify Ollama status
    ollama_online = await ollama_service.health_check()
    if ollama_online:
        logger.info(f"Ollama connected successfully. Current model: {OLLAMA_MODEL}")
    else:
        logger.error("WARNING: Ollama service is unreachable. Ensure it is running at http://localhost:11434")
        
    # Start the system monitoring background broadcast task
    stats_task = asyncio.create_task(broadcast_stats_loop())
    
    yield
    
    # Shutdown logic
    logger.info("Shutting down system stats broadcast loop...")
    stats_task.cancel()
    try:
        await stats_task
    except asyncio.CancelledError:
        pass
    logger.info("JARVIS offline.")

# FastAPI Application instantiation
app = FastAPI(
    title="JARVIS Backend Server",
    description="FastAPI WebSocket and REST Server supporting conversational systems control and tool operations",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration to enable local frontend testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount standard temp_audio folder static endpoint
app.mount("/temp_audio", StaticFiles(directory=TTS_OUTPUT_DIR), name="temp_audio")

# Mount front-end assets if folder exists relative to parent
backend_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(backend_dir)
frontend_dir = os.path.join(project_root, "frontend")

if os.path.exists(frontend_dir):
    app.mount("/css", StaticFiles(directory=os.path.join(frontend_dir, "css")), name="css")
    app.mount("/js", StaticFiles(directory=os.path.join(frontend_dir, "js")), name="js")
    assets_dir = os.path.join(frontend_dir, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
    logger.info(f"Mounted frontend CSS, JS, and assets from: {frontend_dir}")
else:
    logger.warning(f"Frontend folder not found at: {frontend_dir}. Root serving will only return JSON.")



# ---------------- REST ENDPOINTS ----------------

@app.get("/api/health", response_model=HealthResponse)
async def get_health():
    """Return system readiness and connection with local Ollama instance."""
    ollama_connected = await ollama_service.health_check()
    msg = "All systems operational, Sir." if ollama_connected else "Server active, but Ollama service is offline, Sir."
    
    return HealthResponse(
        status="healthy" if ollama_connected else "degraded",
        ollama_connected=ollama_connected,
        model=OLLAMA_MODEL,
        message=msg
    )

@app.get("/api/models")
async def list_models():
    """Retrieve list of locally pulled Ollama models."""
    models_raw = await ollama_service.get_models()
    models_list = []
    for model in models_raw:
        models_list.append(ModelInfo(
            name=model.get("name", "unknown"),
            details=model.get("details", {})
        ))
    return ModelListResponse(models=models_list)

@app.get("/")
async def serve_root():
    """Serve the single-page application at root index."""
    index_path = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return JSONResponse({
        "message": "JARVIS API is online, Boss. Serve the React/Vue frontend files from the 'frontend' sibling directory.",
        "endpoints": {
            "health": "/api/health",
            "models": "/api/models",
            "websocket": "/ws"
        }
    })


async def synthesize_and_send_chunk(text: str, websocket: WebSocket):
    """Asynchronously synthesize TTS audio for a sentence segment and stream it as a chunk to frontend."""
    try:
        # Determine language (Hinglish/Hindi/English)
        lang = detect_language(text)
        # Synthesize audio using edge-tts
        filepath = await speak(text, lang)
        filename = os.path.basename(filepath)
        
        # Send tts_chunk event to frontend
        await manager.send_personal_message({
            "type": "tts_chunk",
            "data": {
                "text": text,
                "language": lang,
                "audio_url": f"/temp_audio/{filename}"
            }
        }, websocket)
        logger.info(f"Streamed sentence TTS chunk to client: '{text[:25]}...'")
    except Exception as e:
        logger.error(f"Failed to synthesize sentence TTS chunk: {e}")


# ---------------- WEBSOCKET ENDPOINT ----------------

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Stateful interactive WebSocket session.
    Manages stats loops, client requests, conversational context, and custom scripts.
    """
    await manager.connect(websocket)
    
    # Initialize connection handshake
    greeting = "Good day, Sir. All systems are operational. I am ready for your instructions."
    await manager.send_personal_message({
        "type": "connected",
        "data": {
            "message": "JARVIS Online",
            "model": OLLAMA_MODEL,
            "greeting": greeting
        }
    }, websocket)
    
    # Initial status broadcast on new connection
    await manager.send_personal_message({
        "type": "agent_status",
        "data": {"agents": AGENTS_LIST}
    }, websocket)
    
    # Conversation memory context limit to this websocket session
    conversation_history: List[Dict[str, Any]] = []
    
    try:
        while True:
            # Await client signals
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                await manager.send_personal_message({
                    "type": "error",
                    "data": {"message": "Invalid JSON format sent to server."}
                }, websocket)
                continue
                
            msg_type = message.get("type")
            payload = message.get("data", {})
            
            # --- Handler: chat_message ---
            if msg_type == "chat_message":
                user_text = payload.get("text", "").strip()
                if not user_text:
                    continue
                    
                # Append user prompt to history
                conversation_history.append({"role": "user", "content": user_text})
                
                # Dynamic Orchestrator activation status
                await update_agent_status_and_broadcast("Orchestrator", "thinking")
                
                full_response_text = ""
                sentence_buffer = ""
                
                # Chat Stream Pipeline via Lead Agent Orchestrator
                async for event in lead_agent.process_intent(conversation_history):
                    ev_type = event.get("type")
                    
                    if ev_type == "thinking":
                        # Forward thinking state
                        await manager.send_personal_message(event, websocket)
                        
                    elif ev_type == "cognitive_log":
                        # Forward visual reasoning log direct to HUD
                        await manager.send_personal_message({
                            "type": "cognitive_log",
                            "data": {"text": event["content"]}
                        }, websocket)
                        
                    elif ev_type == "tool_result":
                        tool_name = event["data"]["tool"]
                        result = event["data"]["result"]
                        
                        # Dynamically update the status of the responsible sub-agent during execution
                        agent_role = get_agent_role_for_tool(tool_name)
                        await update_agent_status_and_broadcast(agent_role, "working")
                        
                        # Send execution feedback to the client
                        await manager.send_personal_message({
                            "type": "tool_result",
                            "data": {
                                "tool": tool_name,
                                "result": result
                            }
                        }, websocket)
                        
                        # Set active subagent back to idle
                        await update_agent_status_and_broadcast(agent_role, "idle")
                        
                    elif ev_type == "token":
                        token = event["content"]
                        full_response_text += token
                        # Send streamed word tokens back to front-end
                        await manager.send_personal_message({
                            "type": "chat_response",
                            "data": {"token": token, "done": False}
                        }, websocket)
                        
                        # Sentence-level TTS Streaming Pipeline
                        sentence_buffer += token
                        # Detect sentence boundaries (., ?, !, Hindi full stop, newline)
                        # Strip trailing whitespace to handle tokens that contain trailing spaces robustly
                        stripped_buffer = sentence_buffer.strip()
                        if any(stripped_buffer.endswith(d) for d in [".", "?", "!", "\n", "।"]):
                            clean_sentence = stripped_buffer
                            if len(clean_sentence) > 3:  # skip tiny items or decimals
                                sentence_buffer = ""
                                # Synthesize and stream the sentence chunk asynchronously
                                asyncio.create_task(synthesize_and_send_chunk(clean_sentence, websocket))
                        
                    elif ev_type == "error":
                        await manager.send_personal_message({
                            "type": "error",
                            "data": {"message": event["message"]}
                        }, websocket)
                
                # Synthesize any remaining sentence buffer content at the end of generation
                if sentence_buffer.strip():
                    asyncio.create_task(synthesize_and_send_chunk(sentence_buffer.strip(), websocket))
                
                # Save assistant output
                if full_response_text:
                    conversation_history.append({"role": "assistant", "content": full_response_text})
                    
                # Finalize Response stream
                await manager.send_personal_message({
                    "type": "chat_response",
                    "data": {
                        "token": "",
                        "done": True,
                        "full_text": full_response_text
                    }
                }, websocket)
                
                # Complete Lead Orchestrator thinking cycle
                await update_agent_status_and_broadcast("Orchestrator", "idle")
            
            # --- Handler: command ---
            elif msg_type == "command":
                action = payload.get("action")
                
                if action == "get_system_stats":
                    await update_agent_status_and_broadcast("System Control", "working")
                    stats = await get_system_stats()
                    await manager.send_personal_message({
                        "type": "tool_result",
                        "data": {"tool": "get_system_stats", "result": stats}
                    }, websocket)
                    await update_agent_status_and_broadcast("System Control", "idle")
                    
                elif action == "execute_terminal":
                    cmd = payload.get("command", "")
                    await update_agent_status_and_broadcast("System Control", "working")
                    res = await execute_tool("execute_terminal", {"command": cmd})
                    await manager.send_personal_message({
                        "type": "tool_result",
                        "data": {"tool": "execute_terminal", "result": res}
                    }, websocket)
                    await update_agent_status_and_broadcast("System Control", "idle")
                    
                elif action == "set_volume":
                    level = payload.get("level", 0.5)
                    set_system_volume(level)
                    # Broadcast updated stats immediately
                    stats = await get_system_stats()
                    await manager.broadcast({"type": "system_stats", "data": stats})
                    
                elif action == "set_brightness":
                    level = payload.get("level", 50)
                    set_system_brightness(level)
                    # Broadcast updated stats immediately
                    stats = await get_system_stats()
                    await manager.broadcast({"type": "system_stats", "data": stats})
                    
                elif action == "toggle_wifi":
                    enable = payload.get("enable", True)
                    toggle_wifi(enable)
                    # Broadcast updated stats immediately
                    stats = await get_system_stats()
                    await manager.broadcast({"type": "system_stats", "data": stats})
                    
                elif action == "media_control":
                    media_action = payload.get("media_action")
                    await trigger_media_control(media_action)
                    
                elif action == "get_country_info":
                    country = payload.get("country", "India")
                    await update_agent_status_and_broadcast("Web Search", "working")
                    
                    # Command Ollama to compile a gorgeous tactical dossier
                    prompt = (
                        f"Tactical analysis request: Compile a concise, high-impact intelligence report on {country}. "
                        f"Include: 1) Latest tech developments, 2) Major musical trends or famous songs, "
                        f"3) Current headline topic. Make it look like a highly advanced tactical military dossier. "
                        f"Start your response with 'TACTICAL DOSSIER COMPILED FOR {country.upper()}, SIR:' and use short list points."
                    )
                    
                    await manager.send_personal_message({"type": "thinking", "data": {"active": True}}, websocket)
                    
                    full_response_text = ""
                    async for event in ollama_service.chat_stream([{"role": "user", "content": prompt}]):
                        ev_type = event.get("type")
                        if ev_type == "token":
                            token = event["content"]
                            full_response_text += token
                            await manager.send_personal_message({
                                "type": "chat_response",
                                "data": {"token": token, "done": False}
                            }, websocket)
                            
                    await manager.send_personal_message({
                        "type": "chat_response",
                        "data": {"token": "", "done": True, "full_text": full_response_text}
                    }, websocket)
                    
                    await manager.send_personal_message({"type": "thinking", "data": {"active": False}}, websocket)
                    await update_agent_status_and_broadcast("Web Search", "idle")
                    
                    # TTS audio prompt
                    if full_response_text:
                        try:
                            summary = f"Tactical dossier compiled for {country}, Sir. Initiating visual readouts."
                            lang = detect_language(summary)
                            filepath = await speak(summary, lang)
                            filename = os.path.basename(filepath)
                            await manager.send_personal_message({
                                "type": "tts_audio",
                                "data": {
                                    "text": summary,
                                    "language": lang,
                                    "audio_url": f"/temp_audio/{filename}"
                                }
                            }, websocket)
                        except Exception as tts_err:
                            logger.error(f"Dossier TTS failed: {tts_err}")
                            
                elif action == "tts_speak":
                    text = payload.get("text", "")
                    lang = payload.get("language")
                    if text:
                        await update_agent_status_and_broadcast("Messaging", "working")
                        try:
                            if not lang:
                                lang = detect_language(text)
                            filepath = await speak(text, lang)
                            filename = os.path.basename(filepath)
                            await manager.send_personal_message({
                                "type": "tts_audio",
                                "data": {
                                    "text": text,
                                    "language": lang,
                                    "audio_url": f"/temp_audio/{filename}"
                                }
                            }, websocket)
                        except Exception as e:
                            await manager.send_personal_message({
                                "type": "error",
                                "data": {"message": f"TTS synthesis failed: {str(e)}"}
                            }, websocket)
                        await update_agent_status_and_broadcast("Messaging", "idle")
                else:
                    await manager.send_personal_message({
                        "type": "error",
                        "data": {"message": f"Unsupported backend action command: '{action}'"}
                    }, websocket)
                    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("WebSocket disconnect registered.")
    except Exception as e:
        logger.error(f"WebSocket session exception occurred: {e}", exc_info=True)
        manager.disconnect(websocket)
