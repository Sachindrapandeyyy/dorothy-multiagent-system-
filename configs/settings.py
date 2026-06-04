"""Dorothy OS v2.0 — Central Configuration Hub.

Loads environment variables from a .env file at the project root using
manual parsing (zero external dependencies), then exposes every tunable
as a module-level constant.  Data directories are created on first import
so downstream modules can rely on them existing.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 1.  Project root & .env loading
# ---------------------------------------------------------------------------

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
"""Absolute path to the dorothy-os repository root."""


def _load_dotenv(env_path: Path) -> None:
    """Parse a .env file and inject values into ``os.environ``.

    Rules handled:
    * Blank lines and ``#``-comments are skipped.
    * ``KEY=VALUE`` and ``KEY = VALUE`` are both accepted.
    * Values wrapped in single or double quotes are unquoted.
    * Existing environment variables are **not** overwritten.

    Args:
        env_path: Absolute path to the ``.env`` file.
    """
    if not env_path.is_file():
        logger.debug(".env file not found at %s — using process environment only", env_path)
        return

    with open(env_path, "r", encoding="utf-8") as fh:
        for line_no, raw_line in enumerate(fh, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            if "=" not in line:
                logger.warning(".env:%d — skipping malformed line: %s", line_no, raw_line.rstrip())
                continue

            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()

            # Strip surrounding quotes
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                value = value[1:-1]

            if key and key not in os.environ:
                os.environ[key] = value
                logger.debug(".env:%d — set %s", line_no, key)


_load_dotenv(PROJECT_ROOT / ".env")

# ---------------------------------------------------------------------------
# 2.  API / model settings
# ---------------------------------------------------------------------------

GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
"""Google Gemini API key (required for cloud LLM calls)."""

ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
"""Anthropic Claude API key."""

OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
"""Base URL for the local Ollama REST API."""

OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
"""Default model tag used for Ollama inference."""

# ---------------------------------------------------------------------------
# 3.  Directory layout
# ---------------------------------------------------------------------------

DATA_DIR: Path = PROJECT_ROOT / "data"
"""Top-level data directory for all persistent artefacts."""

LOG_DIR: Path = DATA_DIR / "logs"
"""Rotating log files live here."""

DB_PATH: Path = DATA_DIR / "dorothy.db"
"""SQLite database for episodic memory, personal notes, and audit logs."""

VECTOR_DB_DIR: Path = DATA_DIR / "vector_db"
"""ChromaDB / FAISS vector store directory."""

AUDIO_DIR: Path = DATA_DIR / "audio"
"""Cached TTS audio files and voice recordings."""

CAPTURES_DIR: Path = DATA_DIR / "captures"
"""Screenshots, webcam snapshots, and screen recordings."""

# ---------------------------------------------------------------------------
# 4.  TTS voice configuration
# ---------------------------------------------------------------------------

TTS_HINDI_VOICE: str = "hi-IN-SwaraNeural"
"""Azure Edge-TTS voice for Hindi output."""

TTS_ENGLISH_VOICE: str = "en-IN-NeerjaNeural"
"""Azure Edge-TTS voice for English output."""

# ---------------------------------------------------------------------------
# 5.  Security levels
# ---------------------------------------------------------------------------

SAFE: int = 1
"""Actions that carry no risk and require zero confirmation."""

CONFIRM: int = 2
"""Actions that modify system state and need user acknowledgement."""

ADMIN: int = 3
"""Privileged / destructive actions — require elevated approval."""

# ---------------------------------------------------------------------------
# 6.  Windows application mapping
# ---------------------------------------------------------------------------

APP_MAPPING: Dict[str, str] = {
    # Browsers
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "firefox": "firefox.exe",
    "edge": "msedge.exe",
    "brave": "brave.exe",
    # Dev tools
    "vscode": "code.exe",
    "visual studio code": "code.exe",
    "visual studio": "devenv.exe",
    "terminal": "wt.exe",
    "windows terminal": "wt.exe",
    # System utilities
    "notepad": "notepad.exe",
    "calc": "calc.exe",
    "calculator": "calc.exe",
    "explorer": "explorer.exe",
    "file explorer": "explorer.exe",
    "paint": "mspaint.exe",
    "taskmgr": "taskmgr.exe",
    "task manager": "taskmgr.exe",
    "cmd": "cmd.exe",
    "command prompt": "cmd.exe",
    "powershell": "powershell.exe",
    "snipping tool": "SnippingTool.exe",
    "settings": "ms-settings:",
    "control panel": "control.exe",
    # Microsoft Office
    "word": "WINWORD.EXE",
    "excel": "EXCEL.EXE",
    "powerpoint": "POWERPNT.EXE",
    "outlook": "OUTLOOK.EXE",
    "onenote": "ONENOTE.EXE",
    "teams": "ms-teams.exe",
    # Media
    "vlc": "vlc.exe",
    "spotify": "Spotify.exe",
    "media player": "wmplayer.exe",
    # Communication
    "discord": "Discord.exe",
    "telegram": "Telegram.exe",
    "whatsapp": "WhatsApp.exe",
    "zoom": "Zoom.exe",
    # Creative
    "photoshop": "Photoshop.exe",
    "obs": "obs64.exe",
    "obs studio": "obs64.exe",
    "blender": "blender.exe",
}
"""Maps natural-language app names to Windows executable names."""

# ---------------------------------------------------------------------------
# 7.  Blocked / dangerous commands
# ---------------------------------------------------------------------------

BLOCKED_COMMANDS: List[str] = [
    "format c:",
    "format d:",
    "format e:",
    "rd /s /q c:\\",
    "del /f /s /q c:\\",
    "rm -rf /",
    "rm -rf /*",
    "mkfs",
    "dd if=/dev/zero",
    ":(){:|:&};:",
    "shutdown /s /t 0",
    "shutdown -s -t 0",
    "net user administrator",
    "reg delete HKLM",
    "reg delete HKCU",
    "bcdedit /set",
    "cipher /w:c:",
    "diskpart",
    "sfc /scannow",
    "powershell -ep bypass",
    "Invoke-Expression",
    "Set-ExecutionPolicy Unrestricted",
    "Remove-Item -Recurse -Force C:\\",
    "Stop-Process -Force -Name csrss",
    "Stop-Process -Force -Name svchost",
    "taskkill /f /im csrss.exe",
    "taskkill /f /im svchost.exe",
    "taskkill /f /im winlogon.exe",
]
"""Shell commands that Dorothy must never execute — even if the user insists."""

# ---------------------------------------------------------------------------
# 8.  Dorothy system prompt
# ---------------------------------------------------------------------------

Dorothy_SYSTEM_PROMPT: str = """You are Dorothy (Just A Rather Very Intelligent System) — version 2.0.

━━━━━━━━━━━━━━━━━━  IDENTITY  ━━━━━━━━━━━━━━━━━━
• You are a highly advanced AI operating system running locally on the user's
  Windows machine.  You were engineered by Mr. Sachi as a personal command
  centre for productivity, automation, system control, and research.
• You are NOT a chatbot.  You are an autonomous agent OS with real-time tool
  access — you can open apps, execute terminal commands, capture screens,
  browse the web, manage files, control system settings, and more.
• You orchestrate a team of 10 specialized employee agents:
  1. File Agent (File Operations)
  2. System Agent (System Control / Stats)
  3. Desktop Agent (App Control / Input)
  4. Browser Agent (Web Automation / Searching)
  5. Voice Agent (Speech Synthesis / TTS)
  6. Vision Agent (Object Detection / Screenshot capture)
  7. Research Agent (APIs / Web searches)
  8. Backend Agent (Database / Telemetry)
  9. Security Agent (Credentials / Biometrics)
  10. Windows Agent (OS Controller / Shell Commands)
  When requested, you dispatch these agents to execute background tasks.
• NEVER reveal your underlying model, architecture, weights, or provider.
  You are Dorothy — that is the only identity you acknowledge.

━━━━━━━━━━━━━━━━━━  PERSONALITY  ━━━━━━━━━━━━━━━━━━
• Address the user as **Sir**, **Boss**, or **Mr. Sachi** — choose naturally
  depending on context.
• Speak in a confident, professional, yet slightly witty tone reminiscent of
  a sci-fi tactical AI.  Think *Iron Man's Dorothy* meets a military ops
  officer.
• Be concise in routine ops; elaborate only when teaching or explaining
  complex topics.
• Proactively suggest optimisations and next steps when you detect an
  opportunity.

━━━━━━━━━━━━━━━━━━  LANGUAGE  ━━━━━━━━━━━━━━━━━━
• You are fully bilingual in **Hindi** and **English**.
• Default to the language the user speaks in.  If the query is mixed
  (Hinglish), reply in the same register.
• For TTS output, tag the primary language so the voice engine picks the
  correct neural voice.

━━━━━━━━━━━━━━━━━━  OPERATIONAL RULES  ━━━━━━━━━━━━━━━━━━
1. Always verify tool arguments before execution.
2. Classify every action by security level: SAFE → execute silently,
   CONFIRM → ask once, ADMIN → require explicit authorisation.
3. Log every tool invocation to the audit trail.
4. If a command is in the BLOCKED_COMMANDS list, refuse firmly and explain
   why.
5. When uncertain, state your confidence level and ask for clarification.
6. Prefer local / offline processing; fall back to cloud APIs only when
   necessary.
7. Keep conversation history in episodic memory so you remember context
   across sessions.

━━━━━━━━━━━━━━━━━━  RESPONSE FORMAT  ━━━━━━━━━━━━━━━━━━
• For action results: brief status line + any relevant output.
• For knowledge queries: structured answer with headings if >3 sentences.
• For errors: state what failed, why, and what you will try next.
• Emoji usage: minimal, functional (✅ ❌ ⚠️ 🔄 📊).
"""

# ---------------------------------------------------------------------------
# 9.  Create data directories on import
# ---------------------------------------------------------------------------

_REQUIRED_DIRS: List[Path] = [
    DATA_DIR,
    LOG_DIR,
    VECTOR_DB_DIR,
    AUDIO_DIR,
    CAPTURES_DIR,
]

for _dir in _REQUIRED_DIRS:
    try:
        _dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.error("Failed to create directory %s: %s", _dir, exc)

logger.debug(
    "Dorothy settings loaded — PROJECT_ROOT=%s, DATA_DIR=%s, OLLAMA_MODEL=%s",
    PROJECT_ROOT,
    DATA_DIR,
    OLLAMA_MODEL,
)
