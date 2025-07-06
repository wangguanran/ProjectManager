#!/bin/bash

# 设置输出目录
OUT_DIR="out"
mkdir -p $OUT_DIR

# Exit immediately if a command exits with a non-zero status.
set -e

# 检查pyinstaller
if ! command -v pyinstaller &> /dev/null; then
    echo "pyinstaller not found, installing..."
    pip install pyinstaller
fi

echo "--- Cleaning up old builds ---"
rm -rf build dist *.egg-info $OUT_DIR
mkdir -p $OUT_DIR

echo "--- Building package ---"
python3 -m build --outdir $OUT_DIR

echo "--- Build complete. Find the artifacts in the 'out' directory. ---"

# 生成独立二进制（需已安装 pyinstaller）
if command -v pyinstaller &> /dev/null; then
    echo "--- Building standalone binary with pyinstaller ---"
    
    # 使用更兼容的配置选项
    pyinstaller \
        --onefile \
        --strip \
        --hidden-import=git \
        --hidden-import=git.cmd \
        --hidden-import=git.repo \
        --hidden-import=importlib_metadata \
        --collect-all=git \
        --collect-all=importlib_metadata \
        --add-data "$(pwd)/pyproject.toml:." \
        --distpath out \
        --workpath out/build \
        --specpath out \
        -n pm \
        src/project_manager.py
    
    echo "Binary generated at out/pm"
    
    # 应用静态链接以提高兼容性
    if command -v staticx &> /dev/null; then
        echo "--- Applying static linking for better compatibility ---"
        # 检查patchelf是否安装
        if command -v patchelf &> /dev/null; then
            staticx out/pm out/pm-static
            mv out/pm-static out/pm
            echo "Static linking applied successfully"
        else
            echo "patchelf not found. Installing..."
            sudo apt-get update && sudo apt-get install -y patchelf
            echo "--- Applying static linking for better compatibility ---"
            staticx out/pm out/pm-static
            mv out/pm-static out/pm
            echo "Static linking applied successfully"
        fi
    else
        echo "staticx not found. Installing for better compatibility..."
        pip install staticx
        echo "--- Applying static linking for better compatibility ---"
        # 检查patchelf是否安装
        if command -v patchelf &> /dev/null; then
            staticx out/pm out/pm-static
            mv out/pm-static out/pm
            echo "Static linking applied successfully"
        else
            echo "patchelf not found. Installing..."
            sudo apt-get update && sudo apt-get install -y patchelf
            echo "--- Applying static linking for better compatibility ---"
            staticx out/pm out/pm-static
            mv out/pm-static out/pm
            echo "Static linking applied successfully"
        fi
    fi
    
    # 再次移除debug_info以减小文件大小
    echo "--- Final debug info removal ---"
    strip out/pm
    
    echo "Final binary generated at out/pm with static linking"
else
    echo "pyinstaller 未安装，跳过二进制打包。可用 pip install pyinstaller 安装。"
fi

# 清理src目录下的egg-info
rm -rf src/*.egg-info 