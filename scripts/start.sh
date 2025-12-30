#!/bin/bash
# Start the Polymarket Trading Bot

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "============================================"
echo "  POLYMARKET AUTONOMOUS TRADING BOT"
echo "============================================"
echo ""

# Check for .env file
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo "Error: .env file not found!"
    echo "Please copy .env.example to .env and configure it."
    echo ""
    echo "  cp .env.example .env"
    echo "  nano .env  # or your preferred editor"
    echo ""
    exit 1
fi

# Load environment
source "$PROJECT_DIR/.env"

# Check required variables
if [ -z "$POLYGON_WALLET_PRIVATE_KEY" ]; then
    echo "Error: POLYGON_WALLET_PRIVATE_KEY not set in .env"
    exit 1
fi

if [ -z "$WALLET_ADDRESS" ]; then
    echo "Error: WALLET_ADDRESS not set in .env"
    exit 1
fi

if [ -z "$OPENAI_API_KEY" ] && [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "Error: At least one LLM API key required (OPENAI_API_KEY or ANTHROPIC_API_KEY)"
    exit 1
fi

echo "Configuration OK"
echo ""

# Parse arguments
MODE="${1:-docker}"

case "$MODE" in
    docker)
        echo "Starting with Docker Compose..."
        cd "$PROJECT_DIR/docker"
        docker-compose up --build
        ;;

    manual)
        echo "Starting in manual mode..."
        echo ""
        echo "Please run in separate terminals:"
        echo ""
        echo "Terminal 1 (Python Research):"
        echo "  cd $PROJECT_DIR/python-research"
        echo "  source .venv/bin/activate"
        echo "  python signal_generator.py"
        echo ""
        echo "Terminal 2 (TypeScript Executor):"
        echo "  cd $PROJECT_DIR/eliza-executor"
        echo "  npm run dev"
        echo ""
        ;;

    research-only)
        echo "Starting Python research layer only..."
        cd "$PROJECT_DIR/python-research"
        if [ -d ".venv" ]; then
            source .venv/bin/activate
        fi
        python signal_generator.py
        ;;

    executor-only)
        echo "Starting TypeScript executor layer only..."
        cd "$PROJECT_DIR/eliza-executor"
        npm run dev
        ;;

    dry-run)
        echo "Starting in dry-run mode (no real trades)..."
        export DRY_RUN=true
        cd "$PROJECT_DIR/docker"
        docker-compose up --build
        ;;

    *)
        echo "Usage: $0 [docker|manual|research-only|executor-only|dry-run]"
        echo ""
        echo "  docker         - Start with Docker Compose (default)"
        echo "  manual         - Show instructions for manual start"
        echo "  research-only  - Start only the Python research layer"
        echo "  executor-only  - Start only the TypeScript executor layer"
        echo "  dry-run        - Start in dry-run mode (no real trades)"
        echo ""
        exit 1
        ;;
esac
