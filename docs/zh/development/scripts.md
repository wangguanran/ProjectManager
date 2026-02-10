# 脚本和自动化

本文档描述了 ProjectManager 项目中可用的各种脚本和自动化工具。

## 构建和安装脚本

### `install.sh`

安装由 `build.sh` 生成的独立 `projman` 可执行文件。

**用法**:
```bash
./install.sh [--system|--user] [--prefix DIR]
```

**功能**:
- 将 `out/binary/projman` 复制到安装目录
- 以 root 运行时默认安装到 `/usr/local/bin`，否则安装到 `~/.local/bin`
- 当安装目录需要权限时自动使用 `sudo`
- 对用户态安装输出 PATH 配置提示

### `uninstall.sh`

从系统中移除 ProjectManager。

**用法**:
```bash
./uninstall.sh
```

**功能**:
- 移除已安装的 Python 包
- 清理配置文件
- 移除虚拟环境（如果由安装脚本创建）
- 从 `~/.local/bin` 和 `/usr/local/bin` 移除独立 `projman`

### `setup_venv.sh`

为开发设置 Python 虚拟环境。

**用法**:
```bash
./setup_venv.sh
```

**功能**:
- 创建新的虚拟环境
- 从 `requirements.txt` 安装依赖（设置 `INSTALL_DEPS=0` 可跳过）
- 激活环境
- 提供开发设置说明

## 构建和发布脚本

### `build.sh`

构建 Python 包以及独立的 `projman` 二进制（PyInstaller）。

**用法**:
```bash
./build.sh
```

**功能**:
- 默认在 `venv/` 中执行（不存在则自动创建）
- Python 包输出到 `out/package/`
- 独立二进制输出到 `out/binary/`
- 仅 Linux：尝试使用 `staticx` 做静态链接（best-effort）
- 只会构建当前系统/架构的二进制；跨平台产物请用 GitHub Actions Release 工作流

### `release.sh`

创建具有版本管理的新发布。

**用法**:
```bash
./release.sh [版本]
```

**功能**:
- 更新源文件中的版本
- 创建 Git 标签
- 构建和发布包
- 创建 GitHub 发布
- 更新变更日志

### `get_latest_release.sh`

根据当前系统/架构下载最新 Release 的资源并安装 `projman`。

**用法**:
```bash
./get_latest_release.sh [--system|--user] [--prefix DIR] [-t TOKEN]
```

**功能**:
- 从 GitHub API 获取最新发布
- 显示发布信息
- 自动选择最匹配的资源（例如 `projman-linux-x86_64`）
- 以 root 运行时默认安装到 `/usr/local/bin`，否则安装到 `~/.local/bin`
- 当安装目录需要权限时自动使用 `sudo`
- Windows 请使用 `install.ps1`

### `install.ps1`

Windows 平台安装脚本（PowerShell）。

**用法**:
```powershell
iwr -useb https://raw.githubusercontent.com/wangguanran/ProjectManager/<tag>/install.ps1 | iex
```

**功能**:
- 下载最新的 Windows Release 资源（例如 `projman-windows-x86_64.exe`）
- 安装 `projman.exe` 到用户或系统目录
- 自动更新 PATH（用户或系统）

### `get_latest_artifact.sh`（GitHub Actions artifacts）

下载最新成功的 GitHub Actions *artifact* 并安装 `projman`。

说明:
- GitHub Actions artifact 下载需要鉴权，必须提供 `GITHUB_TOKEN`。
- 如果希望免 token（公开仓库），建议使用 `get_latest_release.sh`（GitHub Releases）。

## 开发脚本

### `coverage_report.py`

为项目生成代码覆盖率报告。

**用法**:
```bash
python coverage_report.py
```

**功能**:
- 运行带有覆盖率测量的测试
- 生成 HTML 覆盖率报告
- 计算覆盖率统计
- 识别未覆盖的代码区域

### `fix_trailing_whitespace.sh`

从源文件中移除尾随空格。

**用法**:
```bash
./fix_trailing_whitespace.sh
```

**功能**:
- 查找并移除尾随空格
- 处理所有源文件
- 维护文件格式
- 提高代码质量

## Git 钩子

### `hooks/install_hooks.sh`

安装 Git 钩子以进行自动化代码质量检查。

**用法**:
```bash
./hooks/install_hooks.sh
```

**功能**:
- 安装 pre-commit 和 pre-push 钩子
- 配置自动化测试
- 设置代码质量检查
- 确保一致的代码标准

### `hooks/pre-commit`

在每个提交前运行的 pre-commit 钩子。

**功能**:
- 运行代码格式检查
- 执行基本测试
- 验证代码语法
- 防止有问题的提交

### `hooks/pre-push`

在推送到远程前运行的 pre-push 钩子。

**功能**:
- 运行综合测试
- 检查代码覆盖率
- 验证项目结构
- 确保代码质量标准

## GitHub Actions 工作流程

### `.github/workflows/python-app.yml`

Python 应用程序的主要 CI/CD 工作流程。

**触发器**:
- 推送到 main 分支
- 拉取请求
- 手动工作流程调度

**操作**:
- 在多个 Python 版本上运行测试
- 使用 pylint 检查代码质量
- 生成覆盖率报告
- 验证包构建

### `.github/workflows/pylint.yml`

代码质量检查工作流程。

**触发器**:
- 推送到任何分支
- 拉取请求

**操作**:
- 运行 pylint 代码分析
- 报告代码质量问题
- 强制执行编码标准
- 提供详细反馈

### `.github/workflows/publish-python.yml`

Python 包发布工作流程。

**触发器**:
- 推送以 `v*` 开头的标签
- 手动工作流程调度

**操作**:
- 构建 Python 包
- 发布到 PyPI
- 发布到 GitHub Package Registry
- 创建发布资源

### `.github/workflows/publish-docker.yml`

Docker 镜像发布工作流程。

**触发器**:
- 推送以 `v*` 开头的标签
- 手动工作流程调度

**操作**:
- 构建 Docker 镜像
- 发布到 GitHub Container Registry
- 使用版本和最新标签
- 验证镜像功能

### `.github/workflows/publish-release.yml`

发布创建工作流程。

**触发器**:
- 推送以 `v*` 开头的标签
- 手动工作流程调度

**操作**:
- 创建 GitHub 发布
- 上传发布资源
- 生成发布说明
- 通知利益相关者

## Docker 配置

### `Dockerfile`

ProjectManager 的 Docker 镜像定义。

**功能**:
- 多阶段构建以优化
- Python 3.9+ 基础镜像
- 最小运行时依赖
- 安全配置

### `.dockerignore`

从 Docker 构建上下文中排除的文件。

**排除项目**:
- Git 仓库文件
- 开发工具
- 测试文件
- 文档
- 构建工件

## 配置文件

### `.pylintrc`

用于代码质量检查的 Pylint 配置。

**设置**:
- 代码风格规则
- 错误检测模式
- 自定义消息格式
- 项目特定配置

### `pyproject.toml`

项目配置和构建设置。

**部分**:
- 项目元数据
- 构建系统配置
- 开发依赖项
- 工具配置

### `requirements.txt`

Python 包依赖项。

**类别**:
- 运行时依赖项
- 开发依赖项
- 测试依赖项
- 构建依赖项

## 使用示例

### 开发设置

```bash
# 设置开发环境
./setup_venv.sh

# 安装 Git 钩子
./hooks/install_hooks.sh

# 运行带覆盖率的测试
python coverage_report.py
```

### 构建和发布

```bash
# 构建 Python 包 + 独立二进制
./build.sh

# 创建新发布
./release.sh v1.2.3

# 检查最新发布
./get_latest_release.sh
```

### 代码质量

```bash
# 修复格式问题
./fix_trailing_whitespace.sh

# 运行代码质量检查
pylint src/

# 生成覆盖率报告
python coverage_report.py
```

## 最佳实践

1. **始终运行测试**在提交代码前
2. **使用 Git 钩子**进行自动化质量检查
3. **遵循版本控制**发布约定
4. **测试构建**在推送前本地测试
5. **记录更改**在发布说明中

## 故障排除

### 常见问题

1. **构建失败**: 检查依赖项和 Python 版本
2. **钩子错误**: 验证 Git 钩子安装
3. **覆盖率问题**: 确保测试正确运行
4. **发布问题**: 检查版本号和标签

### 调试模式

启用详细输出以进行调试：

```bash
# 详细构建
bash -x ./build.sh

# 调试安装
bash -x ./install.sh

# 详细覆盖率
python coverage_report.py --verbose
```

---

## 其他语言版本

- [English Version](../../en/development/scripts.md) - 英文版文档
