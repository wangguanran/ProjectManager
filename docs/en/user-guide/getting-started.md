# ProjectManager Getting Started Guide

## Overview

ProjectManager is a project and patch (PO) management tool designed for multi-board, multi-project environments. This guide helps you install and start using ProjectManager quickly.

## System Requirements

- **Operating System**: Linux (Ubuntu 18.04+ or CentOS 7+ recommended)
- **Python**: 3.7 or later
- **Git**: 2.20 or later
- **Memory**: At least 2 GB RAM
- **Disk Space**: At least 1 GB free space

## Quick Installation

### Method 1: Install from PyPI (recommended)
```bash
pip install multi-project-manager
```

### Method 2: Install from source
```bash
git clone https://github.com/wangguanran/ProjectManager.git
cd ProjectManager
pip install -e .
```

### Method 3: Use Docker
```bash
docker pull ghcr.io/wangguanran/projectmanager:latest
```

## Verify the Installation

```bash
# Check the version
python -m src --version

# Show the global help
python -m src --help
```

If both commands display information without errors, the installation succeeded.

## Create Your First Project

### 1. Create a board
```bash
# Create a board named "myboard"
python -m src board_new myboard
```

### 2. Create a project
```bash
# Create a project "myproject" under myboard
python -m src project_new myproject
```

### 3. Create a PO package
```bash
# Create a PO named "po_feature1"
python -m src po_new myproject po_feature1
```

### 4. Apply the PO
```bash
# Apply the PO to the project
python -m src po_apply myproject
```

## Basic Workflow

```
Create board → Create project → Create PO → Apply PO → Maintain project
    ↓             ↓             ↓             ↓             ↓
 board_new   project_new      po_new       po_apply       po_list
```

## Command Quick Reference

| Command | Purpose | Example |
|---------|---------|---------|
| `board_new` | Create a board | `python -m src board_new board1` |
| `project_new` | Create a project | `python -m src project_new proj1` |
| `po_new` | Create a PO | `python -m src po_new proj1 po1` |
| `po_apply` | Apply a PO | `python -m src po_apply proj1` |
| `po_revert` | Revert a PO | `python -m src po_revert proj1` |
| `po_list` | List available POs | `python -m src po_list proj1` |

## Sample Configuration

### Board configuration (`projects/myboard/myboard.ini`)

```ini
[myproject]
BOARD_NAME=myboard
PROJECT_PO_CONFIG=po_feature1
PROJECT_PO_IGNORE=vendor/* external/*
```

## Next Steps

- Read the [Command Reference](command-reference.md) for detailed parameters.
- Study [Configuration Management](configuration.md) to understand the `.ini` structure.
- Explore [Project Management](../features/project-management.md) and [PO Ignore Feature](../features/po-ignore-feature.md) for advanced workflows.

## Getting Help

- **CLI help**: `python -m src --help`
- **Command-specific help**: `python -m src <command> --help`
- **GitHub Issues**: [Report problems](https://github.com/wangguanran/ProjectManager/issues)
- **Documentation index**: Visit the [English documentation index](../README.md)

---

## Other Languages

- [中文版](../../zh/user-guide/getting-started.md)
