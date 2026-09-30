@echo off
setlocal
set "LAUNCHER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Ash Hologram Companion.cmd"
if exist "%LAUNCHER%" del /q "%LAUNCHER%"
echo Ash startup launcher removed.
echo Your Ash data in %%USERPROFILE%%\.ash was not deleted.
endlocal
