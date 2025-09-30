# Development Documentation

This directory contains development-related documentation for the ProjectManager project.

## Contents

- **Setup and Installation**: Development environment setup guides
- **Architecture**: System architecture and design documents
- **Contributing**: Guidelines for contributing to the project
- **Testing**: Testing strategies and procedures

## Quick Start

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd ProjectManager
   ```

2. **Set up development environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -e .
   ```

3. **Install development dependencies**:
   ```bash
   pip install -r requirements-dev.txt
   ```

4. **Run tests**:
   ```bash
   python -m pytest tests/
   ```

## Development Workflow

1. **Create a feature branch** from `main`
2. **Make changes** and add tests
3. **Run tests** to ensure everything works
4. **Update documentation** as needed
5. **Submit a pull request**

## Project Structure

```
ProjectManager/
├── src/                    # Source code
│   ├── plugins/           # Plugin modules
│   ├── utils.py           # Utility functions
│   └── __main__.py        # Main entry point
├── tests/                 # Test files
├── docs/                  # Documentation
├── projects/             # Project configurations
└── scripts/              # Build and deployment scripts
```

## Testing

- **Unit Tests**: Located in `tests/` directory
- **Integration Tests**: Test complete workflows
- **Code Coverage**: Run with `coverage run -m pytest`

## Code Style

- Follow PEP 8 style guidelines
- Use type hints where appropriate
- Add docstrings to all public functions
- Keep functions small and focused

## Documentation

- Update relevant documentation when adding features
- Include examples in docstrings
- Maintain README files in each directory 