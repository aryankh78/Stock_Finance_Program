@echo off
REM ============================================================
REM Faraz Energy — check Windows service status (NSSM)
REM ============================================================
setlocal EnableExtensions
cd /d "%~dp0"

set "SERVICE_NAME=FarazEnergy"
set "NSSM_EXE="

where nssm >nul 2>&1
if not errorlevel 1 set "NSSM_EXE=nssm"
if not defined NSSM_EXE if exist "tools\nssm.exe" set "NSSM_EXE=%~dp0tools\nssm.exe"
if not defined NSSM_EXE if exist "tools\nssm\win64\nssm.exe" set "NSSM_EXE=%~dp0tools\nssm\win64\nssm.exe"

echo === Windows service: %SERVICE_NAME% ===
sc query %SERVICE_NAME% 2>nul
if errorlevel 1 echo Service is not installed. Run install_nssm_service.bat as Administrator.

if defined NSSM_EXE (
    echo.
    echo === NSSM status ===
    "%NSSM_EXE%" status %SERVICE_NAME%
)

if exist "set_production_env.bat" (
    call "set_production_env.bat"
)
if not defined APP_PORT set APP_PORT=5001

echo.
echo === Quick URL check ===
echo  http://127.0.0.1:%APP_PORT%
echo.
echo Logs: logs\main.log  logs\service_stderr.log
endlocal
