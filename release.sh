#!/bin/bash

# Release script for ProjectManager
# This script handles version management and Git operations
# GitHub Actions will handle building and publishing to GitHub Releases

echo "--- Starting release process ---"

# 检查是否为 test 模式
if [ "$1" = "--test" ]; then
    TEST_MODE=1
    RELEASE_TYPE=${2:-"patch"}
else
    TEST_MODE=0
    RELEASE_TYPE=${1:-"patch"}
fi

maybe_run() {
    if [ "$TEST_MODE" = "1" ]; then
        echo "[TEST MODE] $*"
    else
        echo "$*"
        eval "$*"
    fi
}

# Get current version from pyproject.toml
current_version=$(grep -E '^version = "' pyproject.toml | head -n1 | awk -F'"' '{print $2}')
echo "Current version: $current_version"

# Calculate new version based on release type
if [ "$RELEASE_TYPE" = "major" ]; then
    new_version=$(echo $current_version | awk -F. '{printf "%d.0.0", $1+1}')
elif [ "$RELEASE_TYPE" = "minor" ]; then
    new_version=$(echo $current_version | awk -F. '{printf "%d.%d.0", $1, $2+1}')
else  # patch (default)
    new_version=$(echo $current_version | awk -F. '{printf "%d.%d.%d", $1, $2, $3+1}')
fi

echo "New version will be: $new_version"

# Update version in pyproject.toml
echo "--> Updating version in pyproject.toml"
update_pyproject_version() {
    if [ "$TEST_MODE" = "1" ]; then
        echo "[TEST MODE] update pyproject.toml: version = \"$new_version\""
        return 0
    fi

    # GNU sed: sed -i
    # BSD sed (macOS): sed -i ''
    if sed --version >/dev/null 2>&1; then
        sed -i "s#^version = \".*\"#version = \"$new_version\"#" pyproject.toml
    else
        sed -i '' "s#^version = \".*\"#version = \"$new_version\"#" pyproject.toml
    fi
}
update_pyproject_version

echo "--- Version updated. Committing changes and creating tag. ---"

# Get current branch name
current_branch=$(git branch --show-current)
echo "Current branch: $current_branch"

# Commit version update (skip pre-commit hooks for version bumps)
maybe_run "git add pyproject.toml"
maybe_run "git commit -m \"Bump version to $new_version\""

# Create tag (delete if exists)
maybe_run "git tag -l | grep -q \"v$new_version\""
TAG_EXISTS=$?

if [ $TAG_EXISTS -eq 0 ]; then
    echo "Tag v$new_version already exists. Deleting and recreating..."
    maybe_run "git tag -d v$new_version"
    maybe_run "git push --no-verify origin :refs/tags/v$new_version 2>/dev/null || true"
fi
maybe_run "git tag v$new_version"

echo "--- Git operations complete. Pushing to remote. ---"

# Push changes to current branch
echo "--> Pushing changes to $current_branch"
maybe_run "git push --no-verify origin $current_branch"

# Push tag with verification
echo "--> Pushing tag v$new_version"
maybe_run "git push --no-verify origin v$new_version"

# Verify tag was pushed successfully
echo "--> Verifying tag push..."
maybe_run "git ls-remote --tags origin | grep -q \"v$new_version\""
TAG_PUSHED=$?

if [ $TAG_PUSHED -eq 0 ]; then
    echo "✓ Tag v$new_version successfully pushed to remote"
else
    echo "✗ Failed to push tag v$new_version"
    echo "Attempting to push tag again..."
    maybe_run "git push origin v$new_version"
fi

echo "--- Release process complete for version $new_version! ---"
echo ""
echo "GitHub Actions will automatically:"
echo "1. Build the binary from the tag"
echo "2. Create a GitHub Release"
echo "3. Upload the binary files"
echo ""
echo "You can monitor the progress at:"
echo "https://github.com/wangguanran/ProjectManager/actions" 
