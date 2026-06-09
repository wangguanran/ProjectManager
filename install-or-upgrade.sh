#!/usr/bin/env bash

set -euo pipefail

DEFAULT_STANDALONE_INSTALLER_URL="https://raw.githubusercontent.com/wangguanran/ProjectManager/main/get_latest_release.sh"
STANDALONE=0
DRY_RUN=0
ARGS=()

while [ "${1:-}" != "" ]; do
    case "$1" in
        --standalone)
            STANDALONE=1
            shift
            ;;
        --dry-run)
            DRY_RUN=1
            shift
            ;;
        *)
            ARGS+=("$1")
            shift
            ;;
    esac
done

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
    if dir="$(script_dir 2>/dev/null)"; then
        if [ "$STANDALONE" = "1" ] && [ -f "$dir/get_latest_release.sh" ]; then
            exec bash "$dir/get_latest_release.sh" "$@"
        fi
        if [ "$STANDALONE" != "1" ] && [ -f "$dir/install.sh" ]; then
            exec bash "$dir/install.sh" "$@"
        fi
    fi

    if [ "$STANDALONE" != "1" ]; then
        echo "Error: default package install requires a source checkout with install.sh." >&2
        echo "Set PROJECTMANAGER_BOOTSTRAP_INSTALLER to an explicit package installer if needed." >&2
        exit 1
    fi

    local installer_url="${PROJECTMANAGER_BOOTSTRAP_INSTALLER_URL:-$DEFAULT_STANDALONE_INSTALLER_URL}"
    if ! command -v curl >/dev/null 2>&1; then
        echo "Error: curl is required to download the ProjectManager installer." >&2
        exit 1
    fi
    curl -fsSL "$installer_url" | bash -s -- "$@"
}

reject_default_release_channel_args() {
    local arg
    for arg in "${ARGS[@]}"; do
        case "$arg" in
            --stable|--beta)
                echo "Error: $arg is only supported with --standalone." >&2
                echo "Default package installs use install.sh; omit release channel options or add --standalone." >&2
                exit 2
                ;;
        esac
    done
}

main() {
    if [ "$STANDALONE" != "1" ]; then
        reject_default_release_channel_args
    fi

    if [ "$DRY_RUN" = "1" ] && [ "$STANDALONE" != "1" ]; then
        echo "DRY-RUN: default package/venv install is active."
        echo "DRY-RUN: would run install.sh ${ARGS[*]}"
        return 0
    fi

    if [ "$STANDALONE" = "1" ] && command -v projman >/dev/null 2>&1; then
        echo "projman found: $(command -v projman)"
        if [ "$DRY_RUN" = "1" ]; then
            echo "Upgrading standalone binary with: projman update --standalone --dry-run ${ARGS[*]}"
            exec projman update --standalone --dry-run "${ARGS[@]}"
        fi
        echo "Upgrading standalone binary with: projman update --standalone ${ARGS[*]}"
        exec projman update --standalone "${ARGS[@]}"
    fi

    if [ "$STANDALONE" = "1" ]; then
        if [ "$DRY_RUN" = "1" ]; then
            echo "DRY-RUN: would install latest standalone ProjectManager release."
            return 0
        fi
        echo "projman not found; installing latest standalone ProjectManager release."
    else
        echo "Installing or upgrading ProjectManager with the package installer."
    fi
    run_installer "${ARGS[@]}"
}

main
