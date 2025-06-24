# ProjectManager Code Analysis

This document provides a detailed analysis of the `ProjectManager` codebase, outlining the functionality of each component.

## Project Overview

This repository provides a command-line tool named `vprj` for managing Android-based projects. It is designed to automate the creation of new projects from predefined templates, manage platform-specific configurations, and streamline the development workflow.

The tool is built as an extensible plugin-based system, allowing for the easy addition of support for new hardware platforms and custom operations.

## Directory Structure (Post-Refactoring)

The project follows a modern and standard Python project structure:

- **`src/`**: Contains the main Python source code.
    - **`vprjcore/`**: The core Python package for the application.
- **`docs/`**: Contains documentation files.
- **`tests/`**: Intended for unit and integration tests.
- **`pyproject.toml`**: The unified project configuration file for metadata, dependencies, and build settings.
- **Shell Scripts (`*.sh`)**: Helper scripts for building, installing, and releasing new versions.

## Core Components Analysis (`src/vprjcore/`)

### 1. `common.py`

This file is the foundation of the project, providing a micro-framework with essential services:

- **Path Management**: Intelligently resolves project paths regardless of the script's execution directory.
- **Logging System**: A singleton `LogManager` that outputs to both the console (INFO level) and timestamped log files (DEBUG level) with automatic archival.
- **Performance Profiling**: A `@func_cprofile` decorator that profiles the execution time of any function it wraps, saving the results to `.cprofile` files.
- **Plugin Architecture**: A sophisticated mechanism for dynamically loading and registering modules (`load_module`, `register_module`). It discovers Python files and registers their functions based on a naming convention (e.g., `after_new_project`), allowing for a highly extensible, plugin-driven architecture.

### 2. `project.py`

This is the main entry point and business logic hub of the application.

- **`Project` Class**: Orchestrates all operations. Its constructor drives the entire process: parsing arguments, identifying the target platform, loading the appropriate plugin module, and executing the requested operation.
- **Plugin Loading**: The `_get_op_handler` method dynamically scans for and imports the correct plugin module from the `vprjcore` directory by matching the project's platform against the `support_list` defined within each plugin. This makes the system platform-agnostic and extensible.
- **Core Operations**:
    - `new_project`: Creates a new project by copying a `base` template. It then renames files and replaces placeholder keywords (like `demo`) within specific files (`.ini`, `.patch`) to customize the new project.
    - `del_project`: Deletes a project's directory and updates its status to "deleted" in the `project_info.json` file (a soft delete).
    - `new_platform`: Creates a new platform template by scanning a clean source tree for files not tracked by Git. It copies these new files and records them in a JSON file, effectively creating a reusable "patch" for a base Android version.
- **Command-Line Interface**: Uses `argparse` to define and parse command-line arguments, which are then passed to the `Project` class.

### 3. `patch_override.py` (formerly `po.py`)

This file is a concrete example of a plugin module.

- **Functionality**: It manages the "override" mechanism for project-specific files.
- **Hooks**: It implements functions that are automatically called at specific points in the project lifecycle:
    - `after_new_project`: After a new project is created, this function moves all its contents (except the `po` directory itself) into a structured `.../po/po_<project_name>_bsp/overrides/` directory. This standardizes the way custom files are handled.
    - `before_compile_project` & `after_compile_project`: These hooks are defined but not fully implemented. They are intended to handle the process of copying override files back to the source tree before compilation and potentially cleaning up afterward.

## Build and Deployment

- **`pyproject.toml`**: Defines all package metadata, dependencies (`GitPython`), and the crucial `[project.scripts]` entry point, which makes the `vprj` command available system-wide after installation.
- **`build.sh`**: A simple script that uses `python -m build` to create distributable packages (wheel and sdist) in the `dist/` directory.
- **`install.sh`**: Installs the built package using `pip`.
- **`uninstall.sh`**: Uninstalls the package.
- **`release.sh`**: An orchestration script that automates the release process: automatically bumps the patch version number in `pyproject.toml`, then calls the uninstall, build, and install scripts in sequence for a full release cycle. 