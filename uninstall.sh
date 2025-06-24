#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

echo "--- Checking if vprjcore is installed ---"

# Check if the package is installed before trying to uninstall
if pip3 show vprjcore > /dev/null 2>&1; then
  echo "--> vprjcore is installed. Uninstalling..."
  pip3 uninstall -y vprjcore
  echo "--- Uninstallation complete ---"
else
  echo "--> vprjcore is not installed. Skipping uninstallation."
fi 