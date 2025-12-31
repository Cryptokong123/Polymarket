@echo off
REM Setup script for Polymarket Trading Bot (Windows)

echo ============================================
echo   POLYMARKET TRADING BOT SETUP (Windows)
echo ============================================
echo.

cd /d "%~dp0\.."

REM Check Python version
echo Checking Python version...
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.9+ from https://python.org
    pause
    exit /b 1
)
python --version

REM Check Node.js version
echo Checking Node.js version...
node --version >nul 2>&1
if errorlevel 1 (
    echo Error: Node.js is not installed or not in PATH
    echo Please install Node.js 18+ from https://nodejs.org
    pause
    exit /b 1
)
node --version

REM Setup Python environment
echo.
echo Setting up Python environment...
cd python-research

if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Installing Python dependencies...
pip install --upgrade pip
pip install -r requirements.txt

REM Setup TypeScript environment
echo.
echo Setting up TypeScript environment...
cd ..\eliza-executor

echo Installing Node.js dependencies...
call npm install

echo Building TypeScript...
call npm run build

REM Create .env if it doesn't exist
cd ..
if not exist ".env" (
    echo.
    echo Creating .env file from template...
    copy .env.example .env
    echo IMPORTANT: Please edit .env with your configuration!
)

REM Create data directories
echo.
echo Creating data directories...
if not exist "data\chroma" mkdir data\chroma
if not exist "shared\signals" mkdir shared\signals
if not exist "shared\executed" mkdir shared\executed
if not exist "shared\results" mkdir shared\results

echo.
echo ============================================
echo   SETUP COMPLETE!
echo ============================================
echo.
echo Next steps:
echo.
echo 1. Configure your .env file:
echo    notepad .env
echo.
echo 2. Add your wallet private key and API keys
echo.
echo 3. Start the bot:
echo    scripts\start.bat
echo.
echo For research-only mode (no real trades):
echo    scripts\start.bat research-only
echo.
pause
