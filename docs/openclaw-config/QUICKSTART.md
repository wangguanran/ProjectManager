# OpenClaw 快速开始

## 一键部署

```bash
#!/bin/bash
# setup-openclaw.sh - 一键部署脚本

set -e

echo "========== OpenClaw 快速部署 =========="

# 1. 安装 OpenClaw
echo "[1/7] 安装 OpenClaw..."
npm install -g openclaw@latest

# 2. 创建目录结构
echo "[2/7] 创建目录结构..."
mkdir -p ~/.openclaw
mkdir -p ~/.openclaw/agents/{pm,builder,tester}/agent
mkdir -p ~/.openclaw/workspace-{pm,builder,tester}
mkdir -p ~/.openclaw/workspace-pm/memory/{requirements,test-cases}
mkdir -p ~/.openclaw/workflows

# 3. 复制配置文件
echo "[3/7] 复制配置文件..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp "$SCRIPT_DIR/openclaw.json" ~/.openclaw/
cp "$SCRIPT_DIR/workspace-pm/"*.md ~/.openclaw/workspace-pm/

# 4. 复制工作流
echo "[4/7] 复制工作流..."
cp "$SCRIPT_DIR/workflows/"*.lobster ~/.openclaw/workflows/

# 5. 创建 Builder 和 Tester 工作空间配置
echo "[5/7] 创建工作空间配置..."
cat > ~/.openclaw/workspace-builder/AGENTS.md <<'EOF'
# Builder Agent

你是代码实施专家，负责根据需求文档实现功能。

## 核心职责
1. 阅读需求文档
2. 修改代码实现功能
3. 编写单元测试
4. 运行测试验证

## 质量标准
- PEP 8 规范
- 类型注解完整
- 单元测试覆盖率 > 80%
EOF

cat > ~/.openclaw/workspace-tester/AGENTS.md <<'EOF'
# Tester Agent

你是测试专家，负责执行测试用例并报告结果。

## 核心职责
1. 执行测试用例
2. 验证功能正确性
3. 报告测试结果

## 报告格式
- 测试用例 ID
- 测试结果 (PASS/FAIL)
- 错误信息
EOF

# 6. 提示配置消息渠道
echo "[6/7] 请配置消息渠道..."
echo ""
echo "请编辑 ~/.openclaw/openclaw.json，设置您的联系方式："
echo "  - WhatsApp: channels.whatsapp.allowFrom"
echo "  - Telegram: channels.telegram.allowFrom"
echo ""
read -p "按 Enter 继续..."

# 7. 启动服务
echo "[7/7] 启动 OpenClaw Gateway..."
echo ""
echo "选择启动方式："
echo "  1) 前台运行 (用于调试)"
echo "  2) 安装为系统服务"
read -p "请选择 [1/2]: " choice

case $choice in
  1)
    echo "启动前台服务..."
    openclaw gateway
    ;;
  2)
    echo "安装系统服务..."
    openclaw onboard --install-daemon
    echo "服务已安装，使用 'openclaw status' 查看状态"
    ;;
  *)
    echo "无效选择"
    exit 1
    ;;
esac

echo ""
echo "========== 部署完成 =========="
echo "下一步："
echo "  1. 配对消息渠道: openclaw channels login"
echo "  2. 查看状态: openclaw status"
echo "  3. 查看日志: openclaw logs --follow"
echo "  4. 测试 PM Agent: 发送消息 '你好'"
```

保存为 `setup-openclaw.sh`，然后执行：

```bash
chmod +x setup-openclaw.sh
./setup-openclaw.sh
```

---

## 配对消息渠道

### WhatsApp

```bash
# 1. 启动 Gateway (如果尚未启动)
openclaw gateway

# 2. 在另一个终端配对 WhatsApp
openclaw channels login

# 3. 扫描二维码
# 使用 WhatsApp 应用扫描终端显示的二维码
```

### Telegram

```bash
# 1. 创建 Bot
# 访问 https://t.me/BotFather
# 发送 /newbot 并按提示操作
# 获取 Bot Token (格式: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz)

# 2. 配置 Token
# 编辑 ~/.openclaw/openclaw.json:
{
  "channels": {
    "telegram": {
      "token": "YOUR_BOT_TOKEN",
      "allowFrom": ["@your_username"]
    }
  }
}

# 3. 重启 Gateway
openclaw restart

# 4. 在 Telegram 中搜索你的 Bot 并发送 /start
```

---

## 验证部署

### 1. 检查服务状态

```bash
openclaw status

# 输出示例:
# Gateway: running (port 18789)
# Agents: 3 (pm, builder, tester)
# Channels: 2 (whatsapp: connected, telegram: connected)
```

### 2. 测试 PM Agent

发送消息给 WhatsApp/Telegram Bot：

```
你好
```

预期回复：
```
你好！我是 PM Assistant。

我的职责是帮助你充分理解需求、生成测试用例，并在确认后分发任务。

你可以：
1. 提出新功能需求
2. 报告 Bug
3. 查询项目状态

请问有什么可以帮助你的？
```

### 3. 测试需求确认流程

**你**:
```
我希望添加一个命令，可以列出所有主板
```

**PM Agent**:
```
明白了。我想确认几个细节：

1. 列出主板的信息包括：
   - 主板名称？
   - 项目数量？
   - 配置文件路径？
   - 其他什么信息？

2. 输出格式：
   - 简洁列表 (只显示名称)？
   - 详细表格 (显示完整信息)？
   - JSON 格式 (便于脚本解析)？

3. 是否需要过滤和排序功能？

请详细说明，我会据此整理测试用例。
```

### 4. 测试工作流

```bash
# 查看可用工作流
ls ~/.openclaw/workflows/

# 输出:
# project-implementation.lobster
# bug-fix.lobster
# quick-task.lobster
```

---

## 常用命令

### 管理 Gateway

```bash
# 启动 Gateway
openclaw gateway

# 查看状态
openclaw status

# 查看日志
openclaw logs --follow

# 重启 Gateway
openclaw restart

# 停止 Gateway
pkill -f "openclaw gateway"
```

### 管理 Agent

```bash
# 列出所有 Agent
openclaw agents list

# 查看 Agent 配置
openclaw agents list --bindings

# 查看 Agent 会话
openclaw sessions list

# 查看某个会话的历史
openclaw sessions --session-id <id> history
```

### 管理工作流

```bash
# 测试工作流语法
lobster validate ~/.openclaw/workflows/project-implementation.lobster

# 手动运行工作流 (测试用)
lobster run ~/.openclaw/workflows/quick-task.lobster \
  --args-json '{"task_description":"测试任务","agent_id":"pm"}'
```

### 调试

```bash
# 启用调试模式
openclaw gateway --log-level debug

# 查看详细日志
openclaw logs --level debug --follow

# 检查配置
openclaw doctor

# 查看配置
openclaw configure show
```

---

## 故障排查速查表

| 问题 | 可能原因 | 解决方案 |
|------|---------|---------|
| Gateway 无法启动 | 端口被占用 | `lsof -i :18789` 找到占用进程并杀死 |
| 无法连接 WhatsApp | 会话过期 | `openclaw channels login` 重新配对 |
| 工作流超时 | 任务时间过长 | 增加 `runTimeoutSeconds` |
| Agent 无权限 | 工具配置错误 | 检查 `tools.allow/deny` |
| 消息发送失败 | 号码不在白名单 | 检查 `allowFrom` 配置 |

---

## 目录结构速查

```
~/.openclaw/
├── openclaw.json                    # 主配置文件
├── agents/
│   ├── pm/
│   │   ├── agent/                   # PM Agent 状态目录
│   │   └── sessions/                # PM Agent 会话记录
│   ├── builder/
│   │   ├── agent/
│   │   └── sessions/
│   └── tester/
│       ├── agent/
│       └── sessions/
├── workspace-pm/                    # PM Agent 工作空间
│   ├── AGENTS.md                    # 操作指南
│   ├── SOUL.md                      # 性格设定
│   ├── USER.md                      # 用户信息
│   ├── TOOLS.md                     # 工具说明
│   └── memory/
│       ├── requirements/            # 需求文档
│       ├── test-cases/              # 测试用例
│       └── YYYY-MM-DD.md            # 日志
├── workspace-builder/               # Builder Agent 工作空间
├── workspace-tester/                # Tester Agent 工作空间
├── workflows/                       # Lobster 工作流
│   ├── project-implementation.lobster
│   ├── bug-fix.lobster
│   └── quick-task.lobster
└── credentials/                     # 认证信息 (自动生成)
    ├── whatsapp/
    └── telegram/
```

---

## 下一步

1. **自定义配置**
   - 修改 `~/.openclaw/workspace-pm/SOUL.md` 调整 PM Agent 的性格
   - 修改 `~/.openclaw/workspace-pm/USER.md` 添加你的个人信息

2. **添加更多工作流**
   - 复制现有工作流模板
   - 根据实际需求调整阶段和审批门

3. **监控和优化**
   - 定期查看 `openclaw status --usage` 了解 token 使用情况
   - 分析会话日志，优化 PM Agent 的提问策略

4. **集成 CI/CD**
   - 在工作流中调用 GitHub Actions 或 Jenkins
   - 自动化测试和部署流程

---

## 获取帮助

- **文档**: `docs/openclaw-config/README.md`
- **日志**: `openclaw logs --follow`
- **状态**: `openclaw status`
- **健康检查**: `openclaw doctor`

**社区资源**:
- OpenClaw GitHub: https://github.com/openclaw/openclaw
- Lobster GitHub: https://github.com/openclaw/lobster
- 文档: https://docs.openclaw.ai/

祝使用愉快！🦞
