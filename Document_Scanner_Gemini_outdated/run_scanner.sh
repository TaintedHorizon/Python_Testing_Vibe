#!/bin/bash

# Get the directory where the script is located to ensure paths are correct.
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Load environment variables from .env file if it exists in the same directory.
if [ -f "$SCRIPT_DIR/.env" ]; then
  set -a # automatically export all variables
  source "$SCRIPT_DIR/.env"
  set +a
fi

# Activate the project-specific virtual environment.
source "$SCRIPT_DIR/.venv/bin/activate"

# Run the python script.
python "$SCRIPT_DIR/document_processor.py"
