@echo off
setlocal

cd /d %~dp0

echo ==============================
echo AI Bot Launch
echo ==============================
echo.

# Verify virtual environment [cite: 6]
if not exist venv\Scripts\python.exe (
    echo [ERROR] Virtual environment not found.
    echo Please run install.bat first.
    pause
    exit /b 1
)

echo Using Python:
venv\Scripts\python.exe --version
echo.

rem Verify .env configuration 
if not exist .env (
    echo [WARNING] .env file not found.
    echo Please create .env and set:
    echo   GEMINI_API_KEY
    echo   ELEVENLABS_API_KEY   (required for TTS)
    echo   VOICE_MASTER         (required if OUTPUT_VOICE_ENABLED=True)
    echo   XAI_API_KEY          (optional, for Grok support)
    pause
) else (
    rem Optional: Check if XAI_API_KEY is missing inside the file
    findstr "XAI_API_KEY" .env >nul
    if errorlevel 1 (
        echo [INFO] XAI_API_KEY not found in .env. 
        echo Grok engine will not work without it.
        echo.
    )
)

echo Before starting:
echo - Make sure VTube Studio is running
echo - Make sure a model is loaded
echo - Allow API connection on first launch
echo.

rem Execute the main script 
venv\Scripts\python.exe main.py

echo.
echo Program ended.
pause
exit /b %errorlevel%