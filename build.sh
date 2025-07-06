#!/bin/bash

# Set output directory
OUT_DIR="out"
mkdir -p $OUT_DIR

# Exit immediately if a command exits with a non-zero status.
set -e

# Check pyinstaller
if ! command -v pyinstaller &> /dev/null; then
    echo "pyinstaller not found, installing..."
    pip install pyinstaller
fi

echo "--- Cleaning up old builds ---"
rm -rf build dist *.egg-info $OUT_DIR
mkdir -p $OUT_DIR

echo "--- Building package ---"
python3 -m build --outdir $OUT_DIR

echo "--- Build complete. Find the artifacts in the 'out' directory. ---"

# Generate standalone binary (requires pyinstaller)
if command -v pyinstaller &> /dev/null; then
    echo "--- Building standalone binary with pyinstaller ---"
    
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
        --distpath out \
        --workpath out/build \
        --specpath out \
        -n pm \
        src/project_manager.py
    
    echo "Binary generated at out/pm"
    
    # Apply static linking for better compatibility
    echo "--- Applying static linking for better compatibility ---"
    # Check if staticx is installed, install if not
    if ! command -v staticx &> /dev/null; then
        echo "staticx not found. Installing for better compatibility..."
        pip install staticx
    fi
    # Check if patchelf is installed, install if not
    if ! command -v patchelf &> /dev/null; then
        echo "patchelf not found. Installing..."
        sudo apt-get update && sudo apt-get install -y patchelf
    fi
    echo "--- Cleaning RPATH/RUNPATH tags before static linking ---"
    find out/ -name "*.so*" -type f -exec patchelf --remove-rpath {} \; 2>/dev/null || true
    patchelf --remove-rpath out/pm 2>/dev/null || true
    echo "RPATH/RUNPATH tags cleaned"
    staticx out/pm out/pm-static
    mv out/pm-static out/pm
    echo "Static linking applied successfully"
    
    # Remove debug info to reduce file size
    echo "--- Final debug info removal ---"
    strip out/pm
    
    echo "Final binary generated at out/pm with static linking"
else
    echo "pyinstaller not installed, skipping binary packaging. Use 'pip install pyinstaller' to install."
fi

# Clean egg-info in src directory
rm -rf src/*.egg-info 