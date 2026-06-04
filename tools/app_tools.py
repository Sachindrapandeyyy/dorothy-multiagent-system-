"""
Dorothy OS v2.0 — Application Control Tools
Provides async Windows application launch, close, list, and media control capabilities.
"""

import os
import sys
import json
import logging
import asyncio
import subprocess
from typing import Dict, Any, List

logger = logging.getLogger("Dorothy.Tools.App")

# Windows app name → executable mapping (loaded from configs at runtime)
_APP_MAPPING: Dict[str, str] = {
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "vscode": "Code.exe",
    "visual studio code": "Code.exe",
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "explorer": "explorer.exe",
    "file explorer": "explorer.exe",
    "paint": "mspaint.exe",
    "task manager": "taskmgr.exe",
    "taskmgr": "taskmgr.exe",
    "cmd": "cmd.exe",
    "command prompt": "cmd.exe",
    "powershell": "powershell.exe",
    "browser": "chrome.exe",
    "word": "winword.exe",
    "excel": "excel.exe",
    "powerpoint": "powerpnt.exe",
    "edge": "msedge.exe",
    "spotify": "spotify.exe",
    "discord": "discord.exe",
    "steam": "steam.exe",
    "vlc": "vlc.exe",
    "obs": "obs64.exe",
    "terminal": "wt.exe",
    "windows terminal": "wt.exe",
}


async def open_application(name: str) -> Dict[str, Any]:
    """Launch a Windows application by common name."""
    if sys.platform != "win32":
        return {"success": False, "error": "Application launch is Windows-only."}
    return await asyncio.to_thread(_open_app_sync, name)


def _open_app_sync(name: str) -> Dict[str, Any]:
    """Synchronous app launcher (runs in thread)."""
    name_lower = name.lower().strip()
    exe = _APP_MAPPING.get(name_lower)

    if exe:
        try:
            os.startfile(exe)
            return {"success": True, "app": name, "exe": exe, "message": f"Launched {name} ({exe})."}
        except Exception:
            # Fallback: try shell start
            try:
                subprocess.Popen(["start", "", exe], shell=True)
                return {"success": True, "app": name, "exe": exe, "message": f"Launched {name} via shell."}
            except Exception as e:
                return {"success": False, "error": f"Failed to launch {name}: {e}"}
    else:
        # Try launching the raw name directly
        try:
            os.startfile(name_lower)
            return {"success": True, "app": name, "message": f"Launched '{name}' directly."}
        except Exception as e:
            return {"success": False, "error": f"Application '{name}' not found in mapping and direct launch failed: {e}"}


async def close_application(name: str) -> Dict[str, Any]:
    """Terminate a running Windows application by process name."""
    if sys.platform != "win32":
        return {"success": False, "error": "Application close is Windows-only."}
    return await asyncio.to_thread(_close_app_sync, name)


def _close_app_sync(name: str) -> Dict[str, Any]:
    """Kill a process by name using taskkill."""
    name_lower = name.lower().strip()
    exe = _APP_MAPPING.get(name_lower, name_lower)

    # Ensure .exe extension
    if not exe.endswith(".exe"):
        exe += ".exe"

    try:
        result = subprocess.run(
            ["taskkill", "/IM", exe, "/F"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return {"success": True, "app": name, "message": f"Successfully terminated {exe}."}
        return {"success": False, "error": result.stderr.strip() or f"Could not terminate {exe}."}
    except Exception as e:
        return {"success": False, "error": f"Failed to close {name}: {e}"}


async def list_running_apps() -> Dict[str, Any]:
    """List all visible windows on the desktop with their process names."""
    if sys.platform != "win32":
        return {"success": False, "error": "Window listing is Windows-only."}
    return await asyncio.to_thread(_list_apps_sync)


def _list_apps_sync() -> Dict[str, Any]:
    """Query visible windows using PowerShell Get-Process."""
    try:
        cmd = (
            'powershell -NoProfile -Command "'
            "Get-Process | Where-Object {$_.MainWindowTitle -ne ''} | "
            "Select-Object ProcessName, MainWindowTitle, Id | ConvertTo-Json -Compress"
            '"'
        )
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout)
            if isinstance(data, dict):
                data = [data]
            apps = [
                {
                    "name": item.get("ProcessName", ""),
                    "title": item.get("MainWindowTitle", ""),
                    "pid": item.get("Id", 0),
                }
                for item in data
            ]
            return {"success": True, "apps": apps, "count": len(apps)}
        return {"success": True, "apps": [], "count": 0}
    except Exception as e:
        logger.error(f"Failed to list running apps: {e}")
        return {"success": False, "error": str(e)}


async def trigger_media_control(action: str) -> Dict[str, Any]:
    """Send media control keypresses (play/pause, next, prev, volume up/down, mute)."""
    return await asyncio.to_thread(_media_control_sync, action)


def _media_control_sync(action: str) -> Dict[str, Any]:
    """Send media keys via pyautogui."""
    try:
        import pyautogui

        key_map = {
            "play": "playpause",
            "pause": "playpause",
            "play_pause": "playpause",
            "next": "nexttrack",
            "previous": "prevtrack",
            "prev": "prevtrack",
            "volume_up": "volumeup",
            "volume_down": "volumedown",
            "mute": "volumemute",
            "stop": "stop",
        }
        key = key_map.get(action.lower().strip())
        if not key:
            return {"success": False, "error": f"Unknown media action: {action}. Valid: {list(key_map.keys())}"}

        pyautogui.press(key)
        return {"success": True, "action": action, "message": f"Media key '{key}' sent."}
    except ImportError:
        return {"success": False, "error": "pyautogui is not installed."}
    except Exception as e:
        return {"success": False, "error": str(e)}
