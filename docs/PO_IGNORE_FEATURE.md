# PO 忽略功能说明

## 概述

在 `po_new` 命令中新增了根据配置文件忽略特定路径仓库的功能。这个功能允许用户在项目配置中指定要忽略的仓库路径模式，避免在创建 PO 时扫描这些仓库的文件修改。

## 功能特性

1. **配置文件支持**: 通过项目配置中的 `PROJECT_PO_IGNORE` 字段指定忽略模式
2. **模式匹配**: 使用 fnmatch 进行通配符模式匹配
3. **多模式支持**: 支持多个忽略模式，用空格分隔
4. **向后兼容**: 保持对现有 `.gitignore` 文件的支持

## 配置方式

### 1. 项目配置文件方式

在项目的 `.ini` 配置文件中添加 `PROJECT_PO_IGNORE` 字段：

```ini
[project_name]
board_name = board_name
PROJECT_PO_CONFIG = po1 po2
PROJECT_PO_IGNORE = vendor/* external/* third_party/* build/*
```

### 2. 文件方式（保持兼容）

继续支持以下文件：
- `.gitignore`: 标准的 Git 忽略文件

## 忽略模式示例

```
vendor/*          # 忽略所有 vendor 目录下的仓库
external/*        # 忽略所有 external 目录下的仓库  
third_party/*     # 忽略所有 third_party 目录下的仓库
build/*           # 忽略所有 build 目录下的仓库
docs              # 忽略 docs 仓库
test_*            # 忽略所有以 test_ 开头的仓库
```

## 工作流程

1. **扫描仓库**: `po_new` 命令扫描当前目录下的所有 Git 仓库
2. **应用忽略规则**: 根据配置的忽略模式过滤仓库
3. **显示结果**: 在控制台显示哪些仓库被忽略，哪些被处理
4. **继续处理**: 只对未被忽略的仓库进行文件修改扫描

## 输出示例

```
Found .repo manifest, scanning repositories...
  Ignoring repository: vendor/foo (matches pattern: vendor/*)
  Ignoring repository: external/bar (matches pattern: external/*)
  Ignoring repository: third_party/baz (matches pattern: third_party/*)
  Found repository: src/main at /path/to/src/main
  Found repository: docs at /path/to/docs
```

## 实现细节

### 修改的文件

- `src/plugins/patch_override.py`: 主要修改文件

### 修改的函数

1. **`__find_repositories()`**: 
   - 新增忽略模式加载
   - 在扫描仓库时应用忽略规则
   - 显示忽略和处理的仓库信息

2. **`__load_ignore_patterns()`**: 
   - 新增 `project_cfg` 参数
   - 优先从项目配置读取忽略模式
   - 保持对 `.gitignore` 文件的支持

### 忽略逻辑

```python
# 检查仓库是否应该被忽略
should_ignore = False
for pattern in ignore_patterns:
    if fnmatch.fnmatch(repo_name, pattern):
        should_ignore = True
        break

if not should_ignore:
    # 处理仓库
    repositories.append((repo_path, repo_name))
else:
    # 跳过仓库
    print(f"  Ignoring repository: {repo_name} (matches pattern: {pattern})")
```

## 使用建议

1. **合理配置**: 只忽略确实不需要处理的仓库，避免遗漏重要修改
2. **模式精确**: 使用精确的模式匹配，避免误忽略需要的仓库
3. **测试验证**: 在重要操作前测试忽略配置是否正确
4. **文档维护**: 在团队中维护忽略配置的文档说明

## 注意事项

1. 忽略模式区分大小写
2. 支持标准的 fnmatch 通配符模式
3. 忽略规则按配置顺序应用，第一个匹配的模式生效
4. 修改忽略配置后需要重新运行 `po_new` 命令才能生效 