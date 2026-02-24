#!/bin/bash
# Script to fetch the latest version from GitHub releases

set -euo pipefail

# Default values
REPO_OWNER="wangguanran"
REPO_NAME="ProjectManager"
GITHUB_API_BASE="https://api.github.com"
GITHUB_TOKEN="${GITHUB_TOKEN:-${GH_TOKEN:-}}"
TOKEN_SOURCE="env" # env|argv
VERSION_ONLY=false
VERIFY_DOWNLOADS=true

# 准备用户本地 bin 目录并加入 PATH（本次会话内生效）
BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"
export PATH="$BIN_DIR:$PATH"

# Install target (projman)
INSTALL_MODE="auto"  # auto|system|user
INSTALL_PREFIX=""

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

# Function to display usage
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo "Options:"
    echo "  -o, --owner OWNER    GitHub repository owner (default: wangguanran)"
    echo "  -r, --repo REPO      GitHub repository name (default: ProjectManager)"
    echo "  -t, --token TOKEN    GitHub token (discouraged; prefer env GITHUB_TOKEN/GH_TOKEN)"
    echo "      --no-verify      Skip checksum verification (insecure; not recommended)"
    echo "      --system         Install to /usr/local/bin (requires root)"
    echo "      --user           Install to ~/.local/bin"
    echo "      --prefix DIR     Install to DIR (overrides --system/--user)"
    echo "  -v, --version-only   Output only the version number"
    echo "  -h, --help           Display this help message"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Get latest release for default repo"
    echo "  $0 -o octocat -r Hello-World         # Get latest release for specific repo"
    echo "  $0 -v                                 # Output only version number"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -o|--owner)
            REPO_OWNER="$2"
            shift 2
            ;;
        -r|--repo)
            REPO_NAME="$2"
            shift 2
            ;;
        -t|--token)
            GITHUB_TOKEN="$2"
            TOKEN_SOURCE="argv"
            shift 2
            ;;
        --no-verify)
            VERIFY_DOWNLOADS=false
            shift
            ;;
        --system)
            INSTALL_MODE="system"
            shift
            ;;
        --user)
            INSTALL_MODE="user"
            shift
            ;;
        --prefix)
            INSTALL_PREFIX="$2"
            shift 2
            ;;
        -v|--version-only)
            VERSION_ONLY=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

warn_if_token_from_argv() {
    if [ "$TOKEN_SOURCE" = "argv" ] && [ -n "$GITHUB_TOKEN" ]; then
        echo "Warning: --token provided via argv; prefer env GITHUB_TOKEN/GH_TOKEN to avoid leaking secrets via shell history/process listing." >&2
    fi
}

require_cmd() {
    local name="$1"
    if ! command -v "$name" >/dev/null 2>&1; then
        echo "Error: required command not found: $name" >&2
        return 1
    fi
}

sha256_file() {
    local path="$1"
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$path" | awk '{print $1}'
        return 0
    fi
    if command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$path" | awk '{print $1}'
        return 0
    fi
    echo "Error: sha256sum/shasum not found; cannot verify downloads." >&2
    return 1
}

verify_binary_candidate() {
    local path="$1"
    local output_file
    output_file="$(mktemp)"
    if "$path" --version >"$output_file" 2>&1; then
        local first_line
        first_line="$(head -n1 "$output_file" || true)"
        rm -f "$output_file" 2>/dev/null || true
        if [ -n "$first_line" ]; then
            echo "Binary self-check passed: $first_line"
        else
            echo "Binary self-check passed."
        fi
        return 0
    fi
    echo "Error: downloaded projman binary failed self-check on this system." >&2
    sed -n '1,3p' "$output_file" >&2 || true
    rm -f "$output_file" 2>/dev/null || true
    echo "Tip: this host may be incompatible with the release binary (for example: glibc mismatch)." >&2
    echo "Tip: install Python package instead: python3 -m pip install --user -U multi-project-manager" >&2
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

detect_arch() {
    local arch
    arch="$(uname -m 2>/dev/null || echo unknown)"
    case "$arch" in
        x86_64|amd64)
            echo "x86_64"
            ;;
        aarch64|arm64)
            echo "arm64"
            ;;
        *)
            echo "$arch"
            ;;
    esac
}

is_checksum_asset_name() {
    local name="${1:-}"
    case "$name" in
        *.sha256|*.sha256.txt)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

resolve_install_dir() {
    local mode="$1"
    local prefix="$2"
    if [ -n "$prefix" ]; then
        echo "$prefix"
        return 0
    fi

    case "$mode" in
        system)
            echo "/usr/local/bin"
            ;;
        user)
            echo "$HOME/.local/bin"
            ;;
        auto)
            if [ "$(id -u)" = "0" ]; then
                echo "/usr/local/bin"
            else
                echo "$HOME/.local/bin"
            fi
            ;;
        *)
            echo "$HOME/.local/bin"
            ;;
    esac
}

# Function to check if curl is available
check_curl() {
    if ! command -v curl &> /dev/null; then
        echo "Error: curl is not installed. Please install curl first."
        exit 1
    fi
}

# Function to check if jq is available
check_jq() {
    if ! command -v jq &> /dev/null; then
        local platform arch url=""
        local sha_url="https://github.com/jqlang/jq/releases/download/jq-1.7.1/sha256sum.txt"
        platform="$(detect_platform)"
        arch="$(detect_arch)"
        case "$platform-$arch" in
            linux-x86_64)
                url="https://github.com/jqlang/jq/releases/download/jq-1.7.1/jq-linux-amd64"
                ;;
            linux-arm64)
                url="https://github.com/jqlang/jq/releases/download/jq-1.7.1/jq-linux-aarch64"
                ;;
            macos-x86_64)
                url="https://github.com/jqlang/jq/releases/download/jq-1.7.1/jq-macos-amd64"
                ;;
            macos-arm64)
                url="https://github.com/jqlang/jq/releases/download/jq-1.7.1/jq-macos-arm64"
                ;;
            *)
                echo "jq is required but not installed. Please install jq and retry." >&2
                return 1
                ;;
        esac
        echo "Installing jq to $BIN_DIR ..." >&2
        require_cmd curl
        require_cmd awk

        local jq_tmp
        jq_tmp="$(mktemp)"
        curl -fsSL "$sha_url" -o "$jq_tmp.sha256sum.txt"
        local jq_name expected actual
        jq_name="$(basename "$url")"
        expected="$(grep -E "  ${jq_name}\$" "$jq_tmp.sha256sum.txt" | awk '{print $1}' | head -n1 || true)"
        if [ -z "$expected" ]; then
            echo "Error: failed to find jq checksum for ${jq_name} in sha256sum.txt; aborting." >&2
            rm -f "$jq_tmp" "$jq_tmp.sha256sum.txt" 2>/dev/null || true
            return 1
        fi

        curl -fsSL "$url" -o "$jq_tmp"
        if [ "$VERIFY_DOWNLOADS" = true ]; then
            actual="$(sha256_file "$jq_tmp")"
            if [ "$actual" != "$expected" ]; then
                echo "Error: jq checksum mismatch for ${jq_name}; aborting install." >&2
                rm -f "$jq_tmp" "$jq_tmp.sha256sum.txt" 2>/dev/null || true
                return 1
            fi
        else
            echo "Warning: download verification disabled (--no-verify). Installing jq without checksum verification." >&2
        fi

        mv "$jq_tmp" "$BIN_DIR/jq"
        chmod +x "$BIN_DIR/jq"
        rm -f "$jq_tmp.sha256sum.txt" 2>/dev/null || true
    fi
}

# Function to fetch latest release
fetch_latest_release() {
    local api_url="${GITHUB_API_BASE}/repos/${REPO_OWNER}/${REPO_NAME}/releases/latest"
    local headers=""
    
    # Add authorization header if token is provided
    if [ -n "$GITHUB_TOKEN" ]; then
        headers="-H \"Authorization: token ${GITHUB_TOKEN}\""
    fi
    
    # Add Accept header for GitHub API v3
    headers="$headers -H \"Accept: application/vnd.github.v3+json\""
    
    echo "Fetching latest release from ${REPO_OWNER}/${REPO_NAME}..." >&2
    
    # Make API request
    local response
    if [ -n "$GITHUB_TOKEN" ]; then
        response=$(curl -s -H "Authorization: token ${GITHUB_TOKEN}" -H "Accept: application/vnd.github.v3+json" "$api_url")
    else
        response=$(curl -s -H "Accept: application/vnd.github.v3+json" "$api_url")
    fi
    
    # Check if request was successful
    if echo "$response" | jq -e '.message' | grep -q "Not Found"; then
        echo "Error: Repository ${REPO_OWNER}/${REPO_NAME} not found or no releases available." >&2
        exit 1
    fi
    
    if echo "$response" | jq -e '.message' | grep -q "API rate limit exceeded"; then
        echo "Error: GitHub API rate limit exceeded. Consider using a personal access token." >&2
        exit 1
    fi
    
    echo "$response"
}

# Function to extract version from release data
extract_version() {
    local release_data="$1"
    local version
    
    # Try to get tag_name first (most common)
    version=$(echo "$release_data" | jq -r '.tag_name // empty')
    
    # If tag_name is empty or null, try name
    if [ -z "$version" ] || [ "$version" = "null" ]; then
        version=$(echo "$release_data" | jq -r '.name // empty')
    fi
    
    # Remove 'v' prefix if present
    version=$(echo "$version" | sed 's/^v//')
    
    echo "$version"
}

# Function to display release information
display_release_info() {
    local release_data="$1"
    local version="$2"
    
    if [ "$VERSION_ONLY" = true ]; then
        echo "$version"
        return
    fi
    
    local name=$(echo "$release_data" | jq -r '.name // .tag_name')
    local published_at=$(echo "$release_data" | jq -r '.published_at')
    local body=$(echo "$release_data" | jq -r '.body // "No description available"')
    local html_url=$(echo "$release_data" | jq -r '.html_url')
    
    echo "Latest Release Information:"
    echo "=========================="
    echo "Version: $version"
    echo "Name: $name"
    echo "Published: $published_at"
    echo "URL: $html_url"
}

# Function to download the first asset from the release and update local bin
download_and_update_bin() {
    local release_data="$1"
    local platform
    platform="$(detect_platform)"
    if [ "$platform" = "windows" ]; then
        echo "Windows detected. Please use install.ps1 for Windows installs." >&2
        return 1
    fi

    local arch
    arch="$(detect_arch)"

    local install_dir
    install_dir="$(resolve_install_dir "$INSTALL_MODE" "$INSTALL_PREFIX")"

    local preferred_asset="projman-${platform}-${arch}"
    local legacy_asset=""
    if [ "$platform" = "linux" ] && [ "$arch" = "x86_64" ]; then
        legacy_asset="multi-project-manager-linux-x64"
    fi

    local asset_url=""
    local asset_name="$preferred_asset"
    asset_url="$(echo "$release_data" | jq -r --arg name "$preferred_asset" '.assets[]? | select(.name==$name) | .browser_download_url' | head -n1)"
    if [ -z "$asset_url" ] || [ "$asset_url" = "null" ]; then
        if [ -n "$legacy_asset" ]; then
            asset_url="$(echo "$release_data" | jq -r --arg name "$legacy_asset" '.assets[]? | select(.name==$name) | .browser_download_url' | head -n1)"
            asset_name="$legacy_asset"
        fi
    fi
    if [ -z "$asset_url" ] || [ "$asset_url" = "null" ]; then
        # Fail closed: do not install a binary for another OS/arch.
        local available_assets
        available_assets="$(
          echo "$release_data" | jq -r '.assets[]? | .name // empty' | sed '/^$/d' | sort | tr '\n' ' '
        )"
        echo "Error: no matching release asset found for platform=${platform}, arch=${arch}." >&2
        echo "Expected asset: ${preferred_asset} (or legacy: ${legacy_asset:-<none>})." >&2
        echo "Available assets: ${available_assets:-<none>}." >&2
        return 1
    fi

    if [ -z "$asset_url" ] || [ -z "$asset_name" ] || is_checksum_asset_name "$asset_name"; then
        echo "No assets found in the latest release. Skipping binary update." >&2
        return 1
    fi

    local checksum_url=""
    local checksum_name="${asset_name}.sha256"
    checksum_url="$(echo "$release_data" | jq -r --arg name "$checksum_name" '.assets[]? | select(.name==$name) | .browser_download_url // empty' | head -n1)"
    if [ -z "$checksum_url" ] || [ "$checksum_url" = "null" ]; then
        checksum_url=""
    fi
    
    echo "Found asset: $asset_name"
    echo "Downloading from: $asset_url"
    
    if ! maybe_sudo mkdir -p "$install_dir"; then
        echo "Failed to create install directory: $install_dir" >&2
        return 1
    fi
    
    # 下载 asset 到临时文件
    local temp_file
    temp_file="$(mktemp)"
    local checksum_file
    checksum_file="$(mktemp)"
    if [ "$VERIFY_DOWNLOADS" = true ] && [ -z "$checksum_url" ]; then
        echo "Error: checksum asset '${checksum_name}' not found; refusing to install without verification." >&2
        echo "Tip: re-run with --no-verify to bypass (insecure)." >&2
        rm -f "$temp_file" "$checksum_file" 2>/dev/null || true
        return 1
    fi
    if [ -n "$checksum_url" ]; then
        if [ -n "$GITHUB_TOKEN" ]; then
            curl -fsSL -L -H "Authorization: token ${GITHUB_TOKEN}" -o "$checksum_file" "$checksum_url"
        else
            curl -fsSL -L -o "$checksum_file" "$checksum_url"
        fi
    fi

    if [ -n "$GITHUB_TOKEN" ]; then
        curl -fsSL -L -H "Authorization: token ${GITHUB_TOKEN}" -o "$temp_file" "$asset_url"
    else
        curl -fsSL -L -o "$temp_file" "$asset_url"
    fi

    if [ "$VERIFY_DOWNLOADS" = true ]; then
        local expected actual
        expected="$(awk '{print $1}' "$checksum_file" | head -n1 || true)"
        if [ -z "$expected" ]; then
            echo "Error: failed to parse checksum file for ${asset_name}; aborting install." >&2
            rm -f "$temp_file" "$checksum_file" 2>/dev/null || true
            return 1
        fi
        actual="$(sha256_file "$temp_file")"
        if [ "$actual" != "$expected" ]; then
            echo "Error: checksum mismatch for ${asset_name}; aborting install." >&2
            rm -f "$temp_file" "$checksum_file" 2>/dev/null || true
            return 1
        fi
    else
        echo "Warning: download verification disabled (--no-verify). Installing projman without checksum verification." >&2
    fi
    rm -f "$checksum_file" 2>/dev/null || true
    
    # 赋予可执行权限
    chmod +x "$temp_file"

    if ! verify_binary_candidate "$temp_file"; then
        rm -f "$temp_file" 2>/dev/null || true
        return 1
    fi
    
    # 重命名为 projman 并移动到 .local/bin 目录
    if ! mv "$temp_file" "$install_dir/projman" 2>/dev/null; then
        if ! maybe_sudo mv "$temp_file" "$install_dir/projman"; then
            echo "Failed to move projman into $install_dir (try --user or run with sudo)" >&2
            rm -f "$temp_file" 2>/dev/null || true
            return 1
        fi
    fi
    maybe_sudo chmod +x "$install_dir/projman" 2>/dev/null || true
    
    echo "Downloaded and installed as $install_dir/projman"
}

# Main execution
main() {
    # Check dependencies
    check_curl
    check_jq
    warn_if_token_from_argv
    
    # Fetch latest release
    local release_data
    release_data=$(fetch_latest_release)
    
    # Extract version
    local version
    version=$(extract_version "$release_data")
    
    if [ -z "$version" ] || [ "$version" = "null" ]; then
        echo "Error: Could not extract version from release data." >&2
        exit 1
    fi
    
    # Display information
    display_release_info "$release_data" "$version"

    if [ "$VERSION_ONLY" = true ]; then
        return 0
    fi

    # Download and update bin
    download_and_update_bin "$release_data"
}

# Run main function
main "$@" 
