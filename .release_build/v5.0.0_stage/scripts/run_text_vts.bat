@echo off
setlocal

cd /d "%~dp0.."

set APP_PRESET=text_vts
python main.py

endlocal
pause