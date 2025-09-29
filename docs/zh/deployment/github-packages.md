# GitHub 包注册表配置

本文档解释了如何使用 GitHub Package Registry 发布 Python 包和 Docker 镜像。

## 概述

此项目配置为发布：
- **Python 包**: 到 GitHub Package Registry 和 PyPI
- **Docker 镜像**: 到 GitHub Container Registry (ghcr.io)

## 先决条件

1. **GitHub 令牌**: 您需要一个具有 `write:packages` 权限的 GitHub Personal Access Token
2. **PyPI API 令牌**: 您需要一个 PyPI API 令牌来发布到 PyPI
3. **仓库权限**: 仓库必须启用包发布功能

## 必需的密钥配置

### GitHub 仓库密钥

在您的 GitHub 仓库中，转到 Settings → Secrets and variables → Actions，并添加：

1. **PYPI_API_TOKEN**（PyPI 发布必需）
   - 值: 来自 https://pypi.org/manage/account/token/ 的 PyPI API 令牌
   - 注意: 使用 `__token__` 作为用户名，令牌作为密码

2. **GITHUB_TOKEN**（GitHub Actions 自动提供）
   - 无需手动添加，GitHub 自动提供

### PyPI API 令牌设置

1. **创建 PyPI API 令牌**:
   - 转到 https://pypi.org/manage/account/token/
   - 点击 "Add API token"
   - 选择范围: "Entire account" 或 "Specific project"
   - 复制令牌（以 `pypi-` 开头）

2. **添加到 GitHub 密钥**:
   - Repository Settings → Secrets and variables → Actions
   - New repository secret: `PYPI_API_TOKEN`
   - 值: 您的 PyPI 令牌

## 配置文件

### Python 包配置

- `pyproject.toml`: 包元数据和构建配置
- `.pypirc`: 包注册表认证（不提交到 git）
- `src/__version__.py`: 版本信息

### Docker 配置

- `Dockerfile`: 容器镜像定义
- `.dockerignore`: 从 Docker 构建上下文中排除的文件

## GitHub Actions 工作流程

### Python 包发布

**文件**: `.github/workflows/publish-python.yml`

**触发器**:
- 推送以 `v*` 开头的标签（例如 `v1.0.0`）
- 手动工作流程调度

**操作**:
1. 使用 `build` 构建 Python 包
2. 发布到 PyPI（需要 `PYPI_API_TOKEN`）
3. 发布到 GitHub Package Registry（使用 `GITHUB_TOKEN`）

### Docker 镜像发布

**文件**: `.github/workflows/publish-docker.yml`

**触发器**:
- 推送以 `v*` 开头的标签（例如 `v1.0.0`）
- 手动工作流程调度

**操作**:
1. 使用 Docker Buildx 构建 Docker 镜像
2. 发布到 GitHub Container Registry (ghcr.io)

### 发布创建

**文件**: `.github/workflows/publish-release.yml`

**触发器**:
- 推送以 `v*` 开头的标签（例如 `v1.0.0`）
- 手动工作流程调度

**操作**:
1. 构建和测试项目
2. 创建具有资源和文档的 GitHub Release

## 安装和使用

### Python 包

**从 PyPI**:
```bash
pip install multi-project-manager
```

**从 GitHub Package Registry**:
```bash
pip install multi-project-manager --index-url https://pypi.pkg.github.com/wangguanran/
```

**使用**:
```bash
python -m src --help
```

### Docker 镜像

**拉取镜像**:
```bash
docker pull ghcr.io/wangguanran/ProjectManager:latest
```

**运行容器**:
```bash
# 基本用法
docker run -v $(pwd)/projects:/app/projects ghcr.io/wangguanran/ProjectManager:latest

# 执行特定命令
docker run -v $(pwd)/projects:/app/projects ghcr.io/wangguanran/ProjectManager:latest po_apply myproject
```

## 版本管理

1. **更新版本**在 `src/__version__.py` 中
2. **创建并推送标签**:
   ```bash
   git tag v0.0.3
   git push origin v0.0.3
   ```
3. **GitHub Actions 将自动**:
   - 构建并将 Python 包发布到 PyPI 和 GitHub Package Registry
   - 构建并将 Docker 镜像发布到 GitHub Container Registry
   - 创建具有资源的 GitHub Release

## 故障排除

### 常见问题

1. **权限被拒绝**: 确保您的 GitHub 令牌具有 `write:packages` 权限
2. **PyPI 认证失败**: 检查 `PYPI_API_TOKEN` 是否正确设置
3. **包已存在**: 版本号必须唯一；增加版本号
4. **Docker 构建失败**: 检查所有必需文件是否存在且不在 `.dockerignore` 中

### 调试

- 检查 GitHub Actions 日志以获取详细的错误消息
- 验证环境变量是否正确设置
- 确保所有必需文件都已提交到仓库

## 安全注意事项

- 永远不要提交包含实际令牌的 `.pypirc` 文件
- 使用 GitHub Secrets 存储敏感信息
- 定期轮换您的 GitHub 令牌和 PyPI 令牌
- 在 GitHub 仓库设置中审查包权限

---

## 其他语言版本

- [English Version](../../en/deployment/github-packages.md) - 英文版文档
