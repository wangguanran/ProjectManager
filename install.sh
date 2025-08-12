#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

echo "--- Installing standalone binary ---"
if [ ! -f out/binary/projctl ]; then
    echo "out/binary/projctl binary not found. Please build first."
    exit 1
fi
TARGET_BIN="$HOME/.local/bin"
mkdir -p "$TARGET_BIN"
cp out/binary/projctl "$TARGET_BIN/projctl"
chmod +x "$TARGET_BIN/projctl"
echo "Copied projctl to $TARGET_BIN/projctl"
echo "Make sure $TARGET_BIN is in your PATH."
echo "You can temporarily add it with:"
echo "  export PATH=\"$TARGET_BIN:\$PATH\""
echo "Then you can use the projctl command in any terminal."

# Test projctl command
if "$TARGET_BIN/projctl" --version; then
    echo "projctl command executed successfully."
else
    echo "projctl command failed to execute."
fi
