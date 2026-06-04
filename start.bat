@echo off
title Dorothy OS v2.0 — Enterprise AI Operating System
color 0B
echo.
echo  ╔══════════════════════════════════════════════════╗
echo  ║          Dorothy OS v2.0 — BOOTING UP            ║
echo  ║      Enterprise AI Operating System Layer       ║
echo  ╚══════════════════════════════════════════════════╝
echo.

:: Check if Ollama is running
echo [INIT] Checking Ollama service...
tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | find /I "ollama.exe" >NUL
if %ERRORLEVEL% NEQ 0 (
    echo [WARN] Ollama is not running. Starting Ollama...
    start "" ollama serve
    timeout /t 3 /nobreak >NUL
) else (
    echo [  OK] Ollama service is active.
)

:: Check virtual environment
if exist "venv\Scripts\activate.bat" (
    echo [INIT] Activating virtual environment...
    call venv\Scripts\activate.bat
) else if exist "..\dorothy\venv\Scripts\activate.bat" (
    echo [INIT] Using existing Dorothy venv...
    call ..\dorothy\venv\Scripts\activate.bat
) else (
    echo [INIT] Creating virtual environment...
    python -m venv venv
    call venv\Scripts\activate.bat
    echo [INIT] Installing dependencies...
    pip install -r requirements.txt
)

echo.
echo [BOOT] Starting Dorothy OS v2.0 server on port 8000...
echo [BOOT] Command Center UI: http://localhost:8000
echo.

:: Launch the server
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --log-level info

pause
