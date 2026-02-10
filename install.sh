#!/bin/bash

set -euo pipefail

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
    echo "Usage: $0 [--system|--user] [--prefix DIR]"
    echo ""
    echo "Options:"
    echo "  --system        Install to system prefix (/usr/local/bin). Requires root."
    echo "  --user          Install to user prefix (~/.local/bin)."
    echo "  --prefix DIR    Install into DIR (overrides --system/--user)."
}

INSTALL_MODE="auto"
PREFIX=""
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
if [ ! -f "$SRC_BIN" ]; then
    echo "$SRC_BIN binary not found. Please run ./build.sh first." >&2
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

echo "--- Installing standalone binary ($PLATFORM) ---"
mkdir -p "$TARGET_BIN"
rm -f "$TARGET_BIN/projman${EXE_SUFFIX}" 2>/dev/null || true
cp "$SRC_BIN" "$TARGET_BIN/projman${EXE_SUFFIX}"
chmod +x "$TARGET_BIN/projman${EXE_SUFFIX}" 2>/dev/null || true
echo "Installed to $TARGET_BIN/projman${EXE_SUFFIX}"

if [ "$TARGET_BIN" != "/usr/local/bin" ] && ! echo ":$PATH:" | grep -q ":$TARGET_BIN:"; then
    echo "PATH does not include $TARGET_BIN."
    echo "You can add it temporarily with:"
    echo "  export PATH=\"$TARGET_BIN:\$PATH\""
fi

# Test projman command
"$TARGET_BIN/projman${EXE_SUFFIX}" --version
echo "projman command executed successfully."
