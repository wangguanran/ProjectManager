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
python -m src project_build <项目名称>
```

**描述**: 根据配置构建指定项目。

**参数**:
- `项目名称`（必需）: 要构建的项目名称

**示例**:
```bash
python -m src project_build myproject
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
python -m src po_apply <项目名称>
```

**描述**: 为指定项目应用所有配置的补丁和覆盖。

**参数**:
- `项目名称`（必需）: 要应用PO的项目名称

**流程**:
1. 从项目配置读取 `PROJECT_PO_CONFIG`
2. 解析PO配置（支持包含/排除）
3. 使用 `git apply` 应用补丁
4. 将覆盖文件复制到目标位置
5. 创建标志文件（`.patch_applied`，`.override_applied`）来跟踪已应用的PO

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
python -m src po_revert <项目名称>
```

**描述**: 回滚指定项目的所有已应用补丁和覆盖。

**参数**:
- `项目名称`（必需）: 要回滚PO的项目名称

**流程**:
1. 从项目配置读取 `PROJECT_PO_CONFIG`
2. 使用 `git apply --reverse` 回滚补丁
3. 删除覆盖文件（如果被git跟踪则从git恢复）
4. 更新标志文件以移除PO引用

**示例**:
```bash
python -m src po_revert myproject
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
python -m src po_list <项目名称> [--short]
```

**描述**: 列出指定项目的所有启用的PO目录。

**参数**:
- `项目名称`（必需）: 项目名称
- `--short`（可选）: 只显示PO名称，不显示详细文件列表

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
