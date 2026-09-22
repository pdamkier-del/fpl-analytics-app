@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "PY=%~dp0runtime\python.exe"

if not exist "%PY%" goto :NO_RUNTIME

echo Starting FPL Analytics...
"%PY%" "%~dp0updater.py"
"%PY%" "%~dp0start_app.py"
set "RC=%ERRORLEVEL%"

if not "%RC%"=="0" (
  echo.
  echo FPL Analytics stopped with an error ^(code %RC%^).
  echo If this happens again, run "Install FPL Website.bat" to repair the runtime.
  echo.
  pause
)
exit /b %RC%

:NO_RUNTIME
echo.
echo The portable FPL runtime is missing.
echo Please run "Install FPL Website.bat" once more.
echo.
pause
exit /b 1
