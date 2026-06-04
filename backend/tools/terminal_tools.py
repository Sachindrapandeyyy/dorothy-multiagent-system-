import subprocess
import asyncio
import logging
from typing import Dict, Any
from backend.config import BLOCKED_COMMANDS

logger = logging.getLogger("JARVIS.TerminalTools")

def run_cmd_sync(cmd: str) -> Dict[str, Any]:
    """Execute the PowerShell subshell synchronously with a timeout."""
    try:
        # Wrap command for powershell to ensure UTF-8 output encoding
        ps_cmd = f'powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; {cmd}"'
        
        # Execute using standard subprocess.run with 30s timeout
        res = subprocess.run(
            ps_cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30.0
        )
        stdout = res.stdout.decode("utf-8", errors="replace")
        stderr = res.stderr.decode("utf-8", errors="replace")
        returncode = res.returncode
    except subprocess.TimeoutExpired:
        stdout = ""
        stderr = "Error: Command timed out after 30 seconds. I had to terminate it for system stability, Boss."
        returncode = -2
    except Exception as e:
        stdout = ""
        stderr = f"Exception occurred during execution: {str(e)}"
        returncode = -3
        
    return {
        "stdout": stdout,
        "stderr": stderr,
        "returncode": returncode
    }

async def execute_command(cmd: str) -> Dict[str, Any]:
    """Execute a PowerShell command with safety checks and a 30 second timeout."""
    cmd_lower = cmd.strip().lower()
    
    # Safety Check: Block any harmful commands
    for blocked in BLOCKED_COMMANDS:
        if blocked.strip().lower() in cmd_lower:
            logger.warning(f"Blocked execution of command: {cmd} due to rule: {blocked}")
            return {
                "stdout": "",
                "stderr": f"Error: Access Denied. The command contains the blocked pattern/keyword: '{blocked.strip()}'. Running this command violates my safety protocols, Sir.",
                "returncode": -1
            }
            
    try:
        logger.info(f"Executing command: {cmd}")
        # Run synchronous subprocess inside an async thread pool to prevent blocking the event loop
        result = await asyncio.to_thread(run_cmd_sync, cmd)
        logger.info(f"Command finished with return code: {result['returncode']}")
        return result
    except Exception as e:
        logger.error(f"Failed to execute command '{cmd}': {e}", exc_info=True)
        return {
            "stdout": "",
            "stderr": f"Exception occurred during execution: {str(e)}",
            "returncode": -3
        }
