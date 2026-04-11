@echo off
setlocal

cd /d %~dp0

echo ==============================
echo AI Bot Setup
echo ==============================
echo.

echo [1/6] Creating virtual environment...
py -3.12 -m venv venv 2>nul
if not exist venv (
    python -m venv venv
)

if not exist venv\Scripts\python.exe (
    echo [ERROR] Failed to create virtual environment.
    pause
    exit /b 1
)

echo [2/6] Upgrading pip...
venv\Scripts\python.exe -m pip install --upgrade pip

echo [3/6] Cleaning conflicting packages...
venv\Scripts\python.exe -m pip uninstall -y google google-generativeai >nul 2>nul

echo [4/6] Installing core dependencies...
call :install google-genai==1.70.0
call :install python-dotenv==1.2.2
call :install pyvts==0.3.3
call :install aiofiles==25.1.0
call :install websockets==16.0
call :install pydantic==2.12.5
call :install elevenlabs==2.41.0
call :install SpeechRecognition==3.14.3

rem --- Added for xAI (Grok) Support ---
echo Installing OpenAI and xAI SDK...
call :install openai==2.31.0
call :install xai-sdk==1.11.0

echo [5/6] Installing PyAudio (optional)...
venv\Scripts\python.exe -m pip install PyAudio

echo [6/6] Verifying installation...
venv\Scripts\python.exe -c "from google import genai" 2>nul
if errorlevel 1 (
    echo [ERROR] google-genai is not installed correctly.
    pause
    exit /b 1
)

venv\Scripts\python.exe -c "import openai" 2>nul
if errorlevel 1 (
    echo [ERROR] openai is not installed correctly.
    pause
    exit /b 1
)

echo.
echo Setup complete!
pause
exit /b 0

:install
echo Installing %1 ...
venv\Scripts\python.exe -m pip install %1
if errorlevel 1 (
    echo [ERROR] Failed to install %1
    pause
    exit /b 1
)
goto :eof