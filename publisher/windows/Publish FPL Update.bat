@echo off
setlocal EnableExtensions EnableDelayedExpansion
title FPL Publisher
color 0A

set "REPO=pdamkier-del/fpl-analytics-app"
set "WORKFLOW=build-publisher-patch-v2.3.yml"

echo.
echo FPL Publisher
echo Repo: %REPO%
echo.

where gh >nul 2>&1
if errorlevel 1 (
  color 0C
  echo ERROR: GitHub CLI ^(gh^) blev ikke fundet.
  echo Installer GitHub CLI og prov igen.
  echo.
  pause
  exit /b 1
)

echo Tjekker GitHub-login...
gh auth status -h github.com
if errorlevel 1 (
  color 0E
  echo.
  echo Du er ikke logget ind i GitHub CLI.
  echo Kor: gh auth login
  echo og start publisheren igen.
  echo.
  pause
  exit /b 1
)

echo.
echo Starter Publish FPL Update...
gh workflow run "%WORKFLOW%" --repo "%REPO%" --ref main
if errorlevel 1 (
  color 0C
  echo.
  echo FAILURE: Kunne ikke starte publisher-workflowet.
  echo.
  pause
  exit /b 1
)

echo Venter pa at GitHub registrerer korslen...
set "RUN_ID="
for /L %%I in (1,1,15) do (
  for /f "delims=" %%R in ('gh run list --repo "%REPO%" --workflow "%WORKFLOW%" --event workflow_dispatch --limit 1 --json databaseId --jq ".[0].databaseId" 2^>nul') do set "RUN_ID=%%R"
  if defined RUN_ID goto :WATCH
  timeout /t 2 /nobreak >nul
)

color 0E
echo.
echo Workflowet blev startet, men run-id kunne ikke findes endnu.
echo Tjek GitHub Actions for status.
echo.
pause
exit /b 0

:WATCH
echo.
echo Folger run !RUN_ID!...
echo.
gh run watch !RUN_ID! --repo "%REPO%" --exit-status
if errorlevel 1 (
  color 0C
  echo.
  echo ==========================================
  echo FAILURE - FPL update blev ikke publiceret
  echo ==========================================
  echo.
  echo Abner den fejlede korsel i GitHub...
  gh run view !RUN_ID! --repo "%REPO%" --web >nul 2>&1
  pause
  exit /b 1
)

color 0A
echo.
echo ==========================================
echo SUCCESS - FPL update er publiceret
echo ==========================================
echo.
echo Din FPL Analytics-app henter opdateringen ved naeste start.
echo.
pause
exit /b 0
