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
        return 0
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
    echo "Usage: $0 [--system|--user] [--prefix DIR] [--standalone]"
    echo ""
    echo "Options:"
    echo "  --system        Install to system prefix (/usr/local/bin). Requires root."
    echo "  --user          Install to user prefix (~/.local/bin)."
    echo "  --prefix DIR    Install into DIR (overrides --system/--user)."
    echo "  --standalone    Install the standalone binary from out/release or out/binary."
}

INSTALL_MODE="auto"
PREFIX=""
INSTALL_STANDALONE="0"
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
        --standalone)
            INSTALL_STANDALONE="1"
            shift
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

if ! maybe_sudo mkdir -p "$TARGET_BIN"; then
    echo "Failed to create install directory: $TARGET_BIN (try --user or run with sudo)" >&2
    exit 1
fi

if [ -d "$TARGET_BIN" ]; then
    TARGET_BIN="$(cd "$TARGET_BIN" && pwd)"
fi

install_standalone() {
    local src_bin
    src_bin="out/release/projman${EXE_SUFFIX}"
    if [ ! -f "$src_bin" ]; then
        src_bin="out/binary/projman${EXE_SUFFIX}"
    fi
    if [ ! -f "$src_bin" ]; then
        echo "projman binary not found under out/release/ or out/binary/. Please run ./build.sh --standalone first." >&2
        exit 1
    fi

    echo "--- Installing standalone binary ($PLATFORM) ---"
    maybe_sudo rm -f "$TARGET_BIN/projman${EXE_SUFFIX}" 2>/dev/null || true
    if ! maybe_sudo cp "$src_bin" "$TARGET_BIN/projman${EXE_SUFFIX}"; then
        echo "Failed to copy binary into $TARGET_BIN (try --user or run with sudo)" >&2
        exit 1
    fi
    maybe_sudo chmod +x "$TARGET_BIN/projman${EXE_SUFFIX}" 2>/dev/null || true
    echo "Installed to $TARGET_BIN/projman${EXE_SUFFIX}"
}

install_package() {
    local wheel_path venv_path venv_python venv_projman tmp_wrapper

    if ! ls out/package/*.whl >/dev/null 2>&1; then
        echo "Python package wheel not found under out/package/. Running ./build.sh ..."
        bash ./build.sh
    fi

    wheel_path="$(ls -t out/package/*.whl | head -n1)"
    if [ -z "$wheel_path" ] || [ ! -f "$wheel_path" ]; then
        echo "Python package wheel not found under out/package/." >&2
        exit 1
    fi

    if [ -n "${PROJMAN_INSTALL_VENV:-}" ]; then
        venv_path="$PROJMAN_INSTALL_VENV"
    elif [ -n "$PREFIX" ]; then
        venv_path="$TARGET_BIN/.projman-venv"
    elif [ "$TARGET_BIN" = "/usr/local/bin" ]; then
        venv_path="/usr/local/share/projman/venv"
    else
        venv_path="$HOME/.local/share/projman/venv"
    fi

    echo "--- Installing Python package ($PLATFORM) ---"
    if [ ! -x "$venv_path/bin/python" ]; then
        if ! maybe_sudo python3 -m venv "$venv_path"; then
            echo "Failed to create virtual environment: $venv_path" >&2
            exit 1
        fi
    fi

    venv_python="$venv_path/bin/python"
    venv_projman="$venv_path/bin/projman"
    if ! maybe_sudo "$venv_python" -m pip install -U pip; then
        echo "Failed to upgrade pip in $venv_path" >&2
        exit 1
    fi
    if ! maybe_sudo "$venv_python" -m pip install --force-reinstall "$wheel_path"; then
        echo "Failed to install package wheel: $wheel_path" >&2
        exit 1
    fi
    if [ ! -x "$venv_projman" ]; then
        echo "Installed console script not found: $venv_projman" >&2
        exit 1
    fi

    tmp_wrapper="$(mktemp 2>/dev/null || mktemp -t projman-wrapper)"
    printf '%s\n' "#!/bin/sh" "exec \"$venv_projman\" \"\$@\"" > "$tmp_wrapper"
    chmod +x "$tmp_wrapper"
    maybe_sudo rm -f "$TARGET_BIN/projman${EXE_SUFFIX}" 2>/dev/null || true
    if ! maybe_sudo cp "$tmp_wrapper" "$TARGET_BIN/projman${EXE_SUFFIX}"; then
        rm -f "$tmp_wrapper" 2>/dev/null || true
        echo "Failed to install wrapper into $TARGET_BIN (try --user or run with sudo)" >&2
        exit 1
    fi
    rm -f "$tmp_wrapper" 2>/dev/null || true
    maybe_sudo chmod +x "$TARGET_BIN/projman${EXE_SUFFIX}" 2>/dev/null || true
    echo "Installed package console script to $TARGET_BIN/projman${EXE_SUFFIX}"
    echo "Virtual environment: $venv_path"
}

if [ "$INSTALL_STANDALONE" = "1" ]; then
    install_standalone
else
    install_package
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
    "$TARGET_BIN/projman${EXE_SUFFIX}" --version
)
rm -rf "$TMP_DIR" 2>/dev/null || true
echo "projman command executed successfully."
