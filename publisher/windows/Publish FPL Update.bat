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
echo Repo: %REPO%
echo.

where gh >nul 2>&1
if errorlevel 1 (
  color 0C
  echo ERROR: GitHub CLI ^(gh^) blev ikke fundet.
  echo.
  pause
  exit /b 1
)

echo Tjekker GitHub-login...
gh auth status -h github.com
if errorlevel 1 (
  color 0E
  echo.
  echo GitHub CLI er ikke logget ind.
  echo.
  pause
  exit /b 1
)

set "OLD_RUN="
for /f "delims=" %%R in ('gh run list --repo "%REPO%" --workflow "%WORKFLOW%" --event workflow_dispatch --limit 1 --json databaseId --jq ".[0].databaseId // empty" 2^>nul') do set "OLD_RUN=%%R"

echo.
echo Starter FPL-publisheren...
gh workflow run "%WORKFLOW%" --repo "%REPO%" --ref main
if errorlevel 1 (
  color 0C
  echo.
  echo FAILURE: Kunne ikke starte GitHub-workflowet.
  echo.
  pause
  exit /b 1
)

echo Venter pa at GitHub registrerer den nye korsel...
set "RUN_ID="
for /L %%I in (1,1,30) do (
  set "LATEST="
  for /f "delims=" %%R in ('gh run list --repo "%REPO%" --workflow "%WORKFLOW%" --event workflow_dispatch --limit 1 --json databaseId --jq ".[0].databaseId // empty" 2^>nul') do set "LATEST=%%R"
  if defined LATEST (
    if not "!LATEST!"=="!OLD_RUN!" (
      set "RUN_ID=!LATEST!"
      goto :WATCH
    )
  )
  timeout /t 2 /nobreak >nul
)

color 0C
echo.
echo ==========================================
echo FAILURE - RUN-ID KUNNE IKKE FINDES
echo ==========================================
echo.
echo Workflowet kan vaere startet, men publisheren kunne ikke koble sig til korslen.
echo Prov igen om et ojeblik.
echo.
pause
exit /b 1

:WATCH
echo.
echo Fundet run !RUN_ID!.
echo Folger publiceringen...
echo.
gh run watch !RUN_ID! --repo "%REPO%" --exit-status

if errorlevel 1 (
  color 0C
  echo.
  echo ==========================================
  echo FAILURE - PUBLICERING FEJLEDE
  echo ==========================================
  echo.
  echo Fejlede trin:
  gh run view !RUN_ID! --repo "%REPO%" --log-failed
  echo.
  pause
  exit /b 1
)

color 0A
echo.
echo ==========================================
echo SUCCESS - FPL UPDATE ER PUBLICERET
echo ==========================================
echo.
echo Luk FPL Analytics og start appen igen.
echo Den henter den nye version automatisk.
echo.
pause
exit /b 0
