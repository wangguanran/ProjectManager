#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

echo "--- Checking if multi-project-manager is installed ---"

# Uninstall from system environment (pip)
if command -v pip3 &> /dev/null; then
    echo "Uninstalling multi-project-manager from system environment (pip)..."
pip3 uninstall -y multi-project-manager || true
fi

# Remove standalone binary from ~/.local/bin
TARGET_BIN="$HOME/.local/bin/mpm"
if [ -f "$TARGET_BIN" ]; then
    echo "Removing standalone binary: $TARGET_BIN"
    rm -f "$TARGET_BIN"
fi

# Remove venv directory and run_mpm.sh script
if [ -d "venv" ]; then
    echo "Removing venv directory..."
    rm -rf venv
fi
if [ -f "run_mpm.sh" ]; then
    echo "Removing run_mpm.sh script..."
    rm -f run_mpm.sh
fi

echo "Uninstallation complete." 