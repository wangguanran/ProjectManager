#!/bin/bash

# 设置输出目录
OUT_DIR="out"
mkdir -p $OUT_DIR

# Exit immediately if a command exits with a non-zero status.
set -e

echo "--- Cleaning up old builds ---"
rm -rf build dist vprjcore.egg-info $OUT_DIR
mkdir -p $OUT_DIR

echo "--- Building package ---"
python3 -m build --outdir $OUT_DIR

echo "--- Build complete. Find the artifacts in the 'out' directory. ---"

# 生成独立二进制（需已安装 pyinstaller）
if command -v pyinstaller &> /dev/null; then
    echo "--- Building standalone binary with pyinstaller ---"
    pyinstaller --onefile -n vprj src/project_manager.py --distpath $OUT_DIR --workpath $OUT_DIR/build --specpath $OUT_DIR
    echo "Binary generated at out/vprj"
else
    echo "pyinstaller 未安装，跳过二进制打包。可用 pip install pyinstaller 安装。"
fi

# 清理src目录下的egg-info
rm -rf src/vprjcore.egg-info 