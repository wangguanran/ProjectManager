# ProjectManager 开发者指南

本指南帮助开发者搭建本地环境、了解项目结构、遵循代码规范并参与贡献。完成基础设置后，可继续阅读 `docs/zh/development` 目录中的专题文档获取更多细节。

## 1. 仓库结构概览

```text
ProjectManager/
├── src/                # 核心源代码
├── tests/              # 自动化测试
├── docs/               # 文档
├── scripts/            # 辅助脚本
├── requirements.txt    # 运行依赖
└── pyproject.toml      # 项目配置
```

## 2. 开发环境搭建

1. **克隆仓库**
   ```bash
   git clone https://github.com/wangguanran/ProjectManager.git
   cd ProjectManager
   ```
2. **创建虚拟环境**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. **安装依赖**
   ```bash
   pip install -r requirements.txt
   pip install -e .
   ```
4. **安装开发工具（可选）**
   ```bash
   pip install pre-commit
   pre-commit install
   ```

## 3. 代码规范

- 遵循项目 `pyproject.toml` 中定义的格式化与 lint 规则。
- 提交前运行 `make lint`、`make test` 或 `pytest` 确认无报错。
- 编写新功能时附带相应的测试用例，并更新中英文文档。

## 4. 贡献流程

1. 从 `main` 分支拉取最新代码，创建功能分支。
2. 完成开发后执行本地测试和代码检查。
3. 填写清晰的提交信息，说明变更目的。
4. 发起 Pull Request，说明中英文文档是否同步更新。
5. 根据代码审查反馈进行迭代直至合并。

## 5. 进一步阅读

- [开发总览](../development/README.md)：构建流程、调试技巧与常见任务。
- [系统架构](../development/architecture.md)：组件拆分与数据流设计。
- [脚本与自动化](../development/scripts.md)：构建脚本与 CI/CD 流程。
- [测试策略](../development/testing.md)：测试层级、工具与覆盖率目标。
- [功能需求](../requirements/requirements.md)：功能规格与验收要点。

## 6. 文档贡献约定

- 同步维护 `docs/zh` 与 `docs/en` 两个目录，确保内容一致。
- 新建文档时更新语言索引文件（`docs/zh/README.md`、`docs/en/README.md`）。
- 若涉及用户操作，请同时更新用户模块与开发者模块中的相关链接。
