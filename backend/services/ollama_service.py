import os
import json
import logging
import asyncio
import socket
import httpx
import time
import webbrowser
from datetime import datetime
from typing import AsyncGenerator, Dict, Any, List
from ollama import AsyncClient
from backend.config import OLLAMA_BASE_URL, OLLAMA_MODEL, JARVIS_SYSTEM_PROMPT, GEMINI_API_KEY
from backend.tools.system_tools import get_system_stats, get_top_processes
from backend.tools.terminal_tools import execute_command
from backend.tools.file_tools import (
    read_file, write_file, create_file, list_directory,
    delete_file, move_file, copy_file, search_files
)
from backend.tools.tts_tools import speak
from backend.tools.app_tools import open_application, close_application, list_running_apps
from backend.tools.api_tools import fetch_public_api_data
from backend.tools.vision_tools import capture_webcam_and_detect_objects, detect_objects

logger = logging.getLogger("JARVIS.OllamaService")

# Complete JSON schema-based tool definition for Qwen3 / Ollama tool support
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_system_stats",
            "description": "Get current system statistics like CPU usage, RAM utilization, Disk space, Battery percentage, and upload/download network speeds."
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_top_processes",
            "description": "Get a list of the top CPU-consuming applications/processes running on the system.",
            "parameters": {
                "type": "object",
                "properties": {
                    "n": {"type": "integer", "description": "Number of processes to return, default is 10."}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_terminal",
            "description": "Execute a terminal or PowerShell command on the host machine. Safe mode is enforced.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The shell/PowerShell command to execute."}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the text contents of a file on the local filesystem safely.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute path to the file to be read."}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write or overwrite content to a file. Overwrite occurs if file already exists.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Destination file path."},
                    "content": {"type": "string", "description": "Full string content to write."}
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_file",
            "description": "Create a new empty or pre-filled file. Fails if the file already exists.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path where the new file should be created."},
                    "content": {"type": "string", "description": "Optional content to initialize the file."}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List the files and directories inside a specific directory path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to list."}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_file",
            "description": "Delete a file or recursively delete a directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file or directory to delete."}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "move_file",
            "description": "Move or rename a file or directory on the disk.",
            "parameters": {
                "type": "object",
                "properties": {
                    "src": {"type": "string", "description": "Source path."},
                    "dest": {"type": "string", "description": "Destination path."}
                },
                "required": ["src", "dest"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "copy_file",
            "description": "Copy a file or directory to a new location.",
            "parameters": {
                "type": "object",
                "properties": {
                    "src": {"type": "string", "description": "Source path."},
                    "dest": {"type": "string", "description": "Destination path."}
                },
                "required": ["src", "dest"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Search for files within a directory matching a glob pattern.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "description": "Starting directory for the search."},
                    "pattern": {"type": "string", "description": "Glob search pattern (e.g. *.log, test_*)."}
                },
                "required": ["directory", "pattern"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_application",
            "description": "Open a Windows application (e.g., chrome, vscode, notepad, calculator, word, paint).",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Common name of the app to launch."}
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "close_application",
            "description": "Close/Terminate a running Windows process/application by name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name of process to close."}
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_running_apps",
            "description": "Retrieve a list of all active user-visible windows on the desktop."
        }
    },
    {
        "type": "function",
        "function": {
            "name": "tts_speak",
            "description": "Convert text into voice/speech (audio) using high quality neural English or Hindi voices.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "The text message that should be spoken."},
                    "language": {"type": "string", "description": "Optional: 'en' for English or 'hi' for Hindi."}
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Get the current system date and time using Python's time and datetime module, Sir."
        }
    },
    {
        "type": "function",
        "function": {
            "name": "shutdown_system",
            "description": "Shut down the laptop/computer safely with a 60-second warning, Boss."
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_website",
            "description": "Launch a specific website URL in the user's default browser instantly, Sir.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The web URL to open, e.g. https://www.google.com"}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_active_processes",
            "description": "Query and list all active tasks and visible window titles currently running on the system, Sir."
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_public_api",
            "description": "Fetch real-time data from a curated list of popular free public APIs (bitcoin, ip_geolocation, joke, cat_fact, public_ip), Sir.",
            "parameters": {
                "type": "object",
                "properties": {
                    "api_key": {"type": "string", "description": "The target public API endpoint key, e.g. bitcoin, joke, cat_fact, ip_geolocation."}
                },
                "required": ["api_key"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "capture_webcam_and_detect",
            "description": "Access the default laptop webcam, capture a live frame, run YOLOv8 object detection on it, annotate bounding boxes, and broadcast results back to HUD, Boss."
        }
    }
]

async def execute_tool(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Execute standard backend tools in a safe, structured manner."""
    logger.info(f"Invoking backend tool: '{name}' with arguments: {args}")
    try:
        if name == "get_system_stats":
            return await get_system_stats()
            
        elif name == "get_top_processes":
            n = args.get("n", 10)
            return {"processes": await get_top_processes(n)}
            
        elif name == "execute_terminal":
            cmd = args.get("command")
            return await execute_command(cmd)
            
        elif name == "read_file":
            return await read_file(args.get("path"))
            
        elif name == "write_file":
            return await write_file(args.get("path"), args.get("content"))
            
        elif name == "create_file":
            return await create_file(args.get("path"), args.get("content", ""))
            
        elif name == "list_directory":
            return await list_directory(args.get("path"))
            
        elif name == "delete_file":
            return await delete_file(args.get("path"))
            
        elif name == "move_file":
            return await move_file(args.get("src"), args.get("dest"))
            
        elif name == "copy_file":
            return await copy_file(args.get("src"), args.get("dest"))
            
        elif name == "search_files":
            return await search_files(args.get("directory"), args.get("pattern"))
            
        elif name == "open_application":
            return await open_application(args.get("name"))
            
        elif name == "close_application":
            return await close_application(args.get("name"))
            
        elif name == "list_running_apps":
            return await list_running_apps()
            
        elif name == "tts_speak":
            text = args.get("text")
            lang = args.get("language")
            filepath = await speak(text, lang)
            # Return path relative to server static context or absolute
            return {
                "success": True, 
                "audio_path": filepath, 
                "filename": os.path.basename(filepath),
                "message": f"Generated TTS audio for: '{text[:30]}...'"
            }
            
        elif name == "get_current_time":
            local_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            utc_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
            epoch_time = time.time()
            return {
                "success": True,
                "local_time": local_time,
                "utc_time": utc_time,
                "epoch": epoch_time,
                "message": f"Current system time compiled, Sir: {local_time}."
            }
            
        elif name == "shutdown_system":
            # Command gives a 60-second warning and allows aborting with 'shutdown /a' in CMD
            cmd = 'shutdown /s /t 60 /c "JARVIS has initiated system shutdown, Sir. Execute shutdown /a to abort."'
            res = await execute_command(cmd)
            return {
                "success": res.get("returncode") == 0,
                "stdout": res.get("stdout"),
                "stderr": res.get("stderr"),
                "message": "System shutdown sequence initiated, Sir. Laptop will shut down in 60 seconds. You can execute 'shutdown /a' in CMD to abort if necessary."
            }
            
        elif name == "open_website":
            url = args.get("url", "").strip()
            if not url.startswith("http"):
                url = "https://" + url
                
            def _open_url():
                webbrowser.open(url)
                return True
                
            await asyncio.to_thread(_open_url)
            return {
                "success": True,
                "url": url,
                "message": f"Web link successfully opened in your default browser, Sir: '{url}'"
            }
            
        elif name == "get_active_processes":
            res = await list_running_apps()
            return res
            
        elif name == "fetch_public_api":
            api_key = args.get("api_key", "bitcoin")
            return await fetch_public_api_data(api_key)
            
        elif name == "capture_webcam_and_detect":
            return await capture_webcam_and_detect_objects()
            
        else:
            return {"success": False, "error": f"Tool '{name}' is not recognized."}
            
    except Exception as e:
        logger.error(f"Error executing tool {name}: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


def is_internet_available() -> bool:
    """Fast check to see if host can resolve a major DNS server to verify internet connection."""
    try:
        socket.setdefaulttimeout(1.5)
        # Attempt to connect to Google DNS port 53
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("8.8.8.8", 53))
        s.close()
        return True
    except Exception:
        return False

async def stream_gemini(messages: List[Dict[str, Any]], system_prompt: str) -> AsyncGenerator[str, None]:
    """Stream response tokens from Google Cloud Gemini Flash API with native search grounding."""
    gemini_contents = []
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content")
        if role == "system":
            continue
        gemini_contents.append({
            "role": "user" if role == "user" else "model",
            "parts": [{"text": content}]
        })
        
    payload = {
        "contents": gemini_contents,
        "systemInstruction": {
            "parts": [{"text": system_prompt}]
        },
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 2048
        },
        "tools": [{"googleSearch": {}}]  # Enforce direct search grounding!
    }
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:streamGenerateContent?key={GEMINI_API_KEY}"
    
    try:
        # Use a short timeout of 5.0 seconds to fail-fast and allow rapid local model fallback
        async with httpx.AsyncClient(timeout=5.0) as client:
            async with client.stream("POST", url, json=payload) as response:
                if response.status_code != 200:
                    err_text = await response.aread()
                    err_message = err_text.decode('utf-8', errors='replace')
                    logger.error(f"Gemini API returned error code {response.status_code}: {err_message}")
                    raise RuntimeError(f"Gemini API error code {response.status_code}")
                    
                buffer = ""
                async for chunk in response.aiter_text():
                    buffer += chunk
                    
                    # Robust streaming JSON object extraction by counting balanced braces
                    while True:
                        start_idx = buffer.find('{')
                        if start_idx == -1:
                            break
                            
                        brace_count = 0
                        end_idx = -1
                        in_string = False
                        escape = False
                        
                        for i in range(start_idx, len(buffer)):
                            char = buffer[i]
                            if escape:
                                escape = False
                                continue
                            if char == '\\':
                                escape = True
                                continue
                            if char == '"':
                                in_string = not in_string
                                continue
                            if not in_string:
                                if char == '{':
                                    brace_count += 1
                                elif char == '}':
                                    brace_count -= 1
                                    if brace_count == 0:
                                        end_idx = i
                                        break
                                        
                        if end_idx != -1:
                            # Extract complete single JSON object
                            json_str = buffer[start_idx:end_idx + 1]
                            buffer = buffer[end_idx + 1:]
                            
                            try:
                                data = json.loads(json_str)
                                candidates = data.get("candidates", [])
                                if candidates:
                                    parts = candidates[0].get("content", {}).get("parts", [])
                                    if parts:
                                        token = parts[0].get("text", "")
                                        if token:
                                            yield token
                            except Exception as e:
                                logger.error(f"Failed to parse streaming JSON chunk: {e}")
                        else:
                            # Object is still compiling in chunk stream, wait for next text chunk
                            break
    except Exception as e:
        logger.error(f"Gemini connection failed: {e}", exc_info=True)
        raise RuntimeError(f"Gemini connection failed: {str(e)}")


class OllamaService:
    def __init__(self):
        self.client = AsyncClient(host=OLLAMA_BASE_URL)
        self.model = OLLAMA_MODEL
        logger.info(f"Initialized Ollama Client at: {OLLAMA_BASE_URL} using model: {self.model}")

    async def health_check(self) -> bool:
        """Check if Ollama service is reachable and ready."""
        try:
            # Try listing models as a ping
            await self.client.list()
            return True
        except Exception as e:
            logger.error(f"Ollama connection health check failed: {e}")
            return False

    async def get_models(self) -> List[Dict[str, Any]]:
        """Get list of models pulled into the local Ollama instance."""
        try:
            res = await self.client.list()
            return res.get('models', [])
        except Exception as e:
            logger.error(f"Failed to fetch model list: {e}")
            return []

    async def chat_stream(self, conversation_history: List[Dict[str, Any]]) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stateful orchestrator that automatically routes conversational requests
        between Cloud Gemini API (online, grounded, real-time) and local Ollama (offline fallback).
        """
        messages = list(conversation_history)
        if not messages or messages[0].get("role") != "system":
            messages.insert(0, {"role": "system", "content": JARVIS_SYSTEM_PROMPT})

        online = is_internet_available()
        use_cloud = bool(GEMINI_API_KEY) and online

        if use_cloud:
            yield {
                "type": "cognitive_log",
                "content": "[COGNITIVE] Uplink stable. Routing query to Google Cloud Gemini Flash with direct search grounding."
            }
            try:
                yield {"type": "thinking", "data": {"active": True}}
                sys_inst = messages[0].get("content", JARVIS_SYSTEM_PROMPT)
                
                async for token in stream_gemini(messages, sys_inst):
                    yield {"type": "token", "content": token}
                    
                yield {"type": "thinking", "data": {"active": False}}
            except Exception as e:
                logger.error(f"Failed to route stream via cloud: {e}")
                yield {
                    "type": "cognitive_log",
                    "content": f"[COGNITIVE] Gemini Cloud exception: {str(e)}. Automatically falling back to local Ollama fallback brain, Sir."
                }
                async for event in self.chat_stream_local(messages):
                    yield event
        else:
            reason = "No Cloud API key configured." if not GEMINI_API_KEY else "Host network connectivity offline."
            yield {
                "type": "cognitive_log",
                "content": f"[COGNITIVE] Fallback active ({reason}). Invoking local Ollama core, Sir."
            }
            async for event in self.chat_stream_local(messages):
                yield event

    async def chat_stream_local(self, messages: List[Dict[str, Any]]) -> AsyncGenerator[Dict[str, Any], None]:
        """Original local Ollama stream routing featuring worker tool support."""

        try:
            logger.info("Sending chat request to Ollama...")
            # Phase 1: Call Ollama with tools to detect if system actions are required
            response = await self.client.chat(
                model=self.model,
                messages=messages,
                tools=TOOLS
            )
            
            tool_calls = getattr(response.message, 'tool_calls', [])
            
            if tool_calls:
                logger.info(f"Model requested tool calls: {[t.function.name for t in tool_calls]}")
                # Activate thinking indicator on client
                yield {"type": "thinking", "data": {"active": True}}
                
                # Append assistant's decision to messages
                messages.append(response.message)
                
                # Execute all tools sequentially
                for tool_call in tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = tool_call.function.arguments
                    
                    # Run tool
                    result = await execute_tool(tool_name, tool_args)
                    
                    # Yield tool results directly to client for transparent logging
                    yield {
                        "type": "tool_result",
                        "data": {
                            "tool": tool_name,
                            "result": result
                        }
                    }
                    
                    # Append result back so the model can construct the final answer
                    messages.append({
                        "role": "tool",
                        "name": tool_name,
                        "content": json.dumps(result)
                    })
                
                # Deactivate thinking indicator before final stream
                yield {"type": "thinking", "data": {"active": False}}
                
                # Phase 2: Stream final conversational synthesis with the tool results
                logger.info("Streaming final response following tool execution...")
                async for chunk in await self.client.chat(
                    model=self.model,
                    messages=messages,
                    stream=True
                ):
                    token = chunk.message.content or ""
                    if token:
                        yield {"type": "token", "content": token}
            else:
                # No tool call requested. Direct conversational streaming.
                logger.info("Direct conversational response. Simulating stream for instantaneous UI response.")
                text = response.message.content or ""
                # To support instant high-quality streaming interface:
                words = text.split(" ")
                for i, word in enumerate(words):
                    space = " " if i < len(words) - 1 else ""
                    yield {"type": "token", "content": word + space}
                    await asyncio.sleep(0.015) # Comfortable readability speed
                    
        except Exception as e:
            logger.error(f"Error in chat stream pipeline: {e}", exc_info=True)
            yield {"type": "error", "message": f"I encountered an error processing that, Sir: {str(e)}"}
