@echo off
REM One-time setup on the Windows server: create venv and install packages
setlocal EnableExtensions
cd /d "%~dp0"

echo ==========================================
echo  Faraz Energy - Server install
echo ==========================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not on PATH.
    echo Install Python 3.10 or 3.11 from python.org and check "Add to PATH".
    pause
    exit /b 1
)

python --version
echo.

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo ERROR: Could not create venv.
        pause
        exit /b 1
    )
)

call .venv\Scripts\activate.bat
echo Upgrading pip...
python -m pip install --upgrade pip
echo Installing packages from requirements_exact.txt ...
python -m pip install -r requirements_exact.txt
if errorlevel 1 (
    echo ERROR: pip install failed.
    pause
    exit /b 1
)

if not exist "logs" mkdir logs
if not exist "data" mkdir data
if not exist "downloads" mkdir downloads

echo.
echo ==========================================
echo  Install finished successfully.
echo  Next steps: see DEPLOYMENT_GUIDE.md
echo ==========================================
pause
endlocal
