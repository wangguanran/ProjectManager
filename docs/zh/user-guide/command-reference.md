# ProjectManager 命令参考

## 概述

本文档提供了 ProjectManager 所有可用命令的详细参考，包括语法、参数、选项和示例。

## 基本语法

```bash
python -m src <命令> <参数> [选项]
```

## 全局选项

所有命令都支持以下全局选项：

| 选项 | 描述 | 示例 |
|------|------|------|
| `--version` | 显示程序版本 | `python -m src --version` |
| `--help` | 显示帮助信息 | `python -m src --help` |
| `--perf-analyze` | 启用性能分析 | `python -m src --perf-analyze po_apply proj1` |

## 项目管理命令

### `project_new` - 创建新项目

**状态**: ✅ 已实现

**语法**:
```bash
python -m src project_new <项目名称>
```

**描述**: 使用指定配置创建新项目。

**参数**:
- `项目名称`（必需）: 要创建的项目名称

**配置**: 项目配置存储在主板特定的 `.ini` 文件中。

**示例**:
```bash
python -m src project_new myproject
```

---

### `project_del` - 删除项目

**状态**: ✅ 已实现

**语法**:
```bash
python -m src project_del <项目名称>
```

**描述**: 删除指定的项目目录并更新配置文件中的状态。

**参数**:
- `项目名称`（必需）: 要删除的项目名称

**示例**:
```bash
python -m src project_del myproject
```

---

### `project_build` - 构建项目

**状态**: ✅ 已实现

**语法**:
```bash
python -m src project_build <项目名称> [--emit-plan [<path>]]
```

**描述**: 根据配置构建指定项目。

**参数**:
- `项目名称`（必需）: 要构建的项目名称

**选项**:
- `--emit-plan`: 输出机器可读的 JSON 执行计划到 stdout（或写入 `<path>`），且不会真正执行构建步骤。

**示例**:
```bash
python -m src project_build myproject
```

---

### `project_diff` - 生成仓库 diff 快照

**状态**: ✅ 已实现

**语法**:
```bash
python -m src project_diff <项目名称> [--keep-diff-dir] [--dry-run] [--emit-plan [<path>]]
```

**描述**: 在 `.cache/build/<项目名称>/<时间戳>/diff` 生成 diff 目录，并归档为 `diff_<项目>_<时间戳>.tar.gz`。

**参数**:
- `项目名称`（必需）: 要生成 diff 的项目名称

**选项**:
- `--keep-diff-dir`: 创建 tar.gz 后保留 diff 目录。
- `--dry-run`: 仅打印计划执行的动作，不创建文件/目录。
- `--emit-plan`: 输出机器可读的 JSON 执行计划到 stdout（或写入 `<path>`），且不会写入任何 diff 输出。

**示例**:
```bash
python -m src project_diff myproject --keep-diff-dir
```

---

### `snapshot_create` - 生成工作区快照（锁文件）

**状态**: ✅ 已实现

**语法**:
```bash
python -m src snapshot_create <项目名称> [--out <path>]
```

**描述**: 生成确定性的 JSON 快照，包含各仓库 HEAD SHA 以及指定项目解析后的启用 PO 列表（用于可复现性）。

**参数**:
- `项目名称`（必需）: 需要记录启用 PO 集合的项目名称

**选项**:
- `--out`: 将快照写入指定路径（缺省则输出到 stdout）

**示例**:
```bash
python -m src snapshot_create myproject --out snapshot.json
```

---

### `snapshot_validate` - 校验工作区与快照一致性

**状态**: ✅ 已实现

**语法**:
```bash
python -m src snapshot_validate <快照路径> [--json]
```

**描述**: 比对当前仓库 HEAD SHA 与启用 PO 集合是否与快照一致；当检测到漂移时以非 0 退出。

**参数**:
- `快照路径`（必需）: `snapshot_create` 生成的快照 JSON 路径

**选项**:
- `--json`: 输出机器可读的 JSON 报告到 stdout

**示例**:
```bash
python -m src snapshot_validate snapshot.json --json
```

---

### `project_pre_build` - 预构建阶段

**状态**: ✅ 已实现

**语法**:
```bash
python -m src project_pre_build <项目名称>
```

**描述**: `project_build` 的预构建阶段（应用 PO 并生成 diff 快照）。

**参数**:
- `项目名称`（必需）: 项目名称

**示例**:
```bash
python -m src project_pre_build myproject
```

---

### `project_do_build` - 构建阶段

**状态**: ✅ 已实现

**语法**:
```bash
python -m src project_do_build <项目名称>
```

**描述**: `project_build` 的构建阶段（当配置了 `PROJECT_BUILD_CMD` 时执行）。

**参数**:
- `项目名称`（必需）: 项目名称

**示例**:
```bash
python -m src project_do_build myproject
```

---

### `project_post_build` - 后构建阶段

**状态**: ✅ 已实现

**语法**:
```bash
python -m src project_post_build <项目名称>
```

**描述**: `project_build` 的后构建阶段（当配置了 `PROJECT_POST_BUILD_CMD` 时执行）。

**参数**:
- `项目名称`（必需）: 项目名称

**示例**:
```bash
python -m src project_post_build myproject
```

---

## 主板管理命令

### `board_new` - 创建新主板

**状态**: ✅ 已实现

**语法**:
```bash
python -m src board_new <主板名称>
```

**描述**: 创建新主板并初始化目录结构。

**参数**:
- `主板名称`（必需）: 要创建的主板名称

**创建的目录结构**:
```
projects/<主板名称>/
  <主板名称>.ini
  po/
```

**示例**:
```bash
python -m src board_new myboard
```

---

### `board_del` - 删除主板

**状态**: ✅ 已实现

**语法**:
```bash
python -m src board_del <主板名称>
```

**描述**: 删除指定的主板及其所有项目。

**参数**:
- `主板名称`（必需）: 要删除的主板名称

**示例**:
```bash
python -m src board_del myboard
```

---

## PO（补丁/覆盖）管理命令

### `po_apply` - 应用补丁和覆盖

**状态**: ✅ 已实现

**语法**:
```bash
python -m src po_apply <项目名称> [--dry-run] [--emit-plan [<path>]] [--force] [--reapply] [--po <po1,po2>]
```

**描述**: 为指定项目应用所有配置的补丁和覆盖。

**参数**:
- `项目名称`（必需）: 要应用PO的项目名称

**选项**:
- `--dry-run`: 仅打印计划执行的动作，不修改文件。
- `--emit-plan`: 输出机器可读的 JSON 执行计划到 stdout（或写入 `<path>`），且不会修改仓库内容。
- `--force`: 允许执行带破坏性的操作（例如覆盖 `.remove` 删除），并允许 custom copy 目标路径位于工作区/仓库之外。
- `--reapply`: 即使已存在已应用记录，也强制重新应用（成功后会覆盖对应记录文件）。
- `--po`: 仅应用指定的 PO（从 `PROJECT_PO_CONFIG` 中筛选，逗号/空格分隔）。

**流程**:
1. 从项目配置读取 `PROJECT_PO_CONFIG`
2. 解析PO配置（支持包含/排除）
3. 使用 `git apply` 应用补丁
4. 将覆盖文件复制到目标位置
5. 在每个目标仓库根目录下写入已应用记录来跟踪状态（例如：`<repo>/.cache/po_applied/<board>/<project>/<po>.json`）

**配置格式**:
```
PROJECT_PO_CONFIG=po_test01 po_test02 -po_test03 po_test04[file1 file2]
```
- `po_test01`: 应用PO
- `-po_test03`: 排除PO
- `po_test04[file1 file2]`: 应用PO但排除特定文件

**示例**:
```bash
python -m src po_apply myproject
```

---

### `po_revert` - 回滚补丁和覆盖

**状态**: ✅ 已实现

**语法**:
```bash
python -m src po_revert <项目名称> [--dry-run] [--emit-plan [<path>]] [--po <po1,po2>]
```

**描述**: 回滚指定项目的所有已应用补丁和覆盖，并清理已应用记录，使后续可再次应用。

**参数**:
- `项目名称`（必需）: 要回滚PO的项目名称

**选项**:
- `--dry-run`: 仅打印计划执行的动作，不修改文件。
- `--emit-plan`: 输出机器可读的 JSON 执行计划到 stdout（或写入 `<path>`），且不会修改仓库内容。
- `--po`: 仅回滚指定的 PO（从 `PROJECT_PO_CONFIG` 中筛选，逗号/空格分隔）。

**流程**:
1. 从项目配置读取 `PROJECT_PO_CONFIG`
2. 使用 `git apply --reverse` 回滚补丁
3. 删除覆盖文件（如果被git跟踪则从git恢复）
4. 清理每个目标仓库根目录下的已应用记录（例如：`<repo>/.cache/po_applied/<board>/<project>/<po>.json`），使后续可再次应用

**示例**:
```bash
python -m src po_revert myproject
```

---

### `po_analyze` - 分析 PO 冲突

**状态**: ✅ 已实现

**语法**:
```bash
python -m src po_analyze <项目名称> [--json] [--strict] [--po <po1,po2>]
```

**描述**: 分析启用的 PO 是否存在补丁目标或覆盖目标的重叠（适用于 CI gate 和评审前检查）。

**参数**:
- `项目名称`（必需）: 要分析 PO 的项目名称

**选项**:
- `--json`: 输出机器可读的 JSON 报告到 stdout
- `--strict`: 当检测到冲突时以非 0 退出
- `--po`: 仅分析指定的 PO（从 `PROJECT_PO_CONFIG` 中筛选，逗号/空格分隔）

**示例**:
```bash
python -m src po_analyze myproject --json --strict
```

---

### `po_new` - 创建新PO目录

**状态**: ✅ 已实现

**语法**:
```bash
python -m src po_new <项目名称> <po名称> [--force]
```

**描述**: 创建新的PO目录结构，并可选择性地用修改的文件填充它。

**参数**:
- `项目名称`（必需）: 项目名称
- `po名称`（必需）: 新PO的名称（必须以'po'开头，只能包含小写字母、数字、下划线）
- `--force`（可选）: 跳过确认提示并创建空目录结构

**功能**:
- 从git仓库中的修改文件进行交互式文件选择
- 支持 .repo 清单文件
- 自动仓库发现
- 从 `.gitignore` 和 `PROJECT_PO_IGNORE` 配置的文件忽略模式
- 为每个文件选择补丁或覆盖
- 自定义补丁命名

**创建的目录结构**:
```
projects/<主板名称>/po/<po名称>/
  patches/
  overrides/
```

**交互式流程**:
1. 扫描git仓库（支持 .repo 清单）
2. 列出每个仓库中的修改文件
3. 允许用户选择要包含的文件
4. 对于每个文件，用户选择：
   - 创建补丁（用于有修改的跟踪文件）
   - 创建覆盖（用于任何文件）
   - 跳过文件

**示例**:
```bash
# 创建PO并选择文件
python -m src po_new myproject po_feature1

# 强制创建空PO目录
python -m src po_new myproject po_feature1 --force
```

---

### `po_update` - 更新已有PO

**状态**: ✅ 已实现

**语法**:
```bash
python -m src po_update <项目名称> <po名称> [--force]
```

**描述**: 更新一个已存在的 PO（PO 目录必须已存在），复用 `po_new` 的交互流程。

**参数**:
- `项目名称`（必需）: 项目名称
- `po名称`（必需）: 要更新的 PO 名称
- `--force`（可选）: 跳过确认提示

**示例**:
```bash
python -m src po_update myproject po_feature1 --force
```

---

### `po_del` - 删除PO目录

**状态**: ✅ 已实现

**语法**:
```bash
python -m src po_del <项目名称> <po名称> [--force]
```

**描述**: 删除指定的PO目录并从所有项目配置中移除它。

**参数**:
- `项目名称`（必需）: 项目名称
- `po名称`（必需）: 要删除的PO名称
- `--force`（可选）: 跳过确认提示

**流程**:
1. 显示目录内容和使用该PO的项目
2. 从 `.ini` 文件中的所有项目配置中移除PO
3. 删除PO目录和所有内容
4. 如果没有剩余PO，则删除空的 `po/` 目录

**安全功能**:
- 显示受影响项目的确认提示
- 显示要删除内容的目录树
- 自动清理空目录

**示例**:
```bash
# 删除PO并确认
python -m src po_del myproject po_feature1

# 强制删除PO
python -m src po_del myproject po_feature1 --force
```

---

### `po_list` - 列出配置的PO

**状态**: ✅ 已实现

**语法**:
```bash
python -m src po_list <项目名称> [--short] [--po <po1,po2>] [--json]
```

**描述**: 列出指定项目的所有启用的PO目录。

**参数**:
- `项目名称`（必需）: 项目名称
- `--short`（可选）: 只显示PO名称，不显示详细文件列表
- `--po`（可选）: 仅列出指定的 PO（从 `PROJECT_PO_CONFIG` 中筛选，逗号/空格分隔）。
- `--json`（可选）: 输出 JSON（便于脚本解析）。

**输出**:
- 列出 `PROJECT_PO_CONFIG` 中启用的所有PO
- 显示每个PO的补丁文件和覆盖文件
- 显示文件计数和路径

**示例**:
```bash
# 列出详细PO信息
python -m src po_list myproject

# 只显示PO名称
python -m src po_list myproject --short
```

---

### `po_status` - 查看 PO 已应用记录状态

**状态**: ✅ 已实现

**语法**:
```bash
python -m src po_status <项目名称> [--po <po1,po2>] [--short] [--json]
```

**描述**: 查看每个目标仓库根目录下的 PO 已应用记录（applied record）状态。

**参数**:
- `项目名称`（必需）: 项目名称

**选项**:
- `--po`: 仅查看指定的 PO（从 `PROJECT_PO_CONFIG` 中筛选，逗号/空格分隔）。
- `--short`: 只输出每个 PO 的汇总，不输出按仓库拆分的明细。
- `--json`: 输出 JSON（便于脚本解析）。

**示例**:
```bash
python -m src po_status myproject --po po_base,po_fix --short
```

---

### `po_clear` - 清理 PO 已应用记录标记

**状态**: ✅ 已实现

**语法**:
```bash
python -m src po_clear <项目名称> [--po <po1,po2>] [--dry-run]
```

**描述**: 清理已应用记录标记（不会回滚任何文件变更）。

**参数**:
- `项目名称`（必需）: 项目名称

**选项**:
- `--po`: 仅清理指定的 PO（从 `PROJECT_PO_CONFIG` 中筛选，逗号/空格分隔）。
- `--dry-run`: 仅打印计划删除项，不实际删除文件。

**示例**:
```bash
python -m src po_clear myproject --po po_base --dry-run
```

---

## 命令状态说明

| 状态 | 含义 | 说明 |
|------|------|------|
| ✅ 已实现 | 功能完全可用 | 可以正常使用，有完整测试覆盖 |
| 🚧 TODO | 功能预留 | 接口已定义，但实现待完成 |
| 🔄 开发中 | 正在开发 | 功能部分实现，可能不稳定 |

## 获取帮助

- **全局帮助**: `python -m src --help`
- **命令帮助**: `python -m src <命令> --help`
- **示例**: `python -m src po_apply --help`

---

## 其他语言版本

- [English Version](../../en/user-guide/command-reference.md)
