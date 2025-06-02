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

# Read host and port from config/p2p.json
echo "Reading configuration from config/p2p.json..."
HOST=$(python -c "import json; config = json.load(open('config/p2p.json')); print(config['host'])")
PORT=$(python -c "import json; config = json.load(open('config/p2p.json')); print(config['port'])")

# Run the application with uvicorn from the project root
echo "Starting FastAPI application with uvicorn on ${HOST}:${PORT}..."
uvicorn src.main:app --host $HOST --port $PORT --reload

# Deactivate the virtual environment when the server stops
deactivate