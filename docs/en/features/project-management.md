# Project Management Features

## Overview

ProjectManager provides comprehensive project management capabilities through its core modules and plugins. This document describes the main features and how to use them.

## Core Modules

### Project Manager Plugin (`src/plugins/project_manager.py`)

The project manager plugin handles project configuration and management operations.

**Key Functions**:
- Project configuration loading and validation
- Board and project relationship management
- Configuration file parsing and updates

### Patch and Override Plugin (`src/plugins/patch_override.py`)

The patch and override plugin provides advanced file modification management through PO (Patch/Override) operations.

**Key Functions**:
- `po_new`: Create new PO directories and select files for patching/overriding
- `po_apply`: Apply patches and overrides to repositories
- `po_revert`: Revert applied patches and overrides
- `po_list`: List configured POs for a project
- `po_del`: Delete PO directories and clean up configurations

**Features**:
- Interactive file selection for PO creation
- Support for both staged and working directory changes
- Automatic repository discovery (including .repo manifest support)
- Enhanced ignore patterns with path containment matching
- Git integration for patch application and reversion

## Utility Modules

### Log Manager (`src/log_manager.py`)

Provides centralized logging functionality with configurable levels and output formats.

**Features**:
- Configurable log levels (DEBUG, INFO, WARNING, ERROR)
- File and console output support
- Structured logging with context information
- Performance profiling integration

### Profiler (`src/profiler.py`)

Performance profiling and monitoring utilities.

**Features**:
- Function execution time measurement
- Memory usage tracking
- Performance bottleneck identification
- Automatic profiling for key operations

### Utils (`src/utils.py`)

Common utility functions used throughout the project.

**Features**:
- Configuration file parsing
- Path manipulation utilities
- Validation functions
- Common data processing operations

## Main Entry Point (`src/__main__.py`)

The main application entry point that orchestrates all operations.

**Features**:
- Command-line interface
- Subcommand routing
- Environment setup and validation
- Error handling and user feedback

## Configuration Management

### Project Configuration Files

Projects are configured using `.ini` files with the following structure:

```ini
[project_name]
board_name = board_name
PROJECT_PO_CONFIG = po1 po2 -po3
PROJECT_PO_IGNORE = vendor/* external/*
```

**Configuration Fields**:
- `board_name`: Associated board for the project
- `PROJECT_PO_CONFIG`: PO configuration with inclusion/exclusion rules
- `PROJECT_PO_IGNORE`: Repository and file ignore patterns

### PO Configuration Syntax

```
po1 po2 -po3 po4[file1 file2] -po5[file3]
```

**Elements**:
- `po1`, `po2`: Include these POs
- `-po3`: Exclude this PO
- `po4[file1 file2]`: Include PO4 but exclude specific files
- `-po5[file3]`: Exclude PO5 but only for specific files

## Repository Management

### Repository Discovery

The system supports multiple repository discovery methods:

1. **Git Repositories**: Standard Git repositories with `.git` directories
2. **Repo Manifest**: Android-style `.repo/manifest.xml` files
3. **Mixed Environments**: Combinations of the above

### Repository Operations

- **Scanning**: Automatic discovery of repositories in the current directory
- **Filtering**: Apply ignore patterns to exclude specific repositories
- **File Analysis**: Detect modified files in repositories
- **Change Management**: Handle staged and unstaged changes

## File Management

### Patch Operations

Patches are created using Git's diff functionality:

```bash
# Create patch from staged changes
git diff --cached -- file_path

# Create patch from working directory changes
git diff -- file_path
```

### Override Operations

Overrides copy files directly from the source to the target location, replacing the original files.

### File Selection

The system provides interactive file selection with the following options:

1. **Create Patch**: For tracked files with modifications
2. **Create Override**: For any file (tracked or untracked)
3. **Skip File**: Exclude from PO creation

## Integration Features

### Git Integration

- Automatic detection of Git repositories
- Support for Git status and diff operations
- Integration with Git hooks for automated operations
- Patch application and reversion using Git commands

### CI/CD Integration

- GitHub Actions workflows for automated testing and deployment
- Docker containerization for consistent environments
- Package publishing to multiple registries
- Automated release management

## Usage Examples

### Basic PO Creation

```bash
# Create a new PO with interactive file selection
python -m src po_new myproject my_po_name

# Create a new PO in force mode (empty structure)
python -m src po_new myproject my_po_name --force
```

### PO Management

```bash
# Apply POs to a project
python -m src po_apply myproject

# Revert POs from a project
python -m src po_revert myproject

# List configured POs
python -m src po_list myproject

# Delete a PO
python -m src po_del myproject my_po_name
```

### Project Management

```bash
# List all projects
python -m src list

# Show project details
python -m src show myproject

# Apply all POs for all projects
python -m src apply_all
```

## Best Practices

1. **PO Naming**: Use descriptive names starting with "po" (e.g., `po_feature_name`)
2. **Configuration**: Keep PO configurations simple and well-documented
3. **Testing**: Test PO applications in a safe environment before production use
4. **Backup**: Always have backups before applying POs to important projects
5. **Documentation**: Document the purpose and contents of each PO

## Troubleshooting

### Common Issues

1. **Repository Not Found**: Ensure you're in the correct directory with Git repositories
2. **Permission Errors**: Check file permissions and Git repository access
3. **PO Application Failed**: Verify that patches are compatible with current repository state
4. **Configuration Errors**: Validate project configuration files for syntax errors

### Debug Mode

Enable debug logging for detailed troubleshooting:

```bash
export LOG_LEVEL=DEBUG
python -m src po_apply myproject
``` 