# ProjectManager 文档

欢迎使用 ProjectManager 文档。本目录包含 ProjectManager 项目的综合文档，按类别组织。

## 文档结构

### 📁 [features/](features/)
功能特定的文档和用户指南。

- **[PO 忽略功能](features/po-ignore-feature_CN.md)**: 增强的PO忽略功能文档，支持路径包含匹配。
- **[项目管理](features/project-management_CN.md)**: 项目管理功能和能力的综合指南。

### 📁 [deployment/](deployment/)
部署和分发文档。

- **[GitHub 包](deployment/github-packages_CN.md)**: 将Python包和Docker镜像发布到GitHub Package Registry的指南。

### 📁 [development/](development/)
开发相关文档。

- **[开发指南](development/README_CN.md)**: 开发设置、工作流程和贡献指南。
- **[脚本和自动化](development/scripts_CN.md)**: 构建脚本、自动化工具和CI/CD工作流程的综合指南。
- **[系统架构](development/architecture_CN.md)**: 详细的系统架构和设计原则。
- **[测试策略](development/testing_CN.md)**: 测试程序、工具和质量保证实践。

## 快速导航

| 类别 | 描述 | 文档 |
|------|------|------|
| **功能** | 面向用户的功能和功能 | [PO 忽略功能](features/po-ignore-feature_CN.md), [项目管理](features/project-management_CN.md) |
| **部署** | 发布和分发指南 | [GitHub 包](deployment/github-packages_CN.md) |
| **开发** | 开发者指南和工作流程 | [开发指南](development/README_CN.md), [脚本](development/scripts_CN.md), [架构](development/architecture_CN.md), [测试](development/testing_CN.md) |

## 开始使用

1. **对于用户**: 从[功能](features/)部分开始，了解可用功能
2. **对于贡献者**: 查看[开发](development/)部分了解设置和贡献指南
3. **对于部署**: 参考[部署](deployment/)部分了解发布说明

## 为文档做贡献

添加新功能或进行更改时：

1. **更新相关文档**在适当的类别中
2. **使用清晰、简洁的语言**并提供示例
3. **遵循现有结构**和命名约定
4. **包含代码示例**在适当的地方
5. **测试文档**以确保准确性

## 文档标准

- **文件命名**: 使用小写字母和连字符（例如 `feature-name.md`）
- **语言**: 所有文档使用中文
- **格式**: Markdown格式，具有清晰的标题和结构
- **示例**: 包含实际示例和用例
- **链接**: 在文档内使用相对链接

## 支持

如果您发现文档问题或需要澄清：

1. 检查相关部分的现有信息
2. 在文档中搜索类似主题
3. 在GitHub上提出具体问题
4. 通过拉取请求贡献改进

---

## 其他语言版本

- [English Version](README_EN.md) - 英文版文档

---

## 已创建的中文版文档

### 功能文档
- [PO 忽略功能](features/po-ignore-feature_CN.md) - 增强的PO忽略功能文档
- [项目管理](features/project-management_CN.md) - 项目管理功能和能力综合指南

### 部署文档
- [GitHub 包](deployment/github-packages_CN.md) - 将Python包和Docker镜像发布到GitHub Package Registry的指南

### 开发文档
- [开发指南](development/README_CN.md) - 开发设置、工作流程和贡献指南
- [脚本和自动化](development/scripts_CN.md) - 构建脚本、自动化工具和CI/CD工作流程综合指南
- [系统架构](development/architecture_CN.md) - 详细系统架构和设计原则
- [测试策略](development/testing_CN.md) - 测试程序、工具和质量保证实践

所有中文版文档都保持了与英文版相同的结构和内容，但使用中文进行描述，方便中文用户理解和使用。

---

## 文档命名规范

### 中文版文档
- 使用 `_CN.md` 后缀
- 例如：`README_CN.md`, `po-ignore-feature_CN.md`

### 英文版文档  
- 使用 `_EN.md` 后缀
- 例如：`README_EN.md`, `po-ignore-feature_EN.md`

### 当前文档结构
```
docs/
├── README_CN.md                    # 中文版文档索引（默认）
├── README_EN.md                    # 英文版文档索引
├── features/
│   ├── po-ignore-feature_CN.md    # PO忽略功能（中文）
│   ├── po-ignore-feature_EN.md    # PO忽略功能（英文）
│   ├── project-management_CN.md   # 项目管理（中文）
│   └── project-management_EN.md   # 项目管理（英文）
├── deployment/
│   ├── github-packages_CN.md      # GitHub包部署（中文）
│   └── github-packages_EN.md      # GitHub包部署（英文）
└── development/
    ├── README_CN.md               # 开发指南（中文）
    ├── README_EN.md               # 开发指南（英文）
    ├── architecture_CN.md         # 系统架构（中文）
    ├── architecture_EN.md         # 系统架构（英文）
    ├── scripts_CN.md              # 脚本和自动化（中文）
    ├── scripts_EN.md              # 脚本和自动化（英文）
    ├── testing_CN.md              # 测试策略（中文）
    └── testing_EN.md              # 测试策略（英文）
```

所有文档都包含相互引用链接，方便用户在中英文版本之间切换。
