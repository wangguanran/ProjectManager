# ProjectManager 用户快速上手指南

本指南面向终端用户，介绍 ProjectManager 的安装、初次配置与常用操作。阅读完毕后，你可以继续查阅 [详细用户手册](../user-guide/README.md) 获得更深入的指引。

## 1. 环境要求

- **操作系统**：建议使用 Linux（Ubuntu 18.04+ 或 CentOS 7+）。
- **Python**：3.8 及以上版本，并安装 `pip`。
- **Git**：2.20 及以上版本，用于同步仓库与管理补丁。

## 2. 安装方式

### 2.1 通过 PyPI 安装（推荐）
```bash
pip install multi-project-manager
```

### 2.2 从源码安装
```bash
git clone https://github.com/wangguanran/ProjectManager.git
cd ProjectManager
pip install -e .
```

### 2.3 使用 Docker 镜像
```bash
docker pull ghcr.io/wangguanran/projectmanager:latest
docker run --rm -v $(pwd)/projects:/app/projects \
  ghcr.io/wangguanran/projectmanager:latest --help
```

## 3. 初次配置

1. 新建一个工作目录（例如 `projects/`）存放主板与项目。
2. 为每块主板创建文件夹，并准备 `<board>.ini` 配置文件。
3. 使用 CLI 初始化主板与项目结构，详见后续命令示例。
4. 如需了解配置细节，请阅读 [配置管理](../user-guide/configuration.md)。

## 4. 常用命令示例

```bash
# 创建主板
python -m src board_new myboard

# 创建项目
python -m src project_new myproject

# 创建 PO
python -m src po_new myproject po_feature_fix

# 应用 PO
python -m src po_apply myproject
```

> 提示：完整命令列表及参数说明请参考 [命令参考](../user-guide/command-reference.md)。

## 5. 推荐学习路径

1. 阅读 [快速开始](../user-guide/getting-started.md) 熟悉基本概念。
2. 按照 [配置管理](../user-guide/configuration.md) 校验项目结构。
3. 查阅 [项目管理](../features/project-management.md) 探索更多场景。
4. 结合 [PO 忽略功能](../features/po-ignore-feature.md) 优化补丁目录。

## 6. 进一步阅读

- [发布指南](../deployment/github-packages.md)：发布 Python 包与 Docker 镜像。
- [功能需求](../requirements/requirements.md)：了解系统能力与验收标准。
- 如遇问题，可在项目 Issue 中提问或查阅常见问题章节（若有）。

## 其他语言版本

- [English Version](../../en/user/README.md)
