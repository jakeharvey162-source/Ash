@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================
echo   Ash Local Intelligence Setup for Windows
echo ============================================
echo.

where ollama >nul 2>nul
if errorlevel 1 (
  echo Ollama was not found.
  where winget >nul 2>nul
  if errorlevel 1 (
    echo Please install Ollama from its official installer, then run this file again.
    exit /b 1
  )
  echo Installing Ollama...
  winget install --id Ollama.Ollama -e --accept-source-agreements --accept-package-agreements
  if errorlevel 1 exit /b 1
)

echo Starting Ollama...
start "" /min ollama serve
timeout /t 3 /nobreak >nul

echo.
echo Pulling Ash coding model...
ollama pull qwen3-coder
if errorlevel 1 exit /b 1

echo.
echo Pulling Ash vision model...
ollama pull qwen3-vl:4b
if errorlevel 1 exit /b 1

echo.
echo Installing Ash desktop Python dependencies...
python -m pip install -r requirements.txt
if errorlevel 1 exit /b 1
python -m pip install -r requirements-control.optional.txt
if errorlevel 1 exit /b 1

echo.
echo Ash local intelligence is ready.
echo Builder model: qwen3-coder
echo Vision model: qwen3-vl:4b
echo.
echo Computer control stays OFF until you explicitly enable it.
echo To enable for this command window:
echo   set ASH_COMPUTER_CONTROL=1
echo.
python local_ai_cli.py --status
pause
