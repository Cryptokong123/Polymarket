#!/bin/bash
# Setup script for Polymarket Trading Bot

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "============================================"
echo "  POLYMARKET TRADING BOT SETUP"
echo "============================================"
echo ""

cd "$PROJECT_DIR"

# Check Python version
echo "Checking Python version..."
if command -v python3.11 &> /dev/null; then
    PYTHON="python3.11"
elif command -v python3.10 &> /dev/null; then
    PYTHON="python3.10"
elif command -v python3.9 &> /dev/null; then
    PYTHON="python3.9"
elif command -v python3 &> /dev/null; then
    PYTHON="python3"
else
    echo "Error: Python 3.9+ is required"
    exit 1
fi
echo "Using: $($PYTHON --version)"

# Check Node.js version
echo "Checking Node.js version..."
if ! command -v node &> /dev/null; then
    echo "Error: Node.js is required"
    echo "Please install Node.js 18+ from https://nodejs.org"
    exit 1
fi
NODE_VERSION=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VERSION" -lt 18 ]; then
    echo "Error: Node.js 18+ is required (found: $(node -v))"
    exit 1
fi
echo "Using: $(node -v)"

# Setup Python environment
echo ""
echo "Setting up Python environment..."
cd "$PROJECT_DIR/python-research"

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    $PYTHON -m venv .venv
fi

echo "Activating virtual environment..."
source .venv/bin/activate

echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Setup TypeScript environment
echo ""
echo "Setting up TypeScript environment..."
cd "$PROJECT_DIR/eliza-executor"

echo "Installing Node.js dependencies..."
npm install

echo "Building TypeScript..."
npm run build

# Create .env if it doesn't exist
cd "$PROJECT_DIR"
if [ ! -f ".env" ]; then
    echo ""
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "IMPORTANT: Please edit .env with your configuration!"
fi

# Create data directories
echo ""
echo "Creating data directories..."
mkdir -p data/chroma shared/signals shared/executed shared/results

echo ""
echo "============================================"
echo "  SETUP COMPLETE!"
echo "============================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Configure your .env file:"
echo "   nano .env"
echo ""
echo "2. Add your wallet private key and API keys"
echo ""
echo "3. (Optional) Set up token allowances:"
echo "   cd python-research && source .venv/bin/activate"
echo "   python scripts/setup_allowances.py"
echo ""
echo "4. Start the bot:"
echo "   ./scripts/start.sh"
echo ""
echo "For dry-run mode (no real trades):"
echo "   ./scripts/start.sh dry-run"
echo ""
