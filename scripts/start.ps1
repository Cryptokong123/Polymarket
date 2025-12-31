# Start the Polymarket Trading Bot (PowerShell)

param(
    [ValidateSet("manual", "research-only", "executor-only", "docker", "dry-run")]
    [string]$Mode = "manual"
)

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  POLYMARKET AUTONOMOUS TRADING BOT" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

$ProjectDir = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectDir

# Check for .env file
if (-not (Test-Path ".env")) {
    Write-Host "Error: .env file not found!" -ForegroundColor Red
    Write-Host "Please copy .env.example to .env and configure it." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Copy-Item .env.example .env" -ForegroundColor Gray
    Write-Host "  notepad .env" -ForegroundColor Gray
    Write-Host ""
    exit 1
}

switch ($Mode) {
    "manual" {
        Write-Host "Starting in manual mode..." -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Please run in separate terminals:" -ForegroundColor White
        Write-Host ""
        Write-Host "Terminal 1 (Python Research):" -ForegroundColor Cyan
        Write-Host "  cd $ProjectDir\python-research" -ForegroundColor Gray
        Write-Host "  .\venv\Scripts\Activate.ps1" -ForegroundColor Gray
        Write-Host "  python signal_generator.py" -ForegroundColor Gray
        Write-Host ""
        Write-Host "Terminal 2 (TypeScript Executor):" -ForegroundColor Cyan
        Write-Host "  cd $ProjectDir\eliza-executor" -ForegroundColor Gray
        Write-Host "  npm run dev" -ForegroundColor Gray
        Write-Host ""
        Write-Host "Or use: .\scripts\start.ps1 -Mode research-only" -ForegroundColor Yellow
    }

    "research-only" {
        Write-Host "Starting Python research layer only..." -ForegroundColor Yellow
        Set-Location "$ProjectDir\python-research"
        if (Test-Path "venv\Scripts\Activate.ps1") {
            & ".\venv\Scripts\Activate.ps1"
        }
        python signal_generator.py
    }

    "executor-only" {
        Write-Host "Starting TypeScript executor layer only..." -ForegroundColor Yellow
        Set-Location "$ProjectDir\eliza-executor"
        npm run dev
    }

    "docker" {
        Write-Host "Starting with Docker Compose..." -ForegroundColor Yellow
        Write-Host "Note: Make sure Docker Desktop is running" -ForegroundColor Yellow
        Set-Location "$ProjectDir\docker"
        docker-compose up --build
    }

    "dry-run" {
        Write-Host "Starting in dry-run mode..." -ForegroundColor Yellow
        $env:DRY_RUN = "true"
        Set-Location "$ProjectDir\docker"
        docker-compose up --build
    }
}
