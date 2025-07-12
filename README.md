# ProjectManager

![GitHub stars](https://img.shields.io/github/stars/wangguanran/ProjectManager.svg) ![GitHub forks](https://img.shields.io/github/forks/wangguanran/ProjectManager.svg) ![GitHub issues](https://img.shields.io/github/issues/wangguanran/ProjectManager.svg) ![GitHub last commit](https://img.shields.io/github/last-commit/wangguanran/ProjectManager.svg)
![Build Status](https://github.com/wangguanran/ProjectManager/actions/workflows/python-app.yml/badge.svg) ![Pylint](https://github.com/wangguanran/ProjectManager/actions/workflows/pylint.yml/badge.svg)
![License](https://img.shields.io/github/license/wangguanran/ProjectManager.svg) ![Python](https://img.shields.io/badge/python-3.7+-blue.svg) ![Platform](https://img.shields.io/badge/platform-linux-blue.svg)

Universal Project and Patch (PO) Management Tool

## Project Overview

ProjectManager is a project management and patch (patch/override, PO) management tool for multi-board, multi-project environments. It supports project/board creation, deletion, building, as well as PO directory management and patch application/rollback operations. Suitable for scenarios requiring batch management of different hardware platforms and custom patches.

## Installation

### Python Package

**From PyPI**:
```bash
pip install multi-project-manager
```

**From GitHub Package Registry**:
```bash
pip install multi-project-manager --index-url https://pypi.pkg.github.com/wangguanran/
```

**From Source**:
```bash
git clone https://github.com/wangguanran/ProjectManager.git
cd ProjectManager
pip install -e .
```

### Docker Image

**Pull the latest image**:
```bash
docker pull ghcr.io/wangguanran/ProjectManager:latest
```

**Run with Docker**:
```bash
# Basic usage
docker run -v $(pwd)/vprojects:/app/vprojects ghcr.io/wangguanran/ProjectManager:latest

# With specific command
docker run -v $(pwd)/vprojects:/app/vprojects ghcr.io/wangguanran/ProjectManager:latest po_apply myproject
```

## Main Features

- Support for unified management of multiple boards and projects
- Project/board creation, deletion, and building (some features are reserved)
- PO (patch/override) directory creation, deletion, and listing
- Apply/rollback patches and overrides for projects
- Automatic log archiving and performance analysis support
- Interactive file selection for PO creation
- Support for .repo manifest and multi-repository environments

## Directory Structure

```
vprojects/
  board01/
    board01.ini          # Board configuration file
    po/
      po_test01/
        patches/         # Git patch files
        overrides/       # Override files
      ...
  common/
    ...
  template/
    ...
.cache/
  logs/         # Log files with timestamp
  cprofile/     # Performance analysis data
src/
  __main__.py   # Command line main entry
  plugins/
    project_manager.py   # Project/board management
    patch_override.py    # PO management and patch application
  ...
```

## Command Line Usage

Start with the following command:

```bash
python -m src <operation> <project_or_board_name> [parameters] [--options]
```

### Global Options

- `--version`: Show program version
- `--help`: Show detailed help for all operations
- `--perf-analyze`: Enable cProfile performance analysis

## Detailed Command Reference

### Project Management Commands

#### `project_new` - Create New Project
**Status**: TODO (Not implemented)

**Usage**: `python -m src project_new <project_name>`

**Description**: Creates a new project with specified configuration.

**Parameters**:
- `project_name` (required): Name of the project to create

**Configuration**: Project configuration is stored in board-specific `.ini` files.

---

#### `project_del` - Delete Project
**Status**: TODO (Not implemented)

**Usage**: `python -m src project_del <project_name>`

**Description**: Deletes the specified project directory and updates its status in the config file.

**Parameters**:
- `project_name` (required): Name of the project to delete

---

#### `project_build` - Build Project
**Status**: TODO (Not implemented)

**Usage**: `python -m src project_build <project_name>`

**Description**: Builds the specified project according to its configuration.

**Parameters**:
- `project_name` (required): Name of the project to build

---

### Board Management Commands

#### `board_new` - Create New Board
**Status**: TODO (Not implemented)

**Usage**: `python -m src board_new <board_name>`

**Description**: Creates a new board with initial directory structure.

**Parameters**:
- `board_name` (required): Name of the board to create

**Directory Structure Created**:
```
vprojects/<board_name>/
  <board_name>.ini
  po/
```

---

#### `board_del` - Delete Board
**Status**: TODO (Not implemented)

**Usage**: `python -m src board_del <board_name>`

**Description**: Deletes the specified board and all its projects.

**Parameters**:
- `board_name` (required): Name of the board to delete

---

### PO (Patch/Override) Management Commands

#### `po_apply` - Apply Patches and Overrides
**Status**: ✅ Implemented

**Usage**: `python -m src po_apply <project_name>`

**Description**: Applies all configured patches and overrides for the specified project.

**Parameters**:
- `project_name` (required): Name of the project to apply PO to

**Process**:
1. Reads `PROJECT_PO_CONFIG` from project configuration
2. Parses PO configuration (supports inclusion/exclusion)
3. Applies patches using `git apply`
4. Copies override files to target locations
5. Creates flag files (`.patch_applied`, `.override_applied`) to track applied POs

**Configuration Format**:
```
PROJECT_PO_CONFIG=po_test01 po_test02 -po_test03 po_test04[file1 file2]
```
- `po_test01`: Apply PO
- `-po_test03`: Exclude PO
- `po_test04[file1 file2]`: Apply PO but exclude specific files

---

#### `po_revert` - Revert Patches and Overrides
**Status**: ✅ Implemented

**Usage**: `python -m src po_revert <project_name>`

**Description**: Reverts all applied patches and overrides for the specified project.

**Parameters**:
- `project_name` (required): Name of the project to revert PO from

**Process**:
1. Reads `PROJECT_PO_CONFIG` from project configuration
2. Reverts patches using `git apply --reverse`
3. Removes override files (restores from git if tracked)
4. Updates flag files to remove PO references

---

#### `po_new` - Create New PO Directory
**Status**: ✅ Implemented

**Usage**: `python -m src po_new <project_name> <po_name> [--force]`

**Description**: Creates a new PO directory structure and optionally populates it with modified files.

**Parameters**:
- `project_name` (required): Name of the project
- `po_name` (required): Name of the new PO (must start with 'po' and contain only lowercase letters, digits, underscores)
- `--force` (optional): Skip confirmation prompts and create empty directory structure

**Features**:
- Interactive file selection from modified files in git repositories
- Support for .repo manifest files
- Automatic repository discovery
- File ignore patterns from `.gitignore` and `PROJECT_PO_IGNORE` config
- Choice between patch and override for each file
- Custom patch naming

**Directory Structure Created**:
```
vprojects/<board_name>/po/<po_name>/
  patches/
  overrides/
```

**Interactive Process**:
1. Scans for git repositories (supports .repo manifest)
2. Lists modified files in each repository
3. Allows user to select files for inclusion
4. For each file, user chooses:
   - Create patch (for tracked files with modifications)
   - Create override (for any file)
   - Skip file

---

#### `po_del` - Delete PO Directory
**Status**: ✅ Implemented

**Usage**: `python -m src po_del <project_name> <po_name> [--force]`

**Description**: Deletes the specified PO directory and removes it from all project configurations.

**Parameters**:
- `project_name` (required): Name of the project
- `po_name` (required): Name of the PO to delete
- `--force` (optional): Skip confirmation prompts

**Process**:
1. Shows directory contents and projects using the PO
2. Removes PO from all project configurations in `.ini` files
3. Deletes PO directory and all contents
4. Removes empty `po/` directory if no POs remain

**Safety Features**:
- Confirmation prompt showing affected projects
- Directory tree display of contents to be deleted
- Automatic cleanup of empty directories

---

#### `po_list` - List Configured POs
**Status**: ✅ Implemented

**Usage**: `python -m src po_list <project_name> [--short]`

**Description**: Lists all enabled PO directories for the specified project.

**Parameters**:
- `project_name` (required): Name of the project
- `--short` (optional): Show only PO names, not detailed file lists

**Output**:
- Lists all POs enabled in `PROJECT_PO_CONFIG`
- Shows patch files and override files for each PO
- Displays file counts and paths

---

## Configuration Files

### Board Configuration (.ini files)

Each board has a configuration file (`<board_name>.ini`) containing project definitions:

```ini
[project_name]
PROJECT_PO_CONFIG=po_test01 po_test02 -po_test03
PROJECT_PO_IGNORE=external vendor/third_party
BOARD_NAME=board01
# Other project-specific configurations
```

**Configuration Keys**:
- `PROJECT_PO_CONFIG`: PO configuration string (see format above)
- `PROJECT_PO_IGNORE`: Space-separated ignore patterns for repositories/files
- `BOARD_NAME`: Board name (auto-populated)

### PO Configuration Format

**Basic Format**: `po_name1 po_name2 -po_name3`

**Advanced Format**: `po_name1[file1 file2] -po_name2[file3]`

**Examples**:
- `po_test01 po_test02`: Apply po_test01 and po_test02
- `po_test01 -po_test02`: Apply po_test01, exclude po_test02
- `po_test01[src/main.c include/header.h]`: Apply po_test01 but exclude specific files
- `po_test01 -po_test02[config.ini]`: Apply po_test01, exclude po_test02 except config.ini

## Logging and Performance Analysis

### Logging
- **Location**: `.cache/logs/`
- **Format**: `Log_YYYYMMDD_HHMMSS.log`
- **Levels**: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Features**: 
  - Colored console output
  - Automatic log rotation
  - Time-based archiving

### Performance Analysis
- **Location**: `.cache/cprofile/`
- **Enable**: Use `--perf-analyze` flag
- **Output**: Detailed function call statistics and timing

## Environment Support

### Repository Types
- Single git repository
- Multiple git repositories (recursive discovery)
- .repo manifest files (Android-style)

### File Types
- **Patches**: Git patch files (`.patch`)
- **Overrides**: Direct file copies
- **Flags**: `.patch_applied`, `.override_applied` (tracking files)

### Ignore Patterns
- `.gitignore` file patterns
- `PROJECT_PO_IGNORE` configuration
- Repository-level exclusions

## Dependencies and Installation

- **Python**: 3.7+
- **Dependencies**: See `requirements.txt`
- **Git**: Required for patch operations
- **File System**: Standard POSIX file operations

## Notes

- Currently, project/board management features are reserved (TODO), while PO management and patch application features are fully implemented.
- Platform management features have been merged into existing plugins, with no separate `platform_manager.py` or `po_manager.py` files.
- To extend platform-related operations, custom plugins can be added in the `vprojects/scripts/` directory.
- All PO operations support interactive confirmation and detailed logging.
- The tool automatically handles multi-repository environments and complex PO configurations.
