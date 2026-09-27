@echo off
REM ============================================================
REM Faraz Energy — NSSM service diagnostics
REM ============================================================
setlocal EnableExtensions
cd /d "%~dp0"

set "SERVICE_NAME=FarazEnergy"
set "NSSM_EXE="

where nssm >nul 2>&1
if not errorlevel 1 set "NSSM_EXE=nssm"
if not defined NSSM_EXE if exist "tools\nssm.exe" set "NSSM_EXE=%~dp0tools\nssm.exe"
if not defined NSSM_EXE if exist "tools\nssm\win64\nssm.exe" set "NSSM_EXE=%~dp0tools\nssm\win64\nssm.exe"

echo === Faraz Energy service diagnostics ===
echo Project folder: %CD%
echo.

echo --- Windows service status ---
sc query %SERVICE_NAME%
echo.

if defined NSSM_EXE (
    echo --- NSSM status ---
    "%NSSM_EXE%" status %SERVICE_NAME%
    echo.
    echo --- NSSM configuration ---
    "%NSSM_EXE%" get %SERVICE_NAME% Application
    "%NSSM_EXE%" get %SERVICE_NAME% AppDirectory
    "%NSSM_EXE%" get %SERVICE_NAME% AppParameters
    "%NSSM_EXE%" get %SERVICE_NAME% ObjectName
    echo.
) else (
    echo NSSM not found.
    echo.
)

echo --- Log files (last 15 lines each) ---
for %%F in (service_boot.log service_stderr.log service_stdout.log main.log) do (
    echo.
    echo === logs\%%F ===
    if exist "logs\%%F" (
        powershell -NoProfile -Command "Get-Content -Path 'logs\%%F' -Tail 15"
    ) else (
        echo File not found.
    )
)

echo.
echo --- Recent NSSM events (last 60 minutes; older entries may show previous install paths) ---
powershell -NoProfile -Command "Get-WinEvent -FilterHashtable @{LogName='Application'; StartTime=(Get-Date).AddMinutes(-60)} -MaxEvents 20 -ErrorAction SilentlyContinue | Where-Object { $_.Message -match 'FarazEnergy|nssm|NSSM' } | Select-Object TimeCreated, Message | Format-List"

echo.
echo --- Manual test reminder ---
echo Run:  run_production_service.bat
echo URL:  http://127.0.0.1:5001
echo.
endlocal
