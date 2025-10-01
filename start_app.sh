#!/bin/bash

# Document Processing System Startup Script
# This script ensures the correct virtual environment is always used
# and the app is run with the proper module syntax from the repo root.

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

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source "$VENV_DIR/bin/activate"

# Verify Python path
echo -e "${GREEN}Using Python: $(which python)${NC}"
echo -e "${GREEN}Python version: $(python --version)${NC}"

# Run the Flask app as a module (the correct way!)
echo -e "${YELLOW}Starting Flask application...${NC}"
echo -e "${GREEN}Application will be available at:${NC}"
echo -e "  ${GREEN}http://127.0.0.1:5000${NC}"
echo -e "  ${GREEN}http://192.168.10.11:5000${NC}"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop the server${NC}"
echo ""

# Execute the Flask app
python -m doc_processor.app

echo -e "${YELLOW}Flask application stopped.${NC}"