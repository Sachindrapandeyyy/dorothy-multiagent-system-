"""
Dorothy OS v2.0 — Ultra-Fast Local Speech-to-Text Service
Uses faster-whisper (CTranslate2) for 10x faster transcription than Google STT.
Runs fully offline — no API keys, no network needed.
"""

import io
import logging
import asyncio
import struct
import wave
from typing import Optional

logger = logging.getLogger("Dorothy.Voice.STT")

class STTService:
    """
    Ultra-fast local STT using faster-whisper.
    Falls back to browser Web Speech API if faster-whisper not installed.
    """

    def __init__(self, model_size: str = "base") -> None:
        self.model = None
        self.model_size = model_size
        self._initialized = False
        self._loading = False

    def initialize(self) -> bool:
        """Load faster-whisper model (lazy load on first use)."""
        if self._initialized:
            return True
        if self._loading:
            return False
        self._loading = True
        try:
            from faster_whisper import WhisperModel
            logger.info(f"Loading faster-whisper model: '{self.model_size}' (first load may take ~10s)...")
            # int8 = fastest CPU inference, no GPU needed
            self.model = WhisperModel(
                self.model_size,
                device="cpu",
                compute_type="int8",
                download_root=None,
            )
            self._initialized = True
            logger.info(f"✓ faster-whisper '{self.model_size}' model loaded. Dorothy is voice-ready.")
            return True
        except ImportError:
            logger.warning("faster-whisper not installed. Run: pip install faster-whisper")
            return False
        except Exception as e:
            logger.error(f"Failed to load faster-whisper: {e}")
            return False
        finally:
            self._loading = False

    async def transcribe_audio_bytes(self, audio_bytes: bytes, language: str = "en") -> Optional[str]:
        """
        Transcribe raw audio bytes (WAV format) to text.
        Audio must be 16kHz mono PCM WAV.
        Returns transcribed text or None.
        """
        if not audio_bytes or len(audio_bytes) < 1000:
            logger.warning("Audio too short to transcribe.")
            return None

        if not self.initialize():
            logger.warning("STT not initialized — faster-whisper unavailable.")
            return None

        loop = asyncio.get_event_loop()

        def _transcribe():
            try:
                import numpy as np
                # Parse WAV bytes
                with io.BytesIO(audio_bytes) as buf:
                    with wave.open(buf, 'rb') as wf:
                        n_frames = wf.getnframes()
                        raw_pcm = wf.readframes(n_frames)
                        sample_rate = wf.getframerate()
                        n_channels = wf.getnchannels()
                        sampwidth = wf.getsampwidth()

                # Convert to float32 numpy array
                if sampwidth == 2:
                    audio_np = np.frombuffer(raw_pcm, dtype=np.int16).astype(np.float32) / 32768.0
                elif sampwidth == 4:
                    audio_np = np.frombuffer(raw_pcm, dtype=np.int32).astype(np.float32) / 2147483648.0
                else:
                    audio_np = np.frombuffer(raw_pcm, dtype=np.float32)

                # Mix stereo to mono
                if n_channels == 2:
                    audio_np = audio_np.reshape(-1, 2).mean(axis=1)

                # Resample to 16kHz if needed (faster-whisper expects 16kHz)
                if sample_rate != 16000:
                    try:
                        import resampy
                        audio_np = resampy.resample(audio_np, sample_rate, 16000)
                    except ImportError:
                        # Simple decimation fallback
                        ratio = sample_rate // 16000
                        if ratio > 1:
                            audio_np = audio_np[::ratio]

                # Transcribe with faster-whisper
                segments, info = self.model.transcribe(
                    audio_np,
                    language=language,
                    beam_size=1,           # fastest beam search
                    best_of=1,             # no sampling overhead
                    vad_filter=True,       # skip silence automatically
                    vad_parameters=dict(min_silence_duration_ms=300),
                    condition_on_previous_text=False,
                )

                text = " ".join(seg.text.strip() for seg in segments).strip()
                logger.info(f"✓ Transcribed ({info.language}, {info.duration:.1f}s audio): '{text}'")
                return text or None

            except Exception as e:
                logger.error(f"Transcription error: {e}", exc_info=True)
                return None

        return await loop.run_in_executor(None, _transcribe)

    async def transcribe_microphone(self, timeout: float = 5.0) -> Optional[str]:
        """Legacy microphone capture via SpeechRecognition (fallback)."""
        try:
            import speech_recognition as sr
            recognizer = sr.Recognizer()
            loop = asyncio.get_event_loop()

            def record():
                with sr.Microphone() as source:
                    recognizer.adjust_for_ambient_noise(source, duration=0.3)
                    try:
                        audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=10.0)
                        return audio
                    except sr.WaitTimeoutError:
                        return None

            audio = await loop.run_in_executor(None, record)
            if not audio:
                return None

            def transcribe():
                try:
                    return recognizer.recognize_google(audio)
                except Exception:
                    return None

            return await loop.run_in_executor(None, transcribe)

        except ImportError:
            logger.warning("SpeechRecognition not available.")
            return None
        except Exception as e:
            logger.error(f"Microphone transcription error: {e}")
            return None


# Singleton instance — model_size "base" balances speed vs accuracy
# Use "tiny" for absolute fastest (less accurate), "small" for higher quality
stt_service = STTService(model_size="base")
