#!/bin/bash
# Script to create a local venv and install dependencies.
#
# Notes:
# - This script is intended to be cross-platform (Linux/macOS/Windows Git Bash).
# - It does not attempt to install system packages (no sudo).

set -euo pipefail

VENV_DIR="${VENV_DIR:-venv}"
INSTALL_DEPS="${INSTALL_DEPS:-1}"

PYTHON=""
if command -v python3 >/dev/null 2>&1; then
    PYTHON="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON="python"
else
    echo "python not found. Please install Python 3 first." >&2
    exit 1
fi

# 3. Create virtual environment
if [ ! -d "$VENV_DIR" ]; then
    "$PYTHON" -m venv "$VENV_DIR"
    echo "Virtual environment '$VENV_DIR' created."
else
    echo "Virtual environment '$VENV_DIR' already exists. Skipping creation."
fi

# 4. Activate virtual environment and install dependencies
if [ -f "$VENV_DIR/bin/activate" ]; then
    # Linux/macOS
    # shellcheck disable=SC1090
    source "$VENV_DIR/bin/activate"
elif [ -f "$VENV_DIR/Scripts/activate" ]; then
    # Windows (Git Bash)
    # shellcheck disable=SC1090
    source "$VENV_DIR/Scripts/activate"
else
    echo "Activation script not found under '$VENV_DIR'. venv creation may have failed." >&2
    exit 1
fi

python -m pip install -U pip setuptools wheel
if [ "$INSTALL_DEPS" = "1" ] && [ -f "requirements.txt" ]; then
    python -m pip install -r requirements.txt
    echo "Dependencies installed."
else
    echo "Skipping dependency installation."
fi

echo "Done!"
