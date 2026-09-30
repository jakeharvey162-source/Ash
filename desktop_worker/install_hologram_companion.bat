@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo.
echo   ASH HOLOGRAM COMPANION INSTALLER
echo   --------------------------------
echo   Always-on hologram + voice + local agent runtime
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
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

echo.
choice /C YN /N /M "Install local always-on voice support? [Y/N] "
if errorlevel 2 goto :skipvoice
".venv\Scripts\python.exe" -m pip install -r requirements-voice.optional.txt
:skipvoice

echo.
choice /C YN /N /M "Install the advanced OpenJarvis local agent pack? [Y/N] "
if errorlevel 2 goto :skipopenjarvis
".venv\Scripts\python.exe" -m pip install -r requirements-openjarvis.optional.txt
if errorlevel 1 (
  echo OpenJarvis pack could not be installed. Ash will continue with its native runtime.
)
:skipopenjarvis

echo.
choice /C YN /N /M "Install optional screen-vision/control dependencies? [Y/N] "
if errorlevel 2 goto :skipcontrol
".venv\Scripts\python.exe" -m pip install -r requirements-control.optional.txt
echo Screen-control packages installed but NOT enabled.
echo Ash still requires explicit configuration and confirmation before control actions.
:skipcontrol

set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "LAUNCHER=%STARTUP%\Ash Hologram Companion.cmd"
(
  echo @echo off
  echo cd /d "%~dp0"
  echo start "" ".venv\Scripts\pythonw.exe" companion_overlay.py
) > "%LAUNCHER%"

set "DESKTOP_LAUNCHER=%USERPROFILE%\Desktop\Ash Hologram.cmd"
(
  echo @echo off
  echo cd /d "%~dp0"
  echo start "" ".venv\Scripts\pythonw.exe" companion_overlay.py
) > "%DESKTOP_LAUNCHER%"

echo.
echo Ash Hologram Companion is installed.
echo - Starts with Windows
echo - Always-on-top animated Ash hologram
echo - Wake word and voice if installed
echo - Paired desktop worker for builds and safe actions
echo - Local memory, tools, schedules and adaptive model routing
echo.
choice /C YN /N /M "Start Ash now? [Y/N] "
if errorlevel 2 goto :done
start "" ".venv\Scripts\pythonw.exe" companion_overlay.py
:done
endlocal
