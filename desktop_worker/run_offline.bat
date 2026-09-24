@echo off
setlocal
cd /d "%~dp0"
python local_ai_cli.py --status
echo.
echo Starting Ash Offline...
python local_ai_cli.py
