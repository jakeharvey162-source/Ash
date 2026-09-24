@echo off
setlocal
cd /d "%~dp0"
echo.
echo Ash Desktop Link
echo ----------------
set /p ASH_PAIR_CODE=Enter the pairing code shown in Ash: 
if "%ASH_PAIR_CODE%"=="" (
  echo No code entered.
  exit /b 1
)
python remote_worker.py --pair "%ASH_PAIR_CODE%"
if errorlevel 1 (
  echo.
  echo Ash could not start. Make sure Python and desktop_worker requirements are installed.
  pause
)
