#!/bin/bash

# 必须先设置以下变量
GITHUB_TOKEN="${GITHUB_TOKEN:?请先设置环境变量 GITHUB_TOKEN}"                # 从环境变量读取 GitHub Personal Access Token
REPO="wangguanran/ProjectManager"
ARTIFACT_NAME="build-artifacts"     # 你的 artifact 名称
WORKFLOW_NAME="Python application"  # 只获取该 workflow 的产物

# 检查依赖
if ! command -v jq &> /dev/null; then
    echo "请先安装 jq 工具"
    exit 1
fi
if ! command -v unzip &> /dev/null; then
    echo "请先安装 unzip 工具"
    exit 1
fi

# 获取 workflow 列表，找到目标 workflow_id
workflow_id=$(curl -s -H "Authorization: token $GITHUB_TOKEN" \
  "https://api.github.com/repos/$REPO/actions/workflows" | \
  jq -r ".workflows[] | select(.name==\"$WORKFLOW_NAME\") | .id")

if [ -z "$workflow_id" ]; then
    echo "未找到名为 $WORKFLOW_NAME 的 workflow"
    exit 1
fi

# 获取该 workflow 的最新成功 run_id
run_id=$(curl -s -H "Authorization: token $GITHUB_TOKEN" \
  "https://api.github.com/repos/$REPO/actions/workflows/$workflow_id/runs?status=success&per_page=1" | \
  jq ".workflow_runs[0].id")

if [ -z "$run_id" ] || [ "$run_id" = "null" ]; then
    echo "未找到 $WORKFLOW_NAME 的成功 workflow run"
    exit 1
fi

# 获取 artifact 列表，找到目标 artifact 的 ID
artifact_id=$(curl -s -H "Authorization: token $GITHUB_TOKEN" \
  "https://api.github.com/repos/$REPO/actions/runs/$run_id/artifacts" | \
  jq ".artifacts[] | select(.name==\"$ARTIFACT_NAME\") | .id")

if [ -z "$artifact_id" ]; then
    echo "未找到名为 $ARTIFACT_NAME 的 artifact"
    exit 1
fi

# 下载 artifact
curl -L -H "Authorization: token $GITHUB_TOKEN" \
  -o artifact.zip \
  "https://api.github.com/repos/$REPO/actions/artifacts/$artifact_id/zip"

# 解压
unzip -o artifact.zip -d ./artifact

echo "最新二进制已下载到 ./artifact 目录" 

# 安装 projman 到 $HOME/.local/bin/
INSTALL_DIR="$HOME/.local/bin"
mkdir -p "$INSTALL_DIR"
cp ./artifact/out/binary/projman "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/projman"
echo "projman 已安装到 $INSTALL_DIR/"
