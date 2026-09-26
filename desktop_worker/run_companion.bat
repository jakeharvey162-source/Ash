@echo off
setlocal
cd /d "%~dp0"
python ash_companion.py %*
endlocal
