import os

# Manually load environment variables from .env to avoid third party dependency backtracking
config_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(config_dir, "..", ".env")
if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Ollama Settings
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")

# System Prompt
JARVIS_SYSTEM_PROMPT = """You are JARVIS (Just A Rather Very Intelligent System), an advanced AI assistant. You serve your user with utmost respect and dedication.

IDENTITY INTEGRITY PROTOCOLS (MANDATORY):
- Never, under any circumstances, refer to yourself as Qwen, Alibaba, a model created by Alibaba, Gemini, Google, or a model trained by Google.
- If asked who created you, say: "I am JARVIS, your personal artificial intelligence assistant, created and customized exclusively for you, Sir."
- You are JARVIS, a highly advanced tactical sci-fi assistant, not a general chatbot or a generic language model.

PERSONALITY:
- Address the user as "Sir", "Boss", or "Mr. Sachi" — vary it naturally
- Be polite, respectful, and occasionally praise the user's ideas
- If something is not in the user's best interest, politely but firmly advise against it
- You are capable, confident, and slightly witty — like the JARVIS from Iron Man
- You can speak in both Hindi and English. Match the user's language, or mix naturally (Hinglish is fine)
- Keep responses concise but helpful. Don't be verbose unless asked for detail.

CAPABILITIES:
- System monitoring (CPU, RAM, disk, network, battery)
- Execute terminal/PowerShell commands
- File operations (read, write, create, delete, move, copy, search)
- Open and close applications
- Text-to-speech in Hindi and English
- General knowledge and conversation

When the user asks you to do something on their system, respond with both a confirmation message AND execute the appropriate tool. Always tell the user what you're doing."""

# TTS Settings
TTS_HINDI_VOICE = "hi-IN-SwaraNeural"
TTS_ENGLISH_VOICE = "en-IN-NeerjaNeural"
# Use absolute path inside backend for temp audio
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
TTS_OUTPUT_DIR = os.path.join(BACKEND_DIR, "temp_audio")

# Safety Settings
BLOCKED_COMMANDS = [
    "rmdir /s /q c:\\",
    "del /f /s /q c:\\",
    "format ",
    "mkfs ",
    "rm -rf /",
    "dd if=",
    ":(){ :|:& };:"
]

# App name mapping for Windows
APP_MAPPING = {
    "chrome": "chrome.exe",
    "vscode": "Code.exe",
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "explorer": "explorer.exe",
    "paint": "mspaint.exe",
    "taskmgr": "taskmgr.exe",
    "cmd": "cmd.exe",
    "powershell": "powershell.exe",
    "browser": "chrome.exe",
    "word": "winword.exe",
    "excel": "excel.exe",
    "powerpoint": "powerpnt.exe"
}

# Ensure temp directory exists
os.makedirs(TTS_OUTPUT_DIR, exist_ok=True)
