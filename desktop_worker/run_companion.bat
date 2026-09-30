@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 companion_overlay.py %*
) else (
  python companion_overlay.py %*
)
endlocal
