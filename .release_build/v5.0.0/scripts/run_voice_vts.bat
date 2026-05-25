@echo off
setlocal

cd /d "%~dp0.."

set APP_PRESET=voice_vts
python main.py

endlocal
pause