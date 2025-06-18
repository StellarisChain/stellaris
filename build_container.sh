#!/bin/bash

# VoxaCommunications NetNode Container Build Script
# This script builds the Docker container for the NetNode application

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
IMAGE_NAME="voxacommunications-netnode"
TAG="latest"
BUILD_ARGS=""
NO_CACHE=false
VERBOSE=false

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

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -n, --name IMAGE_NAME    Set the image name (default: voxa-netnode)"
    echo "  -t, --tag TAG           Set the image tag (default: latest)"
    echo "  -a, --build-arg ARG     Pass build argument to docker build"
    echo "  --no-cache             Build without using cache"
    echo "  -v, --verbose          Enable verbose output"
    echo "  -h, --help             Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Build with defaults"
    echo "  $0 -n myapp -t v1.0.0                # Custom name and tag"
    echo "  $0 --no-cache                        # Build without cache"
    echo "  $0 -a ENV=production -t prod          # With build args"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -n|--name)
            IMAGE_NAME="$2"
            shift 2
            ;;
        -t|--tag)
            TAG="$2"
            shift 2
            ;;
        -a|--build-arg)
            BUILD_ARGS="$BUILD_ARGS --build-arg $2"
            shift 2
            ;;
        --no-cache)
            NO_CACHE=true
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Check if Docker is installed and running
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed or not in PATH"
    exit 1
fi

if ! docker info &> /dev/null; then
    print_error "Docker daemon is not running"
    exit 1
fi

# Check if Dockerfile exists
if [[ ! -f "Dockerfile" ]]; then
    print_error "Dockerfile not found in current directory"
    exit 1
fi

# Build the Docker image
print_status "Building Docker image: ${IMAGE_NAME}:${TAG}"
print_status "Build context: $(pwd)"

# Construct docker build command
DOCKER_CMD="docker build"

if [[ "$NO_CACHE" == true ]]; then
    DOCKER_CMD="$DOCKER_CMD --no-cache"
    print_status "Building without cache"
fi

if [[ "$VERBOSE" == true ]]; then
    DOCKER_CMD="$DOCKER_CMD --progress=plain"
fi

# Add build arguments if any
if [[ -n "$BUILD_ARGS" ]]; then
    DOCKER_CMD="$DOCKER_CMD $BUILD_ARGS"
    print_status "Build arguments: $BUILD_ARGS"
fi

# Add tag and context
DOCKER_CMD="$DOCKER_CMD -t ${IMAGE_NAME}:${TAG} ."

print_status "Executing: $DOCKER_CMD"

# Execute the build
if eval $DOCKER_CMD; then
    print_success "Container built successfully!"
    print_success "Image: ${IMAGE_NAME}:${TAG}"
    
    # Show image information
    print_status "Image details:"
    docker images "${IMAGE_NAME}:${TAG}" --format "table {{.Repository}}\t{{.Tag}}\t{{.ID}}\t{{.CreatedAt}}\t{{.Size}}"
    
    # Optional: Tag as latest if a specific tag was used
    if [[ "$TAG" != "latest" ]]; then
        print_status "Tagging as latest..."
        docker tag "${IMAGE_NAME}:${TAG}" "${IMAGE_NAME}:latest"
        print_success "Also tagged as ${IMAGE_NAME}:latest"
    fi
    
    print_success "Build completed successfully!"
    echo ""
    print_status "To run the container:"
    echo "  docker run -d -p 9999:9999 -p 9000:9000 --name netnode ${IMAGE_NAME}:${TAG}"
    echo ""
    print_status "To run interactively:"
    echo "  docker run -it --rm -p 9999:9999 -p 9000:9000 ${IMAGE_NAME}:${TAG} bash"
    
else
    print_error "Container build failed!"
    exit 1
fi