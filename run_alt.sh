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

# Set PYTHONPATH to include both project root and src directory
export PYTHONPATH="${PYTHONPATH}:$(pwd):$(pwd)/src"

# Run the application with uvicorn
echo "Starting FastAPI application with uvicorn..."
uvicorn src.main:app --host 0.0.0.0 --port 9000 --reload

# Deactivate the virtual environment when the server stops
deactivate