@echo off
REM ============================================================
REM Faraz Energy — remove Windows service (NSSM)
REM Run as Administrator.
REM ============================================================
setlocal EnableExtensions
cd /d "%~dp0"

set "SERVICE_NAME=FarazEnergy"
set "NSSM_EXE="

where nssm >nul 2>&1
if not errorlevel 1 (
    set "NSSM_EXE=nssm"
    goto :nssm_found
)
if exist "tools\nssm.exe" (
    set "NSSM_EXE=%~dp0tools\nssm.exe"
    goto :nssm_found
)
if exist "tools\nssm\win64\nssm.exe" (
    set "NSSM_EXE=%~dp0tools\nssm\win64\nssm.exe"
    goto :nssm_found
)

echo ERROR: nssm.exe not found.
pause
exit /b 1

:nssm_found
net session >nul 2>&1
if errorlevel 1 (
    echo ERROR: Run as Administrator.
    pause
    exit /b 1
)

sc query %SERVICE_NAME% >nul 2>&1
if errorlevel 1 (
    echo Service %SERVICE_NAME% is not installed.
    pause
    exit /b 0
)

echo Stopping %SERVICE_NAME% ...
"%NSSM_EXE%" stop %SERVICE_NAME% confirm
timeout /t 3 /nobreak >nul
echo Removing %SERVICE_NAME% ...
"%NSSM_EXE%" remove %SERVICE_NAME% confirm

echo Done. You can still run start_production.bat manually if needed.
pause
endlocal
