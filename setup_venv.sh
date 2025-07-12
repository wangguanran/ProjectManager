#!/bin/bash
# Script to automatically create venv virtual environment and install dependencies after cloning the repo

set -e

# 1. Check if python3 is installed
if ! command -v python3 &> /dev/null; then
    echo "Python3 is not installed. Please install Python3 first."
    exit 1
fi

# 2. Check if python3-venv is installed
if ! python3 -m venv --help &> /dev/null; then
    echo "python3-venv is not installed. Trying to install..."
    sudo apt update
    sudo apt install -y python3-venv
fi

# 3. Create virtual environment
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "Virtual environment 'venv' created."
else
    echo "Virtual environment 'venv' already exists. Skipping creation."
fi

# 4. Activate virtual environment and install dependencies
source venv/bin/activate
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    echo "Dependencies installed."
else
    echo "requirements.txt not found. Only created the virtual environment."
fi

echo "Done! Use 'source venv/bin/activate' to activate the virtual environment." 