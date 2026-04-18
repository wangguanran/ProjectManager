#!/bin/bash

set -euo pipefail

maybe_sudo() {
    if "$@" 2>/dev/null; then
        return 0
    fi
    if [ "$(id -u)" = "0" ]; then
        return 1
    fi
    if command -v sudo >/dev/null 2>&1; then
        sudo "$@"
        return $?
    fi
    return 1
}

echo "--- Checking if multi-project-manager is installed ---"

# Uninstall from system environment (pip)
if command -v pip3 &> /dev/null; then
    echo "Uninstalling multi-project-manager from system environment (pip)..."
pip3 uninstall -y multi-project-manager || true
fi

# Remove standalone binary from ~/.local/bin
USER_BIN="$HOME/.local/bin/projman"
SYSTEM_BIN="/usr/local/bin/projman"
USER_RUNTIME="$HOME/.local/lib/projman"
SYSTEM_RUNTIME="/usr/local/lib/projman"
if [ -f "$USER_BIN" ]; then
    echo "Removing projman launcher/binary: $USER_BIN"
    rm -f "$USER_BIN"
fi
if [ -f "$SYSTEM_BIN" ]; then
    echo "Removing projman launcher/binary: $SYSTEM_BIN"
    maybe_sudo rm -f "$SYSTEM_BIN"
fi
if [ -d "$USER_RUNTIME" ]; then
    echo "Removing managed runtime: $USER_RUNTIME"
    rm -rf "$USER_RUNTIME"
fi
if [ -d "$SYSTEM_RUNTIME" ]; then
    echo "Removing managed runtime: $SYSTEM_RUNTIME"
    maybe_sudo rm -rf "$SYSTEM_RUNTIME"
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
