# ProjectManager Developer Guide

This guide shows contributors how to set up a local environment, understand the repository layout, follow the project standards, and submit changes. After completing the basics, continue with the deep-dive documents in `docs/en/development`.

## 1. Repository Layout

```text
ProjectManager/
├── src/                # Core source code
├── tests/              # Automated tests
├── docs/               # Documentation
├── scripts/            # Helper scripts
├── requirements.txt    # Runtime dependencies
└── pyproject.toml      # Project configuration
```

## 2. Environment Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/wangguanran/ProjectManager.git
   cd ProjectManager
   ```
2. **Create a virtual environment**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   pip install -e .
   ```
4. **Optional: install tooling**
   ```bash
   pip install pre-commit
   pre-commit install
   ```

## 3. Coding Standards

- Follow the formatting and lint rules defined in `pyproject.toml`.
- Run `make lint`, `make test`, or `pytest` before committing to ensure a clean state.
- Provide tests for new functionality and keep both Chinese and English docs up to date.

## 4. Contribution Workflow

1. Branch from `main` and pull the latest changes.
2. Implement the feature or fix, then run local tests and linters.
3. Write clear commit messages describing the intent of the change.
4. Open a Pull Request and mention documentation updates for both languages.
5. Address code review feedback until the PR is approved and merged.

## 5. Further Reading

- [Development Overview](../development/README.md): Build pipeline, debugging tips, and routine tasks.
- [System Architecture](../development/architecture.md): Component breakdown and data flows.
- [Scripts & Automation](../development/scripts.md): Build scripts and CI/CD workflows.
- [Testing Strategy](../development/testing.md): Test layers, tooling, and coverage goals.
- [Functional Requirements](../requirements/requirements.md): Capability descriptions and acceptance criteria.

## 6. Documentation Expectations

- Update both `docs/en` and `docs/zh` to keep language pairs aligned.
- When adding new topics, remember to update the language indexes (`docs/en/README.md` and `docs/zh/README.md`).
- User-facing changes should be reflected in both the user and developer modules where relevant.
