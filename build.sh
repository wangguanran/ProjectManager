#!/bin/bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

VENV_DIR="${VENV_DIR:-venv}"

is_truthy() {
    case "${1:-}" in
        1|true|TRUE|yes|YES|on|ON)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

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

REQUIRE_LINUX_STANDALONE=0
if [ "$PLATFORM" = "linux" ]; then
    REQUIRE_LINUX_STANDALONE=1
    if is_truthy "${PROJMAN_ALLOW_DYNAMIC_BINARY:-0}"; then
        REQUIRE_LINUX_STANDALONE=0
    fi
fi

VERIFY_RELEASE_BINARY=1
if is_truthy "${PROJMAN_SKIP_BINARY_VALIDATION:-0}"; then
    VERIFY_RELEASE_BINARY=0
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

if ! command -v pyinstaller >/dev/null 2>&1; then
    echo "pyinstaller not found, installing..."
    python -m pip install pyinstaller
fi

PYPROJECT_ABS_PATH="$(python -c 'import os; print(os.path.abspath("pyproject.toml"))')"

# NOTE: On macOS default /bin/bash 3.2 with `set -u`, expanding an empty array
# (e.g. "${arr[@]}") errors with "unbound variable". Build args incrementally.
PYINSTALLER_ARGS=(
    --onefile
    --hidden-import=git
    --hidden-import=git.cmd
    --hidden-import=git.repo
    --hidden-import=src.execution_textual
    --hidden-import=src.plugins.project_manager
    --hidden-import=src.plugins.project_builder
    --hidden-import=src.plugins.patch_override
    --hidden-import=src.plugins.doctor
    --hidden-import=src.plugins.snapshot
    --hidden-import=src.plugins.po_plugins
    --hidden-import=src.operations.registry
    --hidden-import=src.log_manager
    --hidden-import=src.profiler
    --hidden-import=src.utils
    --hidden-import=src._build_info
    --collect-all=git
    --collect-all=rich
    --collect-all=textual
    --add-data "${PYPROJECT_ABS_PATH}${ADD_DATA_SEP}."
    --distpath "$BINARY_DIR"
    --workpath "$BINARY_DIR/build"
    --specpath "$BINARY_DIR"
    -n projman
)

if [ "$PLATFORM" = "linux" ] && command -v strip >/dev/null 2>&1; then
    PYINSTALLER_ARGS+=(--strip)
fi

if python -c "import importlib_metadata" >/dev/null 2>&1; then
    PYINSTALLER_ARGS+=(--hidden-import=importlib_metadata --collect-all=importlib_metadata)
fi

PYINSTALLER_ARGS+=(src/__main__.py)

pyinstaller "${PYINSTALLER_ARGS[@]}"

BINARY_PATH="$BINARY_DIR/projman${EXE_SUFFIX}"
if [ ! -f "$BINARY_PATH" ]; then
    echo "Expected binary not found at $BINARY_PATH" >&2
    ls -la "$BINARY_DIR" >&2 || true
    exit 1
fi
echo "$BINARY_PATH" > "$OUT_DIR/projman_binary_path.txt"
echo "Binary generated at $BINARY_PATH"

# Apply staticx bundling for Linux standalone compatibility.
if [ "$PLATFORM" = "linux" ]; then
    echo -e "\033[32m--- Building Linux standalone binary ---\033[0m"

    if ! command -v patchelf >/dev/null 2>&1; then
        echo "patchelf is required for Linux standalone binaries." >&2
        if [ "$REQUIRE_LINUX_STANDALONE" -eq 1 ]; then
            exit 1
        fi
        echo "Continuing because PROJMAN_ALLOW_DYNAMIC_BINARY is enabled."
    fi

    if ! command -v staticx >/dev/null 2>&1; then
        echo "staticx not found. Installing..."
        if ! python -m pip install staticx; then
            echo "staticx install failed." >&2
            if [ "$REQUIRE_LINUX_STANDALONE" -eq 1 ]; then
                exit 1
            fi
            echo "Continuing because PROJMAN_ALLOW_DYNAMIC_BINARY is enabled."
        fi
    fi

    if command -v patchelf >/dev/null 2>&1 && command -v staticx >/dev/null 2>&1; then
        # staticx depends on pkg_resources, which was removed in newer setuptools.
        if ! python -c "import pkg_resources" >/dev/null 2>&1; then
            echo "pkg_resources not available; installing setuptools<82 for staticx compatibility..."
            python -m pip install "setuptools<82" >/dev/null 2>&1 || true
        fi

        if ! python -c "import pkg_resources" >/dev/null 2>&1; then
            echo "pkg_resources still unavailable after installing setuptools<82." >&2
            if [ "$REQUIRE_LINUX_STANDALONE" -eq 1 ]; then
                exit 1
            fi
            echo "Continuing because PROJMAN_ALLOW_DYNAMIC_BINARY is enabled."
        elif staticx "$BINARY_PATH" "$BINARY_DIR/projman-static"; then
            mv "$BINARY_DIR/projman-static" "$BINARY_PATH"
            echo "Standalone wrapping applied successfully"
        else
            echo "staticx failed." >&2
            if [ "$REQUIRE_LINUX_STANDALONE" -eq 1 ]; then
                exit 1
            fi
            echo "Continuing because PROJMAN_ALLOW_DYNAMIC_BINARY is enabled."
        fi
    else
        echo "staticx or patchelf unavailable." >&2
        if [ "$REQUIRE_LINUX_STANDALONE" -eq 1 ]; then
            exit 1
        fi
        echo "Continuing because PROJMAN_ALLOW_DYNAMIC_BINARY is enabled."
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

if [ "$VERIFY_RELEASE_BINARY" -eq 1 ]; then
    echo -e "\033[32m--- Verifying release binary ---\033[0m"
    python scripts/check_linux_standalone_binary.py "$BINARY_PATH"
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
