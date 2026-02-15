# ProjectManager Command Reference

## Overview

This document describes every CLI command provided by ProjectManager, including syntax, parameters, status, and usage examples.

## Basic Syntax

```bash
python -m src <command> [arguments] [options]
```

## Global Options

All commands accept the following global options:

| Option | Description | Example |
|--------|-------------|---------|
| `--version` | Print the current version | `python -m src --version` |
| `--help` | Show help for the command or the CLI | `python -m src --help` |
| `--perf-analyze` | Enable performance analysis logs | `python -m src --perf-analyze po_apply proj1` |
| `--load-scripts` | Opt-in: import workspace scripts under `projects/scripts/*.py` (unsafe in untrusted workspaces) | `python -m src --load-scripts project_build proj1` |
| `--no-fuzzy` | Require exact operation match (disable fuzzy matching) | `python -m src --no-fuzzy po_list proj1` |
| `--safe-mode` | Safe mode for untrusted workspaces (requires explicit confirmation for destructive ops; blocks env-based script loading) | `python -m src --safe-mode po_apply proj1 --dry-run` |
| `--allow-network` | Safe mode: allow network operations such as `upgrade` | `python -m src --safe-mode --allow-network upgrade --dry-run` |
| `-y`, `--yes` | Safe mode: explicitly confirm destructive operations (non-interactive) | `python -m src --safe-mode -y po_apply proj1` |

---

## Maintenance Commands

### `upgrade` — Upgrade projman binary

**Status**: ✅ Implemented

**Syntax**
```bash
python -m src upgrade [--user|--system|--prefix <dir>] [--owner <owner>] [--repo <repo>] [--require-checksum]
```

**Description**: Auto-detect the current platform/architecture, fetch the latest GitHub Release asset, optionally verify sha256 checksum (if published), and install `projman` to the selected location.

**Examples**
```bash
python -m src upgrade --user
python -m src upgrade --prefix ~/.local/bin
python -m src upgrade --dry-run
python -m src upgrade --require-checksum
```

---

### `doctor` — Workspace diagnostics

**Status**: ✅ Implemented

**Syntax**
```bash
python -m src doctor [--json] [--strict]
```

**Description**: Validate the current workspace layout/config and print remediation hints before running build/PO operations.

**Options**
- `--json`: Print a machine-readable JSON report to stdout.
- `--strict`: Treat warnings as errors (non-zero exit).

**Examples**
```bash
python -m src doctor
python -m src doctor --json
python -m src doctor --strict
```

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
python -m src project_build <project-name> [--emit-plan [<path>]]
```

**Description**: Build the specified project according to its configuration.

**Arguments**
- `project-name` (required): Name of the project to build.

**Options**
- `--emit-plan`: Emit a machine-readable JSON execution plan to stdout (or to `<path>` when provided) without executing any build steps.

**Example**
```bash
python -m src project_build myproject
```

---

### `project_diff` — Generate a repository diff snapshot

**Status**: ✅ Implemented

**Syntax**
```bash
python -m src project_diff <project-name> [--keep-diff-dir] [--dry-run] [--emit-plan [<path>]]
```

**Description**: Generate a timestamped diff directory under `.cache/build/<project-name>/<timestamp>/diff` and archive it as `diff_<project>_<timestamp>.tar.gz`.

**Arguments**
- `project-name` (required): Name of the project to diff.

**Options**
- `--keep-diff-dir`: Preserve the diff directory after creating the tar.gz archive.
- `--dry-run`: Print planned actions without creating files/directories.
- `--emit-plan`: Emit a machine-readable JSON execution plan to stdout (or to `<path>` when provided) without writing any diff output.

**Example**
```bash
python -m src project_diff myproject --keep-diff-dir
```

---

### `project_pre_build` — Run the pre-build stage

**Status**: ✅ Implemented

**Syntax**
```bash
python -m src project_pre_build <project-name>
```

**Description**: Pre-build stage used by `project_build` (applies POs and generates a diff snapshot).

**Arguments**
- `project-name` (required): Name of the project.

**Example**
```bash
python -m src project_pre_build myproject
```

---

### `project_do_build` — Run the build stage

**Status**: ✅ Implemented

**Syntax**
```bash
python -m src project_do_build <project-name>
```

**Description**: Build stage used by `project_build` (runs the configured `PROJECT_BUILD_CMD` when present).

**Arguments**
- `project-name` (required): Name of the project.

**Example**
```bash
python -m src project_do_build myproject
```

---

### `project_post_build` — Run the post-build stage

**Status**: ✅ Implemented

**Syntax**
```bash
python -m src project_post_build <project-name>
```

**Description**: Post-build stage used by `project_build` (runs the configured `PROJECT_POST_BUILD_CMD` when present).

**Arguments**
- `project-name` (required): Name of the project.

**Example**
```bash
python -m src project_post_build myproject
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
python -m src po_apply <project-name> [--dry-run] [--emit-plan [<path>]] [--force] [--reapply] [--po <po1,po2>]
```

**Description**: Apply all configured patches and overrides for the target project.

**Arguments**
- `project-name` (required): Project whose PO set should be applied.

**Options**
- `--dry-run`: Print planned actions without modifying files.
- `--emit-plan`: Emit a machine-readable JSON execution plan to stdout (or to `<path>` when provided) without modifying repositories.
- `--force`: Allow destructive operations (for example, override `.remove` deletions) and allow custom copy targets outside the workspace/repositories.
- `--reapply`: Apply a PO even if applied records already exist (ignores existing markers and overwrites them after success).
- `--po`: Apply only the selected PO(s) from `PROJECT_PO_CONFIG` (comma/space separated).

**Workflow**
1. Read `PROJECT_PO_CONFIG` from the project configuration.
2. Resolve the PO definitions (including includes/excludes).
3. Apply patch files via `git apply`.
4. Copy overrides into the project workspace.
5. Write an applied record under each target repository root to track applied state (for example: `<repo>/.cache/po_applied/<board>/<project>/<po>.json`).

**Example**
```bash
python -m src po_apply myproject
```

---

### `po_revert` — Revert patches and overrides

**Status**: ✅ Implemented

**Syntax**
```bash
python -m src po_revert <project-name> [--dry-run] [--emit-plan [<path>]] [--po <po1,po2>]
```

**Description**: Revert the previously applied patches and overrides for the project, and remove applied record markers so the PO can be applied again.

**Arguments**
- `project-name` (required): Project whose PO set should be reverted.

**Options**
- `--dry-run`: Print planned actions without modifying files.
- `--emit-plan`: Emit a machine-readable JSON execution plan to stdout (or to `<path>` when provided) without modifying repositories.
- `--po`: Revert only the selected PO(s) from `PROJECT_PO_CONFIG` (comma/space separated).

**Example**
```bash
python -m src po_revert myproject
```

---

### `po_new` — Create a PO directory

**Status**: ✅ Implemented

**Syntax**
```bash
python -m src po_new <project-name> <po-name> [--force]
```

**Description**: Create a new PO directory for the project and interactively choose files to include.

**Arguments**
- `project-name` (required): Project that owns the PO.
- `po-name` (required): Name of the PO directory to create.

**Options**
- `--force`: Skip confirmation prompts and create an empty directory structure.

**Generated structure**
```
projects/<board>/po/<po-name>/
  patches/
  overrides/
```

**Example**
```bash
python -m src po_new myproject po_feature_fix
```

---

### `po_update` — Update an existing PO directory

**Status**: ✅ Implemented

**Syntax**
```bash
python -m src po_update <project-name> <po-name> [--force]
```

**Description**: Update an existing PO by re-running the `po_new` workflow (the PO directory must already exist).

**Arguments**
- `project-name` (required): Project that owns the PO.
- `po-name` (required): PO directory to update.

**Options**
- `--force`: Skip confirmation prompts.

**Example**
```bash
python -m src po_update myproject po_feature_fix --force
```

---

### `po_del` — Remove a PO directory

**Status**: ✅ Implemented

**Syntax**
```bash
python -m src po_del <project-name> <po-name> [--force]
```

**Description**: Delete the specified PO directory and clean up associated metadata.

**Arguments**
- `project-name` (required): Project that owns the PO.
- `po-name` (required): PO directory to remove.

**Options**
- `--force`: Skip confirmation prompts.

**Example**
```bash
python -m src po_del myproject po_feature_fix
```

---

### `po_list` — List configured POs

**Status**: ✅ Implemented

**Syntax**
```bash
python -m src po_list <project-name> [--short] [--po <po1,po2>] [--json]
```

**Description**: Display the POs configured for a project, including status and paths.

**Arguments**
- `project-name` (required): Project whose POs should be listed.

**Options**
- `--short`: Print only PO names (no file lists).
- `--po`: List only the selected PO(s) from `PROJECT_PO_CONFIG` (comma/space separated).
- `--json`: Print a machine-readable JSON payload to stdout.

**Example**
```bash
python -m src po_list myproject
```

---

### `po_status` — Show applied record status

**Status**: ✅ Implemented

**Syntax**
```bash
python -m src po_status <project-name> [--po <po1,po2>] [--short] [--json]
```

**Description**: Show applied record markers for POs under each target repository root.

**Arguments**
- `project-name` (required): Project whose PO set should be inspected.

**Options**
- `--po`: Inspect only the selected PO(s) from `PROJECT_PO_CONFIG` (comma/space separated).
- `--short`: Print per-PO summary only.
- `--json`: Print a machine-readable JSON payload to stdout.

**Example**
```bash
python -m src po_status myproject --po po_base,po_fix --short
```

---

### `po_clear` — Clear applied record markers

**Status**: ✅ Implemented

**Syntax**
```bash
python -m src po_clear <project-name> [--po <po1,po2>] [--dry-run]
```

**Description**: Remove applied record markers (without reverting any file changes).

**Arguments**
- `project-name` (required): Project whose PO applied records should be cleared.

**Options**
- `--po`: Clear only the selected PO(s) from `PROJECT_PO_CONFIG` (comma/space separated).
- `--dry-run`: Print planned deletions without removing files.

**Example**
```bash
python -m src po_clear myproject --po po_base --dry-run
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
