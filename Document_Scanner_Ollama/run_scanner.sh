#!/bin/bash

# Get the directory where the script is located to ensure paths are correct.
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Activate the project-specific virtual environment.
source "$SCRIPT_DIR/.venv/bin/activate"

# Run the python script.
python "$SCRIPT_DIR/document_processor.py"
