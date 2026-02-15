# ProjectManager Quickstart Guide

This guide targets end users and explains how to install ProjectManager, perform the initial setup, and run the most common commands. After completing it, continue with the [full user manual](../user-guide/README.md) for deeper topics.

## 1. Prerequisites

- **Operating System**: Linux (Ubuntu 18.04+ or CentOS 7+ recommended).
- **Python**: Version 3.8 or later with `pip` available.
- **Git**: Version 2.20 or later for repository management.

## 2. Installation Options

### 2.1 Install from PyPI (recommended)
```bash
pip install multi-project-manager
```

### 2.2 Install from Source
```bash
git clone https://github.com/wangguanran/ProjectManager.git
cd ProjectManager
pip install -e .
```

### 2.3 Run with Docker
```bash
docker pull ghcr.io/wangguanran/projectmanager:latest
docker run --rm -v $(pwd)/projects:/app/projects \
  ghcr.io/wangguanran/projectmanager:latest --help
```

## 3. First-time Setup

1. Create a workspace directory (for example, `projects/`) to hold boards and projects.
2. Add a folder for each board and prepare the `<board>.ini` configuration file.
3. Use the CLI commands below to initialise board and project structures.
4. Refer to [Configuration Management](../user-guide/configuration.md) for detailed explanations.

## 4. Frequently Used Commands

```bash
# Create a board
python -m src board_new myboard

# Create a project
python -m src project_new myproject

# Create a PO package
python -m src po_new myproject po_feature_fix

# Apply PO changes
python -m src po_apply myproject
```

> Tip: Find the complete command catalogue in the [Command Reference](../user-guide/command-reference.md).

## 5. Suggested Learning Path

1. Start with [Getting Started](../user-guide/getting-started.md) to learn core concepts.
2. Validate your setup via [Configuration Management](../user-guide/configuration.md).
3. Explore advanced workflows in [Project Management](../features/project-management.md).
4. Optimise your patch layout with the [PO Ignore Feature](../features/po-ignore-feature.md).

## 6. Additional Resources

- [Publishing Guide](../deployment/github-packages.md): Release Python packages and Docker images.
- [Functional Requirements](../requirements/requirements.md): Understand capabilities and acceptance criteria.
- For questions, open an issue or check the FAQ section when available.

## Other Languages

- [Chinese Version](../../zh/user/README.md)
