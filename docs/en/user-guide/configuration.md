# ProjectManager Configuration Management

## Overview

This guide explains how ProjectManager stores configuration data, the meaning of each field, inheritance rules, and recommended practices.

## Configuration File Layout

ProjectManager uses INI files located at `projects/<board-name>/<board-name>.ini` to store board and project configuration.

## Example Configuration

### Basic structure

```ini
# Board configuration: projects/myboard/myboard.ini

[common]
# Shared defaults inherited by every project
PROJECT_PO_IGNORE=vendor/* external/* third_party/*
DEFAULT_BUILD_TYPE=release

[myproject]
# Project-specific settings
BOARD_NAME=myboard
PROJECT_PO_CONFIG=po_feature1 po_feature2 -po_experimental
PROJECT_PO_IGNORE=vendor/* external/* tests/*
BUILD_TYPE=debug
VERSION=1.0.0

[myproject-subproject]
# Child project that inherits from the parent
PROJECT_PO_CONFIG=po_feature1 po_subproject
BUILD_TYPE=release
```

## Key Configuration Fields

### `BOARD_NAME`
- **Type**: string
- **Required**: yes
- **Description**: Identifies the board that owns the project
- **Example**: `BOARD_NAME=myboard`
- **Notes**: Automatically populated by the CLI when possible

### `PROJECT_PO_CONFIG`
- **Type**: string
- **Required**: yes
- **Description**: Defines the set of patches/overrides (POs) applied to the project
- **Syntax**: Supports include, exclude, and file-level exclusions
- **Example**: `PROJECT_PO_CONFIG=po1 po2 -po3 po4[file1 file2]`

### `PROJECT_PO_IGNORE`
- **Type**: string
- **Required**: no
- **Description**: Glob patterns for files and directories to skip
- **Syntax**: Space-separated glob patterns
- **Example**: `PROJECT_PO_IGNORE=vendor/* external/* tests/*`

### `BUILD_TYPE`
- **Type**: string
- **Required**: no
- **Description**: Desired build profile for the project
- **Allowed values**: `debug`, `release`, `test`
- **Default**: Inherited from `[common]`

### `VERSION`
- **Type**: string
- **Required**: no
- **Description**: Project version number
- **Format**: Semantic version (e.g., `1.0.0`)

### `DESCRIPTION`
- **Type**: string
- **Required**: no
- **Description**: Human-readable project summary

## PO Configuration Syntax

### Basic format

```
PO_CONFIG = item1 item2 -item3 item4[file1 file2]
```

### Item types

1. **Include** — `po_name`
   - Applies the specified PO.
   - Example: `po_feature1`
2. **Exclude** — `-po_name`
   - Removes a PO from the final set.
   - Example: `-po_experimental`
3. **Conditional include** — `po_name[file1 file2]`
   - Includes the PO but skips the listed files.
   - Example: `po_feature1[src/test.c include/test.h]`

### Configuration examples

- **Simple include**
  ```ini
  PROJECT_PO_CONFIG=po_feature1 po_feature2
  ```
  Applies `po_feature1` and `po_feature2`.

- **Exclude a PO**
  ```ini
  PROJECT_PO_CONFIG=po_feature1 -po_experimental
  ```
  Applies `po_feature1` and removes `po_experimental`.

- **Complex mix**
  ```ini
  PROJECT_PO_CONFIG=po_feature1 po_feature2[src/test.c] -po_experimental[config.ini]
  ```
  Applies `po_feature1`, applies `po_feature2` except `src/test.c`, and excludes `po_experimental` but keeps `config.ini`.

## Inheritance Rules

1. Project sections inherit from the `[common]` section.
2. Child projects inherit from their parent projects.
3. Child settings override parent values when a key is redefined.

### Example

```ini
[common]
PROJECT_PO_IGNORE=vendor/* external/*
BUILD_TYPE=release

[myproject]
PROJECT_PO_CONFIG=po_feature1
# Inherits PROJECT_PO_IGNORE and BUILD_TYPE

[myproject-subproject]
PROJECT_PO_CONFIG=po_feature1 po_subproject
BUILD_TYPE=debug
# Inherits PROJECT_PO_IGNORE, overrides BUILD_TYPE
```

### Naming hierarchy

Use hyphenated names to express inheritance:
- Parent: `myproject`
- Child: `myproject-subproject`
- Grandchild: `myproject-subproject-feature`

## Ignore Patterns

### Supported forms

- **Directories**
  ```
  vendor/*
  external/*
  third_party/*
  ```
- **Files**
  ```
  *.log
  config.ini
  *.tmp
  ```
- **Paths**
  ```
  src/vendor/*
  include/external/*
  ```

### Priority order

1. Project-level ignores (`PROJECT_PO_IGNORE`)
2. Git ignores (`.gitignore`)
3. System-level defaults

## Best Practices

### Structure your workspace

```
projects/
├── board1/
│   ├── board1.ini
│   ├── project1/
│   ├── project2/
│   └── project2-sub/
├── board2/
│   ├── board2.ini
│   └── project3/
└── common/
    └── common.ini
```

### Naming conventions

- **Board names**: lowercase letters, digits, underscores.
- **Project names**: lowercase letters, digits, hyphens, underscores.
- **PO names**: Start with `po_`; use lowercase letters, digits, underscores.

### Manage configurations effectively

- Keep shared settings in `[common]`.
- Use descriptive option names and comments.
- Back up INI files regularly.
- Track changes with semantic version numbers.

### Version control

- Commit configuration files to source control.
- Record the history of configuration changes.
- Test the impact of configuration updates before release.

## Validation

### Automated checks

ProjectManager validates INI files by:
- Ensuring required keys are present.
- Checking PO configuration syntax.
- Verifying referenced paths exist.
- Confirming inheritance relationships are valid.

### Manual checks

```bash
# Inspect project configuration
python -m src po_list myproject

# Review PO resolution
python -m src po_list myproject --short
```

## Troubleshooting

### Common issues

1. **PO syntax errors**
   - *Symptom*: Commands fail with configuration errors.
   - *Fix*: Review `PROJECT_PO_CONFIG` formatting.
2. **Ignore pattern not applied**
   - *Symptom*: Files that should be skipped are still processed.
   - *Fix*: Verify pattern syntax and priority order.
3. **Inheritance not working**
   - *Symptom*: Child project misses expected values.
   - *Fix*: Check naming conventions and section hierarchy.

### Debug tips

1. Inspect `.cache/latest.log` (or `.cache/logs/Log_*.log`) for detailed debug logs.
2. `projects/<board>/projects.json` and `projects/repositories.json` store **relative paths only** and are generally safe to share for troubleshooting (they may still reveal board/project names).
3. Inspect INI syntax manually when editing files.
4. Use `po_list` to preview PO selection results.
5. Review project naming to ensure inheritance mapping.

---

## Other Languages

- [中文版](../../zh/user-guide/configuration.md)
