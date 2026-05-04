#!/usr/bin/env bash

set -euo pipefail

DEFAULT_INSTALLER_URL="https://raw.githubusercontent.com/wangguanran/ProjectManager/main/get_latest_release.sh"

script_dir() {
    local source_path="${BASH_SOURCE[0]:-}"
    if [ -n "$source_path" ] && [ -f "$source_path" ]; then
        cd "$(dirname "$source_path")" && pwd
        return 0
    fi
    return 1
}

run_installer() {
    if [ -n "${PROJECTMANAGER_BOOTSTRAP_INSTALLER:-}" ]; then
        exec bash "$PROJECTMANAGER_BOOTSTRAP_INSTALLER" "$@"
    fi

    local dir=""
    if dir="$(script_dir 2>/dev/null)" && [ -f "$dir/get_latest_release.sh" ]; then
        exec bash "$dir/get_latest_release.sh" "$@"
    fi

    local installer_url="${PROJECTMANAGER_BOOTSTRAP_INSTALLER_URL:-$DEFAULT_INSTALLER_URL}"
    if ! command -v curl >/dev/null 2>&1; then
        echo "Error: curl is required to download the ProjectManager installer." >&2
        exit 1
    fi
    curl -fsSL "$installer_url" | bash -s -- "$@"
}

main() {
    if command -v projman >/dev/null 2>&1; then
        echo "projman found: $(command -v projman)"
        echo "Upgrading with: projman update $*"
        exec projman update "$@"
    fi

    echo "projman not found; installing latest ProjectManager release."
    run_installer "$@"
}

main "$@"
