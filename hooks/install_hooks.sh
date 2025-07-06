#!/bin/bash

# Script to install git hooks for the project

set -e

echo "Installing git hooks..."

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "Error: Not in a git repository"
    exit 1
fi

# Make sure hooks directory exists
mkdir -p .git/hooks

# Install pre-push hook
if [ -f ".git/hooks/pre-push" ]; then
    echo "Pre-push hook already exists. Overwriting..."
fi

# Copy the pre-push hook from hooks directory
if [ -f "hooks/pre-push" ]; then
    cp hooks/pre-push .git/hooks/pre-push
    echo "Pre-push hook copied from hooks/pre-push"
else
    echo "Error: hooks/pre-push not found"
    exit 1
fi

# Make it executable
chmod +x .git/hooks/pre-push

echo "Git hooks installed successfully!"
echo ""
echo "The pre-push hook will now run:"
echo "  - Pylint code quality checks"
echo "  - Pytest unit tests"
echo ""
echo "These checks will run automatically before every git push."
echo "If you need to bypass the hook temporarily, use: git push --no-verify" 