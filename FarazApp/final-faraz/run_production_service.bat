@echo off
REM ============================================================
REM Faraz Energy — headless production runner (Windows service / NSSM)
REM Used by install_nssm_service.bat — not for double-click daily use.
REM For manual testing use start_production.bat instead.
REM ============================================================
setlocal EnableExtensions
cd /d "%~dp0"

if not exist "logs" mkdir logs
echo [%date% %time%] run_production_service started >> "logs\service_boot.log"

set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

if exist "set_production_env.bat" (
    call "set_production_env.bat"
    echo [%date% %time%] loaded set_production_env >> "logs\service_boot.log"
) else (
    echo [%date% %time%] ERROR: set_production_env missing >> "logs\service_boot.log"
    exit /b 1
)

if not defined APP_PORT set APP_PORT=5001
if not defined APP_HOST set APP_HOST=0.0.0.0

set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
    echo [%date% %time%] ERROR: python not found at .venv >> "logs\service_boot.log"
    exit /b 1
)

echo [%date% %time%] starting python on port %APP_PORT% >> "logs\service_boot.log"
"%PYTHON_EXE%" main.py --production --host=%APP_HOST% --port=%APP_PORT%
set "EXIT_CODE=%errorlevel%"
echo [%date% %time%] python exited with code %EXIT_CODE% >> "logs\service_boot.log"
exit /b %EXIT_CODE%
