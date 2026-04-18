#!/bin/bash

set -euo pipefail

maybe_sudo() {
    if "$@" 2>/dev/null; then
        return 0
    fi
    if [ "$(id -u)" = "0" ]; then
        return 1
    fi
    if command -v sudo >/dev/null 2>&1; then
        sudo "$@"
        return $?
    fi
    return 1
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

usage() {
    echo "Usage: $0 [--system|--user] [--prefix DIR] [--package|--binary|--install-kind KIND]"
    echo ""
    echo "Options:"
    echo "  --system        Install to system prefix (/usr/local/bin). Requires root."
    echo "  --user          Install to user prefix (~/.local/bin)."
    echo "  --prefix DIR    Install into DIR (overrides --system/--user)."
    echo "  --package       Install the built wheel into a managed runtime (default on macOS/Linux)."
    echo "  --binary        Install the standalone onefile binary."
    echo "  --install-kind  Explicit install kind: package or binary."
}

INSTALL_MODE="auto"
PREFIX=""
INSTALL_KIND="package"
while [ "${1:-}" != "" ]; do
    case "$1" in
        --system)
            INSTALL_MODE="system"
            shift
            ;;
        --user)
            INSTALL_MODE="user"
            shift
            ;;
        --prefix)
            PREFIX="${2:-}"
            shift 2
            ;;
        --package)
            INSTALL_KIND="package"
            shift
            ;;
        --binary)
            INSTALL_KIND="binary"
            shift
            ;;
        --install-kind)
            INSTALL_KIND="${2:-}"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

PLATFORM="$(detect_platform)"
if [ "$PLATFORM" = "windows" ]; then
    echo "Windows detected. Please use install.ps1 for Windows installs." >&2
    exit 1
fi

EXE_SUFFIX=""
if [ "$PLATFORM" = "windows" ]; then
    EXE_SUFFIX=".exe"
fi

SRC_BIN="out/binary/projman${EXE_SUFFIX}"
WHEEL_PATH=""
if [ -f "out/projman_wheel_path.txt" ]; then
    WHEEL_PATH="$(cat out/projman_wheel_path.txt)"
fi
if [ -z "$WHEEL_PATH" ] || [ ! -f "$WHEEL_PATH" ]; then
    WHEEL_PATH="$(ls -1t out/package/*.whl 2>/dev/null | head -n1 || true)"
fi

case "$INSTALL_KIND" in
    package|binary)
        ;;
    *)
        echo "Invalid install kind: $INSTALL_KIND (expected: package or binary)" >&2
        exit 2
        ;;
esac

if [ "$INSTALL_KIND" = "binary" ] && [ ! -f "$SRC_BIN" ]; then
    echo "$SRC_BIN binary not found. Please run ./build.sh first." >&2
    exit 1
fi
if [ "$INSTALL_KIND" = "package" ] && [ -z "$WHEEL_PATH" ]; then
    echo "No built wheel found under out/package/. Please run ./build.sh first." >&2
    exit 1
fi

if [ -n "$PREFIX" ]; then
    TARGET_BIN="$PREFIX"
else
    case "$INSTALL_MODE" in
        system)
            TARGET_BIN="/usr/local/bin"
            ;;
        user)
            TARGET_BIN="$HOME/.local/bin"
            ;;
        auto)
            if [ "$(id -u)" = "0" ]; then
                TARGET_BIN="/usr/local/bin"
            else
                TARGET_BIN="$HOME/.local/bin"
            fi
            ;;
        *)
            echo "Invalid install mode: $INSTALL_MODE" >&2
            exit 2
            ;;
    esac
fi

TARGET_PROJMAN="$TARGET_BIN/projman${EXE_SUFFIX}"
if [ "$INSTALL_KIND" = "package" ]; then
    echo "--- Installing managed package runtime ($PLATFORM) ---"
    if ! maybe_sudo python3 scripts/install_package.py --wheel "$WHEEL_PATH" --install-dir "$TARGET_BIN" --platform "$PLATFORM"; then
        echo "Failed to install wheel into managed runtime under $TARGET_BIN" >&2
        exit 1
    fi
    echo "Installed launcher to $TARGET_PROJMAN"
else
    echo "--- Installing standalone binary ($PLATFORM) ---"
    if ! maybe_sudo mkdir -p "$TARGET_BIN"; then
        echo "Failed to create install directory: $TARGET_BIN (try --user or run with sudo)" >&2
        exit 1
    fi
    maybe_sudo rm -f "$TARGET_PROJMAN" 2>/dev/null || true
    if ! maybe_sudo cp "$SRC_BIN" "$TARGET_PROJMAN"; then
        echo "Failed to copy binary into $TARGET_BIN (try --user or run with sudo)" >&2
        exit 1
    fi
    maybe_sudo chmod +x "$TARGET_PROJMAN" 2>/dev/null || true
    echo "Installed to $TARGET_PROJMAN"
fi

if [ "$TARGET_BIN" != "/usr/local/bin" ] && ! echo ":$PATH:" | grep -q ":$TARGET_BIN:"; then
    echo "PATH does not include $TARGET_BIN."
    echo "You can add it temporarily with:"
    echo "  export PATH=\"$TARGET_BIN:\$PATH\""
fi

# Test projman command
TMP_DIR="$(mktemp -d 2>/dev/null || mktemp -d -t projman)"
(
    cd "$TMP_DIR"
    "$TARGET_PROJMAN" --version
)
rm -rf "$TMP_DIR" 2>/dev/null || true
echo "projman command executed successfully."
