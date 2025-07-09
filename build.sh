#!/bin/bash

# Set output directories
OUT_DIR="out"
PACKAGE_DIR="$OUT_DIR/package"
BINARY_DIR="$OUT_DIR/binary"
mkdir -p $PACKAGE_DIR $BINARY_DIR

# Exit immediately if a command exits with a non-zero status.
set -e

# Check pyinstaller
if ! command -v pyinstaller &> /dev/null; then
    echo "pyinstaller not found, installing..."
    pip install pyinstaller
fi

echo -e "\033[32m--- Cleaning up old builds ---\033[0m"
rm -rf build dist *.egg-info $OUT_DIR
mkdir -p $PACKAGE_DIR $BINARY_DIR

echo -e "\033[32m--- Building Python package ---\033[0m"
python3 -m build --outdir $PACKAGE_DIR

echo -e "\033[32m--- Python package build complete. Find the artifacts in the '$PACKAGE_DIR' directory. ---\033[0m"

# Generate standalone binary (requires pyinstaller)
if command -v pyinstaller &> /dev/null; then
    echo -e "\033[32m--- Building standalone binary with pyinstaller ---\033[0m"

    # Use more compatible configuration options
    pyinstaller \
        --onefile \
        --strip \
        --hidden-import=git \
        --hidden-import=git.cmd \
        --hidden-import=git.repo \
        --hidden-import=importlib_metadata \
        --collect-all=git \
        --collect-all=importlib_metadata \
        --add-data "$(pwd)/pyproject.toml:." \
        --distpath $BINARY_DIR \
        --workpath $BINARY_DIR/build \
        --specpath $BINARY_DIR \
        -n pm \
        src/__main__.py

    echo "Binary generated at $BINARY_DIR/pm"

    # Apply static linking for better compatibility
    echo -e "\033[32m--- Applying static linking for better compatibility ---\033[0m"
    # Check if staticx is installed, install if not
    if ! command -v staticx &> /dev/null; then
        echo "staticx not found. Installing for better compatibility..."
        pip install staticx
    fi

    staticx $BINARY_DIR/pm $BINARY_DIR/pm-static
    mv $BINARY_DIR/pm-static $BINARY_DIR/pm
    echo "Static linking applied successfully"

    # Remove debug info to reduce file size
    echo -e "\033[32m--- Final debug info removal ---\033[0m"
    strip $BINARY_DIR/pm

    echo "Final binary generated at $BINARY_DIR/pm"
else
    echo "pyinstaller not installed, skipping binary packaging. Use 'pip install pyinstaller' to install."
fi

# Clean egg-info in src directory
rm -rf src/*.egg-info

# Show build summary
echo -e "\033[32m--- Build Summary ---\033[0m"
echo "Python packages: $PACKAGE_DIR/"
echo "Binary executable: $BINARY_DIR/pm"
echo "All artifacts: $OUT_DIR/" 