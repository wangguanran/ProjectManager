#!/bin/bash
# Script to fetch the latest version from GitHub releases

set -e

# Default values
REPO_OWNER="wangguanran"
REPO_NAME="ProjectManager"
GITHUB_API_BASE="https://api.github.com"

# Function to display usage
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo "Options:"
    echo "  -o, --owner OWNER    GitHub repository owner (default: wangguanran)"
    echo "  -r, --repo REPO      GitHub repository name (default: ProjectManager)"
    echo "  -t, --token TOKEN    GitHub personal access token (optional)"
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
        echo "jq not found. Installing jq to $HOME/.local/bin..." >&2
        mkdir -p "$HOME/.local/bin"
        curl -L -o "$HOME/.local/bin/jq" https://github.com/stedolan/jq/releases/latest/download/jq-linux64
        chmod +x "$HOME/.local/bin/jq"
        # 检查 ~/.local/bin 是否在 PATH 中
        if ! echo "$PATH" | grep -q "$HOME/.local/bin"; then
            echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
            export PATH="$HOME/.local/bin:$PATH"
            echo "Added $HOME/.local/bin to PATH. Please run: source ~/.bashrc" >&2
        fi
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
    local bin_dir="$HOME/.local/bin"
    
    # 获取第一个 asset 的下载链接和文件名
    local asset_url=$(echo "$release_data" | jq -r '.assets[0].browser_download_url // empty')
    local asset_name=$(echo "$release_data" | jq -r '.assets[0].name // empty')
    
    if [ -z "$asset_url" ] || [ -z "$asset_name" ]; then
        echo "No assets found in the latest release. Skipping binary update." >&2
        return 1
    fi
    
    echo "Found asset: $asset_name"
    echo "Downloading from: $asset_url"
    
    # 创建 .local/bin 目录（如果不存在）
    mkdir -p "$bin_dir"
    
    # 下载 asset 到临时文件
    local temp_file=$(mktemp)
    curl -L -o "$temp_file" "$asset_url"
    
    # 赋予可执行权限
    chmod +x "$temp_file"
    
    # 重命名为 mpm 并移动到 .local/bin 目录
    mv "$temp_file" "$bin_dir/mpm"
    
    echo "Downloaded and installed as $bin_dir/mpm"
}

# Main execution
main() {
    # Check dependencies
    check_curl
    check_jq
    
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

    # Download and update bin
    download_and_update_bin "$release_data"
}

# Run main function
main "$@" 