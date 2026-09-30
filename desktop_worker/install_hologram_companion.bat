@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo.
echo   ASH HOLOGRAM COMPANION INSTALLER
echo   -------------------------------
echo.

where py >nul 2>nul
if %errorlevel%==0 (
  set "PYCMD=py -3"
) else (
  set "PYCMD=python"
)

%PYCMD% --version >nul 2>nul
if errorlevel 1 (
  echo Python 3.11 or 3.12 is required for the desktop companion.
  echo Install Python from python.org, then run this installer again.
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating private Ash desktop environment...
  %PYCMD% -m venv .venv
  if errorlevel 1 exit /b 1
)

echo Installing Ash desktop core...
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

echo.
choice /M "Install local always-on voice support (recommended)"
if errorlevel 2 goto :skipvoice
".venv\Scripts\python.exe" -m pip install -r requirements-voice.optional.txt
:skipvoice

set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "LAUNCHER=%STARTUP%\Ash Hologram Companion.cmd"
(
  echo @echo off
  echo cd /d "%~dp0"
  echo start "" ".venv\Scripts\pythonw.exe" companion_overlay.py
) > "%LAUNCHER%"

echo.
echo Ash Hologram Companion is installed.
echo It will start with Windows and remain always-on-top.
echo Run run_companion.bat now to preview it.
echo.
choice /M "Start Ash now"
if errorlevel 2 goto :done
start "" ".venv\Scripts\pythonw.exe" companion_overlay.py
:done
endlocal
