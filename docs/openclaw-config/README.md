# OpenClaw 配置指南：需求沟通专家 + 任务分发架构

## 架构概览

本配置实现了一个**需求沟通专家 (Product Manager)** 作为主 Agent，负责与用户充分沟通、确认需求、生成测试用例，待用户确认后再通过 **Lobster 工作流**分发任务给执行 Agent。

```
用户 (WhatsApp/Telegram)
    │
    ▼
┌─────────────────────────┐
│   主 Agent: PM          │  ← 需求沟通专家
│  - 提问澄清需求         │
│  - 生成测试用例         │
│  - 等待用户确认         │
└────────┬────────────────┘
         │ 用户说"确认"或"开始实施"
         ▼
┌─────────────────────────┐
│   Lobster Workflow      │  ← 任务分发引擎
│  - 多阶段审批门         │
│  - 并发任务控制         │
└────────┬────────────────┘
         │
    ┌────┼─────┬─────┐
    ▼    ▼     ▼     ▼
 Builder Tester Docs Reporter
 独立沙箱执行
```

---

## 部署步骤

### 1. 安装 OpenClaw

```bash
# 安装 OpenClaw (需要 Node.js >= 22)
npm install -g openclaw@latest

# 验证安装
openclaw --version
```

### 2. 安装 Lobster

```bash
# 克隆 Lobster 仓库 (假设仓库地址)
git clone https://github.com/openclaw/lobster.git
cd lobster
make install

# 验证安装
lobster --version
```

### 3. 配置 OpenClaw

```bash
# 创建配置目录
mkdir -p ~/.openclaw
mkdir -p ~/.openclaw/agents/{pm,builder,tester}/agent

# 复制配置文件
cp docs/openclaw-config/openclaw.json ~/.openclaw/

# 创建工作空间
mkdir -p ~/.openclaw/workspace-pm
mkdir -p ~/.openclaw/workspace-builder
mkdir -p ~/.openclaw/workspace-tester

# 复制工作空间配置
cp docs/openclaw-config/workspace-pm/* ~/.openclaw/workspace-pm/
```

### 4. 创建工作空间文件

为每个工作空间创建必要的文件：

```bash
# PM Agent 工作空间
cd ~/.openclaw/workspace-pm
mkdir -p memory/requirements memory/test-cases

# 创建 TOOLS.md (可选)
cat > TOOLS.md <<'EOF'
# TOOLS.md - PM Agent 工具说明

## 项目路径
- ProjectManager: /home/wangguanran/ProjectManager
- 测试命令: pytest tests/ -v

## Lobster 工作流
- 完整实施流程: workflows/project-implementation.lobster
- Bug 修复: workflows/bug-fix.lobster
- 快速任务: workflows/quick-task.lobster
EOF

# Builder Agent 工作空间
cd ~/.openclaw/workspace-builder
cat > AGENTS.md <<'EOF'
# Builder Agent

你是代码实施专家，负责根据需求文档实现功能。

## 核心职责
1. 阅读需求文档
2. 修改代码实现功能
3. 确保代码质量和测试覆盖

## 工作流程
1. 分析需求涉及的文件
2. 实施代码修改
3. 编写单元测试
4. 运行测试验证
5. 提交代码并汇报

## 质量标准
- 遵循 PEP 8 规范
- 添加类型注解
- 编写文档字符串
- 单元测试覆盖率 > 80%
EOF

# Tester Agent 工作空间
cd ~/.openclaw/workspace-tester
cat > AGENTS.md <<'EOF'
# Tester Agent

你是测试专家，负责执行测试用例并报告结果。

## 核心职责
1. 执行测试用例
2. 验证功能正确性
3. 报告测试结果

## 测试类型
- 单元测试
- 集成测试
- 回归测试

## 报告格式
- 测试用例 ID
- 测试结果 (PASS/FAIL)
- 错误信息
- 日志输出
EOF
```

### 5. 配置消息渠道

#### WhatsApp 配置

```bash
# 启动 Gateway
openclaw gateway

# 在另一个终端配对 WhatsApp
openclaw channels login
# 扫描二维码
```

#### Telegram 配置

```bash
# 创建 Telegram Bot (访问 @BotFather)
# 获取 Bot Token

# 在 openclaw.json 中配置
{
  "channels": {
    "telegram": {
      "token": "YOUR_BOT_TOKEN",
      "dmPolicy": "allowlist",
      "allowFrom": ["@your_username"]
    }
  }
}
```

### 6. 复制工作流文件

```bash
mkdir -p ~/.openclaw/workflows
cp docs/openclaw-config/workflows/*.lobster ~/.openclaw/workflows/
```

### 7. 设置权限

```bash
# 确保 Lobster 可执行
chmod +x $(which lobster)

# 确保工作流文件可读
chmod 644 ~/.openclaw/workflows/*.lobster
```

### 8. 启动服务

```bash
# 前台启动 (用于调试)
openclaw gateway

# 或安装为系统服务
openclaw onboard --install-daemon
```

---

## 配置文件说明

### openclaw.json

核心配置包含三个 Agent：

#### 1. PM Agent (主 Agent)
```json
{
  "id": "pm",
  "tools": {
    "allow": [
      "read", "write", "edit",      // 文件操作
      "sessions_spawn",              // 创建子 Agent
      "lobster",                     // 工作流
      "message"                      // 发送消息
    ],
    "deny": [
      "exec",                        // 禁止直接执行命令
      "apply_patch"                  // 禁止直接修改代码
    ]
  }
}
```

**关键特性**：
- 只能读写文档，不能执行代码
- 可以启动子 Agent 和工作流
- 必须通过 Lobster 分发任务

#### 2. Builder Agent (执行 Agent)
```json
{
  "id": "builder",
  "sandbox": {
    "mode": "all",                   // 强制沙箱
    "scope": "agent"                 // 独立容器
  },
  "tools": {
    "allow": ["read", "write", "edit", "exec", "apply_patch"],
    "deny": ["sessions_spawn", "message"]
  }
}
```

**关键特性**：
- 在沙箱中执行，隔离风险
- 可以修改代码和执行命令
- 不能创建子 Agent 或发送消息

#### 3. Tester Agent (测试 Agent)
```json
{
  "id": "tester",
  "tools": {
    "allow": ["read", "exec"],       // 只能读取和执行测试
    "deny": ["write", "edit"]        // 禁止修改代码
  }
}
```

**关键特性**：
- 只读权限
- 只能执行测试命令
- 确保测试结果可信

### Lobster 工作流

#### project-implementation.lobster

完整的项目实施流程，包含多个审批门：

```yaml
阶段 1: 准备工作
阶段 2: 代码分析 (Sub-Agent)
阶段 3: 开发实施 (Builder Agent) ← 审批门 1
阶段 4: 单元测试 (Tester Agent)
阶段 5: 集成测试 ← 审批门 2
阶段 6: 结果汇报
阶段 7: 部署确认 ← 审批门 3
阶段 8: 生成文档
阶段 9: 完成通知
```

#### bug-fix.lobster

Bug 修复流程：

```yaml
阶段 1: Bug 复现 (Tester)
阶段 2: 根因分析 (PM) ← 审批门 1
阶段 3: 修复实施 (Builder) ← 审批门 2
阶段 4: 回归测试 (Tester)
阶段 5: 验证通过 ← 审批门 3
阶段 6: 更新文档
阶段 7: 通知用户
```

#### quick-task.lobster

快速任务流程（简化版）：

```yaml
阶段 1: 任务执行
阶段 2: 结果确认 ← 审批门
阶段 3: 通知
```

---

## 使用示例

### 场景 1: 提出新功能需求

**用户输入**：
```
我希望 ProjectManager 支持批量应用 PO
```

**PM Agent 响应**：
```
明白了。我想确认几个细节：

1. 批量应用是指同时应用多个 PO 到一个项目，还是应用一个 PO 到多个项目？
2. 如果某个 PO 应用失败，是继续还是回滚整体？
3. 是否需要进度提示和日志记录？
4. 预期的使用场景是什么？
```

**用户澄清**：
```
1. 同时应用多个 PO 到一个项目
2. 任何失败都应该回滚
3. 需要实时进度和日志
4. 用于快速切换不同配置组合
```

**PM Agent 整理需求**：
```
根据我们的讨论，我整理了需求和测试用例：

## 需求概述
功能: 批量 PO 应用
优先级: P1
影响范围: src/po_apply.py, src/po_manager.py

## 功能详情
1. 命令: python -m src po_apply_batch <project> <po1> <po2> ...
2. 原子操作: 全部成功或全部回滚
3. 实时进度显示
4. 详细日志记录

## 测试用例

### TC-001: 正常批量应用
- 前置: 项目 myproject，3 个有效 PO
- 操作: po_apply_batch myproject po1 po2 po3
- 期望: 所有 PO 成功应用

### TC-002: 部分失败回滚
- 前置: po2 包含冲突文件
- 操作: po_apply_batch myproject po1 po2 po3
- 期望: 检测冲突，回滚 po1，po2/po3 未应用

### TC-003: 空间不足
- 前置: 磁盘空间 < 100MB
- 操作: po_apply_batch myproject po_large
- 期望: 提前检测，拒绝应用

是否确认？确认后我将启动实施流程。
```

**用户确认**：
```
确认无误，开始实施
```

**PM Agent 启动工作流**：
```
收到！我将启动任务分发流程：

[调用 Lobster 工作流]
{
  "action": "run",
  "pipeline": "~/.openclaw/workflows/project-implementation.lobster",
  "argsJson": {
    "requirement_file": "~/.openclaw/workspace-pm/memory/requirements/2026-02-03-batch-po-apply.md",
    "test_cases_file": "~/.openclaw/workspace-pm/memory/test-cases/TC-001-batch-po-apply.md",
    "project_path": "/home/wangguanran/ProjectManager"
  }
}

预计完成时间: 30-45 分钟
关键里程碑:
1. 代码分析 (5 分钟)
2. 功能开发 (20 分钟)
3. 测试验证 (10 分钟)
4. 文档生成 (5 分钟)

我会在关键节点请求您的确认。
```

**工作流执行 (审批门 1)**：
```
[Builder Agent 完成开发]

分析完成。是否开始开发实施？

修改的文件:
- src/po_apply.py (新增 apply_batch 函数)
- src/po_manager.py (新增 rollback 逻辑)
- tests/test_po_apply.py (新增测试用例)

请确认是否继续。
```

**用户**：
```
确认
```

**工作流执行 (审批门 2)**：
```
[Tester Agent 完成单元测试]

单元测试通过。是否继续集成测试？

测试结果:
- TC-001: PASSED
- TC-002: PASSED
- TC-003: PASSED
覆盖率: 87%

请确认是否继续。
```

**用户**：
```
确认
```

**工作流完成**：
```
✅ 项目实施完成

需求: 批量 PO 应用
测试: 全部通过 (3/3)
文档: 已更新 CHANGELOG.md 和 docs/user-guide/

详细报告已保存到:
~/.openclaw/workspace-pm/memory/2026-02-03.md
```

---

### 场景 2: 报告 Bug

**用户输入**：
```
po_apply 命令在文件冲突时崩溃，提示 FileNotFoundError
```

**PM Agent 响应**：
```
我记录下这个 bug。请问：

1. 能稳定复现吗？如果能，具体操作步骤是什么？
2. 完整的错误信息是什么？
3. 发生在什么环境？
   - 主板型号:
   - 项目名称:
   - PO 名称:
4. 冲突的文件路径是什么？

这将帮助我生成准确的测试用例。
```

**用户补充**：
```
1. 可以复现，步骤：
   - po_new myproject po_test
   - 手动修改 po_test/overrides/test.txt
   - po_apply myproject po_test
2. 错误: FileNotFoundError: test.txt not found
3. 主板 board01，项目 project1，PO po_test
4. projects/board01/project1/test.txt
```

**PM Agent 整理**：
```
根据您的描述，我整理了 Bug 信息和测试用例：

## Bug 报告
- ID: BUG-2026-02-03-001
- 描述: po_apply 在处理冲突文件时抛出 FileNotFoundError
- 严重程度: P1 (影响正常使用)
- 影响范围: src/po_apply.py

## 根因假设
可能是路径解析错误，或者文件检查逻辑缺失

## 测试用例

### TC-BUG-001: 复现 Bug
- 前置: po_test/overrides/test.txt 存在，但 project1/test.txt 不存在
- 操作: po_apply myproject po_test
- 期望: 抛出 FileNotFoundError

### TC-BUG-002: 修复验证
- 前置: 修复后的代码
- 操作: 同上
- 期望: 友好的错误提示，不崩溃

是否确认开始修复流程？
```

**用户**：
```
确认
```

**PM Agent 启动 Bug 修复流程**：
```
收到！我将启动 Bug 修复流程：

[调用 Lobster 工作流]
{
  "action": "run",
  "pipeline": "~/.openclaw/workflows/bug-fix.lobster",
  "argsJson": {
    "bug_description": "po_apply 在文件冲突时崩溃",
    "test_case_id": "TC-BUG-001",
    "project_path": "/home/wangguanran/ProjectManager"
  }
}

流程阶段:
1. Bug 复现 (Tester)
2. 根因分析 (PM)
3. 修复实施 (Builder)
4. 回归测试 (Tester)
5. 验证完成

预计完成时间: 15-20 分钟
```

---

## 关键配置说明

### 1. 审批门机制

Lobster 工作流中的 `approval: required` 会暂停流程，等待用户确认：

```yaml
- id: build
  command: ...
  approval: required
  prompt: "分析完成。是否开始开发实施？"
```

用户可以通过以下方式响应：
- `确认` / `开始` / `继续` → 继续执行
- `取消` / `停止` → 取消工作流

### 2. 并发控制

通过 `subagents.maxConcurrent` 控制并发数：

```json
{
  "agents": {
    "list": [{
      "id": "pm",
      "subagents": {
        "maxConcurrent": 3  // 最多 3 个并发子 Agent
      }
    }]
  }
}
```

### 3. 沙箱隔离

Builder 和 Tester Agent 运行在独立沙箱中：

```json
{
  "sandbox": {
    "mode": "all",           // 强制沙箱
    "scope": "agent",        // 每个 Agent 独立容器
    "docker": {
      "setupCommand": "apt-get update && apt-get install -y git python3"
    }
  }
}
```

### 4. 工具权限

PM Agent 不能直接执行代码，必须通过工作流分发：

```json
{
  "tools": {
    "allow": ["read", "write", "sessions_spawn", "lobster"],
    "deny": ["exec", "apply_patch"]  // 禁止直接执行
  }
}
```

---

## 故障排查

### 问题 1: Lobster 工作流无法启动

**症状**：
```
Error: lobster binary not found
```

**解决**：
```bash
# 检查 Lobster 是否在 PATH
which lobster

# 如果不在，指定绝对路径
{
  "action": "run",
  "lobsterPath": "/usr/local/bin/lobster",
  "pipeline": "..."
}
```

### 问题 2: 子 Agent 无法访问文件

**症状**：
```
Error: Permission denied
```

**解决**：
```bash
# 确保工作空间权限
chmod -R 755 ~/.openclaw/workspace-*

# 检查沙箱配置
# 如果需要访问宿主文件，设置 workspaceAccess: "rw"
{
  "sandbox": {
    "workspaceAccess": "rw"
  }
}
```

### 问题 3: 工作流超时

**症状**：
```
Error: lobster subprocess timed out
```

**解决**：
```yaml
# 增加超时时间
- id: long_task
  command: ...
  runTimeoutSeconds: 1200  # 20 分钟
```

### 问题 4: PM Agent 直接执行了代码

**检查配置**：
```json
// 确保 PM Agent 的 tools.deny 包含 exec
{
  "agents": {
    "list": [{
      "id": "pm",
      "tools": {
        "deny": ["exec", "apply_patch", "process"]
      }
    }]
  }
}
```

---

## 最佳实践

### 1. 需求文档模板

在 `~/.openclaw/workspace-pm/memory/requirements/` 使用统一模板：

```markdown
# REQ-YYYY-MM-DD-<feature-name>

## 需求概述
- 功能名称:
- 优先级: P0/P1/P2
- 影响范围:

## 功能详情
1. [详细描述]
2. [用户场景]

## 边界条件
- [异常情况]
- [性能要求]

## 依赖关系
- [依赖的其他功能]

## 验收标准
- [ ] 功能正常
- [ ] 测试通过
- [ ] 文档完整
```

### 2. 测试用例模板

在 `~/.openclaw/workspace-pm/memory/test-cases/` 使用标准格式：

```markdown
# TC-<ID>: <场景描述>

## 前置条件
- [环境准备]

## 测试步骤
1. [操作 1]
2. [操作 2]

## 期望结果
- [断言 1]
- [断言 2]

## 实际结果
- [待填写]

## 状态
- [ ] PASSED
- [ ] FAILED
- [ ] BLOCKED
```

### 3. 工作流选择指南

| 场景 | 使用工作流 | 特点 |
|------|-----------|------|
| 新功能开发 | `project-implementation.lobster` | 完整流程，多个审批门 |
| Bug 修复 | `bug-fix.lobster` | 快速修复，重点验证 |
| 简单任务 | `quick-task.lobster` | 单步执行，快速完成 |
| 文档更新 | 直接使用 PM Agent | 无需工作流 |

### 4. 日志管理

每日在 `memory/YYYY-MM-DD.md` 记录：
```markdown
# 2026-02-03

## 处理的需求
- REQ-001: 批量 PO 应用 (已确认，实施中)
- BUG-001: po_apply 崩溃 (已修复)

## 测试用例
- TC-001: PASSED
- TC-002: PASSED
- TC-BUG-001: PASSED

## 待跟进
- [ ] REQ-001 集成测试
- [ ] 文档更新
```

---

## 进阶配置

### 1. 添加更多执行 Agent

例如添加部署 Agent：

```json
{
  "agents": {
    "list": [
      {
        "id": "deployer",
        "name": "Deployer",
        "workspace": "~/.openclaw/workspace-deployer",
        "tools": {
          "allow": ["read", "exec"],
          "deny": ["write", "edit"]
        }
      }
    ]
  }
}
```

### 2. 自定义审批策略

根据任务重要性调整审批门：

```yaml
# 高风险操作: 多重审批
- id: deploy_production
  approval: required
  prompt: "即将部署到生产环境，请确认所有测试已通过"

# 低风险操作: 批量审批
- id: update_docs
  approval: optional
  prompt: "文档更新完成，是否需要审查？"
```

### 3. 集成 CI/CD

在工作流中调用 CI/CD 流程：

```yaml
- id: ci_build
  command: |
    curl -X POST https://ci.example.com/build \
      -H "Authorization: Bearer $CI_TOKEN" \
      -d '{"project": "ProjectManager", "branch": "main"}'
```

### 4. 通知渠道扩展

支持多种通知方式：

```yaml
- id: notify_all
  command: |
    # WhatsApp
    openclaw.invoke --tool message --args-json '{"provider":"whatsapp", ...}'
    
    # Telegram
    openclaw.invoke --tool message --args-json '{"provider":"telegram", ...}'
    
    # Email (通过外部工具)
    mail -s "任务完成" user@example.com < report.txt
```

---

## 安全注意事项

### 1. 敏感信息保护

- 不要在配置文件中硬编码密码和 Token
- 使用环境变量或 `~/.openclaw/credentials/`
- 测试用例中避免真实的生产数据

### 2. 权限最小化

- PM Agent: 只读 + 工作流启动
- Builder Agent: 沙箱 + 受限工具
- Tester Agent: 只读 + 执行测试

### 3. 审计日志

所有工作流执行都会记录在：
```
~/.openclaw/agents/<agentId>/sessions/<sessionId>.transcript
```

定期审查日志，识别异常行为。

---

## 总结

这套配置实现了：

✅ **需求沟通优先**: PM Agent 必须充分确认需求才能分发任务
✅ **测试用例驱动**: 每个需求都有明确的测试用例
✅ **多重审批门**: 关键阶段需要用户确认
✅ **沙箱隔离**: 执行 Agent 在安全环境中运行
✅ **权限分离**: 不同 Agent 有不同的工具权限
✅ **可追溯性**: 所有操作都有日志记录

**下一步**：
1. 根据实际需求调整 `allowFrom` 中的联系方式
2. 测试工作流，验证审批门是否正常工作
3. 根据使用情况优化超时和并发设置
4. 添加更多自定义工作流

有问题随时查看日志：
```bash
openclaw logs --follow
openclaw agents list --bindings
openclaw sessions list
```
