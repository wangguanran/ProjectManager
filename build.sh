#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

echo "--- Cleaning up old builds ---"
rm -rf build dist vprjcore.egg-info

echo "--- Building package ---"
python3 -m build

echo "--- Build complete. Find the artifacts in the 'dist' directory. ---" 