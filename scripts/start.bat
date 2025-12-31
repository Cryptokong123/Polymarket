@echo off
REM Start the Polymarket Trading Bot (Windows)

echo ============================================
echo   POLYMARKET AUTONOMOUS TRADING BOT
echo ============================================
echo.

cd /d "%~dp0\.."

REM Check for .env file
if not exist ".env" (
    echo Error: .env file not found!
    echo Please copy .env.example to .env and configure it.
    echo.
    echo   copy .env.example .env
    echo   notepad .env
    echo.
    pause
    exit /b 1
)

REM Parse arguments
set MODE=%1
if "%MODE%"=="" set MODE=manual

if "%MODE%"=="manual" goto manual
if "%MODE%"=="research-only" goto research
if "%MODE%"=="executor-only" goto executor
if "%MODE%"=="docker" goto docker
if "%MODE%"=="dry-run" goto dryrun
goto usage

:manual
echo Starting in manual mode...
echo.
echo Please run in separate terminals:
echo.
echo Terminal 1 (Python Research):
echo   cd %cd%\python-research
echo   venv\Scripts\activate
echo   python signal_generator.py
echo.
echo Terminal 2 (TypeScript Executor):
echo   cd %cd%\eliza-executor
echo   npm run dev
echo.
echo Or use 'start.bat research-only' to run just the research layer
echo.
pause
goto end

:research
echo Starting Python research layer only...
cd python-research
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)
python signal_generator.py
goto end

:executor
echo Starting TypeScript executor layer only...
cd eliza-executor
call npm run dev
goto end

:docker
echo Starting with Docker Compose...
echo Note: Make sure Docker Desktop is running
cd docker
docker-compose up --build
goto end

:dryrun
echo Starting in dry-run mode...
set DRY_RUN=true
cd docker
docker-compose up --build
goto end

:usage
echo Usage: start.bat [mode]
echo.
echo Modes:
echo   manual         - Show instructions for manual start (default)
echo   research-only  - Start only the Python research layer
echo   executor-only  - Start only the TypeScript executor layer
echo   docker         - Start with Docker Compose
echo   dry-run        - Start in dry-run mode (no real trades)
echo.
pause
goto end

:end
