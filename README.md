# ProjectManager

![GitHub stars](https://img.shields.io/github/stars/wangguanran/ProjectManager.svg) ![GitHub forks](https://img.shields.io/github/forks/wangguanran/ProjectManager.svg) ![GitHub issues](https://img.shields.io/github/issues/wangguanran/ProjectManager.svg) ![GitHub last commit](https://img.shields.io/github/last-commit/wangguanran/ProjectManager.svg)
![Build Status](https://github.com/wangguanran/ProjectManager/actions/workflows/python-app.yml/badge.svg) ![Pylint](https://github.com/wangguanran/ProjectManager/actions/workflows/pylint.yml/badge.svg)
![License](https://img.shields.io/github/license/wangguanran/ProjectManager.svg) ![Python](https://img.shields.io/badge/python-3.7+-blue.svg) ![Platform](https://img.shields.io/badge/platform-linux-blue.svg)

通用项目和补丁（PO）管理工具

## 项目概述

ProjectManager 是一个适用于多主板、多项目环境的项目管理和补丁（patch/override，PO）管理工具。它支持项目/主板的创建、删除、构建，以及PO目录管理和补丁应用/回滚操作。适用于需要批量管理不同硬件平台和自定义补丁的场景。

## 安装

### Python 包

**从 PyPI 安装**：
```bash
pip install multi-project-manager
```

**从 GitHub Package Registry 安装**：
```bash
pip install multi-project-manager --index-url https://pypi.pkg.github.com/wangguanran/
```

**从源码安装**：
```bash
git clone https://github.com/wangguanran/ProjectManager.git
cd ProjectManager
pip install -e .
```

### Docker 镜像

**拉取最新镜像**：
```bash
docker pull ghcr.io/wangguanran/projectmanager:latest
```

**使用 Docker 运行**：
```bash
# 基本用法
docker run -v $(pwd)/projects:/app/projects ghcr.io/wangguanran/projectmanager:latest

# 执行特定命令
docker run -v $(pwd)/projects:/app/projects ghcr.io/wangguanran/projectmanager:latest po_apply myproject
```

## 主要功能

- 支持统一管理多个主板和项目
- 项目/主板的创建、删除和构建（部分功能预留）
- PO（补丁/覆盖）目录的创建、删除和列表显示
- 为项目应用/回滚补丁和覆盖
- 自动日志归档和性能分析支持
- PO创建的交互式文件选择
- 支持 .repo 清单和多仓库环境

## 目录结构

```
projects/
  board01/
    board01.ini          # 主板配置文件
    po/
      po_test01/
        patches/         # Git 补丁文件
        overrides/       # 覆盖文件
      ...
  common/
    ...
  template/
    ...
.cache/
  logs/         # 带时间戳的日志文件
  cprofile/     # 性能分析数据
src/
  __main__.py   # 命令行主入口
  plugins/
    project_manager.py   # 项目/主板管理
    patch_override.py    # PO管理和补丁应用
  ...
```

## 命令行用法

使用以下命令启动：

```bash
python -m src <操作> <项目或主板名称> [参数] [--选项]
```

### 全局选项

- `--version`: 显示程序版本
- `--help`: 显示所有操作的详细帮助
- `--perf-analyze`: 启用 cProfile 性能分析

## 详细命令参考

### 项目管理命令

#### `project_new` - 创建新项目
**状态**: TODO（未实现）

**用法**: `python -m src project_new <项目名称>`

**描述**: 使用指定配置创建新项目。

**参数**:
- `项目名称`（必需）: 要创建的项目名称

**配置**: 项目配置存储在主板特定的 `.ini` 文件中。

---

#### `project_del` - 删除项目
**状态**: TODO（未实现）

**用法**: `python -m src project_del <项目名称>`

**描述**: 删除指定的项目目录并更新配置文件中的状态。

**参数**:
- `项目名称`（必需）: 要删除的项目名称

---

#### `project_build` - 构建项目
**状态**: TODO（未实现）

**用法**: `python -m src project_build <项目名称>`

**描述**: 根据配置构建指定项目。

**参数**:
- `项目名称`（必需）: 要构建的项目名称

---

### 主板管理命令

#### `board_new` - 创建新主板
**状态**: TODO（未实现）

**用法**: `python -m src board_new <主板名称>`

**描述**: 创建新主板并初始化目录结构。

**参数**:
- `主板名称`（必需）: 要创建的主板名称

**创建的目录结构**:
```
projects/<主板名称>/
  <主板名称>.ini
  po/
```

---

#### `board_del` - 删除主板
**状态**: TODO（未实现）

**用法**: `python -m src board_del <主板名称>`

**描述**: 删除指定的主板及其所有项目。

**参数**:
- `主板名称`（必需）: 要删除的主板名称

---

### PO（补丁/覆盖）管理命令

#### `po_apply` - 应用补丁和覆盖
**状态**: ✅ 已实现

**用法**: `python -m src po_apply <项目名称>`

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

---

#### `po_revert` - 回滚补丁和覆盖
**状态**: ✅ 已实现

**用法**: `python -m src po_revert <项目名称>`

**描述**: 回滚指定项目的所有已应用补丁和覆盖。

**参数**:
- `项目名称`（必需）: 要回滚PO的项目名称

**流程**:
1. 从项目配置读取 `PROJECT_PO_CONFIG`
2. 使用 `git apply --reverse` 回滚补丁
3. 删除覆盖文件（如果被git跟踪则从git恢复）
4. 更新标志文件以移除PO引用

---

#### `po_new` - 创建新PO目录
**状态**: ✅ 已实现

**用法**: `python -m src po_new <项目名称> <po名称> [--force]`

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

---

#### `po_del` - 删除PO目录
**状态**: ✅ 已实现

**用法**: `python -m src po_del <项目名称> <po名称> [--force]`

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

---

#### `po_list` - 列出配置的PO
**状态**: ✅ 已实现

**用法**: `python -m src po_list <项目名称> [--short]`

**描述**: 列出指定项目的所有启用的PO目录。

**参数**:
- `项目名称`（必需）: 项目名称
- `--short`（可选）: 只显示PO名称，不显示详细文件列表

**输出**:
- 列出 `PROJECT_PO_CONFIG` 中启用的所有PO
- 显示每个PO的补丁文件和覆盖文件
- 显示文件计数和路径

---

## 配置文件

### 主板配置文件（.ini 文件）

每个主板都有一个配置文件（`<主板名称>.ini`），包含项目定义：

```ini
[project_name]
PROJECT_PO_CONFIG=po_test01 po_test02 -po_test03
PROJECT_PO_IGNORE=external vendor/third_party
BOARD_NAME=board01
# 其他项目特定配置
```

**配置键**:
- `PROJECT_PO_CONFIG`: PO配置字符串（见上述格式）
- `PROJECT_PO_IGNORE`: 仓库/文件的空格分隔忽略模式
- `BOARD_NAME`: 主板名称（自动填充）

### PO配置格式

**基本格式**: `po_name1 po_name2 -po_name3`

**高级格式**: `po_name1[file1 file2] -po_name2[file3]`

**示例**:
- `po_test01 po_test02`: 应用 po_test01 和 po_test02
- `po_test01 -po_test02`: 应用 po_test01，排除 po_test02
- `po_test01[src/main.c include/header.h]`: 应用 po_test01 但排除特定文件
- `po_test01 -po_test02[config.ini]`: 应用 po_test01，排除 po_test02 但保留 config.ini

## 日志记录和性能分析

### 日志记录
- **位置**: `.cache/logs/`
- **格式**: `Log_YYYYMMDD_HHMMSS.log`
- **级别**: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **功能**: 
  - 彩色控制台输出
  - 自动日志轮转
  - 基于时间的归档

### 性能分析
- **位置**: `.cache/cprofile/`
- **启用**: 使用 `--perf-analyze` 标志
- **输出**: 详细的函数调用统计和计时

## 环境支持

### 仓库类型
- 单个git仓库
- 多个git仓库（递归发现）
- .repo 清单文件（Android风格）

### 文件类型
- **补丁**: Git补丁文件（`.patch`）
- **覆盖**: 直接文件复制
- **标志**: `.patch_applied`，`.override_applied`（跟踪文件）

### 忽略模式
- `.gitignore` 文件模式
- `PROJECT_PO_IGNORE` 配置
- 仓库级排除

## 依赖和安装

- **Python**: 3.7+
- **依赖**: 参见 `requirements.txt`
- **Git**: 补丁操作必需
- **文件系统**: 标准POSIX文件操作

## 注意事项

- 目前，项目/主板管理功能是预留的（TODO），而PO管理和补丁应用功能已完全实现。
- 平台管理功能已合并到现有插件中，没有单独的 `platform_manager.py` 或 `po_manager.py` 文件。
- 要扩展平台相关操作，可以在 `projects/scripts/` 目录中添加自定义插件。
- 所有PO操作都支持交互式确认和详细日志记录。
- 该工具自动处理多仓库环境和复杂的PO配置。

---

## 其他语言版本

- [English Version](README_EN.md) - 英文版文档
