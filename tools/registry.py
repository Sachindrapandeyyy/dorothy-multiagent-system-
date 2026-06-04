"""
Dorothy OS v2.0 — Unified Tool Registry & Executor
Central dispatcher mapping all tool names to their implementations.
Provides the JSON schema definitions for LLM function-calling registration.
"""

import os
import json
import time
import logging
import asyncio
import webbrowser
from datetime import datetime
from typing import Dict, Any, List

from tools.system_tools import (
    get_system_stats, get_top_processes, get_gpu_stats,
    get_system_volume, set_system_volume, set_system_brightness, toggle_wifi,
)
from tools.app_tools import open_application, close_application, list_running_apps, trigger_media_control
from tools.file_tools import read_file, write_file, create_file, list_directory, delete_file, move_file, copy_file, search_files
from tools.terminal_tools import execute_command
from tools.tts_tools import speak
from tools.api_tools import fetch_public_api_data, web_search
from tools.vision_tools import capture_webcam_and_detect_objects, detect_objects
from security.sandbox import sandbox_executor
from vision.screen_perception import screen_perception

logger = logging.getLogger("Dorothy.Tools.Registry")

# ─── Tool JSON Schema Definitions for LLM Function Calling ──────────────────

TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {"type": "function", "function": {
        "name": "get_system_stats",
        "description": "Get current system statistics: CPU usage, RAM, disk space, battery, and network speeds."
    }},
    {"type": "function", "function": {
        "name": "get_top_processes",
        "description": "Get the top CPU-consuming processes running on the system.",
        "parameters": {"type": "object", "properties": {
            "n": {"type": "integer", "description": "Number of processes to return (default: 10)."}
        }}
    }},
    {"type": "function", "function": {
        "name": "get_gpu_stats",
        "description": "Get NVIDIA GPU statistics: temperature, utilization, VRAM usage."
    }},
    {"type": "function", "function": {
        "name": "execute_terminal",
        "description": "Execute a terminal or PowerShell command on the host machine. Safety filters enforced.",
        "parameters": {"type": "object", "properties": {
            "command": {"type": "string", "description": "The shell/PowerShell command to execute."}
        }, "required": ["command"]}
    }},
    {"type": "function", "function": {
        "name": "read_file",
        "description": "Read the text contents of a file on the local filesystem.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "Absolute path to the file to read."}
        }, "required": ["path"]}
    }},
    {"type": "function", "function": {
        "name": "write_file",
        "description": "Write or overwrite content to a file.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "Destination file path."},
            "content": {"type": "string", "description": "Full text content to write."}
        }, "required": ["path", "content"]}
    }},
    {"type": "function", "function": {
        "name": "create_file",
        "description": "Create a new file. Fails if file already exists.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "Path for the new file."},
            "content": {"type": "string", "description": "Optional initial content."}
        }, "required": ["path"]}
    }},
    {"type": "function", "function": {
        "name": "list_directory",
        "description": "List files and directories inside a path.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "Directory path to list."}
        }, "required": ["path"]}
    }},
    {"type": "function", "function": {
        "name": "delete_file",
        "description": "Delete a file or recursively delete a directory.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "Path to delete."}
        }, "required": ["path"]}
    }},
    {"type": "function", "function": {
        "name": "move_file",
        "description": "Move or rename a file or directory.",
        "parameters": {"type": "object", "properties": {
            "src": {"type": "string", "description": "Source path."},
            "dest": {"type": "string", "description": "Destination path."}
        }, "required": ["src", "dest"]}
    }},
    {"type": "function", "function": {
        "name": "copy_file",
        "description": "Copy a file or directory to a new location.",
        "parameters": {"type": "object", "properties": {
            "src": {"type": "string", "description": "Source path."},
            "dest": {"type": "string", "description": "Destination path."}
        }, "required": ["src", "dest"]}
    }},
    {"type": "function", "function": {
        "name": "search_files",
        "description": "Search for files within a directory matching a glob pattern.",
        "parameters": {"type": "object", "properties": {
            "directory": {"type": "string", "description": "Starting directory."},
            "pattern": {"type": "string", "description": "Glob pattern (e.g., *.py, test_*)."}
        }, "required": ["directory", "pattern"]}
    }},
    {"type": "function", "function": {
        "name": "open_application",
        "description": "Open a Windows application (chrome, vscode, notepad, calculator, etc.).",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string", "description": "Common name of the application."}
        }, "required": ["name"]}
    }},
    {"type": "function", "function": {
        "name": "close_application",
        "description": "Close/terminate a running Windows process by name.",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string", "description": "Process name to close."}
        }, "required": ["name"]}
    }},
    {"type": "function", "function": {
        "name": "list_running_apps",
        "description": "List all visible windows/applications currently running on the desktop."
    }},
    {"type": "function", "function": {
        "name": "tts_speak",
        "description": "Convert text into speech audio using neural Hindi or English voices.",
        "parameters": {"type": "object", "properties": {
            "text": {"type": "string", "description": "Text to speak."},
            "language": {"type": "string", "description": "'en' for English or 'hi' for Hindi."}
        }, "required": ["text"]}
    }},
    {"type": "function", "function": {
        "name": "get_current_time",
        "description": "Get the current system date, time, and timezone."
    }},
    {"type": "function", "function": {
        "name": "shutdown_system",
        "description": "Shut down the laptop safely with a 60-second warning countdown."
    }},
    {"type": "function", "function": {
        "name": "open_website",
        "description": "Open a URL in the default browser.",
        "parameters": {"type": "object", "properties": {
            "url": {"type": "string", "description": "Web URL to open (e.g., https://google.com)."}
        }, "required": ["url"]}
    }},
    {"type": "function", "function": {
        "name": "get_active_processes",
        "description": "Query all active tasks and visible window titles running on the device."
    }},
    {"type": "function", "function": {
        "name": "fetch_public_api",
        "description": "Fetch real-time data from public APIs (bitcoin, weather, joke, cat_fact, ip_geolocation, etc.).",
        "parameters": {"type": "object", "properties": {
            "api_key": {"type": "string", "description": "API endpoint key (e.g., bitcoin, joke, weather, trivia)."}
        }, "required": ["api_key"]}
    }},
    {"type": "function", "function": {
        "name": "capture_webcam_and_detect",
        "description": "Capture a webcam frame, run YOLOv8 object detection, annotate, and return results."
    }},
    {"type": "function", "function": {
        "name": "media_control",
        "description": "Send media control keys (play, pause, next, previous, volume_up, volume_down, mute).",
        "parameters": {"type": "object", "properties": {
            "action": {"type": "string", "description": "Media action: play, pause, next, previous, volume_up, volume_down, mute."}
        }, "required": ["action"]}
    }},
    {"type": "function", "function": {
        "name": "set_volume",
        "description": "Set the system audio volume to a specific level (0-100).",
        "parameters": {"type": "object", "properties": {
            "level": {"type": "integer", "description": "Volume level 0-100."}
        }, "required": ["level"]}
    }},
    {"type": "function", "function": {
        "name": "set_brightness",
        "description": "Set the screen brightness to a specific level (0-100).",
        "parameters": {"type": "object", "properties": {
            "level": {"type": "integer", "description": "Brightness level 0-100."}
        }, "required": ["level"]}
    }},
    {"type": "function", "function": {
        "name": "execute_python_sandbox",
        "description": "Execute Python code safely inside an isolated timeout-constrained sandbox. Automatically parses tracebacks for reflection loops.",
        "parameters": {"type": "object", "properties": {
            "code": {"type": "string", "description": "The Python source code to execute."}
        }, "required": ["code"]}
    }},
    {"type": "function", "function": {
        "name": "capture_desktop_screenshot",
        "description": "Capture the active computer desktop screen and save to captures directory."
    }},
    {"type": "function", "function": {
        "name": "locate_and_click_ui_element",
        "description": "Locate a UI element on screen (via natural query or image path) and perform a physical click.",
        "parameters": {"type": "object", "properties": {
            "target": {"type": "string", "description": "Semantic query describing the element (e.g. 'blue submit button') or local template sub-image path."}
        }, "required": ["target"]}
    }},
    {"type": "function", "function": {
        "name": "web_search",
        "description": "Search the web for real-time information, weather, news, or query responses.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "The search query (e.g., 'latest news on Mila', 'weather in Allahabad')."}
        }, "required": ["query"]}
    }},
]


# ─── Unified Tool Executor ───────────────────────────────────────────────────

async def execute_tool(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a registered tool by name with the given arguments."""
    logger.info(f"Executing tool: '{name}' with args: {args}")
    try:
        # System monitoring
        if name == "get_system_stats":
            return await get_system_stats()
        elif name == "get_top_processes":
            return {"processes": await get_top_processes(args.get("n", 10))}
        elif name == "get_gpu_stats":
            result = await get_gpu_stats()
            return result if result else {"success": False, "error": "GPU stats unavailable (no NVIDIA GPU detected)."}

        # Terminal
        elif name == "execute_terminal":
            return await execute_command(args.get("command", ""))

        # File operations
        elif name == "read_file":
            return await read_file(args.get("path", ""))
        elif name == "write_file":
            return await write_file(args.get("path", ""), args.get("content", ""))
        elif name == "create_file":
            return await create_file(args.get("path", ""), args.get("content", ""))
        elif name == "list_directory":
            return await list_directory(args.get("path", ""))
        elif name == "delete_file":
            return await delete_file(args.get("path", ""))
        elif name == "move_file":
            return await move_file(args.get("src", ""), args.get("dest", ""))
        elif name == "copy_file":
            return await copy_file(args.get("src", ""), args.get("dest", ""))
        elif name == "search_files":
            return await search_files(args.get("directory", ""), args.get("pattern", ""))

        # Application control
        elif name == "open_application":
            return await open_application(args.get("name", ""))
        elif name == "close_application":
            return await close_application(args.get("name", ""))
        elif name == "list_running_apps":
            return await list_running_apps()
        elif name == "media_control":
            return await trigger_media_control(args.get("action", ""))

        # Audio/Display control
        elif name == "set_volume":
            return await set_system_volume(args.get("level", 50))
        elif name == "set_brightness":
            return await set_system_brightness(args.get("level", 50))

        # TTS
        elif name == "tts_speak":
            filepath = await speak(args.get("text", ""), args.get("language"))
            return {
                "success": True,
                "audio_path": filepath,
                "filename": os.path.basename(filepath),
                "message": f"Generated TTS audio for: '{args.get('text', '')[:30]}...'",
            }

        # Time
        elif name == "get_current_time":
            local_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            utc_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
            return {
                "success": True,
                "local_time": local_time,
                "utc_time": utc_time,
                "epoch": time.time(),
                "timezone": time.strftime("%Z"),
                "message": f"Current system time: {local_time}",
            }

        elif name == "shutdown_system":
            cmd = 'shutdown /s /f /t 0'
            return await execute_command(cmd)


        # Browser
        elif name == "open_website":
            url = args.get("url", "").strip()
            if not url.startswith("http"):
                url = "https://" + url

            def _open_url():
                webbrowser.open(url)
                return True

            await asyncio.to_thread(_open_url)
            return {"success": True, "url": url, "message": f"Opened in browser: {url}"}

        # Active processes (alias)
        elif name == "get_active_processes":
            return await list_running_apps()

        # Public APIs
        elif name == "fetch_public_api":
            return await fetch_public_api_data(args.get("api_key", "bitcoin"))

        # Web Search
        elif name == "web_search":
            return await web_search(args.get("query", ""))

        # Vision
        elif name == "capture_webcam_and_detect":
            return await capture_webcam_and_detect_objects()

        # Python Sandbox Execution
        elif name == "execute_python_sandbox":
            code = args.get("code", "")
            return await sandbox_executor.execute_python(code)

        # Screen Perception Navigation
        elif name == "capture_desktop_screenshot":
            filepath = screen_perception.capture_screen()
            return {
                "success": True, 
                "filepath": filepath, 
                "filename": os.path.basename(filepath),
                "message": f"Desktop screen successfully captured to: {filepath}"
            }

        elif name == "locate_and_click_ui_element":
            target = args.get("target", "")
            clicked = await screen_perception.click_element(target)
            return {
                "success": clicked,
                "message": f"Successfully clicked target '{target}'" if clicked else f"Failed to locate target '{target}' on screen"
            }

        else:
            return {"success": False, "error": f"Tool '{name}' is not registered."}

    except Exception as e:
        logger.error(f"Error executing tool '{name}': {e}", exc_info=True)
        return {"success": False, "error": str(e)}


# ─── Tool Category Mapping ───────────────────────────────────────────────────

TOOL_AGENT_MAP: Dict[str, str] = {
    # File operations
    "read_file": "file", "write_file": "file", "create_file": "file",
    "list_directory": "file", "delete_file": "file", "move_file": "file",
    "copy_file": "file", "search_files": "file",
    # System control
    "get_system_stats": "system", "get_top_processes": "system", "get_gpu_stats": "system",
    "execute_terminal": "system", "execute_python_sandbox": "system", "open_application": "desktop", "close_application": "desktop",
    "list_running_apps": "desktop", "get_active_processes": "desktop",
    "set_volume": "system", "set_brightness": "system", "media_control": "system",
    "shutdown_system": "system", "get_current_time": "system",
    # Web / API
    "open_website": "browser", "web_search": "browser", "fetch_public_api": "research",
    # Communication
    "tts_speak": "voice",
    # Vision
    "capture_webcam_and_detect": "vision", "capture_desktop_screenshot": "vision", "locate_and_click_ui_element": "vision",
}


def get_agent_for_tool(tool_name: str) -> str:
    """Get the agent category responsible for a given tool."""
    return TOOL_AGENT_MAP.get(tool_name, "system")
