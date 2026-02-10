#!/bin/bash

set -euo pipefail

echo "--- Checking if multi-project-manager is installed ---"

# Uninstall from system environment (pip)
if command -v pip3 &> /dev/null; then
    echo "Uninstalling multi-project-manager from system environment (pip)..."
pip3 uninstall -y multi-project-manager || true
fi

# Remove standalone binary from ~/.local/bin
USER_BIN="$HOME/.local/bin/projman"
SYSTEM_BIN="/usr/local/bin/projman"
if [ -f "$USER_BIN" ]; then
    echo "Removing standalone binary: $USER_BIN"
    rm -f "$USER_BIN"
fi
if [ -f "$SYSTEM_BIN" ]; then
    echo "Removing standalone binary: $SYSTEM_BIN"
    rm -f "$SYSTEM_BIN"
fi

# Remove venv directory and run_projman.sh script
if [ -d "venv" ]; then
    echo "Removing venv directory..."
    rm -rf venv
fi
if [ -f "run_projman.sh" ]; then
    echo "Removing run_projman.sh script..."
    rm -f run_projman.sh
fi

echo "Uninstallation complete." 
