#!/bin/bash

# Build script for Stellaris Docker image
# This script builds the Docker image for the Stellaris blockchain node

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
IMAGE_NAME="stellaris-node"
TAG="latest"
NO_CACHE=false
VERBOSE=false

# Function to print colored output
print_color() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Function to check if Docker is installed and running
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_color $RED "✗ Docker is not installed or not in PATH"
        return 1
    fi
    
    local docker_version=$(docker --version 2>/dev/null)
    print_color $GREEN "✓ Docker is installed: $docker_version"
    
    if ! docker info &> /dev/null; then
        print_color $RED "✗ Docker daemon is not running. Please start Docker."
        return 1
    fi
    
    print_color $GREEN "✓ Docker daemon is running"
    return 0
}

# Function to show usage
show_usage() {
    echo ""
    echo "Stellaris Docker Build Script"
    echo ""
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  --name NAME     Set the image name (default: stellaris)"
    echo "  --tag TAG       Set the image tag (default: latest)"
    echo "  --no-cache      Build without using cache"
    echo "  --verbose       Enable verbose output"
    echo "  --help          Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0"
    echo "  $0 --name my-stellaris --tag v1.0"
    echo "  $0 --no-cache --verbose"
    echo ""
}

# Function to show post-build usage instructions
show_post_build_usage() {
    print_color $BLUE "
Docker Image Build Complete!

Usage examples:
  Run the container:
    docker run -it --rm ${IMAGE_NAME}:${TAG}

  Run with port mapping (if your app exposes ports):
    docker run -it --rm -p 8000:8000 ${IMAGE_NAME}:${TAG}

  Run in detached mode:
    docker run -d --name stellaris-node ${IMAGE_NAME}:${TAG}

  View container logs:
    docker logs stellaris-node

  Stop the container:
    docker stop stellaris-node

  Remove the container:
    docker rm stellaris-node
"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --name)
            IMAGE_NAME="$2"
            shift 2
            ;;
        --tag)
            TAG="$2"
            shift 2
            ;;
        --no-cache)
            NO_CACHE=true
            shift
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        --help)
            show_usage
            exit 0
            ;;
        *)
            print_color $RED "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Main execution
print_color $BLUE "=== Stellaris Docker Build Script ==="
print_color $BLUE "Image: ${IMAGE_NAME}:${TAG}"

if [ "$NO_CACHE" = true ]; then
    print_color $YELLOW "Note: Build cache will be ignored"
fi

# Check if we're in the right directory
if [ ! -f "Dockerfile" ]; then
    print_color $RED "✗ Dockerfile not found in current directory: $(pwd)"
    print_color $YELLOW "Please run this script from the project root directory"
    exit 1
fi

# Check Docker installation and status
if ! check_docker; then
    print_color $RED "Docker is required but not available. Please install Docker and ensure it's running."
    exit 1
fi

# Build the Docker image
print_color $BLUE "\nStarting Docker build..."
print_color $BLUE "Build context: $(pwd)"

# Prepare Docker build command
BUILD_ARGS="build -t ${IMAGE_NAME}:${TAG}"

if [ "$NO_CACHE" = true ]; then
    BUILD_ARGS="$BUILD_ARGS --no-cache"
    print_color $YELLOW "Using --no-cache flag"
fi

if [ "$VERBOSE" = true ]; then
    BUILD_ARGS="$BUILD_ARGS --progress=plain"
fi

BUILD_ARGS="$BUILD_ARGS ."

print_color $BLUE "Running: docker $BUILD_ARGS"
print_color $BLUE "----------------------------------------"

# Execute the build
if docker $BUILD_ARGS; then
    print_color $GREEN "✓ Successfully built Docker image: ${IMAGE_NAME}:${TAG}"
    
    # Show image info
    print_color $BLUE "\nImage information:"
    docker images $IMAGE_NAME --format "table {{.Repository}}\t{{.Tag}}\t{{.ID}}\t{{.CreatedAt}}\t{{.Size}}"
    
    show_post_build_usage
    print_color $GREEN "\n✓ Build completed successfully!"
    exit 0
else
    print_color $RED "\n✗ Docker build failed!"
    exit 1
fi