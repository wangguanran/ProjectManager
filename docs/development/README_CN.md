# 开发文档

本目录包含 ProjectManager 项目的开发相关文档。

## 内容

- **设置和安装**: 开发环境设置指南
- **架构**: 系统架构和设计文档
- **贡献**: 为项目做贡献的指南
- **测试**: 测试策略和程序

## 快速开始

1. **克隆仓库**:
   ```bash
   git clone <repository-url>
   cd ProjectManager
   ```

2. **设置开发环境**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -e .
   ```

3. **安装开发依赖**:
   ```bash
   pip install -r requirements-dev.txt
   ```

4. **运行测试**:
   ```bash
   python -m pytest tests/
   ```

## 开发工作流程

1. 从 `main` 创建功能分支
2. 进行更改并添加测试
3. 运行测试以确保一切正常
4. 根据需要更新文档
5. 提交拉取请求

## 项目结构

```
ProjectManager/
├── src/                    # 源代码
│   ├── plugins/           # 插件模块
│   ├── utils.py           # 工具函数
│   └── __main__.py        # 主入口点
├── tests/                 # 测试文件
├── docs/                  # 文档
├── projects/             # 项目配置
└── scripts/              # 构建和部署脚本
```

## 测试

- **单元测试**: 位于 `tests/` 目录
- **集成测试**: 测试完整工作流程
- **代码覆盖率**: 使用 `coverage run -m pytest` 运行

## 代码风格

- 遵循 PEP 8 风格指南
- 在适当的地方使用类型提示
- 为所有公共函数添加文档字符串
- 保持函数小而专注

## 文档

- 添加功能时更新相关文档
- 在文档字符串中包含示例
- 维护每个目录中的 README 文件

---

## 其他语言版本

- [English Version](README_EN.md) - 英文版文档
