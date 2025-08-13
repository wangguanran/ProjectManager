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

# Copy all hook files from hooks directory
for hook_file in git-hooks/*; do
    if [ -f "$hook_file" ]; then
        hook_name=$(basename "$hook_file")
        
        # Skip non-hook files
        if [ "$hook_name" = "install_hooks.sh" ] || [ "$hook_name" = "README.md" ]; then
            continue
        fi
        
        if [ -f ".git/hooks/$hook_name" ]; then
            echo "Hook $hook_name already exists. Overwriting..."
        fi
        
        cp "$hook_file" ".git/hooks/$hook_name"
        chmod +x ".git/hooks/$hook_name"
        echo "Hook $hook_name copied and made executable"
    fi
done

echo "Git hooks installed successfully!"
echo ""
echo "The following hooks are now active:"
for hook_file in git-hooks/*; do
    if [ -f "$hook_file" ]; then
        hook_name=$(basename "$hook_file")
        if [ "$hook_name" != "install_hooks.sh" ] && [ "$hook_name" != "README.md" ]; then
            echo "  - $hook_name"
        fi
    fi
done
echo ""
echo "These hooks will run automatically before/after git operations."
echo "If you need to bypass hooks temporarily, use: git --no-verify" 