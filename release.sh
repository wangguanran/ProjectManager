#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

echo "--- Starting release process ---"

# Get current version from pyproject.toml
current_version=$(grep "version = " pyproject.toml | awk -F'"' '{print $2}')
echo "Current version: $current_version"

# Increment the patch version number
new_version=$(echo $current_version | awk -F. '{$NF = $NF + 1;} 1' | sed 's/ /./g')
echo "New version will be: $new_version"

# Update version in pyproject.toml
echo "--> Updating version in pyproject.toml"
sed -i "s/version = \"$current_version\"/version = \"$new_version\"/" pyproject.toml

echo "--- Version updated. Calling build and install scripts. ---"

# Uninstall any old versions first
./uninstall.sh

# Call build script
./build.sh

# Call install script
./install.sh

echo "--- Release process complete for version $new_version! ---" 