@echo off
echo ============================================
echo   🤖 JARVIS AI SYSTEM — INITIALIZING...
echo ============================================

:: Check Ollama
ollama list > nul 2>&1
if errorlevel 1 (
    echo [ERROR] Ollama is not running. Start it first.
    pause
    exit /b 1
)

:: Start backend
cd backend
start "" python -m uvicorn main:app --host 0.0.0.0 --port 8000

:: Wait for server
timeout /t 3 /nobreak > nul

:: Open browser
start http://localhost:8000

echo ============================================
echo   ✅ JARVIS is online at http://localhost:8000
echo ============================================
pause
