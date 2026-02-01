# CrewAI 工作流

## 简介

本项目使用 CrewAI 框架实现多 Agent 协作开发流程，模拟真实的软件开发生命周期。

## Agent 列表

| Agent | 角色 | 职责 |
|-------|------|------|
| 需求分析 Agent | 需求分析师 | 与用户对话明确需求，生成测试用例，更新 docs/test_cases_zh.md |
| 架构师 Agent | 系统架构师 | 分解任务，记录到 docs/tasks.md，协调各 Agent |
| 编码 Agent | 后端开发工程师 | 根据任务要求编写代码 |
| Review Agent | 代码审核工程师 | 审核代码质量 |
| 测试 Agent | 测试工程师 | 编写测试用例 |
| 执行 Agent | CI/CD 工程师 | 运行测试，验证结果，提交代码 |

## 工作流程

```
用户需求 → 需求分析 → 架构设计 → 编码 → Review → 测试 → 执行 → 完成
               ↓           ↓        ↓       ↓       ↓
            测试用例    任务分解   代码     审核    测试用例  测试结果
```

## 使用方法

### 1. 安装依赖

```bash
pip install crewai
```

### 2. 运行工作流

```bash
python run_crewai.py "你的需求描述"
```

示例:
```bash
python run_crewai.py "添加主板删除功能"
python run_crewai.py "支持多语言文档"
python run_crewai.py "优化PO应用性能"
```

## 配置文件

- `crewai_agents/config/agents.yaml` - Agent 配置
- `crewai_agents/config/tasks.yaml` - Task 配置
- `crewai_agents/crew.py` - 主工作流逻辑

## 输出文件

- `docs/tasks.md` - 任务分解文档
- `docs/test_cases_zh.md` - 测试用例文档

## 任务状态

任务状态流转:
```
pending → in_progress → review → testing → done
              ↓              ↓          ↓
          (编码中)      (审核中)    (测试中)
              ↓              ↓          ↓
           退回         通过/不通过    通过/退回
```

## 注意事项

1. **需求分析阶段**: 如果需求与现有功能冲突，会提示用户确认
2. **编码阶段**: 只能修改与任务相关的代码，不得添加额外功能
3. **Review 阶段**: 必须通过 pylint 检查，代码覆盖率不降低
4. **测试阶段**: 测试用例需要覆盖正常流程、边界条件和异常场景
5. **执行阶段**: 测试通过后自动生成 commit message 并推送

## Commit Message 规范

```
<type>(<scope>): <subject>

Types:
- feat: 新功能
- fix: 修复 bug
- docs: 文档更新
- style: 代码格式
- refactor: 重构
- test: 测试相关
- chore: 其他
```
