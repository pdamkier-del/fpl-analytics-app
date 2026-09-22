@echo off
setlocal EnableExtensions
set "INSTALLDIR=%LOCALAPPDATA%\FPLAnalytics"
set "STATEBACKUP=%TEMP%\FPLAnalytics-State-Backup"

echo ========================================
echo       FPL Analytics - Installer v1.6
echo ========================================
echo.
echo Installing/updating to:
echo %INSTALLDIR%
echo.

rem Preserve user-created model versions and active configuration during updates.
if exist "%STATEBACKUP%" rmdir /S /Q "%STATEBACKUP%"
if exist "%INSTALLDIR%\model\active.json" (
  mkdir "%STATEBACKUP%" >nul 2>&1
  copy /Y "%INSTALLDIR%\model\active.json" "%STATEBACKUP%\active.json" >nul
)
if exist "%INSTALLDIR%\model\versions" xcopy "%INSTALLDIR%\model\versions\*" "%STATEBACKUP%\versions\" /E /I /Y /Q >nul
if exist "%INSTALLDIR%\model\runs" xcopy "%INSTALLDIR%\model\runs\*" "%STATEBACKUP%\runs\" /E /I /Y /Q >nul
if exist "%INSTALLDIR%\user" xcopy "%INSTALLDIR%\user\*" "%STATEBACKUP%\user\" /E /I /Y /Q >nul

echo Copying FPL Analytics files...
if not exist "%INSTALLDIR%" mkdir "%INSTALLDIR%"
xcopy "%~dp0*" "%INSTALLDIR%\" /E /I /Y /Q >nul
if errorlevel 1 goto :COPY_FAILED

rem Restore user state after app files have been updated.
if exist "%STATEBACKUP%\active.json" copy /Y "%STATEBACKUP%\active.json" "%INSTALLDIR%\model\active.json" >nul
if exist "%STATEBACKUP%\versions" xcopy "%STATEBACKUP%\versions\*" "%INSTALLDIR%\model\versions\" /E /I /Y /Q >nul
if exist "%STATEBACKUP%\runs" xcopy "%STATEBACKUP%\runs\*" "%INSTALLDIR%\model\runs\" /E /I /Y /Q >nul
if exist "%STATEBACKUP%\user" xcopy "%STATEBACKUP%\user\*" "%INSTALLDIR%\user\" /E /I /Y /Q >nul
if exist "%STATEBACKUP%" rmdir /S /Q "%STATEBACKUP%"

echo.
echo Preparing the private FPL runtime...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%INSTALLDIR%\setup_runtime.ps1" -InstallDir "%INSTALLDIR%"
if errorlevel 1 goto :RUNTIME_FAILED

echo.
echo Creating Desktop shortcut...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$ws=New-Object -ComObject WScript.Shell; $desktop=[Environment]::GetFolderPath('Desktop'); $s=$ws.CreateShortcut((Join-Path $desktop 'FPL Analytics.lnk')); $s.TargetPath=(Join-Path $env:LOCALAPPDATA 'FPLAnalytics\Start FPL App.bat'); $s.WorkingDirectory=(Join-Path $env:LOCALAPPDATA 'FPLAnalytics'); $s.IconLocation=($env:SystemRoot+'\System32\shell32.dll,220'); $s.Save()"
if errorlevel 1 goto :SHORTCUT_FAILED

echo.
echo Update complete.
echo Your existing Model Lab versions and saved squad have been preserved.
echo Automatic GitHub updates are now enabled.
echo.
echo Starting the app now...
start "" "%INSTALLDIR%\Start FPL App.bat"
timeout /t 2 /nobreak >nul
exit /b 0

:RUNTIME_FAILED
echo.
echo The portable runtime could not be downloaded or started.
echo Check your internet connection and run this installer again.
echo.
pause
exit /b 1

:COPY_FAILED
echo.
echo The FPL Analytics files could not be copied to:
echo %INSTALLDIR%
echo.
pause
exit /b 1

:SHORTCUT_FAILED
echo.
echo The app was installed, but the Desktop shortcut could not be created.
echo You can still start it here:
echo %INSTALLDIR%\Start FPL App.bat
echo.
pause
exit /b 1
