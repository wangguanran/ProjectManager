#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

echo "--- Installing the package ---"
# Use a wildcard to find the wheel file, making the script version-agnostic.
pip3 install --force-reinstall dist/vprjcore-*-py3-none-any.whl

echo "--- Installation complete! ---" 