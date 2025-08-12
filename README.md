# ProjectManager

![GitHub stars](https://img.shields.io/github/stars/wangguanran/ProjectManager.svg) ![GitHub forks](https://img.shields.io/github/forks/wangguanran/ProjectManager.svg) ![GitHub issues](https://github.com/wangguanran/ProjectManager/issues.svg) ![GitHub last commit](https://img.shields.io/github/last-commit/wangguanran/ProjectManager.svg)
![Build Status](https://github.com/wangguanran/ProjectManager/actions/workflows/python-app.yml/badge.svg) ![Pylint](https://github.com/wangguanran/ProjectManager/actions/workflows/pylint.yml/badge.svg)
![License](https://img.shields.io/github/license/wangguanran/ProjectManager.svg) ![Python](https://img.shields.io/badge/python-3.7+-blue.svg) ![Platform](https://img.shields.io/badge/platform-linux-blue.svg)

通用项目和补丁（PO）管理工具

## 🚀 快速开始

### 安装

```bash
# 从 PyPI 安装（推荐）
pip install multi-project-manager

# 从源码安装
git clone https://github.com/wangguanran/ProjectManager.git
cd ProjectManager
pip install -e .

# 使用 Docker
docker pull ghcr.io/wangguanran/projectmanager:latest
```

### 基本使用

```bash
# 创建主板
python -m src board_new myboard

# 创建项目
python -m src project_new myproject

# 创建 PO
python -m src po_new myproject po_feature1

# 应用 PO
python -m src po_apply myproject
```

## 📖 项目概述

ProjectManager 是一个适用于多主板、多项目环境的项目管理和补丁（patch/override，PO）管理工具。它支持项目/主板的创建、删除、构建，以及PO目录管理和补丁应用/回滚操作。适用于需要批量管理不同硬件平台和自定义补丁的场景。

## ✨ 主要功能

- 🏗️ **项目管理**: 支持统一管理多个主板和项目
- 🔧 **PO管理**: 补丁和覆盖的创建、应用、回滚
- 📁 **多仓库支持**: 支持 .repo 清单和多仓库环境
- 🎯 **交互式操作**: PO创建的交互式文件选择
- 📊 **日志分析**: 自动日志归档和性能分析支持
- ⚡ **高性能**: 优化的文件操作和配置解析

## 📚 文档

### 用户指南
- **[快速开始](../docs/user-guide/getting-started_CN.md)** - 安装和基本使用
- **[命令参考](../docs/user-guide/command-reference_CN.md)** - 完整命令说明
- **[配置管理](../docs/user-guide/configuration_CN.md)** - 配置文件详解

### 功能文档
- **[PO忽略功能](../docs/features/po-ignore-feature_CN.md)** - 增强的PO忽略功能
- **[项目管理](../docs/features/project-management_CN.md)** - 项目管理功能详解

### 开发文档
- **[开发指南](../docs/development/README_CN.md)** - 开发设置和贡献指南
- **[系统架构](../docs/development/architecture_CN.md)** - 系统架构设计
- **[测试策略](../docs/development/testing_CN.md)** - 测试程序和质量保证

### 需求文档
- **[功能需求](../docs/requirements/requirements_CN.md)** - 详细需求规格和测试用例

## 🏗️ 项目结构

```
projects/
├── board01/                    # 主板目录
│   ├── board01.ini            # 主板配置文件
│   ├── project1/              # 项目1
│   ├── project2/              # 项目2
│   └── po/                    # PO目录
│       ├── po_feature1/       # PO1
│       │   ├── patches/       # Git补丁文件
│       │   └── overrides/     # 覆盖文件
│       └── po_feature2/       # PO2
├── common/                     # 通用配置
└── template/                   # 模板文件
```

## 🔧 系统要求

- **操作系统**: Linux (推荐 Ubuntu 18.04+ 或 CentOS 7+)
- **Python**: 3.7 或更高版本
- **Git**: 2.20 或更高版本
- **内存**: 最少 2GB RAM
- **磁盘空间**: 最少 1GB 可用空间

## 📋 功能状态

| 功能模块 | 状态 | 说明 |
|----------|------|------|
| 主板管理 | 🚧 开发中 | 创建、删除主板功能 |
| 项目管理 | 🚧 开发中 | 创建、删除、构建项目 |
| PO管理 | ✅ 已完成 | 创建、应用、回滚PO |
| 配置管理 | ✅ 已完成 | 配置文件解析和继承 |
| 日志系统 | ✅ 已完成 | 日志记录和性能分析 |

## 🚀 快速命令参考

| 命令 | 用途 | 示例 |
|------|------|------|
| `board_new` | 创建主板 | `python -m src board_new board1` |
| `project_new` | 创建项目 | `python -m src project_new proj1` |
| `po_new` | 创建PO | `python -m src po_new proj1 po1` |
| `po_apply` | 应用PO | `python -m src po_apply proj1` |
| `po_revert` | 回滚PO | `python -m src po_revert proj1` |
| `po_list` | 列出PO | `python -m src po_list proj1` |

## 🤝 贡献

我们欢迎所有形式的贡献！请查看我们的 [贡献指南](CONTRIBUTING.md) 了解如何参与项目开发。

### 贡献方式
- 🐛 报告 Bug
- 💡 提出新功能建议
- 📝 改进文档
- 🔧 提交代码修复
- 🧪 编写测试用例

## 📄 许可证

本项目采用 [MIT 许可证](LICENSE) 开源。

## 🌐 其他语言版本

- [English Version](README_EN.md) - 英文版文档
- [中文文档](../docs/README_CN.md) - 中文版文档索引

## 📞 获取帮助

- **命令行帮助**: `python -m src --help`
- **GitHub Issues**: [提交问题](https://github.com/wangguanran/ProjectManager/issues)
- **文档**: 查看 [完整文档](../docs/README_CN.md)
- **讨论**: [GitHub Discussions](https://github.com/wangguanran/ProjectManager/discussions)

---

**⭐ 如果这个项目对你有帮助，请给我们一个星标！**
