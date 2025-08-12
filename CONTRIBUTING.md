# Contributing to Project Manager

Thank you for your interest in contributing to Project Manager! This document provides guidelines for contributing to the project.

## Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/wangguanran/ProjectManager.git
   cd ProjectManager
   ```

2. **Set up virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install development dependencies**
   ```bash
   make install-dev
   # or
   pip install -e ".[dev]"
   ```

4. **Install git hooks**
   ```bash
   make setup-hooks
   ```

## Development Workflow

### Code Style

We use several tools to maintain code quality:

- **Black**: Code formatting
- **isort**: Import sorting
- **pylint**: Code linting
- **mypy**: Type checking

Run all formatting and linting:
```bash
make format  # Format code
make lint    # Check code quality
```

### Testing

Run tests:
```bash
make test        # Run all tests
make test-cov    # Run tests with coverage
pytest -m unit   # Run only unit tests
pytest -m integration  # Run only integration tests
```

### Pre-commit Checks

Before committing, ensure:
1. All tests pass: `make test`
2. Code is formatted: `make format`
3. Linting passes: `make lint`
4. Type checking passes: `mypy src/`

### Making Changes

1. Create a feature branch from `main`
2. Make your changes
3. Add tests for new functionality
4. Update documentation if needed
5. Run all checks: `make check-all`
6. Submit a pull request

## Project Structure

```
ProjectManager/
├── src/                    # Source code
│   ├── plugins/           # Plugin modules
│   ├── __main__.py        # Entry point
│   ├── log_manager.py     # Logging utilities
│   ├── profiler.py        # Profiling utilities
│   └── utils.py           # General utilities
├── tests/                 # Test files
├── docs/                  # Documentation
├── projects/             # Test projects
├── hooks/                # Git hooks
└── scripts/              # Build and utility scripts
```

## Testing Guidelines

- Write unit tests for all new functionality
- Use descriptive test names
- Group related tests in test classes
- Use fixtures for common setup
- Aim for high test coverage

## Documentation

- Update README.md for user-facing changes
- Add docstrings to new functions and classes
- Update relevant documentation in `docs/`

## Release Process

1. Update version in `pyproject.toml`
2. Update CHANGELOG.md
3. Create a release tag
4. Push to trigger CI/CD pipeline

## Questions?

If you have questions about contributing, please open an issue or contact the maintainers. 