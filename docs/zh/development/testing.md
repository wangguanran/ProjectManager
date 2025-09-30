# 测试策略和程序

本文档描述了 ProjectManager 项目中使用的测试策略、程序和工具。

## 测试理念

ProjectManager 遵循全面的测试方法，确保代码质量、可靠性和可维护性。测试策略涵盖多个级别和类型的测试，以提供对系统功能的信心。

## 测试级别

### 1. 单元测试

**目的**: 隔离测试单个函数和方法

**覆盖范围**: 核心功能、工具函数和插件方法

**工具**: pytest, unittest

**位置**: `tests/` 目录

**示例**:
```python
def test_parse_po_config():
    """测试 PO 配置解析。"""
    config = "po1 po2 -po3 po4[file1 file2]"
    result = PatchOverride._PatchOverride__parse_po_config(config)
    assert "po1" in result[0]  # apply_pos
    assert "po3" in result[1]  # exclude_pos
```

### 2. 集成测试

**目的**: 测试模块和组件之间的交互

**覆盖范围**: 端到端工作流程、插件交互、文件系统操作

**工具**: 具有真实文件系统操作的 pytest

**示例**:
```python
def test_po_creation_workflow():
    """测试完整的 PO 创建工作流程。"""
    # 设置测试环境
    # 执行 PO 创建
    # 验证结果
    # 清理
```

### 3. 系统测试

**目的**: 在真实环境中测试完整系统

**覆盖范围**: 完整应用程序工作流程、命令行界面、配置管理

**工具**: 具有 Docker 容器、真实 Git 仓库的 pytest

## 测试组织

### 目录结构

```
tests/
├── test_main.py              # 主应用程序测试
├── test_log_manager.py       # 日志功能测试
├── test_profiler.py          # 性能分析功能测试
├── test_utils.py             # 工具函数测试
├── projects/                 # 测试项目配置
│   ├── board01/
│   │   ├── board01.ini
│   │   └── po/
│   └── common/
└── fixtures/                 # 测试数据和夹具
```

### 测试文件命名约定

- `test_*.py`: 测试文件
- `test_*_*.py`: 具有描述性名称的测试文件
- `*_test.py`: 测试文件的替代命名

### 测试函数命名约定

- `test_*`: 测试函数
- `test_*_*`: 描述性测试函数名称
- `test_*_error_*`: 错误条件测试
- `test_*_success_*`: 成功条件测试

## 测试工具和框架

### 1. pytest

**主要测试框架**

**功能**:
- 测试数据设置的夹具支持
- 参数化测试
- 丰富的断言消息
- 插件生态系统

**配置**: `pytest.ini` 或 `pyproject.toml`

**用法**:
```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/test_utils.py

# 运行详细输出
pytest -v

# 运行覆盖率
pytest --cov=src
```

### 2. Coverage.py

**代码覆盖率测量**

**功能**:
- 行覆盖率测量
- 分支覆盖率分析
- HTML 报告生成
- 覆盖率阈值

**配置**: `.coveragerc`

**用法**:
```bash
# 运行带覆盖率的测试
coverage run -m pytest

# 生成覆盖率报告
coverage report

# 生成 HTML 报告
coverage html
```

### 3. Mock 和 Patching

**隔离和控制**

**功能**:
- 模拟外部依赖
- 控制文件系统操作
- 模拟 Git 命令
- 测试错误条件

**用法**:
```python
from unittest.mock import patch, MagicMock

@patch('subprocess.run')
def test_git_command(mock_run):
    mock_run.return_value.returncode = 0
    # 测试实现
```

## 测试数据管理

### 1. 测试仓库

**合成 Git 仓库**

**目的**: 提供受控的测试环境

**结构**:
```
tests/projects/
├── board01/
│   ├── .git/                 # Git 仓库
│   ├── board01.ini          # 配置
│   ├── src/                 # 源文件
│   └── po/                  # PO 目录
└── common/
    └── .repo/               # Repo 清单
```

### 2. 测试配置文件

**示例配置文件**

**目的**: 测试配置解析和验证

**示例**:
```ini
# tests/projects/board01/board01.ini
[project1]
board_name = board01
PROJECT_PO_CONFIG = po1 po2
PROJECT_PO_IGNORE = vendor/*

[project2]
board_name = board01
PROJECT_PO_CONFIG = po3 -po4
```

### 3. 测试夹具

**可重用的测试数据**

**目的**: 在多个测试中提供一致的测试数据

**实现**:
```python
import pytest

@pytest.fixture
def sample_project_config():
    return {
        "project1": {
            "board_name": "board01",
            "PROJECT_PO_CONFIG": "po1 po2",
            "PROJECT_PO_IGNORE": "vendor/*"
        }
    }
```

## 测试程序

### 1. 预提交测试

**提交前的自动化测试**

**工具**: Git 钩子 (`hooks/pre-commit`)

**程序**:
- 运行单元测试
- 检查代码格式
- 验证语法
- 基本集成测试

**配置**:
```bash
# 安装钩子
./hooks/install_hooks.sh
```

### 2. 预推送测试

**推送前的综合测试**

**工具**: Git 钩子 (`hooks/pre-push`)

**程序**:
- 完整测试套件执行
- 覆盖率分析
- 性能测试
- 集成测试

### 3. 持续集成测试

**CI/CD 中的自动化测试**

**工具**: GitHub Actions

**工作流程**:
- `.github/workflows/python-app.yml`
- `.github/workflows/pylint.yml`

**程序**:
- 多平台测试
- 依赖测试
- 构建验证
- 质量检查

## 测试类别

### 1. 功能测试

**目的**: 验证功能按预期工作

**示例**:
- PO 创建和管理
- 配置文件解析
- 仓库发现
- 文件修改检测

### 2. 错误处理测试

**目的**: 验证正确的错误处理和恢复

**示例**:
- 无效配置文件
- 缺少依赖项
- 文件系统错误
- Git 命令失败

### 3. 性能测试

**目的**: 验证性能特征

**示例**:
- 大型仓库扫描
- 负载下的内存使用
- 处理时间测量
- 可扩展性测试

### 4. 安全测试

**目的**: 验证安全措施

**示例**:
- 路径遍历预防
- 输入验证
- 权限检查
- 配置清理

## 测试执行

### 1. 本地开发测试

**快速反馈循环**

**命令**:
```bash
# 在开发中运行测试
pytest tests/ -v

# 运行特定测试类别
pytest tests/ -k "test_po"

# 运行覆盖率
pytest --cov=src --cov-report=html
```

### 2. 完整测试套件

**综合测试**

**命令**:
```bash
# 运行所有带覆盖率的测试
python coverage_report.py

# 运行不同 Python 版本
tox

# 运行性能测试
pytest tests/ -m "performance"
```

### 3. 持续集成

**自动化测试**

**触发器**:
- 推送到任何分支
- 拉取请求
- 标签创建
- 手动工作流程调度

**环境**:
- Ubuntu (最新)
- Windows (最新)
- macOS (最新)
- 多个 Python 版本

## 覆盖率要求

### 1. 覆盖率阈值

**最低要求**:
- **行覆盖率**: 80%
- **分支覆盖率**: 70%
- **函数覆盖率**: 85%

### 2. 覆盖率排除

**从覆盖率中排除**:
- 测试文件
- 配置文件
- 文档
- 构建脚本
- 第三方代码

### 3. 覆盖率报告

**报告类型**:
- 控制台输出
- HTML 报告
- XML 报告（用于 CI 集成）
- 覆盖率徽章

## 测试维护

### 1. 测试更新

**何时更新测试**:
- 添加新功能
- 实现错误修复
- API 更改
- 配置更改

### 2. 测试重构

**最佳实践**:
- 保持测试简单和专注
- 使用描述性测试名称
- 避免测试相互依赖
- 维护测试数据一致性

### 3. 测试文档

**文档要求**:
- 测试目的和范围
- 测试数据设置
- 预期结果
- 已知限制

## 故障排除测试

### 1. 常见问题

**测试失败**:
- 环境差异
- 文件系统权限
- Git 配置问题
- 依赖版本冲突

### 2. 调试测试

**调试技术**:
```bash
# 运行调试输出
pytest -v -s

# 运行单个测试
pytest tests/test_utils.py::test_specific_function

# 运行 pdb
pytest --pdb
```

### 3. 测试环境

**环境设置**:
```bash
# 设置测试环境
./setup_venv.sh

# 安装测试依赖
pip install -r requirements-dev.txt

# 验证测试环境
pytest --collect-only
```

## 性能测试

### 1. 性能基准

**关键指标**:
- 仓库扫描时间
- PO 应用时间
- 内存使用
- 文件系统操作

### 2. 负载测试

**测试场景**:
- 大量仓库
- 复杂 PO 配置
- 多个并发操作
- 大型文件修改

### 3. 性能监控

**工具**:
- 内置性能分析器 (`src/profiler.py`)
- pytest-benchmark
- memory_profiler
- cProfile

## 未来测试改进

### 1. 测试自动化

**计划增强**:
- 自动化测试数据生成
- 动态测试用例创建
- 性能回归测试
- 安全漏洞扫描

### 2. 测试基础设施

**基础设施改进**:
- 测试容器化
- 并行测试执行
- 分布式测试
- 基于云的测试环境

### 3. 测试质量

**质量改进**:
- 变异测试
- 基于属性的测试
- 契约测试
- 混沌工程

---

## 其他语言版本

- [English Version](../../en/development/testing.md) - 英文版文档
