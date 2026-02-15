# ProjectManager Agent Guide

You are working in the `ProjectManager` repository - a Python CLI tool for multi-board, multi-project patch/override management with Git integration.

## Priorities

1. Treat `docs/test_cases_en.md` as the source of truth for expected behavior.
2. Keep changes minimal and tightly scoped.
3. Prefer reproducible steps with exact commands and file paths.
4. After each module-level change (or after verifying a test suite passes), make a small commit and push it.
5. Before each commit, run `make format` (black + isort).
6. After each push, confirm GitHub Actions is green for the pushed commit SHA.
7. Track work in the repo-root TODO note and delete completed TODO items:
   - `./TODO.md`

## Code Organization

```
src/
  __main__.py              # CLI entry, arg parsing, config loading
  log_manager.py           # Logging utilities
  profiler.py              # Performance profiling decorators
  utils.py                 # Helper functions
  plugins/                 # Operations/plugins
    project_manager.py     # project_new, project_del
    project_builder.py     # project_build, project_diff, build stages
    patch_override.py      # po_apply, po_revert, po_new, po_update, po_del, po_list
    po_plugins/            # PO plugin runtime (commits/patches/overrides/custom)
  operations/              # Operation registry
  hooks/                   # Git hooks support

tests/
  blackbox/                # CLI-level tests
  whitebox/                # Unit/whitebox tests (mirrors src structure)

projects/                  # Project definitions (INI files)
  common/common.ini        # Shared config
  board*/board*.ini        # Board/project configs

docs/
  en/                      # English docs
  zh/                      # Chinese docs
```

## Essential Commands

### Setup & Installation
```bash
REPO_ROOT="$(git rev-parse --show-toplevel)" && cd "$REPO_ROOT"
python3 -m venv /tmp/pm-venv
/tmp/pm-venv/bin/python -m pip install -U pip
/tmp/pm-venv/bin/python -m pip install -e '.[dev]'
/tmp/pm-venv/bin/projman --help
```

### Development
```bash
# Test (runs pytest with coverage)
make test

# Format code (black + isort)
make format

# Lint (pylint + black check + isort check)
make lint

# All checks
make check-all
```

### Build & Install (Standalone Binary)
```bash
./build.sh
./install.sh
```

## Safety Rules

- For destructive operations (`po_apply`, `po_revert`, `project_diff`), use `--dry-run` first on real repositories.
- Avoid destructive git commands (e.g., `git reset --hard`) unless explicitly requested.
- Never commit secrets/tokens.

## Version & Build

- `--version` includes short git commit hash when available.
- Build metadata: `scripts/write_build_info.py` (used by `build.sh` and CI).
- Version is in `pyproject.toml`.

## CI/CD

GitHub Actions workflows in `.github/workflows/`:
- `python-app.yml`: Main test suite
- `pylint.yml`: Linting
- `publish-python.yml`: PyPI release
- `publish-release.yml`: GitHub release

Check CI status after push:
```bash
SHA="$(git rev-parse HEAD)"
curl -sS -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/wangguanran/ProjectManager/actions/runs?per_page=30&branch=master" \
  | SHA="$SHA" python3 -c 'import os,sys,json; sha=os.environ["SHA"]; data=json.load(sys.stdin); runs=[r for r in data.get("workflow_runs",[]) if r.get("head_sha")==sha]; print([(r.get("name"),r.get("status"),r.get("conclusion")) for r in runs])'
```

