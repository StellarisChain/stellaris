#!/bin/bash

# Create a virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python -m venv .venv
fi

# Activate the virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

# Install requirements
echo "Installing requirements..."
python -m pip install -r requirements.txt

# Set PYTHONPATH to include project root and src directory
export PYTHONPATH="${PYTHONPATH}:$(pwd):$(pwd)/src"

# Read host and port from config/settings.json
echo "Reading configuration from config/settings.json..."
HOST=$(python -c "import json;import os;import io;from typing import LiteralString;exec(open('src/util/jsonreader.py').read());config_data = read_json_from_namespace('config.settings');print(config_data['server-settings']['host'])")
PORT=$(python -c "import json;import os;import io;from typing import LiteralString;exec(open('src/util/jsonreader.py').read());config_data = read_json_from_namespace('config.settings');print(config_data['server-settings']['port'])")

# Read auto-reload setting from config/dev.json
echo "Reading auto-reload configuration from config/dev.json..."
AUTO_RELOAD=$(python -c "import json; config = json.load(open('config/dev.json')); print(config['uvicorn-config']['auto-reload'])")

# Build uvicorn command with conditional --reload flag
UVICORN_CMD="uvicorn src.main:app --host $HOST --port $PORT"
if [ "$AUTO_RELOAD" = "True" ]; then
    UVICORN_CMD="$UVICORN_CMD --reload"
    echo "Auto-reload enabled"
else
    echo "Auto-reload disabled"
fi

# Run the application with uvicorn from the project root
echo "Starting FastAPI application with uvicorn on ${HOST}:${PORT}..."
$UVICORN_CMD

# Deactivate the virtual environment when the server stops
deactivate