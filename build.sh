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

echo -e "\033[32m--- Generating build metadata (git commit hash) ---\033[0m"
python3 scripts/write_build_info.py
cleanup_build_info() {
    rm -f src/_build_info.py
}
trap cleanup_build_info EXIT

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
        --hidden-import=src.plugins.project_manager \
        --hidden-import=src.plugins.project_builder \
        --hidden-import=src.plugins.patch_override \
        --hidden-import=src.operations.registry \
        --hidden-import=src.log_manager \
        --hidden-import=src.profiler \
        --hidden-import=src.utils \
        --hidden-import=src._build_info \
        --collect-all=git \
        --collect-all=importlib_metadata \
        --add-data "$(pwd)/pyproject.toml:." \
        --distpath $BINARY_DIR \
        --workpath $BINARY_DIR/build \
        --specpath $BINARY_DIR \
        -n projman \
        src/__main__.py

echo "Binary generated at $BINARY_DIR/projman"

    # Apply static linking for better compatibility (Linux-only; staticx does not support macOS).
    if [ "$(uname -s)" = "Linux" ]; then
        echo -e "\033[32m--- Applying static linking for better compatibility ---\033[0m"
        # Check if staticx is installed, install if not
        if ! command -v staticx &> /dev/null; then
            echo "staticx not found. Installing for better compatibility..."
            pip install staticx
        fi

        staticx $BINARY_DIR/projman $BINARY_DIR/projman-static
        mv $BINARY_DIR/projman-static $BINARY_DIR/projman
        echo "Static linking applied successfully"
    else
        echo "Skipping staticx (unsupported on $(uname -s))."
    fi

    # Remove debug info to reduce file size.
    # On macOS, stripping invalidates the code signature and can cause the binary to be killed at runtime.
    echo -e "\033[32m--- Final debug info removal ---\033[0m"
    if [ "$(uname -s)" = "Darwin" ]; then
        echo "Skipping external strip on macOS to preserve code signature."
    else
        strip $BINARY_DIR/projman
    fi

echo "Final binary generated at $BINARY_DIR/projman"
else
    echo "pyinstaller not installed, skipping binary packaging. Use 'pip install pyinstaller' to install."
fi

# Clean egg-info in src directory
rm -rf src/*.egg-info

# Show build summary
echo -e "\033[32m--- Build Summary ---\033[0m"
echo "Python packages: $PACKAGE_DIR/"
echo "Binary executable: $BINARY_DIR/projman"
echo "All artifacts: $OUT_DIR/" 
