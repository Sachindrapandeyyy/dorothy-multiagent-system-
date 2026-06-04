import os
import json
import logging
import asyncio
import subprocess
from typing import Dict, Any, List
from backend.config import APP_MAPPING

logger = logging.getLogger("JARVIS.AppTools")

async def open_application(name: str) -> Dict[str, Any]:
    """Launch a Windows application by name or mapping."""
    name_lower = name.lower().strip()
    
    # Check if application exists in the mapping
    app_exe = APP_MAPPING.get(name_lower, name)
    
    try:
        logger.info(f"Attempting to launch application: {name} (resolved to: {app_exe})")
        
        # Use os.startfile on Windows for robust execution (it handles system paths, protocols, shortcuts, etc.)
        def _launch():
            try:
                os.startfile(app_exe)
                return True
            except FileNotFoundError:
                # If startfile fails, try running it as a shell command as fallback
                return False
                
        launched = await asyncio.to_thread(_launch)
        
        if launched:
            return {"success": True, "message": f"Successfully launched {name}, Boss."}
            
        # Fallback to subprocess search/execution
        def _fallback_launch():
            res = subprocess.run(
                f"start {app_exe}",
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=10.0
            )
            return res.returncode == 0, res.stderr.decode('utf-8', errors='replace')

        success, err_msg = await asyncio.to_thread(_fallback_launch)
        if success:
            return {"success": True, "message": f"Launched {name} via shell execution, Sir."}
        else:
            logger.error(f"Failed to launch app '{name}': {err_msg}")
            return {"success": False, "error": f"Could not find or open application: {name}. {err_msg}"}
            
    except Exception as e:
        logger.error(f"Error opening application {name}: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

async def close_application(name: str) -> Dict[str, Any]:
    """Close a running Windows application by killing its process."""
    name_lower = name.lower().strip()
    
    # Resolve process name
    app_exe = APP_MAPPING.get(name_lower, name)
    if not app_exe.endswith(".exe"):
        app_exe += ".exe"
        
    try:
        logger.info(f"Attempting to terminate application process: {app_exe}")
        
        def _terminate():
            res = subprocess.run(
                f"taskkill /IM {app_exe} /F",
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=10.0
            )
            return res.returncode, res.stderr.decode('utf-8', errors='replace')
            
        returncode, err_msg = await asyncio.to_thread(_terminate)
        
        if returncode == 0:
            return {"success": True, "message": f"Successfully closed {name} ({app_exe}), Sir."}
        else:
            if "not found" in err_msg.lower():
                return {"success": False, "error": f"Process {app_exe} is not currently running, Boss."}
            return {"success": False, "error": err_msg}
            
    except Exception as e:
        logger.error(f"Error closing application {name}: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

async def list_running_apps() -> Dict[str, Any]:
    """Retrieve a filtered list of user-visible windows currently running."""
    try:
        # PowerShell command to fetch processes with visible main window titles
        cmd = 'Get-Process | Where-Object {$_.MainWindowTitle -ne ""} | Select-Object -Property Id, ProcessName, MainWindowTitle | ConvertTo-Json -Compress'
        
        def _list_apps():
            res = subprocess.run(
                f'powershell.exe -NoProfile -NonInteractive -Command "{cmd}"',
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=15.0
            )
            return res.returncode, res.stdout.decode('utf-8', errors='replace'), res.stderr.decode('utf-8', errors='replace')
            
        returncode, stdout, stderr = await asyncio.to_thread(_list_apps)
        
        if returncode != 0:
            logger.error(f"Failed to list running apps: {stderr}")
            return {"success": False, "error": stderr}
            
        output = stdout.strip()
        if not output:
            return {"success": True, "apps": []}
            
        # Parse JSON output from PowerShell
        try:
            data = json.loads(output)
            # Ensure it is a list
            if isinstance(data, dict):
                data = [data]
                
            # Filter and structure
            apps = []
            for item in data:
                apps.append({
                    "pid": item.get("Id"),
                    "name": item.get("ProcessName"),
                    "title": item.get("MainWindowTitle")
                })
            return {"success": True, "apps": apps}
        except json.JSONDecodeError:
            # Fallback parsing in case output is not valid compact JSON
            return {"success": True, "apps": [], "raw": output}
            
    except Exception as e:
        logger.error(f"Error listing running applications: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

async def trigger_media_control(action: str) -> Dict[str, Any]:
    """Emulate media control key presses (playpause, nexttrack, prevtrack, volumemute)."""
    action_lower = action.lower().strip()
    valid_actions = ["playpause", "nexttrack", "prevtrack", "volumemute"]
    if action_lower not in valid_actions:
        return {"success": False, "error": f"Invalid media key: '{action}'."}
    try:
        import pyautogui
        def _press():
            pyautogui.press(action_lower)
        await asyncio.to_thread(_press)
        return {"success": True, "message": f"Triggered media control: '{action_lower}'"}
    except Exception as e:
        logger.error(f"Error triggering media control {action}: {e}")
        return {"success": False, "error": str(e)}
