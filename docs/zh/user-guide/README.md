# ProjectManager 用户指南目录

本目录汇总所有面向用户的中文文档，帮助你从零开始安装 ProjectManager、熟练掌握命令行工具，并了解核心功能特性。

## 📘 学习路线

1. **入门阶段**
   - [快速开始](getting-started.md)：准备运行环境、初始化主板与项目。
   - [命令参考](command-reference.md)：掌握常用命令及参数。
   - [配置管理](configuration.md)：理解 `.ini` 配置文件结构与校验方法。
2. **进阶阶段**
   - [项目管理](../features/project-management.md)：管理多主板、多项目的最佳实践。
   - [PO 忽略功能](../features/po-ignore-feature.md)：按路径模式忽略补丁或覆盖文件。
3. **部署阶段**
   - [GitHub Packages 发布指南](../deployment/github-packages.md)：发布 Python 包与 Docker 镜像。

## 🔍 快速导航

| 任务 | 推荐文档 | 关键命令 |
|------|----------|----------|
| 安装工具 | [快速开始](getting-started.md) | `pip install` / Docker |
| 初始化主板 | [快速开始](getting-started.md#初始化项目结构) | `python -m src board_new` |
| 创建项目 | [快速开始](getting-started.md#初始化项目结构) | `python -m src project_new` |
| 管理补丁 | [命令参考](command-reference.md#po-管理命令) | `po_new`、`po_apply` |
| 调整配置 | [配置管理](configuration.md) | 编辑 `<board>.ini` |

## 💡 常见问题

- 命令出错？使用 `python -m src <命令> --help` 查看帮助。
- 配置失效？对照 [配置管理](configuration.md#常见问题) 校验字段。
- 需要更多功能介绍？查阅 [项目管理](../features/project-management.md) 与 [PO 忽略功能](../features/po-ignore-feature.md)。

## 📬 反馈与贡献

欢迎通过 GitHub Issues 反馈问题，或提交 Pull Request 改进文档。更新内容时，请同步维护英文文档并在对应索引中添加链接。
