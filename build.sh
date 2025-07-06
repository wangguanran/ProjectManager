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
        --onefile \                    # Package everything into a single executable file
        --strip \                      # Strip debug symbols to reduce file size
        --hidden-import=git \          # Include git module explicitly
        --hidden-import=git.cmd \      # Include git.cmd module explicitly
        --hidden-import=git.repo \     # Include git.repo module explicitly
        --hidden-import=importlib_metadata \  # Include importlib_metadata module explicitly
        --collect-all=git \            # Collect all git-related modules and data
        --collect-all=importlib_metadata \    # Collect all importlib_metadata modules and data
        --add-data "$(pwd)/pyproject.toml:." \  # Include pyproject.toml in the package
        --distpath out \               # Set output directory for the executable
        --workpath out/build \         # Set temporary build directory
        --specpath out \               # Set directory for the .spec file
        -n pm \                        # Set the name of the output executable
        src/project_manager.py         # Main script to package
    
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