@echo off
REM ========================================================
REM PostgreSQL Setup Script for Faraz Energy Project
REM Windows Version
REM ========================================================

echo ==========================================
echo PostgreSQL Setup for Faraz Energy Project
echo ==========================================
echo.

REM --- Check PostgreSQL service status ---
echo [INFO] Checking PostgreSQL service status...
sc query postgresql-x64-18 >nul 2>&1
if %errorlevel% NEQ 0 (
    echo [WARN] PostgreSQL service 'postgresql-x64-18' not found.
    echo Trying alternative service names...
    
    REM Try common PostgreSQL service names
    sc query postgresql-x64-16 >nul 2>&1
    if %errorlevel%==0 (
        set "PG_SERVICE=postgresql-x64-16"
        goto :check_status
    )
    
    sc query postgresql-x64-15 >nul 2>&1
    if %errorlevel%==0 (
        set "PG_SERVICE=postgresql-x64-15"
        goto :check_status
    )
    
    echo [ERROR] Could not find PostgreSQL service.
    echo Please make sure PostgreSQL is installed.
    echo.
    echo You can check manually with:
    echo   sc query ^| findstr postgresql
    pause
    exit /b 1
) else (
    set "PG_SERVICE=postgresql-x64-18"
)

:check_status
echo [INFO] Found PostgreSQL service: %PG_SERVICE%
sc query %PG_SERVICE% | findstr "RUNNING" >nul 2>&1
if %errorlevel% NEQ 0 (
    echo [INFO] PostgreSQL service is not running. Starting it...
    net start %PG_SERVICE%
    if %errorlevel% NEQ 0 (
        echo [ERROR] Failed to start PostgreSQL service.
        echo Please start it manually as Administrator or check the service status.
        pause
        exit /b 1
    )
    echo [INFO] PostgreSQL service started successfully.
) else (
    echo [INFO] PostgreSQL service is already running.
)
echo.

REM --- Check if psql is available ---
where psql >nul 2>&1
if %errorlevel% NEQ 0 (
    echo [WARN] psql command not found in PATH.
    echo PostgreSQL might be installed but not in PATH.
    echo.
    echo Common PostgreSQL installation paths:
    echo   C:\Program Files\PostgreSQL\18\bin\psql.exe
    echo   C:\Program Files\PostgreSQL\16\bin\psql.exe
    echo.
    echo Please add PostgreSQL bin directory to your PATH or run psql manually.
    echo.
    echo For now, you can manually run these SQL commands in pgAdmin or psql:
    echo.
    echo   CREATE USER mohammadreza WITH PASSWORD '';
    echo   ALTER USER mohammadreza CREATEDB;
    echo.
    pause
    exit /b 1
)

echo [INFO] psql found. Setting up database...
echo.

REM --- Try to find PostgreSQL installation ---
set "PG_BIN="
set "PG_PSQL="
if exist "C:\Program Files\PostgreSQL\18\bin\psql.exe" (
    set "PG_BIN=C:\Program Files\PostgreSQL\18\bin"
    set "PG_PSQL=C:\Program Files\PostgreSQL\18\bin\psql.exe"
) else if exist "C:\Program Files\PostgreSQL\16\bin\psql.exe" (
    set "PG_BIN=C:\Program Files\PostgreSQL\16\bin"
    set "PG_PSQL=C:\Program Files\PostgreSQL\16\bin\psql.exe"
) else if exist "C:\Program Files\PostgreSQL\15\bin\psql.exe" (
    set "PG_BIN=C:\Program Files\PostgreSQL\15\bin"
    set "PG_PSQL=C:\Program Files\PostgreSQL\15\bin\psql.exe"
) else (
    where psql >nul 2>&1
    if %errorlevel%==0 (
        set "PG_PSQL=psql"
        echo [INFO] Using psql from PATH...
    ) else (
        set "PG_PSQL="
    )
)

REM --- Create user if it doesn't exist ---
if "%PG_PSQL%"=="" (
    echo [ERROR] Could not find psql.exe
    echo Please add PostgreSQL bin directory to PATH or run commands manually.
    goto :manual_setup
)

echo [INFO] Creating user 'mohammadreza' if it doesn't exist...
echo [INFO] Using: %PG_PSQL%
if not defined PGPASSWORD (
    echo [INFO] Tip: To avoid password prompt, run:  set PGPASSWORD=YourPostgresPassword
    echo.
)

REM Use a temp SQL file to avoid Windows CMD escaping issues with DO $$ ... $$
set "TEMP_SQL=%TEMP%\faraz_create_user_%RANDOM%.sql"
echo DO $$ > "%TEMP_SQL%"
echo BEGIN >> "%TEMP_SQL%"
echo   IF NOT EXISTS (SELECT FROM pg_catalog.pg_user WHERE usename = 'mohammadreza') THEN >> "%TEMP_SQL%"
echo     CREATE USER mohammadreza WITH PASSWORD '' CREATEDB; >> "%TEMP_SQL%"
echo   END IF; >> "%TEMP_SQL%"
echo END >> "%TEMP_SQL%"
echo $$; >> "%TEMP_SQL%"

REM Try with password from environment first, then interactive
"%PG_PSQL%" -U postgres -f "%TEMP_SQL%" 2>nul
if %errorlevel% NEQ 0 (
    echo [WARN] First attempt failed. You may need to enter the postgres password:
    "%PG_PSQL%" -U postgres -f "%TEMP_SQL%"
    if %errorlevel% NEQ 0 (
        del /q "%TEMP_SQL%" 2>nul
        goto :manual_setup
    )
)
del /q "%TEMP_SQL%" 2>nul

echo [INFO] User 'mohammadreza' is ready.
goto :setup_complete

:manual_setup
echo.
echo ==========================================
echo Manual Setup Required
echo ==========================================
echo.
echo Please run these SQL commands in pgAdmin or psql:
echo.
echo   1. Open pgAdmin or psql
echo   2. Connect as 'postgres' user
echo   3. Run these commands:
echo.
echo   CREATE USER mohammadreza WITH PASSWORD '';
echo   ALTER USER mohammadreza CREATEDB;
echo.
echo Or if you prefer to use 'postgres' user directly,
echo we can update config/main_config.json to use 'postgres' instead.
echo.
goto :setup_complete

:setup_complete

echo.
echo ==========================================
echo [INFO] PostgreSQL setup check completed.
echo ==========================================
echo.
echo Next steps:
echo   1. Make sure PostgreSQL service is running
echo   2. User 'mohammadreza' should exist (or use 'postgres' user)
echo   3. Run 'run_webapp.bat' to start the application
echo.
echo The application will automatically create:
echo   - User: bsp_admin
echo   - Database: bsp_db
echo.
pause
