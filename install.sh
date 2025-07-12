#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

echo "--- Installing standalone binary ---"
if [ ! -f out/binary/mpm ]; then
    echo "out/binary/mpm binary not found. Please build first."
    exit 1
fi
TARGET_BIN="$HOME/.local/bin"
mkdir -p "$TARGET_BIN"
cp out/binary/mpm "$TARGET_BIN/mpm"
chmod +x "$TARGET_BIN/mpm"
echo "Copied mpm to $TARGET_BIN/mpm"
echo "Make sure $TARGET_BIN is in your PATH."
echo "You can temporarily add it with:"
echo "  export PATH=\"$TARGET_BIN:\$PATH\""
echo "Then you can use the mpm command in any terminal."

# Test mpm command
if "$TARGET_BIN/mpm" --version; then
    echo "mpm command executed successfully."
else
    echo "mpm command failed to execute."
fi
