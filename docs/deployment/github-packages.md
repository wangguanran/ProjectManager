# GitHub Package Registry Configuration

This document explains how to use GitHub Package Registry for publishing Python packages and Docker images.

## Overview

This project is configured to publish:
- **Python Package**: To GitHub Package Registry and PyPI
- **Docker Image**: To GitHub Container Registry (ghcr.io)

## Prerequisites

1. **GitHub Token**: You need a GitHub Personal Access Token with `write:packages` permission
2. **PyPI API Token**: You need a PyPI API token for publishing to PyPI
3. **Repository Permissions**: The repository must have package publishing enabled

## Required Secrets Configuration

### GitHub Repository Secrets

In your GitHub repository, go to Settings → Secrets and variables → Actions, and add:

1. **PYPI_API_TOKEN** (required for PyPI publishing)
   - Value: Your PyPI API token from https://pypi.org/manage/account/token/
   - Note: Use `__token__` as username and the token as password

2. **GITHUB_TOKEN** (automatically provided by GitHub Actions)
   - No need to add manually, GitHub provides this automatically

### PyPI API Token Setup

1. **Create PyPI API Token**:
   - Go to https://pypi.org/manage/account/token/
   - Click "Add API token"
   - Choose scope: "Entire account" or "Specific project"
   - Copy the token (starts with `pypi-`)

2. **Add to GitHub Secrets**:
   - Repository Settings → Secrets and variables → Actions
   - New repository secret: `PYPI_API_TOKEN`
   - Value: Your PyPI token

## Configuration Files

### Python Package Configuration

- `pyproject.toml`: Package metadata and build configuration
- `.pypirc`: Package registry authentication (not committed to git)
- `src/__version__.py`: Version information

### Docker Configuration

- `Dockerfile`: Container image definition
- `.dockerignore`: Files to exclude from Docker build context

## GitHub Actions Workflows

### Python Package Publishing

**File**: `.github/workflows/publish-python.yml`

**Triggers**:
- Push tags starting with `v*` (e.g., `v1.0.0`)
- Manual workflow dispatch

**Actions**:
1. Builds Python package using `build`
2. Publishes to PyPI (requires `PYPI_API_TOKEN`)
3. Publishes to GitHub Package Registry (uses `GITHUB_TOKEN`)

### Docker Image Publishing

**File**: `.github/workflows/publish-docker.yml`

**Triggers**:
- Push tags starting with `v*` (e.g., `v1.0.0`)
- Manual workflow dispatch

**Actions**:
1. Builds Docker image using Docker Buildx
2. Publishes to GitHub Container Registry (ghcr.io)

### Release Creation

**File**: `.github/workflows/publish-release.yml`

**Triggers**:
- Push tags starting with `v*` (e.g., `v1.0.0`)
- Manual workflow dispatch

**Actions**:
1. Builds and tests the project
2. Creates GitHub Release with assets and documentation

## Installation and Usage

### Python Package

**From PyPI**:
```bash
pip install multi-project-manager
```

**From GitHub Package Registry**:
```bash
pip install multi-project-manager --index-url https://pypi.pkg.github.com/wangguanran/
```

**Usage**:
```bash
python -m src --help
```

### Docker Image

**Pull the image**:
```bash
docker pull ghcr.io/wangguanran/ProjectManager:latest
```

**Run the container**:
```bash
# Basic usage
docker run -v $(pwd)/projects:/app/projects ghcr.io/wangguanran/ProjectManager:latest

# With specific command
docker run -v $(pwd)/projects:/app/projects ghcr.io/wangguanran/ProjectManager:latest po_apply myproject
```

## Version Management

1. **Update version** in `src/__version__.py`
2. **Create and push a tag**:
   ```bash
   git tag v0.0.3
   git push origin v0.0.3
   ```
3. **GitHub Actions will automatically**:
   - Build and publish the Python package to PyPI and GitHub Package Registry
   - Build and publish the Docker image to GitHub Container Registry
   - Create a GitHub Release with assets

## Troubleshooting

### Common Issues

1. **Permission Denied**: Ensure your GitHub token has `write:packages` permission
2. **PyPI Authentication Failed**: Check that `PYPI_API_TOKEN` is set correctly
3. **Package Already Exists**: Version numbers must be unique; increment the version
4. **Docker Build Fails**: Check that all required files are present and not in `.dockerignore`

### Debugging

- Check GitHub Actions logs for detailed error messages
- Verify environment variables are set correctly
- Ensure all required files are committed to the repository

## Security Notes

- Never commit `.pypirc` file with actual tokens
- Use GitHub Secrets for sensitive information
- Regularly rotate your GitHub tokens and PyPI tokens
- Review package permissions in GitHub repository settings 