# ProjectManager Documentation

Welcome to the ProjectManager documentation. This directory contains comprehensive documentation for the ProjectManager project, organized by category.

## Documentation Structure

### 📁 [features/](features/)
Feature-specific documentation and user guides.

- **[PO Ignore Feature](features/po-ignore-feature_EN.md)**: Documentation for the enhanced PO ignore functionality with path containment matching.
- **[Project Management](features/project-management_EN.md)**: Comprehensive guide to project management features and capabilities.

### 📁 [deployment/](deployment/)
Deployment and distribution documentation.

- **[GitHub Packages](deployment/github-packages_EN.md)**: Guide for publishing Python packages and Docker images to GitHub Package Registry.

### 📁 [development/](development/)
Development-related documentation.

- **[Development Guide](development/README_EN.md)**: Development setup, workflow, and contribution guidelines.
- **[Scripts and Automation](development/scripts_EN.md)**: Comprehensive guide to build scripts, automation tools, and CI/CD workflows.
- **[System Architecture](development/architecture_EN.md)**: Detailed system architecture and design principles.
- **[Testing Strategy](development/testing_EN.md)**: Testing procedures, tools, and quality assurance practices.

## Quick Navigation

| Category | Description | Documents |
|----------|-------------|-----------|
| **Features** | User-facing features and functionality | [PO Ignore Feature](features/po-ignore-feature_EN.md), [Project Management](features/project-management_EN.md) |
| **Deployment** | Publishing and distribution guides | [GitHub Packages](deployment/github-packages_EN.md) |
| **Development** | Developer guides and workflows | [Development Guide](development/README_EN.md), [Scripts](development/scripts_EN.md), [Architecture](development/architecture_EN.md), [Testing](development/testing_EN.md) |

## Getting Started

1. **For Users**: Start with the [Features](features/) section to understand available functionality
2. **For Contributors**: Check the [Development](development/) section for setup and contribution guidelines
3. **For Deployment**: Refer to the [Deployment](deployment/) section for publishing instructions

## Contributing to Documentation

When adding new features or making changes:

1. **Update relevant documentation** in the appropriate category
2. **Use clear, concise language** and provide examples
3. **Follow the existing structure** and naming conventions
4. **Include code examples** where appropriate
5. **Test documentation** to ensure accuracy

## Documentation Standards

- **File Naming**: Use lowercase with hyphens (e.g., `feature-name.md`)
- **Language**: All documentation is in English
- **Format**: Markdown format with clear headings and structure
- **Examples**: Include practical examples and use cases
- **Links**: Use relative links within the documentation

## Support

If you find issues with the documentation or need clarification:

1. Check the relevant section for existing information
2. Search for similar topics in the documentation
3. Open an issue on GitHub with specific questions
4. Contribute improvements through pull requests

---

## Other Language Versions

- [中文版文档](README_CN.md) - Chinese documentation

---

## Documentation Naming Convention

### Chinese Documentation
- Uses `_CN.md` suffix
- Examples: `README_CN.md`, `po-ignore-feature_CN.md`

### English Documentation
- Uses `_EN.md` suffix  
- Examples: `README_EN.md`, `po-ignore-feature_EN.md`

### Current Documentation Structure
```
docs/
├── README_CN.md                    # Chinese documentation index (default)
├── README_EN.md                    # English documentation index
├── features/
│   ├── po-ignore-feature_CN.md    # PO Ignore Feature (Chinese)
│   ├── po-ignore-feature_EN.md    # PO Ignore Feature (English)
│   ├── project-management_CN.md   # Project Management (Chinese)
│   └── project-management_EN.md   # Project Management (English)
├── deployment/
│   ├── github-packages_CN.md      # GitHub Packages (Chinese)
│   └── github-packages_EN.md      # GitHub Packages (English)
└── development/
    ├── README_CN.md               # Development Guide (Chinese)
    ├── README_EN.md               # Development Guide (English)
    ├── architecture_CN.md         # System Architecture (Chinese)
    ├── architecture_EN.md         # System Architecture (English)
    ├── scripts_CN.md              # Scripts and Automation (Chinese)
    ├── scripts_EN.md              # Scripts and Automation (English)
    ├── testing_CN.md              # Testing Strategy (Chinese)
    └── testing_EN.md              # Testing Strategy (English)
```

All documents contain cross-references to facilitate switching between Chinese and English versions. 