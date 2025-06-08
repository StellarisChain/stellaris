#!/bin/bash

# VoxaCommunications-NetNode Nuitka Compilation Script
# This script compiles the Python application into a standalone executable using Nuitka

set -e  # Exit on any error

echo "🚀 Starting Nuitka compilation for VoxaCommunications-NetNode..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Create a virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python -m venv .venv
fi

# Activate the virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

# Install Nuitka
echo -e "${YELLOW}📥 Installing Nuitka...${NC}"
pip install nuitka

# Create build directory
BUILD_DIR="build"
DIST_DIR="dist"
mkdir -p "$BUILD_DIR"
mkdir -p "$DIST_DIR"

echo -e "${YELLOW}📦 Installing dependencies...${NC}"
pip install -r requirements.txt

echo -e "${YELLOW}🔧 Compiling with Nuitka...${NC}"

# Nuitka compilation command
python -m nuitka \
    --standalone \
    --onefile \
    --output-dir="$DIST_DIR" \
    --output-filename="voxa-netnode" \
    --include-package=src \
    --include-package=fastapi \
    --include-package=uvicorn \
    --include-package=pydantic \
    --include-package=cryptography \
    --include-package=kytan \
    --include-package=kvprocessor \
    --include-package=colorama \
    --include-package=dotenv \
    --include-package=rsa \
    --include-package=psutil \
    --include-package=httpx \
    --include-data-dir=config=config \
    --include-data-dir=data=data \
    --include-data-file=summary.txt=summary.txt \
    --include-data-file=README.md=README.md \
    --include-data-file=.env=.env \
    --python-flag=no_site \
    --python-flag=no_warnings \
    --enable-plugin=anti-bloat \
    --show-progress \
    --show-memory \
    --assume-yes-for-downloads \
    --warn-implicit-exceptions \
    --warn-unusual-code \
    src/main.py

# Check if compilation was successful
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Compilation successful!${NC}"
    echo -e "${GREEN}📍 Executable location: $DIST_DIR/voxa-netnode${NC}"
    
    # Display file size
    if [ -f "$DIST_DIR/voxa-netnode" ]; then
        FILE_SIZE=$(du -h "$DIST_DIR/voxa-netnode" | cut -f1)
        echo -e "${GREEN}📏 Executable size: $FILE_SIZE${NC}"
        
        # Make executable
        chmod +x "$DIST_DIR/voxa-netnode"
        echo -e "${GREEN}🔑 Made executable${NC}"
    fi
    
    echo -e "${GREEN}🎉 VoxaCommunications-NetNode compiled successfully!${NC}"
    echo -e "${YELLOW}ℹ️  To run: ./$DIST_DIR/voxa-netnode${NC}"
    
else
    echo -e "${RED}❌ Compilation failed!${NC}"
    exit 1
fi