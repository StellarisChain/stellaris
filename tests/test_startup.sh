#!/bin/bash
set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Change to the project root directory (parent of tests)
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

echo "Changed to project root: $(pwd)"

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

# Read host and port from config/p2p.json
echo "Reading configuration from config/p2p.json..."
HOST=$(python -c "import json;import os;import io;from typing import LiteralString;exec(open('src/util/jsonreader.py').read());config_data = read_json_from_namespace('config.settings');print(config_data['server-settings']['host'])")
PORT=$(python -c "import json;import os;import io;from typing import LiteralString;exec(open('src/util/jsonreader.py').read());config_data = read_json_from_namespace('config.settings');print(config_data['server-settings']['port'])")

echo "Testing FastAPI application startup..."

# Start the server in background
uvicorn src.main:app --host $HOST --port $PORT &
SERVER_PID=$!

# Wait a bit for server to start
sleep 60 # increase as server start time may vary

# Test if server is responding
if curl -f http://$HOST:$PORT/status/health 2>/dev/null || curl -f http://$HOST:$PORT/info/program_stats 2>/dev/null; then
    echo "✅ Server started successfully and is responding"
    kill $SERVER_PID
    exit 0
else
    echo "❌ Server failed to respond"
    kill $SERVER_PID 2>/dev/null || true
    exit 1
fi