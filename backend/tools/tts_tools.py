import os
import uuid
import logging
import asyncio
import edge_tts
import pyttsx3
from backend.config import TTS_HINDI_VOICE, TTS_ENGLISH_VOICE, TTS_OUTPUT_DIR

logger = logging.getLogger("JARVIS.TTSTools")

def detect_language(text: str) -> str:
    """Heuristic to detect language. Returns 'hi' if Devanagari chars are present, else 'en'."""
    # Check for Devanagari character block (U+0900 to U+097F)
    for char in text:
        if '\u0900' <= char <= '\u097F':
            return 'hi'
    return 'en'

def speak_fallback(text: str, language: str) -> str:
    """Synchronous fallback TTS using pyttsx3 to be run in a threadpool."""
    try:
        # Initialize pyttsx3 engine
        engine = pyttsx3.init()
        
        # Configure rate (speed)
        engine.setProperty('rate', 160)
        
        # Select voice based on language
        voices = engine.getProperty('voices')
        selected_voice_id = None
        
        # Look for custom voice matching language
        if language == 'hi':
            # Attempt to find a Hindi voice
            for v in voices:
                if 'hindi' in v.name.lower() or 'india' in v.name.lower() or 'hi' in getattr(v, 'languages', []):
                    selected_voice_id = v.id
                    break
        else:
            # Attempt to find an English (ideally male/Guy-like) voice
            for v in voices:
                if 'david' in v.name.lower() or 'guy' in v.name.lower() or 'en' in getattr(v, 'languages', []):
                    selected_voice_id = v.id
                    break
                    
        # Apply voice if found, otherwise uses default system voice
        if selected_voice_id:
            engine.setProperty('voice', selected_voice_id)
            
        filename = f"fallback_{uuid.uuid4().hex}.wav"
        filepath = os.path.join(TTS_OUTPUT_DIR, filename)
        
        # Save audio file
        engine.save_to_file(text, filepath)
        engine.runAndWait()
        
        # Force cleanup of the engine to avoid handle leaks
        del engine
        
        logger.info(f"Generated fallback audio via pyttsx3 at {filepath}")
        return filepath
    except Exception as e:
        logger.error(f"Fallback pyttsx3 generation failed: {e}", exc_info=True)
        raise e

async def speak(text: str, language: str = None) -> str:
    """Generate audio from text using high-quality edge-tts, with a pyttsx3 fallback."""
    if not text or not text.strip():
        raise ValueError("Cannot speak empty text, Sir.")
        
    if not language:
        language = detect_language(text)
        
    voice = TTS_HINDI_VOICE if language == 'hi' else TTS_ENGLISH_VOICE
    filename = f"tts_{uuid.uuid4().hex}.mp3"
    filepath = os.path.join(TTS_OUTPUT_DIR, filename)
    
    # Ensure temporary output directory exists
    os.makedirs(TTS_OUTPUT_DIR, exist_ok=True)
    
    try:
        logger.info(f"Attempting to generate TTS using edge-tts (voice={voice})")
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(filepath)
        
        if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
            logger.info(f"Successfully generated TTS at {filepath}")
            return filepath
        else:
            raise RuntimeError("Generated edge-tts file was empty or not created.")
            
    except Exception as e:
        logger.warning(f"edge-tts failed: {e}. Attempting pyttsx3 fallback...", exc_info=True)
        try:
            # Run synchronous pyttsx3 in an async executor thread
            fallback_filepath = await asyncio.to_thread(speak_fallback, text, language)
            return fallback_filepath
        except Exception as err:
            logger.error(f"Both TTS systems failed to generate audio: {err}", exc_info=True)
            raise RuntimeError("Unable to generate text-to-speech audio, Boss.")
