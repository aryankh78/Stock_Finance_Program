@echo off
REM ============================================================
REM Faraz Energy — install Windows service via NSSM (v10)
REM Auto-start at boot + automatic restart after crash.
REM Run as Administrator. See DEPLOYMENT_GUIDE.md
REM ============================================================
setlocal EnableExtensions
cd /d "%~dp0"
set "APP_ROOT=%~dp0"
REM NSSM fails CreateProcess if AppDirectory has a trailing backslash
set "APP_ROOT_NSSM=%~dp0"
if "%APP_ROOT_NSSM:~-1%"=="\" set "APP_ROOT_NSSM=%APP_ROOT_NSSM:~0,-1%"

set "SERVICE_NAME=FarazEnergy"
set "NSSM_EXE="

where nssm >nul 2>&1
if not errorlevel 1 set "NSSM_EXE=nssm"
if not defined NSSM_EXE if exist "tools\nssm.exe" set "NSSM_EXE=%APP_ROOT%tools\nssm.exe"
if not defined NSSM_EXE if exist "tools\nssm\win64\nssm.exe" set "NSSM_EXE=%APP_ROOT%tools\nssm\win64\nssm.exe"
if not defined NSSM_EXE goto :no_nssm

net session >nul 2>&1
if errorlevel 1 goto :need_admin

if not exist ".venv\Scripts\python.exe" goto :no_venv
if not exist "set_production_env.bat" goto :no_env
if not exist "tools\set_nssm_environment.ps1" goto :no_tools

call "set_production_env.bat"
if not defined APP_PORT set APP_PORT=5001
if not defined APP_HOST set APP_HOST=0.0.0.0
if not defined WAITRESS_THREADS set WAITRESS_THREADS=8
if not defined SESSION_COOKIE_SECURE set SESSION_COOKIE_SECURE=0

if not exist "logs" mkdir logs

echo Granting LocalSystem access to project folder ...
icacls "%APP_ROOT%" /grant "SYSTEM:(OI)(CI)RX" /T >nul 2>&1
icacls "%APP_ROOT%logs" /grant "SYSTEM:(OI)(CI)M" /T >nul 2>&1
if exist "%APP_ROOT%data" icacls "%APP_ROOT%data" /grant "SYSTEM:(OI)(CI)M" /T >nul 2>&1

sc query %SERVICE_NAME% >nul 2>&1
if not errorlevel 1 goto :remove_old_service
goto :ask_account

:remove_old_service
echo Stopping and removing existing service %SERVICE_NAME% ...
"%NSSM_EXE%" stop %SERVICE_NAME% confirm
timeout /t 3 /nobreak >nul
"%NSSM_EXE%" remove %SERVICE_NAME% confirm

:ask_account
set "USE_LOCAL_SYSTEM=1"
echo.
echo Service account:
echo   1 = LocalSystem  (recommended for C:\FarazApp\...)
echo   2 = Your Windows user  (same as manual test; needs password)
echo.
set "ACCOUNT_CHOICE="
set /p ACCOUNT_CHOICE=Choose 1 or 2 [default 1]: 
if "%ACCOUNT_CHOICE%"=="2" set "USE_LOCAL_SYSTEM="
if "%ACCOUNT_CHOICE%"=="2" (
    set "SVC_PASS="
    set /p SVC_PASS=Enter Windows password for %USERDOMAIN%\%USERNAME%: 
    if not defined SVC_PASS goto :need_password
)

:install_service
set "PYTHON_EXE=%APP_ROOT%.venv\Scripts\python.exe"

echo Installing service %SERVICE_NAME% ...
echo Using python directly (same as manual test, without batch wrapper).
"%NSSM_EXE%" install %SERVICE_NAME% "%PYTHON_EXE%"
if errorlevel 1 goto :install_failed
"%NSSM_EXE%" set %SERVICE_NAME% AppParameters "main.py --production --host=%APP_HOST% --port=%APP_PORT% --threads=%WAITRESS_THREADS%"

"%NSSM_EXE%" set %SERVICE_NAME% AppDirectory "%APP_ROOT_NSSM%"
"%NSSM_EXE%" set %SERVICE_NAME% DisplayName "Faraz Energy Web Application"
"%NSSM_EXE%" set %SERVICE_NAME% Description "Faraz Energy TSE signaling web app - Waitress production server"
"%NSSM_EXE%" set %SERVICE_NAME% Start SERVICE_AUTO_START

if defined USE_LOCAL_SYSTEM (
    "%NSSM_EXE%" set %SERVICE_NAME% ObjectName LocalSystem
) else (
    echo Granting "Log on as a service" right ...
    powershell -NoProfile -ExecutionPolicy Bypass -File "%APP_ROOT%tools\grant_service_logon.ps1" -Account "%USERDOMAIN%\%USERNAME%"
    "%NSSM_EXE%" set %SERVICE_NAME% ObjectName "%USERDOMAIN%\%USERNAME%" "%SVC_PASS%"
    set "SVC_PASS="
    if errorlevel 1 goto :bad_password
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%APP_ROOT%tools\set_nssm_environment.ps1" -NssmExe "%NSSM_EXE%" -ServiceName "%SERVICE_NAME%"
if errorlevel 1 goto :env_failed

"%NSSM_EXE%" set %SERVICE_NAME% AppRestartDelay 5000
"%NSSM_EXE%" set %SERVICE_NAME% AppThrottle 15000
"%NSSM_EXE%" set %SERVICE_NAME% AppExit 0 Restart
"%NSSM_EXE%" set %SERVICE_NAME% AppExit 1 Restart
"%NSSM_EXE%" set %SERVICE_NAME% AppExit 2 Restart

"%NSSM_EXE%" set %SERVICE_NAME% AppStdout "%APP_ROOT%logs\service_stdout.log"
"%NSSM_EXE%" set %SERVICE_NAME% AppStderr "%APP_ROOT%logs\service_stderr.log"
"%NSSM_EXE%" set %SERVICE_NAME% AppRotateFiles 1
"%NSSM_EXE%" set %SERVICE_NAME% AppRotateBytes 10485760

echo Verifying Python environment ...
"%PYTHON_EXE%" -c "import waitress" >nul 2>&1
if errorlevel 1 goto :runner_failed

echo Starting service ...
"%NSSM_EXE%" start %SERVICE_NAME%
set "WAIT_SEC=0"
:wait_running
timeout /t 2 /nobreak >nul
set /a WAIT_SEC+=2
sc query %SERVICE_NAME% | findstr /C:"RUNNING" >nul
if not errorlevel 1 goto :service_running
sc query %SERVICE_NAME% | findstr /C:"STOPPED" >nul
if not errorlevel 1 goto :start_failed
if %WAIT_SEC% geq 120 goto :start_pending
goto :wait_running

:service_running

echo.
echo ==========================================
echo  Faraz Energy service installed OK
echo ==========================================
echo  Service name: %SERVICE_NAME%
if defined USE_LOCAL_SYSTEM (
    echo  Runs as:      LocalSystem
) else (
    echo  Runs as:      %USERDOMAIN%\%USERNAME%
)
echo  Status:       run service_status.bat
echo  Diagnose:     diagnose_service.bat
echo  App logs:       logs\main.log
echo  Service logs:   logs\service_stdout.log
echo                  logs\service_stderr.log
echo ==========================================
echo.
goto :end_ok

:no_nssm
echo ERROR: nssm.exe not found.
echo Copy win64 nssm.exe to tools\ or add to PATH.
goto :end_fail

:need_admin
echo ERROR: Run this file as Administrator.
goto :end_fail

:need_password
echo ERROR: Password is required for option 2.
goto :end_fail

:bad_password
echo ERROR: Could not set service account. Wrong password or policy block.
goto :end_fail

:no_venv
echo ERROR: Virtual environment not found. Run install_server.bat first.
goto :end_fail

:no_env
echo ERROR: set_production_env not found.
goto :end_fail

:no_tools
echo ERROR: tools\set_nssm_environment.ps1 not found. Copy the full project folder.
goto :end_fail

:install_failed
echo ERROR: nssm install failed.
goto :end_fail

:env_failed
echo ERROR: Could not set service environment variables.
goto :end_fail

:runner_failed
echo ERROR: Python or Waitress is not ready. Run install_server.bat first.
goto :end_fail

:start_failed
echo ERROR: Service failed to start or stopped immediately.
echo.
echo Running diagnostics ...
call "%APP_ROOT%diagnose_service.bat"
goto :end_fail

:start_pending
sc query %SERVICE_NAME% | findstr /C:"RUNNING" >nul
if not errorlevel 1 goto :service_running
echo WARNING: Service is still starting after 120 seconds.
echo Check service_status.bat and http://127.0.0.1:%APP_PORT%
echo.
call "%APP_ROOT%diagnose_service.bat"
goto :end_fail

:end_ok
pause
endlocal
exit /b 0

:end_fail
pause
endlocal
exit /b 1
