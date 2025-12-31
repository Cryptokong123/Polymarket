# Setup script for Polymarket Trading Bot (PowerShell)

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  POLYMARKET TRADING BOT SETUP (Windows)" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

$ProjectDir = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectDir

# Check Python version
Write-Host "Checking Python version..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host $pythonVersion -ForegroundColor Green
} catch {
    Write-Host "Error: Python is not installed or not in PATH" -ForegroundColor Red
    Write-Host "Please install Python 3.9+ from https://python.org" -ForegroundColor Red
    exit 1
}

# Check Node.js version
Write-Host "Checking Node.js version..." -ForegroundColor Yellow
try {
    $nodeVersion = node --version 2>&1
    Write-Host "Node.js $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "Error: Node.js is not installed or not in PATH" -ForegroundColor Red
    Write-Host "Please install Node.js 18+ from https://nodejs.org" -ForegroundColor Red
    exit 1
}

# Setup Python environment
Write-Host ""
Write-Host "Setting up Python environment..." -ForegroundColor Yellow
Set-Location "$ProjectDir\python-research"

if (-not (Test-Path "venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
}

Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& ".\venv\Scripts\Activate.ps1"

Write-Host "Installing Python dependencies..." -ForegroundColor Yellow
pip install --upgrade pip
pip install -r requirements.txt

# Setup TypeScript environment
Write-Host ""
Write-Host "Setting up TypeScript environment..." -ForegroundColor Yellow
Set-Location "$ProjectDir\eliza-executor"

Write-Host "Installing Node.js dependencies..." -ForegroundColor Yellow
npm install

Write-Host "Building TypeScript..." -ForegroundColor Yellow
npm run build

# Create .env if it doesn't exist
Set-Location $ProjectDir
if (-not (Test-Path ".env")) {
    Write-Host ""
    Write-Host "Creating .env file from template..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host "IMPORTANT: Please edit .env with your configuration!" -ForegroundColor Red
}

# Create data directories
Write-Host ""
Write-Host "Creating data directories..." -ForegroundColor Yellow
$dirs = @("data\chroma", "shared\signals", "shared\executed", "shared\results")
foreach ($dir in $dirs) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  SETUP COMPLETE!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Configure your .env file:" -ForegroundColor White
Write-Host "   notepad .env" -ForegroundColor Gray
Write-Host ""
Write-Host "2. Add your wallet private key and API keys" -ForegroundColor White
Write-Host ""
Write-Host "3. Start the bot:" -ForegroundColor White
Write-Host "   .\scripts\start.ps1" -ForegroundColor Gray
Write-Host ""
Write-Host "For research-only mode:" -ForegroundColor White
Write-Host "   .\scripts\start.ps1 -Mode research-only" -ForegroundColor Gray
Write-Host ""
