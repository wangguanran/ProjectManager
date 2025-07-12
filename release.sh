#!/bin/bash

# Release script for ProjectManager
# This script handles version management and Git operations
# GitHub Actions will handle building and publishing to GitHub Releases

set -e

echo "--- Starting release process ---"

# Configuration
RELEASE_TYPE=${1:-"patch"}  # patch, minor, major

# Get current version from pyproject.toml
current_version=$(grep "version = " pyproject.toml | awk -F'"' '{print $2}')
echo "Current version: $current_version"

# Calculate new version based on release type
if [ "$RELEASE_TYPE" = "major" ]; then
    new_version=$(echo $current_version | awk -F. '{print $1 + 1 ".0.0"}')
elif [ "$RELEASE_TYPE" = "minor" ]; then
    new_version=$(echo $current_version | awk -F. '{print $1 "." $2 + 1 ".0"}')
else  # patch (default)
    new_version=$(echo $current_version | awk -F. '{$NF = $NF + 1;} 1' | sed 's/ /./g')
fi

echo "New version will be: $new_version"

# Update version in pyproject.toml
echo "--> Updating version in pyproject.toml"
sed -i "s/version = \"$current_version\"/version = \"$new_version\"/" pyproject.toml

echo "--- Version updated. Committing changes and creating tag. ---"

# Get current branch name
current_branch=$(git branch --show-current)
echo "Current branch: $current_branch"

# Commit version update (skip pre-commit hooks for version bumps)
git add pyproject.toml
git commit -m "Bump version to $new_version"

# Create tag (delete if exists)
if git tag -l | grep -q "v$new_version"; then
    echo "Tag v$new_version already exists. Deleting and recreating..."
    git tag -d v$new_version
    git push --no-verify origin :refs/tags/v$new_version 2>/dev/null || true
fi
git tag v$new_version

echo "--- Git operations complete. Pushing to remote. ---"

# Push changes to current branch
echo "--> Pushing changes to $current_branch"
git push --no-verify origin $current_branch

# Push tag with verification
echo "--> Pushing tag v$new_version"
git push --no-verify origin v$new_version

# Verify tag was pushed successfully
echo "--> Verifying tag push..."
if git ls-remote --tags origin | grep -q "v$new_version"; then
    echo "✓ Tag v$new_version successfully pushed to remote"
else
    echo "✗ Failed to push tag v$new_version"
    echo "Attempting to push tag again..."
    git push origin v$new_version
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