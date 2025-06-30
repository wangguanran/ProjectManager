#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

echo "--- Installing standalone binary ---"
if [ ! -f out/pm ]; then
    echo "out/pm binary not found. Please build first."
    exit 1
fi
TARGET_BIN="$HOME/.local/bin"
mkdir -p "$TARGET_BIN"
cp out/pm "$TARGET_BIN/pm"
chmod +x "$TARGET_BIN/pm"
echo "Copied pm to $TARGET_BIN/pm"
echo "Make sure $TARGET_BIN is in your PATH."
echo "You can temporarily add it with:"
echo "  export PATH=\"$TARGET_BIN:\$PATH\""
echo "Then you can use the pm command in any terminal."

# Test pm command
if "$TARGET_BIN/pm" --version; then
    echo "pm command executed successfully."
else
    echo "pm command failed to execute."
    exit 1
fi

# Test pm command version
EXPECTED_VERSION=$(grep '^version' pyproject.toml | head -n1 | cut -d '"' -f2)
PM_VERSION=$("$TARGET_BIN/pm" --version 2>/dev/null)
if [ "$PM_VERSION" = "$EXPECTED_VERSION" ]; then
    echo -e "\033[32mpm version matched: $PM_VERSION\033[0m"
else
    echo -e "\033[31mError: pm version mismatch! Expected $EXPECTED_VERSION, got $PM_VERSION\033[0m"
    exit 1
fi 