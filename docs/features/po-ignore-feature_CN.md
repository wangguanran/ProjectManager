# PO 忽略功能

## 概述

`po_new` 命令已增强，能够基于配置文件忽略特定的仓库路径。此功能允许用户在项目配置中指定要忽略的仓库路径模式，在创建PO时避免扫描这些仓库的文件修改。

## 功能

1. **配置文件支持**: 通过项目配置中的 `PROJECT_PO_IGNORE` 字段指定忽略模式
2. **模式匹配**: 使用 fnmatch 进行通配符模式匹配
3. **路径包含匹配**: 自动增强简单模式以匹配包含指定路径的仓库和文件
4. **多模式支持**: 支持由空格分隔的多个忽略模式
5. **向后兼容性**: 保持对现有 `.gitignore` 文件的支持

## 配置

### 1. 项目配置文件方法

在项目的 `.ini` 配置文件中添加 `PROJECT_PO_IGNORE` 字段：

```ini
[project_name]
board_name = board_name
PROJECT_PO_CONFIG = po1 po2
PROJECT_PO_IGNORE = vendor/* external/* third_party/* build/*
```

### 2. 文件方法（保持兼容性）

继续支持以下文件：
- `.gitignore`: 标准 Git 忽略文件

## 忽略模式示例

### 基本模式
```
vendor/*          # 忽略 vendor 目录下的所有仓库
external/*        # 忽略 external 目录下的所有仓库  
third_party/*     # 忽略 third_party 目录下的所有仓库
build/*           # 忽略 build 目录下的所有仓库
docs              # 忽略 docs 仓库
test_*            # 忽略所有以 test_ 开头的仓库
```

### 增强模式（自动生成）
配置简单模式时，系统会自动生成增强模式以匹配包含指定路径的仓库和文件：

**配置**: `PROJECT_PO_IGNORE = vendor`

**自动生成的增强模式**:
```
vendor              # 原始模式
*vendor*            # 匹配任何包含 "vendor" 的路径
*vendor/*           # 匹配以 "vendor" 开头的目录
*/vendor/*          # 匹配包含 "vendor" 的目录
*/vendor            # 匹配以 "vendor" 结尾的路径
```

**实际效果**:
- 忽略的仓库: `vendor/`, `my_vendor_lib/`, `lib/vendor/`, `external/vendor/`
- 忽略的文件: `src/vendor_config.h`, `include/vendor.h`, `docs/vendor_guide.md`

## 工作流程

1. **扫描仓库**: `po_new` 命令从当前目录开始扫描所有 Git 仓库
2. **应用忽略规则**: 根据配置的忽略模式过滤仓库
3. **显示结果**: 在控制台中显示哪些仓库被忽略，哪些被处理
4. **继续处理**: 只扫描未被忽略的仓库以查找文件修改

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

- `src/plugins/patch_override.py`: 主要修改的文件

### 修改的函数

1. **`__find_repositories()`**: 
   - 添加了忽略模式加载
   - 扫描仓库时应用忽略规则
   - 显示被忽略和处理的仓库信息

2. **`__load_ignore_patterns()`**: 
   - 添加了 `project_cfg` 参数
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

### 增强模式生成逻辑

```python
# 为简单模式自动生成增强模式
enhanced_patterns = []
for pattern in config_patterns:
    # 跳过已包含通配符或特殊字符的模式
    if any(char in pattern for char in ['*', '?', '[', ']']):
        continue
    
    # 生成包含匹配模式
    enhanced_patterns.extend([
        f"*{pattern}*",  # 匹配任何包含模式的路径
        f"*{pattern}/*",  # 匹配以模式开头的目录
        f"*/{pattern}/*",  # 匹配包含模式的目录
        f"*/{pattern}",   # 匹配以模式结尾的路径
    ])
```

## 使用建议

1. **合理配置**: 只忽略真正不需要处理的仓库，避免遗漏重要修改
2. **精确模式**: 使用精确的模式匹配，避免意外忽略需要的仓库
3. **测试验证**: 在重要操作前测试忽略配置
4. **文档维护**: 在团队内维护忽略配置的文档

## 注意事项

1. 忽略模式区分大小写
2. 支持标准 fnmatch 通配符模式
3. 简单模式会自动增强为包含匹配模式（跳过已包含通配符的模式）
4. 忽略规则按配置顺序应用，第一个匹配的模式生效
5. 忽略配置的更改需要重新运行 `po_new` 命令才能生效

---

## 其他语言版本

- [English Version](po-ignore-feature_EN.md) - 英文版文档
