#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

echo "--- Starting release process ---"

# Get current version from setup.py
current_version=$(grep "version=" setup.py | awk -F'"' '{print $2}')
echo "Current version: $current_version"

# Increment the patch version number
new_version=$(echo $current_version | awk -F. '{$NF = $NF + 1;} 1' | sed 's/ /./g')
echo "New version will be: $new_version"

# Update version in setup.py
echo "--> Updating version in setup.py"
sed -i "s/version=\"$current_version\"/version=\"$new_version\"/" setup.py

echo "--- Version updated. Calling build and install scripts. ---"

# Uninstall any old versions first
./uninstall.sh

# Call build script
./build.sh

# Call install script
./install.sh

echo "--- Release process complete for version $new_version! ---" 