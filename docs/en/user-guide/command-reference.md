# ProjectManager Command Reference

## Overview

This document describes every CLI command provided by ProjectManager, including syntax, parameters, status, and usage examples.

## Basic Syntax

```bash
python -m src <command> <arguments> [options]
```

## Global Options

All commands accept the following global options:

| Option | Description | Example |
|--------|-------------|---------|
| `--version` | Print the current version | `python -m src --version` |
| `--help` | Show help for the command or the CLI | `python -m src --help` |
| `--perf-analyze` | Enable performance analysis logs | `python -m src --perf-analyze po_apply proj1` |

---

## Project Management Commands

### `project_new` — Create a project

**Status**: ✅ Implemented

**Syntax**
```bash
python -m src project_new <project-name>
```

**Description**: Create a project using the configuration defined for the target board.

**Arguments**
- `project-name` (required): Name of the project to create.

**Configuration**: Project metadata is stored in the board-specific `.ini` file.

**Example**
```bash
python -m src project_new myproject
```

---

### `project_del` — Remove a project

**Status**: ✅ Implemented

**Syntax**
```bash
python -m src project_del <project-name>
```

**Description**: Delete the project directory and update its state in the configuration file.

**Arguments**
- `project-name` (required): Name of the project to remove.

**Example**
```bash
python -m src project_del myproject
```

---

### `project_build` — Build a project

**Status**: ✅ Implemented

**Syntax**
```bash
python -m src project_build <project-name>
```

**Description**: Build the specified project according to its configuration.

**Arguments**
- `project-name` (required): Name of the project to build.

**Example**
```bash
python -m src project_build myproject
```

---

## Board Management Commands

### `board_new` — Create a board

**Status**: ✅ Implemented

**Syntax**
```bash
python -m src board_new <board-name>
```

**Description**: Create a board and initialise the directory structure.

**Arguments**
- `board-name` (required): Name of the board to create.

**Generated structure**
```
projects/<board-name>/
  <board-name>.ini
  po/
```

**Example**
```bash
python -m src board_new myboard
```

---

### `board_del` — Remove a board

**Status**: ✅ Implemented

**Syntax**
```bash
python -m src board_del <board-name>
```

**Description**: Delete the specified board and all associated projects.

**Arguments**
- `board-name` (required): Name of the board to delete.

**Example**
```bash
python -m src board_del myboard
```

---

## PO (Patch/Override) Management Commands

### `po_apply` — Apply patches and overrides

**Status**: ✅ Implemented

**Syntax**
```bash
python -m src po_apply <project-name>
```

**Description**: Apply all configured patches and overrides for the target project.

**Arguments**
- `project-name` (required): Project whose PO set should be applied.

**Workflow**
1. Read `PROJECT_PO_CONFIG` from the project configuration.
2. Resolve the PO definitions (including includes/excludes).
3. Apply patch files via `git apply`.
4. Copy overrides into the project workspace.
5. Generate logs under the PO directory for auditing.

**Example**
```bash
python -m src po_apply myproject
```

---

### `po_revert` — Revert patches and overrides

**Status**: ✅ Implemented

**Syntax**
```bash
python -m src po_revert <project-name>
```

**Description**: Revert the previously applied patches and overrides for the project.

**Arguments**
- `project-name` (required): Project whose PO set should be reverted.

**Example**
```bash
python -m src po_revert myproject
```

---

### `po_new` — Create a PO directory

**Status**: ✅ Implemented

**Syntax**
```bash
python -m src po_new <project-name> <po-name>
```

**Description**: Create a new PO directory for the project and interactively choose files to include.

**Arguments**
- `project-name` (required): Project that owns the PO.
- `po-name` (required): Name of the PO directory to create.

**Generated structure**
```
projects/<board>/<project>/po/<po-name>/
  patches/
  overrides/
```

**Example**
```bash
python -m src po_new myproject feature_fix
```

---

### `po_del` — Remove a PO directory

**Status**: ✅ Implemented

**Syntax**
```bash
python -m src po_del <project-name> <po-name>
```

**Description**: Delete the specified PO directory and clean up associated metadata.

**Arguments**
- `project-name` (required): Project that owns the PO.
- `po-name` (required): PO directory to remove.

**Example**
```bash
python -m src po_del myproject feature_fix
```

---

### `po_list` — List configured POs

**Status**: ✅ Implemented

**Syntax**
```bash
python -m src po_list <project-name>
```

**Description**: Display the POs configured for a project, including status and paths.

**Arguments**
- `project-name` (required): Project whose POs should be listed.

**Example**
```bash
python -m src po_list myproject
```

---

## Related Documentation

- [Getting Started Guide](getting-started.md)
- [Configuration Management](configuration.md)
- [Project Management Feature](../features/project-management.md)
- [PO Ignore Feature](../features/po-ignore-feature.md)

---

## Other Languages

- [中文版](../../zh/user-guide/command-reference.md)
