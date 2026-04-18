#!/bin/bash

# 必须先设置以下变量
GITHUB_TOKEN="${GITHUB_TOKEN:-}"                # 从环境变量读取 GitHub Personal Access Token
if [ -z "$GITHUB_TOKEN" ]; then
  echo "Error: GITHUB_TOKEN is required to download GitHub Actions artifacts." >&2
  echo "Tip: for tokenless installs (GitHub Releases), use ./get_latest_release.sh" >&2
  exit 2
fi
REPO="wangguanran/ProjectManager"
ARTIFACT_NAME="build-artifacts"     # 你的 artifact 名称
WORKFLOW_NAME="Python application"  # 只获取该 workflow 的产物

# 准备用户本地 bin 目录并加入 PATH（本次会话内生效）
BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"
export PATH="$BIN_DIR:$PATH"

INSTALL_KIND="package"  # package|binary

detect_platform() {
  local uname_s
  uname_s="$(uname -s 2>/dev/null || echo unknown)"
  case "$uname_s" in
    Linux)
      echo "linux"
      ;;
    Darwin)
      echo "macos"
      ;;
    MINGW*|MSYS*|CYGWIN*|Windows_NT)
      echo "windows"
      ;;
    *)
      echo "unknown"
      ;;
  esac
}

usage() {
  cat <<'EOF'
Usage: ./get_latest_artifact.sh [--package|--binary|--install-kind KIND]

Options:
  --package        Install the wheel artifact into a managed runtime (default).
  --binary         Install the standalone onefile artifact.
  --install-kind   Explicit install kind: package or binary.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --package)
      INSTALL_KIND="package"
      shift
      ;;
    --binary)
      INSTALL_KIND="binary"
      shift
      ;;
    --install-kind)
      INSTALL_KIND="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

case "$INSTALL_KIND" in
  package|binary)
    ;;
  *)
    echo "Invalid install kind: $INSTALL_KIND (expected: package or binary)" >&2
    exit 2
    ;;
esac

# 安装 jq（用户态，无需 sudo）
install_jq() {
  local arch
  arch=$(uname -m)
  local url=""
  case "$arch" in
    x86_64|amd64)
      url="https://github.com/jqlang/jq/releases/download/jq-1.7.1/jq-linux-amd64"
      ;;
    aarch64|arm64)
      url="https://github.com/jqlang/jq/releases/download/jq-1.7.1/jq-linux-aarch64"
      ;;
    *)
      echo "未支持的架构: $arch，请手动安装 jq" >&2
      return 1
      ;;
  esac
  echo "正在为 $arch 安装 jq 到 $BIN_DIR/jq ..."
  curl -fsSL "$url" -o "$BIN_DIR/jq" && chmod +x "$BIN_DIR/jq"
}

# 退回方案：使用 python3 构建 unzip 的最小实现
install_unzip_shim() {
  if command -v python3 >/dev/null 2>&1; then
    cat > "$BIN_DIR/unzip" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
zipfile=""
outdir="."
while [[ $# -gt 0 ]]; do
  case "$1" in
    -d)
      outdir="$2"; shift 2 ;;
    -o)
      shift ;;
    -*)
      # 忽略其他不相关参数
      shift ;;
    *)
      zipfile="$1"; shift ;;
  esac
done
if [[ -z "${zipfile}" ]]; then
  echo "用法: unzip [-o] [-d 目录] ZIP文件" >&2
  exit 2
fi
python3 - "$zipfile" "$outdir" <<'PY'
import sys, zipfile, os
zip_path=sys.argv[1]
outdir=sys.argv[2]
os.makedirs(outdir, exist_ok=True)
with zipfile.ZipFile(zip_path) as z:
    z.extractall(outdir)
print(f"已解压到 {outdir}")
PY
SH
    chmod +x "$BIN_DIR/unzip"
  else
    echo "未找到 python3，无法创建 unzip 的用户态实现，请手动安装 unzip 或 python3" >&2
    return 1
  fi
}

# 确保依赖存在（无 sudo 安装）
if ! command -v jq >/dev/null 2>&1; then
  install_jq || exit 1
fi
if ! command -v unzip >/dev/null 2>&1; then
  install_unzip_shim || exit 1
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

INSTALL_DIR="$HOME/.local/bin"
mkdir -p "$INSTALL_DIR"
PLATFORM="$(detect_platform)"

if [ "$INSTALL_KIND" = "package" ]; then
  WHEEL_PATH="$(ls -1t ./artifact/out/package/*.whl 2>/dev/null | head -n1 || true)"
  if [ -z "$WHEEL_PATH" ]; then
    echo "artifact 中未找到 wheel 包（./artifact/out/package/*.whl）" >&2
    exit 1
  fi
  if [ ! -f ./artifact/scripts/install_package.py ]; then
    echo "artifact 中未找到 scripts/install_package.py，无法执行包安装。" >&2
    exit 1
  fi
  python3 ./artifact/scripts/install_package.py \
    --wheel "$WHEEL_PATH" \
    --install-dir "$INSTALL_DIR" \
    --platform "$PLATFORM"
  echo "projman 已以受管运行时方式安装到 $INSTALL_DIR/"
else
  cp ./artifact/out/binary/projman "$INSTALL_DIR/"
  chmod +x "$INSTALL_DIR/projman"
  echo "projman 独立二进制已安装到 $INSTALL_DIR/"
fi
