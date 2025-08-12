# ProjectManager 快速开始指南

## 概述

ProjectManager 是一个适用于多主板、多项目环境的项目管理和补丁（PO）管理工具。本指南将帮助你快速安装和开始使用 ProjectManager。

## 系统要求

- **操作系统**: Linux (推荐 Ubuntu 18.04+ 或 CentOS 7+)
- **Python**: 3.7 或更高版本
- **Git**: 2.20 或更高版本
- **内存**: 最少 2GB RAM
- **磁盘空间**: 最少 1GB 可用空间

## 快速安装

### 方法 1: 从 PyPI 安装（推荐）

```bash
pip install multi-project-manager
```

### 方法 2: 从源码安装

```bash
git clone https://github.com/wangguanran/ProjectManager.git
cd ProjectManager
pip install -e .
```

### 方法 3: 使用 Docker

```bash
docker pull ghcr.io/wangguanran/projectmanager:latest
```

## 验证安装

安装完成后，验证安装是否成功：

```bash
# 检查版本
python -m src --version

# 查看帮助
python -m src --help
```

如果看到版本信息和帮助内容，说明安装成功。

## 创建第一个项目

### 1. 创建主板

```bash
# 创建名为 "myboard" 的主板
python -m src board_new myboard
```

### 2. 创建项目

```bash
# 在 myboard 下创建项目 "myproject"
python -m src project_new myproject
```

### 3. 创建 PO（补丁/覆盖）

```bash
# 创建名为 "po_feature1" 的 PO
python -m src po_new myproject po_feature1
```

### 4. 应用 PO

```bash
# 将 PO 应用到项目
python -m src po_apply myproject
```

## 基本工作流程

```
创建主板 → 创建项目 → 创建 PO → 应用 PO → 管理项目
    ↓           ↓         ↓         ↓         ↓
  board_new  project_new po_new  po_apply  po_list
```

## 常用命令速查

| 命令 | 用途 | 示例 |
|------|------|------|
| `board_new` | 创建主板 | `python -m src board_new board1` |
| `project_new` | 创建项目 | `python -m src project_new proj1` |
| `po_new` | 创建 PO | `python -m src po_new proj1 po1` |
| `po_apply` | 应用 PO | `python -m src po_apply proj1` |
| `po_revert` | 回滚 PO | `python -m src po_revert proj1` |
| `po_list` | 列出 PO | `python -m src po_list proj1` |

## 配置文件示例

### 主板配置文件 (`projects/myboard/myboard.ini`)

```ini
[myproject]
BOARD_NAME=myboard
PROJECT_PO_CONFIG=po_feature1
PROJECT_PO_IGNORE=vendor/* external/*
```

## 下一步

- 查看 [详细功能文档](../features/) 了解所有功能
- 阅读 [最佳实践](../best-practices_CN.md) 学习最佳使用方法
- 参考 [故障排除](../troubleshooting_CN.md) 解决常见问题

## 获取帮助

- **命令行帮助**: `python -m src --help`
- **特定命令帮助**: `python -m src <命令> --help`
- **GitHub Issues**: [提交问题](https://github.com/wangguanran/ProjectManager/issues)
- **文档**: 查看 [完整文档](../README_CN.md)

---

## 其他语言版本

- [English Version](getting-started_EN.md)
