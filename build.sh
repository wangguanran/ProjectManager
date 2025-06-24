#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

echo "--- Cleaning up old builds ---"
rm -rf build dist vprjcore.egg-info

echo "--- Building package ---"
python3 -m build

echo "--- Build complete. Find the artifacts in the 'dist' directory. ---"

# 生成独立二进制（需已安装 pyinstaller）
if command -v pyinstaller &> /dev/null; then
    echo "--- Building standalone binary with pyinstaller ---"
    cd src
    pyinstaller --onefile -n vprj vprjcore/project.py
    cd ..
    cp src/dist/vprj dist/
    echo "Binary generated at dist/vprj"
else
    echo "pyinstaller 未安装，跳过二进制打包。可用 pip install pyinstaller 安装。"
fi 