# OpenClaw 配置方案总结

## 配置文件清单

本目录包含完整的 OpenClaw 配置，用于实现**需求沟通专家 + 任务分发**架构。

### 📁 文件结构

```
docs/openclaw-config/
├── README.md                        # 详细配置指南
├── QUICKSTART.md                    # 快速开始指南
├── SUMMARY.md                       # 本文件
├── openclaw.json                    # 主配置文件
├── workspace-pm/                    # PM Agent 工作空间
│   ├── AGENTS.md                    # 操作指南
│   ├── SOUL.md                      # 性格设定
│   └── USER.md                      # 用户信息
├── workspace-builder/               # (运行时创建)
└── workflows/                       # Lobster 工作流
    ├── project-implementation.lobster  # 完整实施流程
    ├── bug-fix.lobster                 # Bug 修复流程
    └── quick-task.lobster              # 快速任务流程
```

---

## 核心设计

### 架构图

```
用户 (WhatsApp/Telegram)
    │
    ▼
┌─────────────────────────┐
│   PM Agent (主角色)     │  ← 需求沟通专家
│  - 充分沟通需求         │     不执行代码
│  - 生成测试用例         │     只负责分发任务
│  - 等待用户确认         │
└────────┬────────────────┘
         │ 用户说"确认"
         ▼
┌─────────────────────────┐
│   Lobster Workflow      │  ← 任务分发引擎
│  - 多阶段审批门         │     (带审批流程)
│  - 并发任务控制         │
└────────┬────────────────┘
         │
    ┌────┼─────┬─────┐
    ▼    ▼     ▼     ▼
 Builder Tester Docs Reporter
 (子 Agent 并发执行)
```

### 关键特性

#### 1. PM Agent (需求专家)
- ✅ **充分沟通**: 通过多轮问答充分理解需求
- ✅ **测试先行**: 生成明确的测试用例
- ✅ **用户确认**: 必须等待用户明确确认
- ✅ **权限隔离**: 不能直接执行代码，只能分发任务

**工具权限**:
```json
"allow": ["read", "write", "edit", "sessions_spawn", "lobster"],
"deny": ["exec", "apply_patch", "process"]
```

#### 2. Builder Agent (执行专家)
- ✅ **沙箱运行**: 在 Docker 容器中执行，隔离风险
- ✅ **代码实施**: 可以修改代码和执行命令
- ✅ **质量保证**: 自动运行测试验证

**工具权限**:
```json
"allow": ["read", "write", "edit", "exec", "apply_patch"],
"deny": ["sessions_spawn", "message"]
```

#### 3. Tester Agent (测试专家)
- ✅ **只读执行**: 只能读取文件和执行测试
- ✅ **结果验证**: 确保测试结果可信
- ✅ **报告生成**: 生成详细的测试报告

**工具权限**:
```json
"allow": ["read", "exec"],
"deny": ["write", "edit", "sessions_spawn"]
```

---

## 工作流程

### 场景 1: 新功能开发

```
用户: "我希望添加批量 PO 应用功能"
  ↓
PM Agent: 提问澄清 (2-3 轮)
  - 批量的定义？
  - 失败处理策略？
  - 性能要求？
  ↓
PM Agent: 生成需求文档 + 测试用例
  - REQ-YYYY-MM-DD-batch-po.md
  - TC-001, TC-002, TC-003
  ↓
用户: "确认，开始实施"
  ↓
Lobster Workflow: project-implementation.lobster
  ├─ 阶段 1: 代码分析 (Sub-Agent)
  ├─ 阶段 2: 功能开发 (Builder) ← 审批门 1
  ├─ 阶段 3: 单元测试 (Tester)
  ├─ 阶段 4: 集成测试 ← 审批门 2
  ├─ 阶段 5: 结果汇报
  ├─ 阶段 6: 部署确认 ← 审批门 3
  ├─ 阶段 7: 生成文档
  └─ 阶段 8: 通知用户
```

### 场景 2: Bug 修复

```
用户: "po_apply 在冲突时崩溃"
  ↓
PM Agent: 收集信息
  - 复现步骤？
  - 错误信息？
  - 环境信息？
  ↓
PM Agent: 生成 Bug 报告 + 测试用例
  - BUG-YYYY-MM-DD-001.md
  - TC-BUG-001 (复现)
  - TC-BUG-002 (验证修复)
  ↓
用户: "确认，开始修复"
  ↓
Lobster Workflow: bug-fix.lobster
  ├─ 阶段 1: Bug 复现 (Tester)
  ├─ 阶段 2: 根因分析 (PM) ← 审批门 1
  ├─ 阶段 3: 修复实施 (Builder) ← 审批门 2
  ├─ 阶段 4: 回归测试 (Tester)
  ├─ 阶段 5: 验证通过 ← 审批门 3
  ├─ 阶段 6: 更新文档
  └─ 阶段 7: 通知用户
```

---

## 核心配置说明

### 1. openclaw.json

**关键配置项**:

```json
{
  "agents": {
    "list": [
      {
        "id": "pm",
        "tools": {
          "allow": [...],   // PM 只能读写和分发任务
          "deny": ["exec"]  // 不能执行代码
        }
      },
      {
        "id": "builder",
        "sandbox": {
          "mode": "all",    // 强制沙箱
          "scope": "agent"  // 独立容器
        }
      }
    ]
  },
  "bindings": [
    {
      "agentId": "pm",     // 所有消息路由到 PM Agent
      "match": {"channel": "whatsapp"}
    }
  ]
}
```

### 2. workspace-pm/AGENTS.md

定义 PM Agent 的行为规范：

**核心原则**:
1. **不要假设** - 必须通过对话确认需求
2. **测试先行** - 测试用例是需求的镜像
3. **明确审批** - 用户说"确认"才能进入下一阶段
4. **文档驱动** - 所有需求落实到文档

**禁止行为**:
- ❌ 未经确认就开始编码
- ❌ 跳过测试用例编写
- ❌ 假设用户需求

### 3. workspace-pm/SOUL.md

定义 PM Agent 的性格和沟通风格：

**性格特质**:
- 善于倾听、逻辑清晰
- 注重细节、沟通高效
- 结构化思维、测试先行

**沟通风格**:
- 开放式问题引导用户
- 重复需求确保理解一致
- 主动询问边界条件

### 4. Lobster 工作流

**project-implementation.lobster** (完整实施):
```yaml
9 个阶段 + 3 个审批门
- 代码分析 → 开发 → 测试 → 部署
- 每个关键点都需要用户确认
```

**bug-fix.lobster** (Bug 修复):
```yaml
7 个阶段 + 3 个审批门
- 复现 → 分析 → 修复 → 验证
- 快速修复，重点验证
```

**quick-task.lobster** (快速任务):
```yaml
3 个阶段 + 1 个审批门
- 执行 → 确认 → 通知
- 简单任务的快速路径
```

---

## 部署步骤 (简化版)

### 1. 安装依赖

```bash
# 安装 OpenClaw
npm install -g openclaw@latest

# 安装 Lobster (假设已有二进制)
# 或从源码构建
```

### 2. 复制配置

```bash
# 创建目录
mkdir -p ~/.openclaw/agents/{pm,builder,tester}/agent
mkdir -p ~/.openclaw/workspace-{pm,builder,tester}
mkdir -p ~/.openclaw/workflows

# 复制配置
cp openclaw.json ~/.openclaw/
cp workspace-pm/* ~/.openclaw/workspace-pm/
cp workflows/* ~/.openclaw/workflows/
```

### 3. 配置消息渠道

编辑 `~/.openclaw/openclaw.json`:

```json
{
  "channels": {
    "whatsapp": {
      "allowFrom": ["+8613800000000"]  // 替换为你的号码
    }
  }
}
```

### 4. 启动服务

```bash
# 前台运行 (调试用)
openclaw gateway

# 或安装为系统服务
openclaw onboard --install-daemon
```

### 5. 配对 WhatsApp

```bash
openclaw channels login
# 扫描二维码
```

---

## 使用示例

### 测试 PM Agent

**发送消息**:
```
你好
```

**预期回复**:
```
你好！我是 PM Assistant。

我的职责是帮助你充分理解需求、生成测试用例，并在确认后分发任务。

你可以：
1. 提出新功能需求
2. 报告 Bug
3. 查询项目状态

请问有什么可以帮助你的？
```

### 提出需求

**你**:
```
我希望添加一个命令，列出所有主板
```

**PM Agent**:
```
明白了。我想确认几个细节：

1. 列出主板的信息包括：
   - 主板名称？
   - 项目数量？
   - 配置文件路径？

2. 输出格式：
   - 简洁列表？
   - 详细表格？
   - JSON 格式？

3. 是否需要过滤和排序？

请详细说明，我会据此整理测试用例。
```

**你 (澄清)**:
```
1. 显示主板名称和项目数量
2. 简洁列表格式
3. 按名称排序
```

**PM Agent**:
```
根据我们的讨论，我整理了需求和测试用例：

## 需求概述
功能: board_list 命令
优先级: P2
影响范围: src/__main__.py (新增命令)

## 测试用例

TC-001: 正常列出主板
- 操作: python -m src board_list
- 期望: 显示所有主板和项目数量，按名称排序

TC-002: 空目录处理
- 前置: projects/ 目录为空
- 操作: python -m src board_list
- 期望: 友好提示 "没有找到主板"

TC-003: 权限错误
- 前置: projects/ 目录不可读
- 操作: python -m src board_list
- 期望: 清晰的错误提示

是否确认？确认后我将启动实施流程。
```

**你**:
```
确认
```

**PM Agent (启动工作流)**:
```
收到！我将启动任务分发流程：

预计完成时间: 15-20 分钟
关键里程碑:
1. 代码分析 (3 分钟)
2. 功能开发 (10 分钟)
3. 测试验证 (5 分钟)

我会在关键节点请求您的确认。
```

---

## 监控和调试

### 查看状态

```bash
# Gateway 状态
openclaw status

# Agent 列表
openclaw agents list

# 会话列表
openclaw sessions list
```

### 查看日志

```bash
# 实时日志
openclaw logs --follow

# 调试日志
openclaw logs --level debug --follow

# 特定会话日志
openclaw sessions --session-id <id> history
```

### 工作流调试

```bash
# 验证工作流语法
lobster validate ~/.openclaw/workflows/project-implementation.lobster

# 手动运行工作流 (测试)
lobster run ~/.openclaw/workflows/quick-task.lobster \
  --args-json '{"task_description":"测试","agent_id":"pm"}'
```

---

## 故障排查

| 问题 | 检查 | 解决 |
|------|------|------|
| PM Agent 直接执行代码 | `openclaw.json` 中 tools.deny | 确保包含 "exec" |
| 工作流无法启动 | Lobster 是否在 PATH | `which lobster` |
| 子 Agent 无权限 | sandbox 配置 | 检查 workspaceAccess |
| 消息发送失败 | allowFrom 配置 | 检查号码是否在白名单 |

---

## 扩展和定制

### 添加新 Agent

例如添加部署 Agent：

```json
{
  "agents": {
    "list": [
      {
        "id": "deployer",
        "workspace": "~/.openclaw/workspace-deployer",
        "tools": {"allow": ["read", "exec"]}
      }
    ]
  }
}
```

### 创建自定义工作流

复制现有工作流模板：

```bash
cp ~/.openclaw/workflows/quick-task.lobster \
   ~/.openclaw/workflows/my-workflow.lobster

# 编辑并调整阶段
```

### 调整审批策略

根据任务重要性调整审批门：

```yaml
# 高风险: 多重审批
- id: deploy_production
  approval: required
  prompt: "即将部署到生产，请确认"

# 低风险: 可选审批
- id: update_docs
  approval: optional
  prompt: "文档更新完成，是否审查？"
```

---

## 文档导航

- **[README.md](README.md)**: 详细配置指南和架构说明
- **[QUICKSTART.md](QUICKSTART.md)**: 快速开始和一键部署脚本
- **[openclaw.json](openclaw.json)**: 主配置文件
- **[workspace-pm/AGENTS.md](workspace-pm/AGENTS.md)**: PM Agent 操作指南
- **[workspace-pm/SOUL.md](workspace-pm/SOUL.md)**: PM Agent 性格设定
- **[workspace-pm/USER.md](workspace-pm/USER.md)**: 用户信息
- **[workflows/](workflows/)**: Lobster 工作流目录

---

## 关键要点

### ✅ PM Agent 的核心职责

1. **充分沟通** - 通过多轮对话理解需求
2. **生成测试用例** - 测试用例是需求的镜像
3. **等待确认** - 用户说"确认"才能分发任务
4. **只负责分发** - 不直接执行代码

### ✅ 工作流的审批门

- 关键阶段需要用户确认
- 失败时可以取消或回滚
- 所有操作都有日志记录

### ✅ 权限隔离

- PM Agent: 读写 + 分发
- Builder Agent: 沙箱执行
- Tester Agent: 只读 + 测试

### ✅ 可追溯性

- 所有需求有文档
- 所有测试用例有记录
- 所有操作有日志

---

## 下一步

1. ✅ 部署 OpenClaw 和 Lobster
2. ✅ 配置消息渠道
3. ✅ 测试 PM Agent 对话流程
4. ✅ 运行示例工作流
5. 📝 根据实际需求调整配置
6. 📝 创建自定义工作流
7. 📝 监控和优化性能

---

## 联系和反馈

- **项目**: ProjectManager
- **作者**: Wang Guanran
- **仓库**: https://github.com/wangguanran/ProjectManager

如有问题，请查看日志：
```bash
openclaw logs --follow
openclaw doctor
```

祝使用愉快！🦞
