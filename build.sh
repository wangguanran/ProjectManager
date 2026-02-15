#!/bin/bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

VENV_DIR="${VENV_DIR:-venv}"

detect_platform() {
    local uname_s
    uname_s="$(uname -s 2>/dev/null || echo unknown)"
    case "$uname_s" in
        Linux)
            echo "linux"
            ;;
        Darwin)
            echo "macos"
            ;;
        MINGW*|MSYS*|CYGWIN*|Windows_NT)
            echo "windows"
            ;;
        *)
            echo "unknown"
            ;;
    esac
}

ensure_venv() {
    if [ -n "${VIRTUAL_ENV:-}" ]; then
        echo "Using active virtualenv: $VIRTUAL_ENV"
        return 0
    fi

    if [ ! -d "$VENV_DIR" ]; then
        echo "Virtualenv '$VENV_DIR' not found; running ./setup_venv.sh ..."
        INSTALL_DEPS=0 bash ./setup_venv.sh
    fi

    if [ -f "$VENV_DIR/bin/activate" ]; then
        # shellcheck disable=SC1090
        source "$VENV_DIR/bin/activate"
    elif [ -f "$VENV_DIR/Scripts/activate" ]; then
        # shellcheck disable=SC1090
        source "$VENV_DIR/Scripts/activate"
    else
        echo "Activation script not found under '$VENV_DIR'." >&2
        exit 1
    fi
}

PLATFORM="$(detect_platform)"
ADD_DATA_SEP=":"
EXE_SUFFIX=""
if [ "$PLATFORM" = "windows" ]; then
    ADD_DATA_SEP=";"
    EXE_SUFFIX=".exe"
fi

ensure_venv

python -m pip install -U pip setuptools wheel
python -m pip install -r requirements.txt

# Set output directories
OUT_DIR="out"
PACKAGE_DIR="$OUT_DIR/package"
BINARY_DIR="$OUT_DIR/binary"
mkdir -p "$PACKAGE_DIR" "$BINARY_DIR"

echo -e "\033[32m--- Cleaning up old builds ---\033[0m"
if ! rm -rf build dist .pytest_cache *.egg-info "$OUT_DIR" 2>/dev/null; then
    if command -v sudo >/dev/null 2>&1; then
        echo "Permission denied during cleanup; retrying with sudo..."
        sudo rm -rf build dist .pytest_cache *.egg-info "$OUT_DIR"
    else
        echo "Cleanup failed (permission denied) and sudo is unavailable." >&2
        echo "Please remove build artifacts manually and retry." >&2
        exit 1
    fi
fi
mkdir -p "$PACKAGE_DIR" "$BINARY_DIR"

echo -e "\033[32m--- Generating build metadata (git commit hash) ---\033[0m"
python scripts/write_build_info.py
cleanup_build_info() {
    rm -f src/_build_info.py
}
trap cleanup_build_info EXIT

echo -e "\033[32m--- Building Python package ---\033[0m"
python -m build --outdir "$PACKAGE_DIR"
echo -e "\033[32m--- Python package build complete. Find the artifacts in the '$PACKAGE_DIR' directory. ---\033[0m"

echo -e "\033[32m--- Building standalone binary with pyinstaller ---\033[0m"
PYINSTALLER_STRIP_ARGS=()
if [ "$PLATFORM" = "linux" ] && command -v strip >/dev/null 2>&1; then
    PYINSTALLER_STRIP_ARGS=(--strip)
fi

if ! command -v pyinstaller >/dev/null 2>&1; then
    echo "pyinstaller not found, installing..."
    python -m pip install pyinstaller
fi

IMPORTLIB_METADATA_ARGS=()
if python -c "import importlib_metadata" >/dev/null 2>&1; then
    IMPORTLIB_METADATA_ARGS=(--hidden-import=importlib_metadata --collect-all=importlib_metadata)
fi

PYPROJECT_ABS_PATH="$(python -c 'import os; print(os.path.abspath("pyproject.toml"))')"

pyinstaller \
    --onefile \
    "${PYINSTALLER_STRIP_ARGS[@]}" \
    --hidden-import=git \
    --hidden-import=git.cmd \
    --hidden-import=git.repo \
    --hidden-import=src.plugins.project_manager \
    --hidden-import=src.plugins.project_builder \
    --hidden-import=src.plugins.patch_override \
    --hidden-import=src.plugins.doctor \
    --hidden-import=src.plugins.po_plugins \
    --hidden-import=src.operations.registry \
    --hidden-import=src.log_manager \
    --hidden-import=src.profiler \
    --hidden-import=src.utils \
    --hidden-import=src._build_info \
    "${IMPORTLIB_METADATA_ARGS[@]}" \
    --collect-all=git \
    --add-data "${PYPROJECT_ABS_PATH}${ADD_DATA_SEP}." \
    --distpath "$BINARY_DIR" \
    --workpath "$BINARY_DIR/build" \
    --specpath "$BINARY_DIR" \
    -n projman \
    src/__main__.py

BINARY_PATH="$BINARY_DIR/projman${EXE_SUFFIX}"
if [ ! -f "$BINARY_PATH" ]; then
    echo "Expected binary not found at $BINARY_PATH" >&2
    ls -la "$BINARY_DIR" >&2 || true
    exit 1
fi
echo "$BINARY_PATH" > "$OUT_DIR/projman_binary_path.txt"
echo "Binary generated at $BINARY_PATH"

# Apply static linking for better compatibility (Linux-only; staticx does not support macOS/Windows).
# NOTE: staticx is best-effort. If it fails, keep the non-static binary.
if [ "$PLATFORM" = "linux" ]; then
    echo -e "\033[32m--- Applying static linking for better compatibility ---\033[0m"

    if ! command -v staticx >/dev/null 2>&1; then
        echo "staticx not found. Installing for better compatibility..."
        if ! python -m pip install staticx; then
            echo "staticx install failed; continuing without static linking."
        fi
    fi

    if command -v staticx >/dev/null 2>&1; then
        # staticx depends on pkg_resources, which was removed in newer setuptools.
        if ! python -c "import pkg_resources" >/dev/null 2>&1; then
            echo "pkg_resources not available; installing setuptools<82 for staticx compatibility..."
            python -m pip install "setuptools<82" >/dev/null 2>&1 || true
        fi

        if ! python -c "import pkg_resources" >/dev/null 2>&1; then
            echo "pkg_resources still unavailable; skipping staticx."
        elif staticx "$BINARY_PATH" "$BINARY_DIR/projman-static"; then
            mv "$BINARY_DIR/projman-static" "$BINARY_PATH"
            echo "Static linking applied successfully"
        else
            echo "staticx failed; continuing without static linking."
        fi
    else
        echo "staticx unavailable; continuing without static linking."
    fi
else
    echo "Skipping staticx (unsupported on $PLATFORM)."
fi

# Remove debug info to reduce file size.
# On macOS, stripping invalidates the code signature and can cause the binary to be killed at runtime.
echo -e "\033[32m--- Final debug info removal ---\033[0m"
if [ "$PLATFORM" = "linux" ] && command -v strip >/dev/null 2>&1; then
    strip "$BINARY_PATH"
else
    echo "Skipping external strip on $PLATFORM."
fi

if [ "$PLATFORM" != "windows" ]; then
    chmod 755 "$BINARY_PATH" 2>/dev/null || true
fi

RELEASE_BINARY_DIR="$OUT_DIR/release"
mkdir -p "$RELEASE_BINARY_DIR"
RELEASE_BINARY_PATH="$RELEASE_BINARY_DIR/projman${EXE_SUFFIX}"
cp -L "$BINARY_PATH" "$RELEASE_BINARY_PATH"
echo "$RELEASE_BINARY_PATH" > "$OUT_DIR/projman_binary_path.txt"
if [ "$PLATFORM" != "windows" ]; then
    chmod 755 "$RELEASE_BINARY_PATH" 2>/dev/null || true
fi

echo "Final binary generated at $BINARY_PATH"
echo "Release binary generated at $RELEASE_BINARY_PATH"

# Clean egg-info in src directory
rm -rf src/*.egg-info

# Show build summary
echo -e "\033[32m--- Build Summary ---\033[0m"
echo "Platform: $PLATFORM"
echo "Python packages: $PACKAGE_DIR/"
echo "Binary executable: $BINARY_PATH"
echo "All artifacts: $OUT_DIR/"
