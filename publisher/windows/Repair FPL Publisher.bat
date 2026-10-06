@echo off
setlocal EnableExtensions
title Repair FPL Publisher

set "INSTALLDIR=%LOCALAPPDATA%\FPLPublisher"
set "TARGET=%INSTALLDIR%\Publish FPL Update.bat"

echo.
echo Reparerer FPL Publisher...
echo.

if not exist "%INSTALLDIR%" mkdir "%INSTALLDIR%"
if errorlevel 1 goto :FAIL

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "$url='https://raw.githubusercontent.com/pdamkier-del/fpl-analytics-app/main/publisher/windows/Publish%%20FPL%%20Update.bat';" ^
  "$out=Join-Path $env:LOCALAPPDATA 'FPLPublisher\Publish FPL Update.bat';" ^
  "Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $out;" ^
  "Unblock-File -LiteralPath $out"
if errorlevel 1 goto :FAIL

echo Opdaterer desktop-genvej...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "$desktop=[Environment]::GetFolderPath('Desktop');" ^
  "$target=Join-Path $env:LOCALAPPDATA 'FPLPublisher\Publish FPL Update.bat';" ^
  "$lnk=Join-Path $desktop 'Publish FPL Update.lnk';" ^
  "$ws=New-Object -ComObject WScript.Shell;" ^
  "$s=$ws.CreateShortcut($lnk);" ^
  "$s.TargetPath=$target;" ^
  "$s.WorkingDirectory=(Split-Path $target);" ^
  "$s.IconLocation=($env:SystemRoot+'\System32\shell32.dll,137');" ^
  "$s.Save();" ^
  "Unblock-File -LiteralPath $lnk -ErrorAction SilentlyContinue"
if errorlevel 1 goto :FAIL

echo.
echo ==========================================
echo SUCCESS - publisheren er repareret
echo ==========================================
echo.
echo Brug nu dit normale 'Publish FPL Update'-ikon pa skrivebordet.
echo.
pause
exit /b 0

:FAIL
echo.
echo FAILURE - publisheren kunne ikke repareres.
echo Send dette vindue til ChatGPT.
echo.
pause
exit /b 1
