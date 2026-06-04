import logging
import json
import asyncio
from typing import AsyncGenerator, Dict, Any, List
from backend.services.ollama_service import OllamaService, TOOLS, execute_tool, is_internet_available
from backend.services.websocket_manager import manager
from backend.config import GEMINI_API_KEY
from backend.services.agent_router import TaskVectorRouter

logger = logging.getLogger("JARVIS.LeadAgent")

class LeadAgent:
    """
    JARVIS Lead Orchestrator Agent.
    Intelligently analyzes user intent, activates and delegates tasks to specialized subagents,
    monitors their execution outputs, and streams synthesized tactical reports to the HUD.
    """
    def __init__(self):
        self.ollama = OllamaService()
        self.router = TaskVectorRouter()
        
        # Agent metadata for HUD dashboard coordination
        self.agent_map = {
            "file": {"name": "File Agent", "role": "File Operations", "icon": "📁"},
            "system": {"name": "System Agent", "role": "System Control", "icon": "⚙️"},
            "code": {"name": "Code Agent", "role": "Code Generation", "icon": "💻"},
            "web": {"name": "Web Agent", "role": "Web Search", "icon": "🌐"},
            "comms": {"name": "Comms Agent", "role": "Messaging", "icon": "📱"}
        }

    async def broadcast_agent_state(self, agent_key: str, status: str):
        """Update a specific worker agent's state on the frontend HUD dashboard."""
        if agent_key in self.agent_map:
            role = self.agent_map[agent_key]["role"]
            # Trigger main.py status updater to sync state and broadcast
            from backend.main import update_agent_status_and_broadcast
            await update_agent_status_and_broadcast(role, status)

    async def log_activity(self, text: str, agent_key: str = "Orchestrator"):
        """Log a tactical action to the HUD activity log console."""
        agent_name = self.agent_map.get(agent_key, {}).get("name", "JARVIS Lead")
        await manager.broadcast({
            "type": "agent_status",
            "data": {
                "log_entry": {
                    "text": text,
                    "agent": agent_name
                }
            }
        })

    async def execute_worker_task(self, worker_key: str, tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
        """Activate a specialized subagent, log its actions, execute tools, and return results."""
        agent_name = self.agent_map.get(worker_key, {}).get("name", "Worker Agent")
        logger.info(f"Delegating tool '{tool_name}' to '{agent_name}' with args: {tool_args}")
        
        # 1. Update subagent card status to "working"
        await self.broadcast_agent_state(worker_key, "working")
        await self.log_activity(f"Activated for sub-routine: '{tool_name}'", worker_key)
        
        # 2. Execute target backend tool
        try:
            result = await execute_tool(tool_name, tool_args)
            await self.log_activity(f"Completed execution: '{tool_name}' with status: {result.get('success', True)}", worker_key)
            return result
        except Exception as e:
            logger.error(f"Error in worker {agent_name} executing {tool_name}: {e}")
            await self.log_activity(f"Routine failed: {str(e)}", worker_key)
            return {"success": False, "error": str(e)}
        finally:
            # 3. Restore subagent status to "idle"
            await self.broadcast_agent_state(worker_key, "idle")

    def resolve_worker_for_tool(self, tool_name: str) -> str:
        """Map specific tools to their responsible specialized worker subagent."""
        file_tools = ["read_file", "write_file", "create_file", "list_directory", "delete_file", "move_file", "copy_file", "search_files"]
        system_tools = ["get_system_stats", "get_top_processes", "execute_terminal", "open_application", "close_application", "list_running_apps", "set_volume", "set_brightness", "toggle_wifi", "media_control"]
        comms_tools = ["tts_speak"]
        
        if tool_name in file_tools:
            return "file"
        elif tool_name in system_tools:
            return "system"
        elif tool_name in comms_tools:
            return "comms"
        return "system" # Default fallback

    async def process_intent(self, conversation_history: List[Dict[str, Any]]) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Main cognitive loop of the Orchestrator Brain.
        Analyzes requests, coordinates tool calls across worker agents, and streams responses.
        """
        messages = list(conversation_history)
        
        # Local Task Vector Classification and Multi-Agent Routing
        user_query = ""
        for msg in reversed(conversation_history):
            if msg.get("role") == "user":
                user_query = msg.get("content", "")
                break
                
        if user_query:
            matched_agent, scores = self.router.route_task(user_query)
            formatted_scores = ", ".join(f"{k}: {v}" for k, v in scores.items())
            
            # Broadcast the mathematical task vector similarity logs to HUD
            yield {
                "type": "cognitive_log",
                "content": f"[COGNITIVE] Vector Routing matched Agent centroid: '{matched_agent.upper()}' (Cosine Scores: {formatted_scores})"
            }
            yield {
                "type": "cognitive_log",
                "content": f"[COGNITIVE] Routing system sub-routines to {self.agent_map[matched_agent]['name']}, Sir."
            }
            
            # Briefly highlight the targeted agent card as "thinking" to indicate active routing
            await self.broadcast_agent_state(matched_agent, "thinking")
            await asyncio.sleep(0.4) # Diagnostic pause for visual HUD sync
            await self.broadcast_agent_state(matched_agent, "idle")

        # Intercept and inject real-time context to bypass weak local tool calling
        import re
        from datetime import datetime
        query_lower = user_query.lower()
        intercepted_context = ""
        
        if any(w in query_lower for w in ["time", "date", "clock", "समय"]):
            local_time = datetime.now().strftime("%A, %B %d, %Y %I:%M:%S %p")
            intercepted_context = f"REAL-TIME SYSTEM CONTEXT: The current date and time is exactly: {local_time}."
            
        elif any(w in query_lower for w in ["stats", "health", "cpu", "ram", "memory", "battery", "telemetry"]):
            from backend.tools.system_tools import get_system_stats
            stats = await get_system_stats()
            ram_pct = stats['ram']['percent']
            cpu_pct = stats['cpu']
            disk_pct = stats['disk'][0]['percent'] if stats['disk'] else 0
            bat_pct = stats['battery']['percent']
            intercepted_context = (
                f"REAL-TIME SYSTEM TELEMETRY: CPU load is {cpu_pct}%, RAM utilization is {ram_pct}% "
                f"({stats['ram']['used_gb']} GB of {stats['ram']['total_gb']} GB used), "
                f"primary C: drive is {disk_pct}% full, and Laptop Battery level is {bat_pct}%."
            )
            
        elif any(w in query_lower for w in ["process", "task", "running", "active apps"]):
            from backend.tools.app_tools import list_running_apps
            res = await list_running_apps()
            if res.get("success"):
                apps_list = ", ".join(f"{a['name']} ({a['title']})" for a in res["apps"][:6])
                intercepted_context = f"REAL-TIME ACTIVE PROCESSES ON DEVICE: The visible window applications running are: {apps_list}."
                
        elif "shutdown" in query_lower or "turn off" in query_lower or "power off" in query_lower:
            res = await execute_tool("shutdown_system", {})
            intercepted_context = f"SYSTEM INSTRUCTION EXECUTION: A controlled shutdown sequence has been initiated: {res.get('message')}."
            
        elif any(w in query_lower for w in ["bitcoin", "btc", "joke", "cat fact", "public ip", "geolocation"]):
            # Resolve api key
            api_key = "bitcoin"
            if "joke" in query_lower:
                api_key = "joke"
            elif "cat fact" in query_lower:
                api_key = "cat_fact"
            elif "geolocation" in query_lower:
                api_key = "ip_geolocation"
            elif "public ip" in query_lower:
                api_key = "public_ip"
                
            res = await execute_tool("fetch_public_api", {"api_key": api_key})
            if res.get("success"):
                intercepted_context = f"REAL-TIME PUBLIC API DATA [{res.get('api_name')}]: Live response payload is: {json.dumps(res.get('data'))}."
            else:
                intercepted_context = f"REAL-TIME PUBLIC API ERROR: Could not fetch endpoint: {res.get('error')}."
                
        elif any(w in query_lower for w in ["webcam", "camera", "detect object", "optical scan", "vision"]):
            # Let the HUD log active vision scanners engaging
            yield {
                "type": "cognitive_log",
                "content": "[COGNITIVE] Optical vision scanners engaged. Initiating local webcam capture..."
            }
            res = await execute_tool("capture_webcam_and_detect", {})
            if res.get("success"):
                intercepted_context = (
                    f"TACTICAL OPTICAL SCAN COMPLETED: Accessed default system webcam, Sir. "
                    f"Found {res.get('count')} objects. Bounding box overlays rendered and saved "
                    f"to active HUD directory at: {res.get('image_url')}. "
                    f"Parsed detected targets: {res.get('detected_objects')}. "
                    f"Here is the tactical optical feed: ![Optical Scan Web Capture]({res.get('image_url')})"
                )
            else:
                intercepted_context = f"TACTICAL OPTICAL SCAN FAILED: Optical hardware error: {res.get('error')}."
            
        elif "open " in query_lower or ".com" in query_lower or ".in" in query_lower or ".org" in query_lower:
            urls = re.findall(r'(https?://\S+|[a-zA-Z0-9.-]+\.[a-zA-Z]{2,6}\b\S*)', user_query)
            if urls:
                target_url = urls[0]
                res = await execute_tool("open_website", {"url": target_url})
                intercepted_context = f"SYSTEM INSTRUCTION EXECUTION: Successfully launched URL in default browser: {res.get('message')}."
                
        if intercepted_context:
            yield {
                "type": "cognitive_log",
                "content": f"[COGNITIVE] Pre-intercept matches query. Injected real-time system context: '{intercepted_context[:45]}...'"
            }
            messages.append({
                "role": "system", 
                "content": intercepted_context + " State this exact system data/status clearly in a highly respectful, concise, and helpful JARVIS voice, Sir."
            })

        online = is_internet_available()
        use_cloud = bool(GEMINI_API_KEY) and online
        
        if use_cloud:
            logger.info("Orchestrator routing query to Cloud Gemini Flash hybrid stream...")
            async for event in self.ollama.chat_stream(messages):
                yield event
            return

        # Activate Lead Orchestrator status to thinking (local model fallback execution)
        await self.broadcast_agent_state("comms", "idle")
        
        try:
            logger.info("Orchestrator analyzing input intent locally...")
            yield {"type": "thinking", "data": {"active": True}}
            await self.log_activity("Analyzing command intent parameters locally...", "Orchestrator")
            
            # Pass 1: Call Ollama with registered capabilities
            response = await self.ollama.client.chat(
                model=self.ollama.model,
                messages=messages,
                tools=TOOLS
            )
            
            tool_calls = getattr(response.message, 'tool_calls', [])
            
            if tool_calls:
                logger.info(f"Orchestrator resolved worker tool tasks: {[t.function.name for t in tool_calls]}")
                messages.append(response.message)
                
                # Execute all worker tasks sequentially
                for tool_call in tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = tool_call.function.arguments
                    
                    # Resolve which worker agent is responsible
                    worker_key = self.resolve_worker_for_tool(tool_name)
                    
                    # Run worker task
                    result = await self.execute_worker_task(worker_key, tool_name, tool_args)
                    
                    # Stream tool result back to HUD logs
                    yield {
                        "type": "tool_result",
                        "data": {
                            "tool": tool_name,
                            "result": result
                        }
                    }
                    
                    # Feed results back into conversation memory
                    messages.append({
                        "role": "tool",
                        "name": tool_name,
                        "content": json.dumps(result)
                    })
                
                yield {"type": "thinking", "data": {"active": False}}
                await self.log_activity("Synthesizing worker execution metrics into tactical report...", "Orchestrator")
                
                # Pass 2: Stream final conversational report synthesis
                async for chunk in await self.ollama.client.chat(
                    model=self.ollama.model,
                    messages=messages,
                    stream=True
                ):
                    token = chunk.message.content or ""
                    if token:
                        yield {"type": "token", "content": token}
            else:
                # Direct conversational response. Simulating smooth high-speed stream.
                yield {"type": "thinking", "data": {"active": False}}
                await self.log_activity("Direct communication channel established.", "Orchestrator")
                text = response.message.content or ""
                words = text.split(" ")
                for i, word in enumerate(words):
                    space = " " if i < len(words) - 1 else ""
                    yield {"type": "token", "content": word + space}
                    await asyncio.sleep(0.015)
                    
        except Exception as e:
            logger.error(f"Error in LeadAgent orchestrator: {e}", exc_info=True)
            yield {"type": "error", "message": f"Orchestrator neural synapse anomaly, Sir: {str(e)}"}
