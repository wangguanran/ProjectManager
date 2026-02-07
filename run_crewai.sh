#!/bin/bash
# CrewAI 快速启动脚本

set -e

# 进入项目目录
cd "$(dirname "$0")"

# 激活虚拟环境
if [ ! -d ".venv" ]; then
    echo "错误: 虚拟环境不存在，请先运行 setup_venv.sh"
    exit 1
fi

source .venv/bin/activate

# 禁用国际代理（MiniMax 是国内服务）
unset ALL_PROXY all_proxy
echo "✓ 已禁用国际代理"

# 检查凭证（支持 API Key 与 OAuth Token）
CONFIG_FILE="config/crewai.json"

eval "$(python3 - <<'PY'
import json

path = 'config/crewai.json'
try:
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
except FileNotFoundError:
    data = {
        "provider": "minimax",
        "api_key_env": "MINIMAX_API_KEY",
        "auth_mode": "api_key",
    }

primary = data.get("primary", data)
env_name = primary.get("credential_env") or primary.get("api_key_env") or ""
auth_mode = primary.get("auth_mode", "api_key")
provider = primary.get("provider", "")

print(f'CREDENTIAL_ENV=\"{env_name}\"')
print(f'AUTH_MODE=\"{auth_mode}\"')
print(f'PROVIDER=\"{provider}\"')
PY
)"

if [ -z "$CREDENTIAL_ENV" ]; then
    echo "错误: 配置文件中未找到 credential_env/api_key_env"
    exit 1
fi

if [ -z "${!CREDENTIAL_ENV}" ]; then
    if [ "$AUTH_MODE" = "oauth" ]; then
        echo "⚠️ 未检测到 $CREDENTIAL_ENV ，启动浏览器登录流程..."
        TOKEN=$(python3 -m src.crew.oauth_login --provider "$PROVIDER" --env-name "$CREDENTIAL_ENV")
        if [ -z "$TOKEN" ]; then
            echo "登录未完成或失败，请重试。"
            exit 1
        fi
        export "$CREDENTIAL_ENV"="$TOKEN"
        echo "✓ 已获取并保存 OAuth Token (${CREDENTIAL_ENV})"
    else
        echo "错误: 未设置 $CREDENTIAL_ENV 环境变量 (provider=$PROVIDER, auth_mode=$AUTH_MODE)"
        echo "请导出 API Key，例如: export $CREDENTIAL_ENV='your-api-key'"
        exit 1
    fi
fi

echo "✓ 凭证已配置 (${CREDENTIAL_ENV}, auth_mode=${AUTH_MODE})"
echo ""

# 显示帮助信息
if [ "$1" == "--help" ] || [ "$1" == "-h" ]; then
    cat << EOF
CrewAI 工作流使用说明
====================

用法:
  ./run_crewai.sh <标题> <类型> <详细描述>

参数:
  标题        - 需求/任务的标题
  类型        - new_requirement | bug | optimization
  详细描述    - 功能的详细说明

示例:
  # 新功能
  ./run_crewai.sh "添加用户登录" "new_requirement" "实现用户名密码登录功能"
  
  # Bug 修复
  ./run_crewai.sh "修复登录问题" "bug" "特殊字符导致登录失败"
  
  # 优化
  ./run_crewai.sh "优化性能" "optimization" "减少数据库查询"

输出文件:
  - docs/tasks.md            任务列表
  - docs/test_cases_crew.md  测试用例

EOF
    exit 0
fi

# 检查参数
if [ $# -lt 3 ]; then
    echo "错误: 参数不足"
    echo "用法: ./run_crewai.sh <标题> <类型> <详细描述>"
    echo "执行 './run_crewai.sh --help' 查看详细帮助"
    exit 1
fi

TITLE="$1"
TYPE="$2"
DETAILS="$3"

# 验证类型
if [[ ! "$TYPE" =~ ^(new_requirement|bug|optimization)$ ]]; then
    echo "错误: 类型必须是 new_requirement, bug 或 optimization"
    exit 1
fi

# 运行 CrewAI
echo "======================================"
echo "CrewAI 工作流启动"
echo "======================================"
echo "标题: $TITLE"
echo "类型: $TYPE"
echo "详细: $DETAILS"
echo "======================================"
echo ""

python3 -m src crew_run _ \
    --title "$TITLE" \
    --request-type "$TYPE" \
    --details "$DETAILS" \
    --auto-confirm

echo ""
echo "======================================"
echo "工作流完成！"
echo "======================================"
echo "查看输出:"
echo "  - 任务列表: docs/tasks.md"
echo "  - 测试用例: docs/test_cases_crew.md"
