#!/bin/bash

# Stellaris Chain Build Script
# This script builds the Stellaris Chain project using pyproject.toml

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to install build dependencies
install_build_deps() {
    print_status "Installing build dependencies..."
    
    # Check if pip is available
    if ! command_exists pip; then
        print_error "pip is not installed. Please install Python and pip first."
        exit 1
    fi
    
    # Upgrade pip and install build tools
    python -m pip install --upgrade pip
    python -m pip install --upgrade build wheel setuptools
    
    print_success "Build dependencies installed"
}

# Function to create virtual environment
create_venv() {
    if [ "$1" = "true" ]; then
        print_status "Creating virtual environment..."
        python -m venv stellaris-venv
        source stellaris-venv/bin/activate
        python -m pip install --upgrade pip
        print_success "Virtual environment created and activated"
    fi
}

# Function to install dependencies
install_deps() {
    print_status "Installing project dependencies..."
    
    # Install the project in development mode with all dependencies
    python -m pip install -e ".[dev]"
    
    print_success "Dependencies installed"
}

# Function to run type checking
run_type_check() {
    if [ "$1" = "true" ]; then
        print_status "Running type checking with mypy..."
        if command_exists mypy; then
            mypy stellaris/ || {
                print_warning "Type checking completed with issues"
                return 0
            }
            print_success "Type checking passed"
        else
            print_warning "mypy not found, skipping type checking"
        fi
    fi
}

# Function to run tests
run_tests() {
    if [ "$1" = "true" ]; then
        print_status "Running tests..."
        if command_exists pytest; then
            if [ -d "tests" ]; then
                pytest tests/ || {
                    print_warning "Tests completed with issues"
                    return 0
                }
                print_success "All tests passed"
            else
                print_warning "No tests directory found, skipping tests"
            fi
        else
            print_warning "pytest not found, skipping tests"
        fi
    fi
}

# Function to build the package
build_package() {
    print_status "Building the package..."
    
    # Clean previous builds
    rm -rf build/ dist/ *.egg-info/
    
    # Build the package
    python -m build
    
    print_success "Package built successfully"
    print_status "Built files are available in the 'dist/' directory"
}

# Function to install the built package
install_package() {
    if [ "$1" = "true" ]; then
        print_status "Installing the built package..."
        
        # Find the wheel file
        WHEEL_FILE=$(find dist/ -name "*.whl" | head -n 1)
        
        if [ -n "$WHEEL_FILE" ]; then
            python -m pip install "$WHEEL_FILE" --force-reinstall
            print_success "Package installed successfully"
        else
            print_error "No wheel file found in dist/ directory"
            exit 1
        fi
    fi
}

# Function to show usage
show_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Build script for Stellaris Chain project.

OPTIONS:
    -h, --help          Show this help message
    -v, --venv          Create and use virtual environment
    -t, --type-check    Run type checking with mypy
    -T, --test          Run tests with pytest
    -i, --install       Install the built package after building
    -c, --clean         Clean build artifacts before building
    --dev-deps          Install development dependencies
    --no-build          Skip building (useful for just installing deps)

EXAMPLES:
    $0                  Basic build
    $0 -v -t -T         Build with venv, type checking, and tests
    $0 -c -i            Clean build and install
    $0 --dev-deps       Install development dependencies only

EOF
}

# Default options
USE_VENV=false
RUN_TYPE_CHECK=false
RUN_TESTS=false
INSTALL_PACKAGE=false
CLEAN_BUILD=false
INSTALL_DEV_DEPS=false
NO_BUILD=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_usage
            exit 0
            ;;
        -v|--venv)
            USE_VENV=true
            shift
            ;;
        -t|--type-check)
            RUN_TYPE_CHECK=true
            shift
            ;;
        -T|--test)
            RUN_TESTS=true
            shift
            ;;
        -i|--install)
            INSTALL_PACKAGE=true
            shift
            ;;
        -c|--clean)
            CLEAN_BUILD=true
            shift
            ;;
        --dev-deps)
            INSTALL_DEV_DEPS=true
            shift
            ;;
        --no-build)
            NO_BUILD=true
            shift
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Main build process
main() {
    print_status "Starting Stellaris Chain build process..."
    
    # Check if we're in the right directory
    if [ ! -f "pyproject.toml" ]; then
        print_error "pyproject.toml not found. Please run this script from the project root."
        exit 1
    fi
    
    # Clean build artifacts if requested
    if [ "$CLEAN_BUILD" = "true" ]; then
        print_status "Cleaning build artifacts..."
        rm -rf build/ dist/ *.egg-info/ stellaris-venv/
        print_success "Build artifacts cleaned"
    fi
    
    # Install build dependencies
    install_build_deps
    
    # Create virtual environment if requested
    create_venv "$USE_VENV"
    
    # Install dependencies
    if [ "$INSTALL_DEV_DEPS" = "true" ] || [ "$NO_BUILD" = "false" ]; then
        install_deps
    fi
    
    # Run type checking if requested
    run_type_check "$RUN_TYPE_CHECK"
    
    # Run tests if requested
    run_tests "$RUN_TESTS"
    
    # Build the package unless --no-build is specified
    if [ "$NO_BUILD" = "false" ]; then
        build_package
        
        # Install the package if requested
        install_package "$INSTALL_PACKAGE"
    fi
    
    print_success "Build process completed successfully!"
    
    if [ "$USE_VENV" = "true" ]; then
        print_status "Virtual environment is active. To deactivate, run: deactivate"
    fi
    
    if [ "$NO_BUILD" = "false" ]; then
        print_status "To install the package, run: pip install dist/*.whl"
    fi
}

# Run main function
main "$@"
