@echo off
setlocal

cd /d "%~dp0.."

set APP_PRESET=text_chat
python main.py

endlocal
pause