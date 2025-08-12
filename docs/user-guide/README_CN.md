# ProjectManager 用户指南

欢迎使用 ProjectManager 用户指南！本目录包含面向用户的功能说明和使用指南。

## 📚 文档导航

### 🚀 快速开始
- **[快速开始指南](getting-started_CN.md)** - 安装和基本使用步骤
- **[系统要求](getting-started_CN.md#系统要求)** - 运行环境要求

### 📖 详细使用
- **[命令参考](command-reference_CN.md)** - 完整命令说明和示例
- **[配置管理](configuration_CN.md)** - 配置文件详解和最佳实践
- **[PO管理指南](po-management_CN.md)** - 补丁和覆盖管理详解

### 🎯 功能特性
- **[PO忽略功能](../features/po-ignore-feature_CN.md)** - 增强的文件忽略功能
- **[项目管理](../features/project-management_CN.md)** - 项目管理功能详解
- **[多仓库支持](../features/multi-repo-support_CN.md)** - .repo清单和多仓库环境

### 🔧 高级功能
- **[性能分析](../development/performance-analysis_CN.md)** - 性能监控和优化
- **[日志管理](../development/logging_CN.md)** - 日志记录和归档
- **[脚本扩展](../development/scripts_CN.md)** - 自定义脚本和插件

## 🎯 用户角色指南

### 👤 新用户
1. 阅读 [快速开始指南](getting-started_CN.md)
2. 了解 [基本概念](getting-started_CN.md#概述)
3. 尝试 [创建第一个项目](getting-started_CN.md#创建第一个项目)

### 👨‍💻 开发者
1. 掌握 [PO管理](po-management_CN.md)
2. 学习 [配置管理](configuration_CN.md)
3. 了解 [高级功能](../development/)

### 🚀 高级用户
1. 深入 [性能优化](../development/performance-analysis_CN.md)
2. 学习 [脚本扩展](../development/scripts_CN.md)
3. 参与 [项目贡献](../development/README_CN.md)

## 📋 常用工作流程

### 基本工作流程
```
安装 → 创建主板 → 创建项目 → 创建PO → 应用PO → 管理项目
  ↓         ↓         ↓         ↓         ↓         ↓
快速开始   主板管理   项目管理   PO创建   PO应用   日常维护
```

### PO管理流程
```
创建PO → 选择文件 → 生成补丁/覆盖 → 应用PO → 验证结果
   ↓         ↓           ↓            ↓         ↓
 po_new   文件选择    文件生成      po_apply   结果检查
```

### 配置管理流程
```
编辑配置 → 验证配置 → 应用配置 → 测试功能 → 备份配置
   ↓         ↓         ↓         ↓         ↓
配置文件   语法检查   配置应用   功能测试   配置备份
```

## 🔍 快速查找

### 按功能查找
| 功能 | 文档 | 命令 |
|------|------|------|
| 创建主板 | [快速开始](getting-started_CN.md) | `board_new` |
| 创建项目 | [快速开始](getting-started_CN.md) | `project_new` |
| 创建PO | [PO管理](po-management_CN.md) | `po_new` |
| 应用PO | [PO管理](po-management_CN.md) | `po_apply` |
| 回滚PO | [PO管理](po-management_CN.md) | `po_revert` |
| 配置管理 | [配置管理](configuration_CN.md) | 编辑.ini文件 |

### 按问题查找
| 问题类型 | 解决方案 | 文档 |
|----------|----------|------|
| 安装问题 | 检查系统要求 | [快速开始](getting-started_CN.md#系统要求) |
| 配置错误 | 验证配置文件 | [配置管理](configuration_CN.md#配置验证) |
| PO应用失败 | 检查PO配置 | [PO管理](po-management_CN.md#故障排除) |
| 性能问题 | 启用性能分析 | [性能分析](../development/performance-analysis_CN.md) |

## 📚 学习路径

### 入门路径（1-2小时）
1. [快速开始指南](getting-started_CN.md) - 30分钟
2. [基本命令练习](getting-started_CN.md#基本使用) - 30分钟
3. [创建简单项目](getting-started_CN.md#创建第一个项目) - 1小时

### 进阶路径（1-2天）
1. [命令参考](command-reference_CN.md) - 半天
2. [配置管理](configuration_CN.md) - 半天
3. [PO管理实践](po-management_CN.md) - 1天

### 专家路径（1-2周）
1. [高级功能](../development/) - 1周
2. [性能优化](../development/performance-analysis_CN.md) - 3天
3. [脚本开发](../development/scripts_CN.md) - 4天

## 🆘 获取帮助

### 自助帮助
- **命令行帮助**: `python -m src --help`
- **命令帮助**: `python -m src <命令> --help`
- **文档搜索**: 使用浏览器搜索功能

### 社区帮助
- **GitHub Issues**: [提交问题](https://github.com/wangguanran/ProjectManager/issues)
- **GitHub Discussions**: [参与讨论](https://github.com/wangguanran/ProjectManager/discussions)
- **贡献指南**: [参与开发](../development/README_CN.md)

### 紧急问题
- 检查 [故障排除](../troubleshooting_CN.md)
- 查看 [常见问题](../faq_CN.md)
- 提交详细的Issue报告

## 📝 文档反馈

我们重视您的反馈！如果您发现文档问题或有改进建议：

1. **提交Issue**: 在GitHub上创建Issue
2. **直接编辑**: 提交Pull Request改进文档
3. **讨论建议**: 在Discussions中提出建议

## 🔄 文档更新

- **最后更新**: 2024年12月
- **版本**: 1.0.0
- **维护者**: ProjectManager团队

---

## 🌐 其他语言版本

- [English Version](README_EN.md) - 英文版用户指南
- [中文版文档](../README_CN.md) - 中文版文档索引
