# PO Ignore Feature

## Overview

The `po_new` command has been enhanced with the ability to ignore specific repository paths based on configuration files. This feature allows users to specify repository path patterns to ignore in project configuration, avoiding scanning these repositories for file modifications when creating POs.

## Features

1. **Configuration File Support**: Specify ignore patterns through the `PROJECT_PO_IGNORE` field in project configuration
2. **Pattern Matching**: Uses fnmatch for wildcard pattern matching
3. **Path Containment Matching**: Automatically enhances simple patterns to match repositories and files containing the specified path
4. **Multiple Pattern Support**: Supports multiple ignore patterns separated by spaces
5. **Backward Compatibility**: Maintains support for existing `.gitignore` files

## Configuration

### 1. Project Configuration File Method

Add the `PROJECT_PO_IGNORE` field to your project's `.ini` configuration file:

```ini
[project_name]
board_name = board_name
PROJECT_PO_CONFIG = po1 po2
PROJECT_PO_IGNORE = vendor/* external/* third_party/* build/*
```

### 2. File Method (Maintains Compatibility)

Continues to support the following files:
- `.gitignore`: Standard Git ignore file

## Ignore Pattern Examples

### Basic Patterns
```
vendor/*          # Ignore all repositories under vendor directory
external/*        # Ignore all repositories under external directory  
third_party/*     # Ignore all repositories under third_party directory
build/*           # Ignore all repositories under build directory
docs              # Ignore docs repository
test_*            # Ignore all repositories starting with test_
```

### Enhanced Patterns (Auto-generated)
When configuring simple patterns, the system automatically generates enhanced patterns to match repositories and files containing the specified path:

**Configuration**: `PROJECT_PO_IGNORE = vendor`

**Auto-generated Enhanced Patterns**:
```
vendor              # Original pattern
*vendor*            # Match any path containing "vendor"
*vendor/*           # Match directories starting with "vendor"
*/vendor/*          # Match directories containing "vendor"
*/vendor            # Match paths ending with "vendor"
```

**Actual Effects**:
- Ignored repositories: `vendor/`, `my_vendor_lib/`, `lib/vendor/`, `external/vendor/`
- Ignored files: `src/vendor_config.h`, `include/vendor.h`, `docs/vendor_guide.md`

## Workflow

1. **Scan Repositories**: The `po_new` command scans all Git repositories starting from the current directory
2. **Apply Ignore Rules**: Filters repositories according to configured ignore patterns
3. **Display Results**: Shows which repositories are ignored and which are processed in the console
4. **Continue Processing**: Only scans repositories that are not ignored for file modifications

## Output Example

```
Found .repo manifest, scanning repositories...
  Ignoring repository: vendor/foo (matches pattern: vendor/*)
  Ignoring repository: external/bar (matches pattern: external/*)
  Ignoring repository: third_party/baz (matches pattern: third_party/*)
  Found repository: src/main at /path/to/src/main
  Found repository: docs at /path/to/docs
```

## Implementation Details

### Modified Files

- `src/plugins/patch_override.py`: Main modified file

### Modified Functions

1. **`__find_repositories()`**: 
   - Added ignore pattern loading
   - Applied ignore rules when scanning repositories
   - Displayed ignored and processed repository information

2. **`__load_ignore_patterns()`**: 
   - Added `project_cfg` parameter
   - Prioritized reading ignore patterns from project configuration
   - Maintained support for `.gitignore` files

### Ignore Logic

```python
# Check if repository should be ignored
should_ignore = False
for pattern in ignore_patterns:
    if fnmatch.fnmatch(repo_name, pattern):
        should_ignore = True
        break

if not should_ignore:
    # Process repository
    repositories.append((repo_path, repo_name))
else:
    # Skip repository
    print(f"  Ignoring repository: {repo_name} (matches pattern: {pattern})")
```

### Enhanced Pattern Generation Logic

```python
# Auto-generate enhanced patterns for simple patterns
enhanced_patterns = []
for pattern in config_patterns:
    # Skip patterns that already contain wildcards or special characters
    if any(char in pattern for char in ['*', '?', '[', ']']):
        continue
    
    # Generate containment matching patterns
    enhanced_patterns.extend([
        f"*{pattern}*",  # Match any path containing the pattern
        f"*{pattern}/*",  # Match directories starting with the pattern
        f"*/{pattern}/*",  # Match directories containing the pattern
        f"*/{pattern}",   # Match paths ending with the pattern
    ])
```

## Usage Recommendations

1. **Reasonable Configuration**: Only ignore repositories that truly don't need processing to avoid missing important modifications
2. **Precise Patterns**: Use precise pattern matching to avoid accidentally ignoring needed repositories
3. **Test Verification**: Test ignore configuration before important operations
4. **Documentation Maintenance**: Maintain documentation of ignore configuration within the team

## Notes

1. Ignore patterns are case-sensitive
2. Supports standard fnmatch wildcard patterns
3. Simple patterns are automatically enhanced to containment matching patterns (skips patterns already containing wildcards)
4. Ignore rules are applied in configuration order, with the first matching pattern taking effect
5. Changes to ignore configuration require re-running the `po_new` command to take effect 