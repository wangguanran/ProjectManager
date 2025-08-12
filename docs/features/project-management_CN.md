# 项目管理功能

## 概述

ProjectManager 通过其核心模块和插件提供全面的项目管理功能。本文档描述了主要功能以及如何使用它们。

## 核心模块

### 项目管理插件 (`src/plugins/project_manager.py`)

项目管理插件处理项目配置和管理操作。

**主要功能**:
- 项目配置加载和验证
- 主板和项目关系管理
- 配置文件解析和更新

### 补丁和覆盖插件 (`src/plugins/patch_override.py`)

补丁和覆盖插件通过PO（补丁/覆盖）操作提供高级文件修改管理。

**主要功能**:
- `po_new`: 创建新的PO目录并选择文件进行补丁/覆盖
- `po_apply`: 将补丁和覆盖应用到仓库
- `po_revert`: 回滚已应用的补丁和覆盖
- `po_list`: 列出项目的配置PO
- `po_del`: 删除PO目录并清理配置

**特性**:
- PO创建的交互式文件选择
- 支持暂存区和工作目录更改
- 自动仓库发现（包括 .repo 清单支持）
- 具有路径包含匹配的增强忽略模式
- 补丁应用和回滚的Git集成

## 实用模块

### 日志管理器 (`src/log_manager.py`)

提供具有可配置级别和输出格式的集中日志功能。

**特性**:
- 可配置的日志级别（DEBUG, INFO, WARNING, ERROR）
- 文件和控制台输出支持
- 具有上下文信息的结构化日志记录
- 性能分析集成

### 性能分析器 (`src/profiler.py`)

性能分析和监控工具。

**特性**:
- 函数执行时间测量
- 内存使用跟踪
- 性能瓶颈识别
- 关键操作的自动性能分析

### 工具 (`src/utils.py`)

整个项目中使用的通用工具函数。

**特性**:
- 配置文件解析
- 路径操作工具
- 验证函数
- 通用数据处理操作

## 主入口点 (`src/__main__.py`)

协调所有操作的主应用程序入口点。

**特性**:
- 命令行界面
- 子命令路由
- 环境设置和验证
- 错误处理和用户反馈

## 配置管理

### 项目配置文件

项目使用具有以下结构的 `.ini` 文件进行配置：

```ini
[project_name]
board_name = board_name
PROJECT_PO_CONFIG = po1 po2 -po3
PROJECT_PO_IGNORE = vendor/* external/*
```

**配置字段**:
- `board_name`: 项目的关联主板
- `PROJECT_PO_CONFIG`: 具有包含/排除规则的PO配置
- `PROJECT_PO_IGNORE`: 仓库和文件忽略模式

### PO配置语法

```
po1 po2 -po3 po4[file1 file2] -po5[file3]
```

**元素**:
- `po1`, `po2`: 包含这些PO
- `-po3`: 排除此PO
- `po4[file1 file2]`: 包含PO4但排除特定文件
- `-po5[file3]`: 排除PO5但仅针对特定文件

## 仓库管理

### 仓库发现

系统支持多种仓库发现方法：

1. **Git仓库**: 具有 `.git` 目录的标准Git仓库
2. **Repo清单**: Android风格的 `.repo/manifest.xml` 文件
3. **混合环境**: 上述方法的组合

### 仓库操作

- **扫描**: 自动发现当前目录中的仓库
- **过滤**: 应用忽略模式以排除特定仓库
- **文件分析**: 检测仓库中的修改文件
- **更改管理**: 处理暂存和未暂存的更改

## 文件管理

### 补丁操作

补丁使用Git的diff功能创建：

```bash
# 从暂存更改创建补丁
git diff --cached -- file_path

# 从工作目录更改创建补丁
git diff -- file_path
```

### 覆盖操作

覆盖将文件直接从源复制到目标位置，替换原始文件。

### 文件选择

系统提供具有以下选项的交互式文件选择：

1. **创建补丁**: 用于有修改的跟踪文件
2. **创建覆盖**: 用于任何文件（跟踪或未跟踪）
3. **跳过文件**: 从PO创建中排除

## 集成功能

### Git集成

- 自动检测Git仓库
- 支持Git状态和diff操作
- 与Git钩子集成以实现自动化操作
- 使用Git命令进行补丁应用和回滚

### CI/CD集成

- GitHub Actions工作流程用于自动化测试和部署
- Docker容器化以确保环境一致性
- 包发布到多个注册表
- 自动化发布管理

## 使用示例

### 基本PO创建

```bash
# 创建具有交互式文件选择的新PO
python -m src po_new myproject my_po_name

# 在强制模式下创建新PO（空结构）
python -m src po_new myproject my_po_name --force
```

### PO管理

```bash
# 将PO应用到项目
python -m src po_apply myproject

# 从项目回滚PO
python -m src po_revert myproject

# 列出配置的PO
python -m src po_list myproject

# 删除PO
python -m src po_del myproject my_po_name
```

### 项目管理

```bash
# 列出所有项目
python -m src list

# 显示项目详情
python -m src show myproject

# 为所有项目应用所有PO
python -m src apply_all
```

## 最佳实践

1. **PO命名**: 使用以"po"开头的描述性名称（例如 `po_feature_name`）
2. **配置**: 保持PO配置简单且文档完善
3. **测试**: 在生产使用前在安全环境中测试PO应用
4. **备份**: 在将PO应用到重要项目前始终进行备份
5. **文档**: 记录每个PO的目的和内容

## 故障排除

### 常见问题

1. **找不到仓库**: 确保您在具有Git仓库的正确目录中
2. **权限错误**: 检查文件权限和Git仓库访问
3. **PO应用失败**: 验证补丁与当前仓库状态兼容
4. **配置错误**: 验证项目配置文件是否存在语法错误

### 调试模式

启用调试日志记录以进行详细故障排除：

```bash
export LOG_LEVEL=DEBUG
python -m src po_apply myproject
```

---

## 其他语言版本

- [English Version](project-management_EN.md) - 英文版文档
