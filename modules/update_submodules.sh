#!/bin/bash

# Script to update all submodules in the modules directory
# This script will iterate through all subdirectories in /modules that are git submodules
# and update them to their latest commits

set -e  # Exit on any error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODULES_DIR="$SCRIPT_DIR"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🔄 Updating submodules in $MODULES_DIR"
echo "Project root: $PROJECT_ROOT"

cd "$PROJECT_ROOT"

# First, ensure we're in a git repository
if [ ! -d ".git" ]; then
    echo "❌ Error: Not in a git repository"
    exit 1
fi

# Initialize and update all submodules
echo "📥 Initializing and updating all submodules..."
git submodule update --init --recursive

# Get list of all submodules in the modules directory
SUBMODULES=$(git config --file .gitmodules --get-regexp path | grep "^submodule\..*\.path modules/" | cut -d' ' -f2)

if [ -z "$SUBMODULES" ]; then
    echo "⚠️  No submodules found in modules directory"
    exit 0
fi

echo "📦 Found submodules:"
echo "$SUBMODULES"
echo

# Update each submodule
for submodule in $SUBMODULES; do
    echo "🔄 Updating submodule: $submodule"
    
    if [ -d "$submodule" ]; then
        cd "$submodule"
        
        # Check if it's a git repository
        if [ -d ".git" ]; then
            echo "  📡 Fetching latest changes..."
            git fetch origin
            
            echo "  🔀 Checking out and pulling latest changes..."
            # Save current branch
            current_branch=$(git rev-parse --abbrev-ref HEAD)
            
            # If we have a dev branch and we're not on it, switch to dev
            if git show-ref --verify --quiet refs/remotes/origin/dev; then
                if [ "$current_branch" != "dev" ]; then
                    echo "    🌿 Switching to dev branch..."
                    git checkout dev 2>/dev/null || git checkout -b dev origin/dev
                fi
                echo "    📥 Pulling latest changes from dev branch..."
                git pull origin dev
            # Otherwise try main branch first, then master
            elif git show-ref --verify --quiet refs/remotes/origin/main; then
                if [ "$current_branch" != "main" ]; then
                    echo "    🌿 Switching to main branch..."
                    git checkout main 2>/dev/null || git checkout -b main origin/main
                fi
                echo "    📥 Pulling latest changes from main branch..."
                git pull origin main
            elif git show-ref --verify --quiet refs/remotes/origin/master; then
                if [ "$current_branch" != "master" ]; then
                    echo "    🌿 Switching to master branch..."
                    git checkout master 2>/dev/null || git checkout -b master origin/master
                fi
                echo "    📥 Pulling latest changes from master branch..."
                git pull origin master
            else
                echo "  ⚠️  Warning: No dev, main, or master branch found, staying on current branch"
                git pull
            fi
            
            echo "  ✅ Successfully updated $submodule"
        else
            echo "  ❌ Error: $submodule is not a git repository"
        fi
        
        cd "$PROJECT_ROOT"
    else
        echo "  ❌ Error: Directory $submodule does not exist"
    fi
    echo
done

echo "🎉 All submodules updated successfully!"

# Show the status of all submodules
echo "📊 Submodule status:"
git submodule status