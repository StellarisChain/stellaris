#!/bin/bash

# Script to generate patches for all submodules in the modules directory
# This script will iterate through all subdirectories in /modules that are git submodules
# and generate patch files for any uncommitted changes

set -e  # Exit on any error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODULES_DIR="$SCRIPT_DIR"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PATCHES_DIR="$PROJECT_ROOT/patches"

echo "🔧 Generating patches for submodules in $MODULES_DIR"
echo "Project root: $PROJECT_ROOT"
echo "Patches will be saved to: $PATCHES_DIR"

cd "$PROJECT_ROOT"

# First, ensure we're in a git repository
if [ ! -d ".git" ]; then
    echo "❌ Error: Not in a git repository"
    exit 1
fi

# Create patches directory if it doesn't exist
mkdir -p "$PATCHES_DIR"

# Get list of all submodules in the modules directory
SUBMODULES=$(git config --file .gitmodules --get-regexp path | grep "^submodule\..*\.path modules/" | cut -d' ' -f2)

if [ -z "$SUBMODULES" ]; then
    echo "⚠️  No submodules found in modules directory"
    exit 0
fi

echo "📦 Found submodules:"
echo "$SUBMODULES"
echo

PATCHES_GENERATED=0

# Generate patches for each submodule
for submodule in $SUBMODULES; do
    echo "🔍 Checking submodule: $submodule"
    
    if [ -d "$submodule" ]; then
        cd "$submodule"
        
        # Check if it's a git repository
        if [ -d ".git" ]; then
            # Get the submodule name (last part of the path)
            submodule_name=$(basename "$submodule")
            patch_prefix="$PATCHES_DIR/${submodule_name}"
            
            # Check for uncommitted changes
            if ! git diff --quiet; then
                echo "  📝 Found unstaged changes, generating patch..."
                git diff > "${patch_prefix}-unstaged.patch"
                echo "  ✅ Generated: ${patch_prefix}-unstaged.patch"
                PATCHES_GENERATED=$((PATCHES_GENERATED + 1))
            fi
            
            # Check for staged changes
            if ! git diff --cached --quiet; then
                echo "  📝 Found staged changes, generating patch..."
                git diff --cached > "${patch_prefix}-staged.patch"
                echo "  ✅ Generated: ${patch_prefix}-staged.patch"
                PATCHES_GENERATED=$((PATCHES_GENERATED + 1))
            fi
            
            # Check for unpushed commits
            current_branch=$(git rev-parse --abbrev-ref HEAD)
            
            # Determine the base branch to compare against
            base_branch=""
            if git rev-parse --verify "origin/main" >/dev/null 2>&1; then
                base_branch="origin/main"
            elif git rev-parse --verify "origin/master" >/dev/null 2>&1; then
                base_branch="origin/master"
            elif git rev-parse --verify "origin/$current_branch" >/dev/null 2>&1; then
                base_branch="origin/$current_branch"
            fi
            
            if [ -n "$base_branch" ]; then
                # If we're on dev branch, compare against main
                if [ "$current_branch" = "dev" ] && [ "$base_branch" != "origin/dev" ]; then
                    if git rev-parse --verify "origin/main" >/dev/null 2>&1; then
                        base_branch="origin/main"
                    fi
                fi
                
                unpushed_commits=$(git rev-list --count "$base_branch..$current_branch")
                if [ "$unpushed_commits" -gt 0 ]; then
                    echo "  📝 Found $unpushed_commits unpushed commits (compared to $base_branch), generating patch..."
                    git format-patch "$base_branch" --output-directory="$PATCHES_DIR" --subject-prefix="$submodule_name"
                    echo "  ✅ Generated patches for unpushed commits in $PATCHES_DIR"
                    PATCHES_GENERATED=$((PATCHES_GENERATED + unpushed_commits))
                fi
            else
                echo "  ⚠️  Warning: No remote tracking branch found"
                # Generate patch for all commits on current branch
                commit_count=$(git rev-list --count HEAD)
                if [ "$commit_count" -gt 0 ]; then
                    echo "  📝 Generating patches for all commits on current branch..."
                    git format-patch --root --output-directory="$PATCHES_DIR" --subject-prefix="$submodule_name"
                    echo "  ✅ Generated patches for all commits in $PATCHES_DIR"
                    PATCHES_GENERATED=$((PATCHES_GENERATED + commit_count))
                fi
            fi
            
            # If no changes found
            if git diff --quiet && git diff --cached --quiet; then
                if git rev-parse --verify "origin/$current_branch" >/dev/null 2>&1; then
                    if [ "$(git rev-list --count origin/$current_branch..$current_branch)" -eq 0 ]; then
                        echo "  ✨ No changes found in $submodule"
                    fi
                else
                    if [ "$(git rev-list --count HEAD)" -eq 0 ]; then
                        echo "  ✨ No changes found in $submodule"
                    fi
                fi
            fi
            
        else
            echo "  ❌ Error: $submodule is not a git repository"
        fi
        
        cd "$PROJECT_ROOT"
    else
        echo "  ❌ Error: Directory $submodule does not exist"
    fi
    echo
done

if [ "$PATCHES_GENERATED" -gt 0 ]; then
    echo "🎉 Generated $PATCHES_GENERATED patch file(s) in $PATCHES_DIR"
    echo "📁 Patch files:"
    ls -la "$PATCHES_DIR"/*.patch 2>/dev/null || echo "  (No .patch files found, but format-patch may have generated numbered files)"
    ls -la "$PATCHES_DIR"/00*.patch 2>/dev/null || true
else
    echo "✨ No patches needed - all submodules are clean and up to date!"
fi