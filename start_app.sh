#!/bin/bash

# Document Processing System Startup Script
# This script ensures the correct virtual environment is always used
# and the app is run with the proper module syntax from the repo root.
#
# 🤖 AI ASSISTANTS: See .github/copilot-instructions.md for critical patterns!
# ⚠️  ALWAYS use this script instead of running Flask directly!

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Python Testing Vibe Document Processor ===${NC}"
echo -e "${YELLOW}Starting Flask application with proper environment...${NC}"

# Get script directory and repo root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$SCRIPT_DIR"
DOC_PROCESSOR_DIR="$REPO_ROOT/doc_processor"
VENV_DIR="$DOC_PROCESSOR_DIR/venv"

# Verify we're in the right directory
if [ ! -d "$DOC_PROCESSOR_DIR" ]; then
    echo -e "${RED}ERROR: doc_processor directory not found. Are you in the repo root?${NC}"
    exit 1
fi

# Verify virtual environment exists
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${RED}ERROR: Virtual environment not found at $VENV_DIR${NC}"
    echo -e "${YELLOW}Please create the virtual environment first:${NC}"
    echo "  cd $DOC_PROCESSOR_DIR"
    echo "  python3 -m venv venv"
    echo "  source venv/bin/activate"
    echo "  pip install -r requirements.txt"
    exit 1
fi

# Change to repo root
cd "$REPO_ROOT"
echo -e "${GREEN}Changed to repo root: $(pwd)${NC}"

# Load environment variables from doc_processor/.env if present
ENV_FILE="$REPO_ROOT/doc_processor/.env"
if [ -f "$ENV_FILE" ]; then
    echo -e "${YELLOW}Loading environment from ${ENV_FILE}${NC}"
    set -o allexport
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +o allexport
fi

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source "$VENV_DIR/bin/activate"

# Verify Python path
echo -e "${GREEN}Using Python: $(which python)${NC}"
echo -e "${GREEN}Python version: $(python --version)${NC}"

# Run the Flask app as a module (the correct way!)
echo -e "${YELLOW}Starting Flask application...${NC}"
HOST_TO_BIND="${HOST:-127.0.0.1}"
PORT_TO_BIND="${PORT:-5000}"
echo -e "${GREEN}Application will be available at:${NC}"
echo -e "  ${GREEN}http://${HOST_TO_BIND}:${PORT_TO_BIND}${NC}"
echo -e "  ${GREEN}http://192.168.10.11:${PORT_TO_BIND}${NC}"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop the server${NC}"
echo ""

# Determine the port to use (allow overriding via environment variable)
PORT_TO_FREE="${PORT:-5000}"
echo -e "${YELLOW}Ensuring port ${PORT_TO_FREE} is free before starting...${NC}"
kill_pids=()
if command -v lsof >/dev/null 2>&1; then
    # lsof prints PIDs listening on the chosen port
    mapfile -t kill_pids < <(lsof -tiTCP:${PORT_TO_FREE} -sTCP:LISTEN || true)
else
    # Fallback to ss if lsof isn't available
    mapfile -t kill_pids < <(ss -ltnp 2>/dev/null | awk -v port=":${PORT_TO_FREE} " '$0 ~ port {print $0}' | sed -n 's/.*pid=\([0-9]*\).*/\1/p' || true)
fi

if [ ${#kill_pids[@]} -ne 0 ]; then
    echo -e "${YELLOW}Found process(es) using port ${PORT_TO_FREE}: ${kill_pids[*]}${NC}"
    for pid in "${kill_pids[@]}"; do
        if [ -n "$pid" ]; then
            echo -e "${YELLOW}Stopping PID $pid to free port ${PORT_TO_FREE}...${NC}"
            kill -TERM "$pid" 2>/dev/null || kill -KILL "$pid" 2>/dev/null || true
            sleep 1
        fi
    done
    echo -e "${GREEN}Port ${PORT_TO_FREE} freed.${NC}"
else
    echo -e "${GREEN}Port ${PORT_TO_FREE} was free.${NC}"
fi

# Export HOST/PORT for the app and run it
export HOST="$HOST_TO_BIND"
export PORT="$PORT_TO_BIND"
python -m doc_processor.app

echo -e "${YELLOW}Flask application stopped.${NC}"