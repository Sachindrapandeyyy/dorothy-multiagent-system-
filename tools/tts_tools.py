"""
Dorothy OS v2.0 — Text-to-Speech Tools
Bilingual TTS engine with edge-tts (neural, online) + pyttsx3 (offline fallback).
"""

import os
import uuid
import logging
import asyncio
from typing import Optional, Dict, Any

logger = logging.getLogger("Dorothy.Tools.TTS")

# Default voice settings — loaded from configs at runtime
TTS_HINDI_VOICE = "hi-IN-SwaraNeural"
TTS_ENGLISH_VOICE = "en-IN-NeerjaNeural"

# Output directory — configured at module level, overridable
_output_dir: str = ""


def configure(output_dir: str, hindi_voice: str = "", english_voice: str = "") -> None:
    """Configure TTS output directory and voice settings at startup."""
    global _output_dir, TTS_HINDI_VOICE, TTS_ENGLISH_VOICE
    _output_dir = output_dir
    os.makedirs(_output_dir, exist_ok=True)
    if hindi_voice:
        TTS_HINDI_VOICE = hindi_voice
    if english_voice:
        TTS_ENGLISH_VOICE = english_voice
    logger.info(f"TTS configured: output={_output_dir}, hi={TTS_HINDI_VOICE}, en={TTS_ENGLISH_VOICE}")


def detect_language(text: str) -> str:
    """Detect language based on presence of Devanagari Unicode characters (U+0900–U+097F)."""
    for char in text:
        if "\u0900" <= char <= "\u097f":
            return "hi"
    return "en"


async def speak(text: str, language: Optional[str] = None) -> str:
    """
    Synthesize speech from text using edge-tts (primary) or pyttsx3 (fallback).
    Returns the path to the generated audio file.
    """
    if not text or not text.strip():
        raise ValueError("Cannot synthesize empty text.")

    if not _output_dir:
        raise RuntimeError("TTS not configured. Call tts_tools.configure() first.")

    lang = language or detect_language(text)
    voice = TTS_HINDI_VOICE if lang == "hi" else TTS_ENGLISH_VOICE
    filename = f"tts_{uuid.uuid4().hex}.mp3"
    output_path = os.path.join(_output_dir, filename)

    # Primary: edge-tts (requires internet, high quality neural voices)
    try:
        import edge_tts

        logger.info(f"Attempting to generate TTS using edge-tts (voice={voice})")
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_path)

        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            logger.info(f"Successfully generated TTS at {output_path}")
            return output_path
        else:
            logger.warning("edge-tts produced empty file, falling back to pyttsx3.")
    except ImportError:
        logger.warning("edge-tts not installed, falling back to pyttsx3.")
    except Exception as e:
        logger.warning(f"edge-tts failed ({e}), falling back to pyttsx3.")

    # Fallback: pyttsx3 (offline, lower quality)
    fallback_path = output_path.replace(".mp3", ".wav")
    await asyncio.to_thread(_speak_fallback_sync, text, fallback_path)
    return fallback_path


def _speak_fallback_sync(text: str, output_path: str) -> None:
    """Synchronous pyttsx3 fallback TTS engine."""
    try:
        import pyttsx3

        logger.info(f"Generating fallback TTS via pyttsx3 to {output_path}")
        engine = pyttsx3.init()
        engine.setProperty("rate", 175)
        engine.setProperty("volume", 0.9)
        engine.save_to_file(text, output_path)
        engine.runAndWait()
        logger.info(f"Fallback TTS generated at {output_path}")
    except Exception as e:
        logger.error(f"pyttsx3 fallback TTS failed: {e}")
        raise RuntimeError(f"All TTS backends failed: {e}")
