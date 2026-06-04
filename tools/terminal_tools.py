"""
Dorothy OS v2.0 — Terminal Execution Tools
Safe PowerShell command execution with blocked command filtering and timeout protection.
"""

import logging
import asyncio
import subprocess
from typing import Dict, Any

logger = logging.getLogger("Dorothy.Tools.Terminal")

# Dangerous command patterns that are always blocked
BLOCKED_COMMANDS = [
    "rmdir /s /q c:\\",
    "del /f /s /q c:\\",
    "format ",
    "mkfs ",
    "rm -rf /",
    "dd if=",
    ":(){ :|:& };:",
    "remove-item c:\\",
    "remove-item -recurse c:\\",
    "reg delete",
    "reg add",
    "bcdedit",
    "diskpart",
]


def _is_blocked(command: str) -> bool:
    """Check if a command matches any blocked pattern."""
    cmd_lower = command.lower().strip()
    for blocked in BLOCKED_COMMANDS:
        if blocked.lower() in cmd_lower:
            return True
    return False


async def execute_command(command: str) -> Dict[str, Any]:
    """Execute a PowerShell command safely with timeout protection."""
    if not command or not command.strip():
        return {"success": False, "error": "Empty command."}

    if _is_blocked(command):
        logger.warning(f"BLOCKED dangerous command: {command}")
        return {
            "success": False,
            "error": f"Command blocked by security policy: '{command[:50]}...'",
            "blocked": True,
        }

    logger.info(f"Executing terminal command: {command[:80]}...")
    return await asyncio.to_thread(_run_cmd_sync, command)


def _run_cmd_sync(command: str) -> Dict[str, Any]:
    """Synchronous PowerShell command runner (runs in thread)."""
    try:
        # Wrap command in PowerShell for consistent UTF-8 execution
        ps_command = (
            f'powershell -NoProfile -ExecutionPolicy Bypass '
            f'-Command "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; {command}"'
        )
        result = subprocess.run(
            ps_command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
            encoding="utf-8",
            errors="replace",
        )
        return {
            "success": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout.strip()[:5000],  # Cap output length
            "stderr": result.stderr.strip()[:2000],
            "command": command,
        }
    except subprocess.TimeoutExpired:
        logger.warning(f"Command timed out after 30s: {command[:50]}")
        return {"success": False, "error": "Command timed out after 30 seconds.", "command": command}
    except Exception as e:
        logger.error(f"Command execution failed: {e}")
        return {"success": False, "error": str(e), "command": command}
