# Scripts and Automation

This document describes the various scripts and automation tools available in the ProjectManager project.

## Build and Installation Scripts

### `install.sh`

Installs the standalone `projman` binary produced by `build.sh`.

**Usage**:
```bash
./install.sh [--system|--user] [--prefix DIR]
```

**Features**:
- Copies `out/binary/projman` into an install prefix
- Auto-selects `/usr/local/bin` when run as root, otherwise `~/.local/bin`
- Prints PATH guidance for user installs

### `uninstall.sh`

Removes ProjectManager from the system.

**Usage**:
```bash
./uninstall.sh
```

**Features**:
- Removes installed Python package
- Cleans up configuration files
- Removes virtual environment (if created by install script)
- Removes standalone `projman` from `~/.local/bin` and `/usr/local/bin`

### `setup_venv.sh`

Sets up a Python virtual environment for development.

**Usage**:
```bash
./setup_venv.sh
```

**Features**:
- Creates a new virtual environment
- Installs dependencies from `requirements.txt` (set `INSTALL_DEPS=0` to skip)
- Activates the environment
- Provides development setup instructions

## Build and Release Scripts

### `build.sh`

Builds the Python package and the standalone `projman` binary (PyInstaller).

**Usage**:
```bash
./build.sh
```

**Features**:
- Automatically runs inside `venv/` (creates it if missing)
- Builds Python packages into `out/package/`
- Builds the standalone binary into `out/binary/`
- Linux-only: best-effort static linking via `staticx`

### `release.sh`

Creates a new release with version management.

**Usage**:
```bash
./release.sh [version]
```

**Features**:
- Updates version in source files
- Creates Git tag
- Builds and publishes packages
- Creates GitHub release
- Updates changelog

### `get_latest_release.sh`

Downloads the latest GitHub Release asset for the current OS/arch and installs `projman`.

**Usage**:
```bash
./get_latest_release.sh [--system|--user] [--prefix DIR] [-t TOKEN]
```

**Features**:
- Fetches latest release from GitHub API
- Displays release information
- Selects the best-matching asset (for example `projman-linux-x86_64`)
- Installs `projman` to `/usr/local/bin` when run as root, otherwise `~/.local/bin`
- For Windows, use `install.ps1`

### `install.ps1`

Windows installer for `projman` (PowerShell).

**Usage**:
```powershell
iwr -useb https://raw.githubusercontent.com/wangguanran/ProjectManager/<tag>/install.ps1 | iex
```

**Features**:
- Downloads the latest Windows release asset (for example `projman-windows-x86_64.exe`)
- Installs `projman.exe` to a per-user or system directory
- Updates PATH (User or Machine)

## Development Scripts

### `coverage_report.py`

Generates code coverage reports for the project.

**Usage**:
```bash
python coverage_report.py
```

**Features**:
- Runs tests with coverage measurement
- Generates HTML coverage reports
- Calculates coverage statistics
- Identifies uncovered code areas

### `fix_trailing_whitespace.sh`

Removes trailing whitespace from source files.

**Usage**:
```bash
./fix_trailing_whitespace.sh
```

**Features**:
- Finds and removes trailing whitespace
- Processes all source files
- Maintains file formatting
- Improves code quality

## Git Hooks

### `hooks/install_hooks.sh`

Installs Git hooks for automated code quality checks.

**Usage**:
```bash
./hooks/install_hooks.sh
```

**Features**:
- Installs pre-commit and pre-push hooks
- Configures automated testing
- Sets up code quality checks
- Ensures consistent code standards

### `hooks/pre-commit`

Pre-commit hook that runs before each commit.

**Features**:
- Runs code formatting checks
- Executes basic tests
- Validates code syntax
- Prevents commits with issues

### `hooks/pre-push`

Pre-push hook that runs before pushing to remote.

**Features**:
- Runs comprehensive tests
- Checks code coverage
- Validates project structure
- Ensures code quality standards

## GitHub Actions Workflows

### `.github/workflows/python-app.yml`

Main CI/CD workflow for Python application.

**Triggers**:
- Push to main branch
- Pull requests
- Manual workflow dispatch

**Actions**:
- Runs tests on multiple Python versions
- Checks code quality with pylint
- Generates coverage reports
- Validates package building

### `.github/workflows/pylint.yml`

Code quality check workflow.

**Triggers**:
- Push to any branch
- Pull requests

**Actions**:
- Runs pylint code analysis
- Reports code quality issues
- Enforces coding standards
- Provides detailed feedback

### `.github/workflows/publish-python.yml`

Python package publishing workflow.

**Triggers**:
- Push tags starting with `v*`
- Manual workflow dispatch

**Actions**:
- Builds Python package
- Publishes to PyPI
- Publishes to GitHub Package Registry
- Creates release assets

### `.github/workflows/publish-docker.yml`

Docker image publishing workflow.

**Triggers**:
- Push tags starting with `v*`
- Manual workflow dispatch

**Actions**:
- Builds Docker image
- Publishes to GitHub Container Registry
- Tags with version and latest
- Validates image functionality

### `.github/workflows/publish-release.yml`

Release creation workflow.

**Triggers**:
- Push tags starting with `v*`
- Manual workflow dispatch

**Actions**:
- Creates GitHub release
- Uploads release assets
- Generates release notes
- Notifies stakeholders

## Docker Configuration

### `Dockerfile`

Docker image definition for ProjectManager.

**Features**:
- Multi-stage build for optimization
- Python 3.9+ base image
- Minimal runtime dependencies
- Secure configuration

### `.dockerignore`

Files excluded from Docker build context.

**Excluded Items**:
- Git repository files
- Development tools
- Test files
- Documentation
- Build artifacts

## Configuration Files

### `.pylintrc`

Pylint configuration for code quality checks.

**Settings**:
- Code style rules
- Error detection patterns
- Custom message formatting
- Project-specific configurations

### `pyproject.toml`

Project configuration and build settings.

**Sections**:
- Project metadata
- Build system configuration
- Development dependencies
- Tool configurations

### `requirements.txt`

Python package dependencies.

**Categories**:
- Runtime dependencies
- Development dependencies
- Testing dependencies
- Build dependencies

## Usage Examples

### Development Setup

```bash
# Set up development environment
./setup_venv.sh

# Install Git hooks
./hooks/install_hooks.sh

# Run tests with coverage
python coverage_report.py
```

### Building and Releasing

```bash
# Build packages + standalone binary
./build.sh

# Create a new release
./release.sh v1.2.3

# Check latest release
./get_latest_release.sh
```

### Code Quality

```bash
# Fix formatting issues
./fix_trailing_whitespace.sh

# Run code quality checks
pylint src/

# Generate coverage report
python coverage_report.py
```

## Best Practices

1. **Always run tests** before committing code
2. **Use Git hooks** for automated quality checks
3. **Follow versioning** conventions for releases
4. **Test builds** locally before pushing
5. **Document changes** in release notes

## Troubleshooting

### Common Issues

1. **Build failures**: Check dependencies and Python version
2. **Hook errors**: Verify Git hook installation
3. **Coverage issues**: Ensure tests are running correctly
4. **Release problems**: Check version numbers and tags

### Debug Mode

Enable verbose output for debugging:

```bash
# Verbose build
bash -x ./build.sh

# Debug installation
bash -x ./install.sh

# Detailed coverage
python coverage_report.py --verbose
``` 
