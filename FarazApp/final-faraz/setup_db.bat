@echo off
REM ========================================================
REM Database Setup Script
REM ========================================================

echo ==========================================
echo Database Setup for Faraz Energy Project
echo ==========================================
echo.

REM Check if venv exists
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found.
    echo Please run 'run_webapp.bat' first to create the virtual environment.
    pause
    exit /b 1
)

REM Activate venv
call "venv\Scripts\activate.bat"

REM Run setup script
python setup_database.py

pause
