"""
Dorothy OS v2.0 — Real-Time Voice Pipeline
End-to-end pipeline: Browser audio → faster-whisper STT → Dorothy brain → Streaming TTS
Designed for sub-second perceived latency via sentence-level TTS streaming.
"""

import os
import logging
import asyncio
from typing import Optional, List, Dict, Any

from voice.stt_service import stt_service

logger = logging.getLogger("Dorothy.Voice.Pipeline")


class VoicePipeline:
    """
    Orchestrates the full voice interaction loop:
    1. Receive raw WAV audio bytes from browser via WebSocket
    2. Transcribe with faster-whisper (local, offline, fast)
    3. Route through Dorothy's multi-agent brain
    4. Stream TTS audio sentences back in real-time
    """

    def __init__(self) -> None:
        self.active_sessions: Dict[str, bool] = {}  # websocket_id → is_processing

    async def process_voice_input(
        self,
        audio_bytes: bytes,
        session_id: str,
        conversation_history: List[Dict[str, str]],
        websocket,
        manager,
        supervisor,
        llm,
        memory_store,
    ) -> Optional[str]:
        """
        Full pipeline: audio → text → Dorothy response → streaming TTS.
        Returns the transcribed text, or None if transcription failed.
        """

        # ── Step 1: Send "listening" status ─────────────────────────
        await self._send_voice_status(websocket, manager, "transcribing", "🎤 Processing your voice...")

        # ── Step 2: Transcribe audio with faster-whisper ─────────────
        try:
            transcript = await stt_service.transcribe_audio_bytes(audio_bytes)
        except Exception as e:
            logger.error(f"STT error: {e}")
            transcript = None

        if not transcript or len(transcript.strip()) < 2:
            await self._send_voice_status(websocket, manager, "idle", "❌ Could not understand audio. Try again.")
            logger.warning("Voice input: transcription empty or too short.")
            return None

        logger.info(f"🎤 Voice command: '{transcript}'")

        # ── Step 3: Echo transcript back to UI ───────────────────────
        await manager.send_personal({
            "type": "voice_transcript",
            "data": {
                "text": transcript,
                "status": "final"
            }
        }, websocket)

        await self._send_voice_status(websocket, manager, "thinking", "🧠 Dorothy is thinking...")

        # ── Step 4: Add to conversation history ──────────────────────
        conversation_history.append({"role": "user", "content": transcript})

        # ── Step 5: Save to semantic memory (non-blocking) ───────────
        from datetime import datetime
        asyncio.create_task(memory_store.add_document(
            transcript,
            {"role": "user", "timestamp": datetime.now().isoformat(), "source": "voice"}
        ))

        # ── Step 6: Fast intent routing (Layer 1) ────────────────────
        from orchestrator.action_executor import execute_intent
        action_result = await execute_intent(transcript)
        if action_result:
            agent_id = action_result.get("agent_id", "system")
            try:
                from main import update_agent_status
                await update_agent_status(agent_id, "working")
            except Exception:
                pass

        # ── Step 7: Full multi-agent graph execution ──────────────────
        await self._send_voice_status(websocket, manager, "processing", "⚡ Multi-agent pipeline running...")

        final_state = await supervisor.execute_graph(
            query=transcript,
            history=conversation_history,
            websocket=websocket,
            manager=manager,
            action_result=action_result,
        )

        # ── Step 8: Save response to history ─────────────────────────
        response_text = final_state.get("response_tokens", "")
        if response_text:
            conversation_history.append({"role": "assistant", "content": response_text})
            asyncio.create_task(memory_store.add_document(
                response_text,
                {"role": "assistant", "timestamp": datetime.now().isoformat(), "source": "voice_response"}
            ))

        # ── Step 9: Send end marker and restore idle status ──────────
        await manager.send_personal(
            {"type": "chat_response", "data": {"type": "end"}},
            websocket,
        )
        await self._send_voice_status(websocket, manager, "idle", "✅ Ready")

        return transcript

    async def _send_voice_status(
        self,
        websocket,
        manager,
        status: str,
        label: str,
    ) -> None:
        """Send voice pipeline status update to the browser."""
        try:
            await manager.send_personal({
                "type": "voice_status",
                "data": {"status": status, "label": label}
            }, websocket)
        except Exception as e:
            logger.debug(f"Could not send voice status: {e}")


# ─── Singleton ────────────────────────────────────────────────────────────────

voice_pipeline = VoicePipeline()
