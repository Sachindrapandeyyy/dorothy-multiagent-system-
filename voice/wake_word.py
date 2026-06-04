"""
Dorothy OS v2.0 — Hands-Free Wake Word Detection.
Monitors microphone streams for 'Hey Dorothy' noise levels or keywords.
"""

import logging
import asyncio
from typing import Callable, Optional, Any
from voice.stt_service import stt_service

logger = logging.getLogger("Dorothy.Voice.WakeWord")

class WakeWordDetector:
    """Listens continuously in the background for "Hey Dorothy" wake triggers."""

    def __init__(self, callback: Optional[Callable[[str], Any]] = None) -> None:
        self.callback = callback
        self.is_running = False
        self._task = None

    def start(self, callback: Callable[[str], Any]) -> None:
        """Start continuous background wake-word listening."""
        if self.is_running:
            return
        self.callback = callback
        self.is_running = True
        self._task = asyncio.create_task(self._listen_loop())
        logger.info("Wake word detector started in the background.")

    def stop(self) -> None:
        """Stop background wake-word listening."""
        self.is_running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("Wake word detector stopped.")

    async def _listen_loop(self) -> None:
        """Continuous async loop scanning microphone inputs."""
        
        if not stt_service.initialize():
            logger.warning("Continuous backend WakeWord failed: speech_recognition not installed.")
            return

        while self.is_running:
            try:
                # Capture short audio fragment
                text = await stt_service.transcribe_microphone(timeout=3.0)
                if text:
                    cleaned = text.lower().strip()
                    if "dorothy" in cleaned or "hey dorothy" in cleaned:
                        logger.info("🚀 WAKE WORD DETECTED: 'Hey Dorothy'")
                        
                        # Extract the command if any, or trigger active command mode
                        command = cleaned.split("dorothy", 1)[-1].strip()
                        if self.callback:
                            if asyncio.iscoroutinefunction(self.callback):
                                await self.callback(command)
                            else:
                                self.callback(command)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in continuous wake-word detector: {e}")
                await asyncio.sleep(2)

wake_detector = WakeWordDetector()
