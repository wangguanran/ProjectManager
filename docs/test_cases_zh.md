# 测试用例（中文入口）

> 说明: 项目当前的完整、细化测试用例以 `docs/test_cases_en.md` 为准（包含 Case ID、前置条件、步骤、预期结果）。
>
> 本文件保留为中文入口与关键用例摘要，避免与英文版本重复维护导致不一致。

## 快速验证（建议每次提交前执行）

```bash
make format
make lint
pytest
```

## 关键用例摘要（详细步骤见英文用例）

### CLI

- CLI-001: `--help` 显示 operations 与插件 flags
- CLI-002: `--version` 输出版本（可能包含 `+g<shortsha>`）
- CLI-003/004/005: operation 精确匹配、模糊匹配、歧义提示

### PO（Patch/Override）

- PO-005: patch 应用成功（真实 `git apply`）
- PO-006: patch 应用失败应中止且不遗留已应用记录（例如 `.cache/po_applied/...json`，避免重试被错误跳过）

### Diff

- BUILD-001/002: `project_diff` 单仓/多仓打包结构正确（详细结构以英文用例为准）
