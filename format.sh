#!/bin/bash

# Function to install a python package if not present
install_if_missing() {
    pkg_name="$1"
    if ! command -v $pkg_name &> /dev/null; then
        echo "$pkg_name not found, installing..."
        if command -v pip3 &> /dev/null; then
            pip3 install $pkg_name
        elif command -v pip &> /dev/null; then
            pip install $pkg_name
        else
            echo "Error: pip is not installed. Please install pip first." >&2
            exit 1
        fi
        # Check again after install
        if ! command -v $pkg_name &> /dev/null; then
            echo "Error: Failed to install $pkg_name." >&2
            exit 1
        fi
    fi
}

# Ensure black and isort are installed
install_if_missing black
install_if_missing isort

# Run black
black .
if [ $? -ne 0 ]; then
    echo "Error: black failed to format the code." >&2
    exit 1
fi

# Run isort
isort .
if [ $? -ne 0 ]; then
    echo "Error: isort failed to format the code." >&2
    exit 1
fi