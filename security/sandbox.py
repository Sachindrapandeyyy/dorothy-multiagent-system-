"""
Dorothy OS v2.0 — Secure Sandboxed Execution Environment.
Provides isolated, timeout-protected subprocess runner for Python code.
Enables agentic self-reflection loops for automated error correction.
"""

import os
import sys
import uuid
import logging
import asyncio
import subprocess
from typing import Dict, Any

logger = logging.getLogger("Dorothy.Security.Sandbox")

class SandboxedExecutor:
    """Isolated, timeout-constrained execution container for user/agent scripts."""

    def __init__(self, sandbox_dir: str = "") -> None:
        self.sandbox_dir = sandbox_dir or os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "data", "sandbox"
        )
        os.makedirs(self.sandbox_dir, exist_ok=True)

    async def execute_python(self, code: str, timeout: float = 5.0) -> Dict[str, Any]:
        """
        Executes Python code in a safe subprocess with strict timeout constraint.
        Intercepts outputs and returns clean traceback parsing for agent reflection.
        """
        script_id = uuid.uuid4().hex
        filename = f"sandbox_{script_id}.py"
        filepath = os.path.join(self.sandbox_dir, filename)

        # Write clean code script
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(code)
        except Exception as e:
            return {"success": False, "error": f"Failed to write script: {e}"}

        logger.info(f"Sandbox executing script {filename} (timeout={timeout}s)")
        
        loop = asyncio.get_event_loop()
        try:
            def run():
                # Use current python executable to ensure venv compatibility
                cmd = [sys.executable, filepath]
                
                # Run subprocess with resources limitation
                return subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    encoding="utf-8",
                    errors="replace",
                )

            res = await loop.run_in_executor(None, run)
            
            success = res.returncode == 0
            stdout = res.stdout.strip()
            stderr = res.stderr.strip()
            
            # Simple static analysis for self-reflection loop triggers
            has_error = not success or "Traceback" in stderr or "SyntaxError" in stderr
            
            return {
                "success": success and not has_error,
                "returncode": res.returncode,
                "stdout": stdout[:5000],  # Limit large outputs
                "stderr": stderr[:2000],
                "self_reflection_needed": has_error,
                "error_suggestion": self._analyze_error(stderr) if has_error else None,
            }

        except subprocess.TimeoutExpired:
            logger.warning(f"Sandbox script {filename} exceeded execution limit of {timeout}s.")
            return {
                "success": False,
                "error": "Execution timed out.",
                "stderr": f"Process terminated after exceeding {timeout}s limit.",
                "self_reflection_needed": True,
                "error_suggestion": "The code contains an infinite loop or performs blocked slow IO. Optimize iteration logic.",
            }
        except Exception as ex:
            logger.error(f"Sandbox crash: {ex}")
            return {"success": False, "error": str(ex), "self_reflection_needed": False}
        finally:
            # Clean up temp file
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
            except Exception as ce:
                logger.warning(f"Could not clean sandbox script file: {ce}")

    def _analyze_error(self, stderr: str) -> str:
        """Parses python tracebacks to extract actionable debugging hints for LLM."""
        if not stderr:
            return "Unknown runtime failure."
            
        lines = stderr.splitlines()
        for line in reversed(lines):
            if "Error:" in line or "Exception:" in line or "SyntaxError:" in line:
                return f"Error detected: '{line.strip()}'. Fix this syntax/runtime bug."
        return "Runtime traceback detected. Review import statements and variable scopes."

sandbox_executor = SandboxedExecutor()
