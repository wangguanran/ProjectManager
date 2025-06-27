#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

echo "Please select installation method:"
echo "1) System-wide installation (pip install to system/current Python environment)"
echo "2) Install standalone binary (no Python environment required)"
echo "3) venv isolated installation (recommended for development/testing)"
echo -n "Enter option [1/2/3] and press Enter: "
read choice

if [ "$choice" == "1" ]; then
    echo "--- System-wide installation ---"
    if ! command -v pip3 &> /dev/null; then
        echo "pip3 not found. Please install pip3 first."
        exit 1
    fi
    WHEEL_FILE=$(ls out/*.whl | head -n 1)
    if [ -z "$WHEEL_FILE" ]; then
        echo "No .whl package found in out directory. Please build first."
        exit 1
    fi
    pip3 install --upgrade pip
    pip3 install "$WHEEL_FILE"
    echo "Installed to system environment. You can use the vprj command directly (if entry_points is configured)."

elif [ "$choice" == "2" ]; then
    echo "--- Installing standalone binary ---"
    if [ ! -f out/pm ]; then
        echo "out/pm binary not found. Please build first."
        exit 1
    fi
    TARGET_BIN="$HOME/.local/bin"
    mkdir -p "$TARGET_BIN"
    cp out/pm "$TARGET_BIN/pm"
    chmod +x "$TARGET_BIN/pm"
    echo "Copied pm to $TARGET_BIN/pm"
    echo "Make sure $TARGET_BIN is in your PATH."
    echo "You can temporarily add it with:"
    echo "  export PATH=\"$TARGET_BIN:\$PATH\""
    echo "Then you can use the pm command in any terminal."

elif [ "$choice" == "3" ]; then
    echo "--- venv isolated installation ---"
    if ! command -v python3 &> /dev/null; then
        echo "Python3 not found."
        exit 1
    fi
    if [ ! -d "venv" ]; then
        python3 -m venv venv
    fi
    source venv/bin/activate
    pip install --upgrade pip
    WHEEL_FILE=$(ls out/*.whl | head -n 1)
    if [ -z "$WHEEL_FILE" ]; then
        echo "No .whl package found in out directory. Please build first."
        deactivate
        exit 1
    fi
    pip install "$WHEEL_FILE"
    deactivate
    cat > run_pm.sh << EOF
#!/bin/bash
source "$(dirname "$0")/venv/bin/activate"
pm "\$@"
EOF
    chmod +x run_pm.sh
    echo "Installed in venv environment. Use ./run_pm.sh to start the tool."
else
    echo "Invalid option. Exiting."
    exit 1
fi 