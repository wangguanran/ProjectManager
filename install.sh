#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

echo "--- Installing standalone binary ---"
if [ ! -f out/binary/pm ]; then
    echo "out/binary/pm binary not found. Please build first."
    exit 1
fi
TARGET_BIN="$HOME/.local/bin"
mkdir -p "$TARGET_BIN"
cp out/binary/pm "$TARGET_BIN/pm"
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
