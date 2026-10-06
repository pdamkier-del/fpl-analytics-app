@echo off
setlocal EnableExtensions EnableDelayedExpansion
title FPL Publisher
color 0A

set "REPO=pdamkier-del/fpl-analytics-app"
set "WORKFLOW=build-publisher-patch-v2.3.yml"

echo.
echo ==========================================
echo              FPL PUBLISHER
echo ==========================================
echo.
echo Starter publicering...
echo.

where gh >nul 2>&1
if errorlevel 1 (
  color 0C
  echo ERROR: GitHub CLI ^(gh^) blev ikke fundet.
  echo.
  pause
  exit /b 1
)

gh auth status -h github.com >nul 2>&1
if errorlevel 1 (
  color 0C
  echo ERROR: GitHub-login mangler.
  echo.
  echo Korer kun i terminalen - browseren bliver ikke aabnet.
  echo Log ind med: gh auth login
  echo.
  pause
  exit /b 1
)

set "OLD_RUN="
for /f "delims=" %%R in ('gh run list --repo "%REPO%" --workflow "%WORKFLOW%" --event workflow_dispatch --limit 1 --json databaseId --jq ".[0].databaseId // empty" 2^>nul') do set "OLD_RUN=%%R"

gh workflow run "%WORKFLOW%" --repo "%REPO%" --ref main >nul 2>&1
if errorlevel 1 (
  color 0C
  echo ERROR: Publiceringen kunne ikke startes.
  echo.
  pause
  exit /b 1
)

echo Workflow startet.
echo Venter pa GitHub...
set "RUN_ID="
for /L %%I in (1,1,45) do (
  set "LATEST="
  for /f "delims=" %%R in ('gh run list --repo "%REPO%" --workflow "%WORKFLOW%" --event workflow_dispatch --limit 1 --json databaseId --jq ".[0].databaseId // empty" 2^>nul') do set "LATEST=%%R"
  if defined LATEST (
    if not "!LATEST!"=="!OLD_RUN!" (
      set "RUN_ID=!LATEST!"
      goto :POLL
    )
  )
  timeout /t 2 /nobreak >nul
)

color 0C
echo.
echo FAILURE: GitHub-run kunne ikke findes.
echo.
pause
exit /b 1

:POLL
echo Run !RUN_ID! fundet.
echo.

:CHECK
set "STATUS="
set "CONCLUSION="
for /f "tokens=1,2 delims=|" %%A in ('gh run view !RUN_ID! --repo "%REPO%" --json status,conclusion --jq ".status + \"|\" + (.conclusion // \"\")" 2^>nul') do (
  set "STATUS=%%A"
  set "CONCLUSION=%%B"
)

if not defined STATUS (
  timeout /t 2 /nobreak >nul
  goto :CHECK
)

if /I "!STATUS!"=="completed" goto :DONE

<nul set /p "=."
timeout /t 3 /nobreak >nul
goto :CHECK

:DONE
echo.
echo.

if /I "!CONCLUSION!"=="success" (
  color 0A
  echo ==========================================
  echo SUCCESS - FPL UPDATE ER PUBLICERET
  echo ==========================================
  echo.
  echo Luk FPL Analytics og start appen igen.
  echo.
  pause
  exit /b 0
)

color 0C
echo ==========================================
echo FAILURE - PUBLICERING FEJLEDE
echo ==========================================
echo.
echo Run: !RUN_ID!
echo Status: !CONCLUSION!
echo.
echo GitHub bliver ikke aabnet automatisk.
echo.
pause
exit /b 1
