# ProjectManager 配置管理

## 概述

本文档详细说明了 ProjectManager 的配置系统，包括配置文件格式、配置项说明和最佳实践。

## 配置文件结构

ProjectManager 使用 INI 格式的配置文件来管理项目和主板配置。配置文件位于 `projects/<主板名称>/<主板名称>.ini`。

## 配置文件示例

### 基本配置文件结构

```ini
# 主板配置文件: projects/myboard/myboard.ini

[common]
# 通用配置，所有项目继承
PROJECT_PO_IGNORE=vendor/* external/* third_party/*
DEFAULT_BUILD_TYPE=release

[myproject]
# 项目特定配置
BOARD_NAME=myboard
PROJECT_PO_CONFIG=po_feature1 po_feature2 -po_experimental
PROJECT_PO_IGNORE=vendor/* external/* tests/*
BUILD_TYPE=debug
VERSION=1.0.0

[myproject-subproject]
# 子项目配置，继承父项目配置
PROJECT_PO_CONFIG=po_feature1 po_subproject
BUILD_TYPE=release
```

## 配置项详解

### 核心配置项

#### `BOARD_NAME`
- **类型**: 字符串
- **必需**: 是
- **描述**: 指定项目所属的主板名称
- **示例**: `BOARD_NAME=myboard`
- **自动填充**: 系统会自动填充此值

#### `PROJECT_PO_CONFIG`
- **类型**: 字符串
- **必需**: 是
- **描述**: 定义项目使用的PO（补丁/覆盖）配置
- **语法**: 支持包含、排除和文件级排除
- **示例**: `PROJECT_PO_CONFIG=po1 po2 -po3 po4[file1 file2]`

#### `PROJECT_PO_IGNORE`
- **类型**: 字符串
- **必需**: 否
- **描述**: 定义要忽略的文件和目录模式
- **语法**: 空格分隔的glob模式
- **示例**: `PROJECT_PO_IGNORE=vendor/* external/* tests/*`

### 扩展配置项

#### `BUILD_TYPE`
- **类型**: 字符串
- **必需**: 否
- **描述**: 项目构建类型
- **可选值**: `debug`, `release`, `test`
- **默认值**: 从 `[common]` 继承

#### `VERSION`
- **类型**: 字符串
- **必需**: 否
- **描述**: 项目版本号
- **格式**: 语义化版本号（如 `1.0.0`）

#### `DESCRIPTION`
- **类型**: 字符串
- **必需**: 否
- **描述**: 项目描述信息

## PO配置语法详解

### 基本语法

```
PO配置 = PO项1 PO项2 -PO项3 PO项4[文件1 文件2]
```

### PO项类型

#### 1. 包含PO
- **格式**: `po_name`
- **作用**: 应用指定的PO
- **示例**: `po_feature1`

#### 2. 排除PO
- **格式**: `-po_name`
- **作用**: 排除指定的PO
- **示例**: `-po_experimental`

#### 3. 条件PO
- **格式**: `po_name[文件1 文件2]`
- **作用**: 应用PO但排除特定文件
- **示例**: `po_feature1[src/test.c include/test.h]`

### 配置示例

#### 简单配置
```ini
PROJECT_PO_CONFIG=po_feature1 po_feature2
```
- 应用 `po_feature1` 和 `po_feature2`

#### 排除配置
```ini
PROJECT_PO_CONFIG=po_feature1 -po_experimental
```
- 应用 `po_feature1`，排除 `po_experimental`

#### 复杂配置
```ini
PROJECT_PO_CONFIG=po_feature1 po_feature2[src/test.c] -po_experimental[config.ini]
```
- 应用 `po_feature1`
- 应用 `po_feature2` 但排除 `src/test.c`
- 排除 `po_experimental` 但保留 `config.ini`

## 配置继承机制

### 继承规则

1. **项目配置** 继承 **通用配置** (`[common]`)
2. **子项目** 继承 **父项目** 配置
3. **子项目配置** 覆盖 **父项目配置**

### 继承示例

```ini
[common]
PROJECT_PO_IGNORE=vendor/* external/*
BUILD_TYPE=release

[myproject]
PROJECT_PO_CONFIG=po_feature1
# 继承 PROJECT_PO_IGNORE=vendor/* external/*
# 继承 BUILD_TYPE=release

[myproject-subproject]
PROJECT_PO_CONFIG=po_feature1 po_subproject
BUILD_TYPE=debug
# 继承 PROJECT_PO_IGNORE=vendor/* external/*
# 覆盖 BUILD_TYPE=debug
```

### 子项目命名规则

子项目通过连字符命名来建立继承关系：
- 父项目: `myproject`
- 子项目: `myproject-subproject`
- 孙项目: `myproject-subproject-feature`

## 忽略模式详解

### 支持的忽略模式

#### 1. 目录忽略
```
vendor/*          # 忽略vendor目录下的所有内容
external/*        # 忽略external目录下的所有内容
third_party/*     # 忽略third_party目录下的所有内容
```

#### 2. 文件忽略
```
*.log             # 忽略所有.log文件
config.ini        # 忽略特定文件
*.tmp             # 忽略所有.tmp文件
```

#### 3. 路径忽略
```
src/vendor/*      # 忽略src/vendor目录
include/external/* # 忽略include/external目录
```

### 忽略模式优先级

1. **项目级忽略** (`PROJECT_PO_IGNORE`) 优先级最高
2. **Git忽略** (`.gitignore`) 优先级中等
3. **系统忽略** 优先级最低

## 配置文件最佳实践

### 1. 组织结构

```
projects/
├── board1/
│   ├── board1.ini          # 主板配置
│   ├── project1/           # 项目1
│   ├── project2/           # 项目2
│   └── project2-sub/       # 子项目
├── board2/
│   ├── board2.ini          # 主板配置
│   └── project3/           # 项目3
└── common/
    └── common.ini          # 通用配置
```

### 2. 命名规范

- **主板名称**: 使用小写字母、数字和下划线
- **项目名称**: 使用小写字母、数字、连字符和下划线
- **PO名称**: 必须以 `po_` 开头，只能包含小写字母、数字和下划线

### 3. 配置管理

- 将通用配置放在 `[common]` 部分
- 使用有意义的配置项名称
- 添加注释说明配置项的用途
- 定期备份配置文件

### 4. 版本控制

- 将配置文件纳入版本控制
- 使用语义化版本号
- 记录配置变更历史
- 测试配置变更的影响

## 配置验证

### 自动验证

ProjectManager 会自动验证配置文件：
- 检查必需配置项
- 验证PO配置语法
- 检查文件路径有效性
- 验证配置继承关系

### 手动验证

```bash
# 验证项目配置
python -m src po_list myproject

# 检查PO配置
python -m src po_list myproject --short
```

## 故障排除

### 常见配置问题

#### 1. PO配置语法错误
**症状**: 命令执行失败，提示配置错误
**解决**: 检查 `PROJECT_PO_CONFIG` 语法

#### 2. 忽略模式无效
**症状**: 应该被忽略的文件仍然被处理
**解决**: 检查忽略模式语法和优先级

#### 3. 配置继承失败
**症状**: 子项目没有继承父项目配置
**解决**: 检查项目命名和配置文件结构

### 调试技巧

1. **启用详细日志**: 使用 `--verbose` 选项
2. **检查配置文件**: 验证INI文件格式
3. **测试PO配置**: 使用 `po_list` 命令验证
4. **查看继承关系**: 检查项目命名规范

---

## 其他语言版本

- [English Version](configuration_EN.md)
