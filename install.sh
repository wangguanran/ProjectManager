#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

echo "--- Installing standalone binary ---"
if [ ! -f out/binary/projman ]; then
    echo "out/binary/projman binary not found. Please build first."
    exit 1
fi
TARGET_BIN="$HOME/.local/bin"
mkdir -p "$TARGET_BIN"
rm -f "$TARGET_BIN/projman" 2>/dev/null || true
cp out/binary/projman "$TARGET_BIN/projman"
chmod +x "$TARGET_BIN/projman"
echo "Copied projman to $TARGET_BIN/projman"
echo "Make sure $TARGET_BIN is in your PATH."
echo "You can temporarily add it with:"
echo "  export PATH=\"$TARGET_BIN:\$PATH\""
echo "Then you can use the projman command in any terminal."

# Test projman command
if "$TARGET_BIN/projman" --version; then
    echo "projman command executed successfully."
else
    echo "projman command failed to execute."
fi
