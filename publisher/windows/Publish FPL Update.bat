@echo off
setlocal EnableExtensions
title FPL Publisher
color 0A

set "BASE=%LOCALAPPDATA%\FPLPublisher"
set "RUNNER=%BASE%\Publisher Runner.bat"
set "URL=https://raw.githubusercontent.com/pdamkier-del/fpl-analytics-app/main/publisher/windows/Publisher%%20Runner.bat"

if not exist "%BASE%" mkdir "%BASE%"

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "try { Invoke-WebRequest -UseBasicParsing -Uri '%URL%' -OutFile '%RUNNER%'; Unblock-File -LiteralPath '%RUNNER%' -ErrorAction SilentlyContinue; exit 0 } catch { exit 1 }"

if errorlevel 1 (
  color 0C
  echo.
  echo ERROR: Kunne ikke hente den nyeste publisher.
  echo Tjek internetforbindelsen og prov igen.
  echo.
  pause
  exit /b 1
)

call "%RUNNER%"
exit /b %errorlevel%
