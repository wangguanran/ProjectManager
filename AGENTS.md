# ProjectManager Agent Guide

You are working in the `ProjectManager` repository - a Python CLI tool for multi-board, multi-project patch/override management with Git integration.

## Priorities

1. Treat `docs/test_cases_en.md` as the source of truth for expected behavior.
2. Keep changes minimal and tightly scoped.
3. Prefer reproducible steps with exact commands and file paths.
4. After each module-level change (or after verifying a test suite passes), make a small commit and push it.
5. Before each commit, run `make format` (black + isort).
6. After each push, confirm GitHub Actions is green for the pushed commit SHA.
7. For `bug/*` and `feature/*` PRs targeting `main`, let `auto-version-bump.yml` update `pyproject.toml` only when release code changes are present; do not manually bump it unless the workflow cannot run.
8. For major releases, run the `Bump Major Version` workflow; it creates a `ci/*` PR that increments major and resets minor/patch to 0.
9. After merging a stable release PR to `main`, create and push the matching `vX.Y.Z` tag from the updated `main` commit.
10. Do not consider release work complete until the publish workflow and published artifacts are verified.
11. When waiting for GitHub Codex review, treat explicit Codex comments as actionable feedback; if Codex only reacts with a thumbs-up and leaves no comments, treat the review as OK.
12. After any PR is merged, switch the local checkout back to `main`, sync it to the merged `origin/main`, and delete the local temporary work branch.
13. For automated implementation/completion workflows, create normal ready PRs by default instead of draft PRs so auto-merge can be armed without manual GitHub actions.
14. Use draft PRs only for WIP/unfinished work; do not enable auto-merge while a PR is still draft.
15. If a workflow creates or encounters a draft PR, the completion subagent owns marking it ready with `gh pr ready` after execution, review, and verification are complete, then enabling auto-merge.
16. Auto-merge workflows and manual dispatches must treat draft PRs as a successful waiting/skip state, not as a failed run or a force-merge path.
17. Track work in the repo-root TODO note and delete completed TODO items:
   - `./TODO.md`
18. For complex tasks, the main agent must not run commands or edit files directly; it only analyzes, decomposes, assigns/publishes tasks, guides subagents, and collects results.
19. For a single issue-fix workflow, assign ownership as follows:
   - Step 1 (problem analysis) and step 2 (plan/task decomposition): the main agent.
   - Steps 3-5 (code/doc edit, formatting, testing/verification): one execution subagent.
   - Step 6 (review): a second subagent that reports only actionable findings or `OK`.
   - Step 7 (review feedback correction): handled through interaction between the first two subagents.
   - Steps 8-10 (commit/push, CI check, result summary): one completion subagent.

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
- Stable release tags must match `pyproject.toml` exactly: `pyproject.toml` version `X.Y.Z` -> tag `vX.Y.Z`.
- `bug/*` PRs targeting `main` automatically increment the patch version when release code changes are present, for example `0.1.0` -> `0.1.1`.
- `feature/*` PRs targeting `main` automatically increment the minor version and reset patch when release code changes are present, for example `0.1.1` -> `0.2.0`.
- PRs without release code changes must keep the same `pyproject.toml` version as `main`.
- Major releases are manual: run the `Bump Major Version` workflow to create a `ci/*` PR that bumps `0.2.3` -> `1.0.0`.

## CI/CD

GitHub Actions workflows in `.github/workflows/`:
- `python-app.yml`: Main test suite
- `pylint.yml`: Linting
- `publish-python.yml`: Manual PyPI release
- `publish-release.yml`: Tag-based stable release, GitHub Release assets, PyPI publish, and Docker publish
- `auto-merge-pr.yml`: PR auto-merge orchestration; arm auto-merge only for ready PRs and skip draft/WIP PRs until they are marked ready
- `auto-version-bump.yml`: PR version bump automation for `bug/*` and `feature/*`
- `bump-major-version.yml`: Manual major version bump PR creation
- `validate-main-pr-source.yml`: Required main PR gate, including branch source, rebase/no-merge, and version bump validation

Stable release flow:
```bash
# After the release PR is merged and local main is synced:
VERSION="$(python3 - <<'PY'
import tomllib
from pathlib import Path
print(tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]["version"])
PY
)"
git tag "v${VERSION}"
git push origin "v${VERSION}"
gh run list --repo wangguanran/ProjectManager --workflow publish-release.yml --limit 5
gh run watch <run-id> --repo wangguanran/ProjectManager --exit-status
gh release view "v${VERSION}" --repo wangguanran/ProjectManager
```

After publishing, verify the `publish-release.yml` run completed successfully and confirm:
- the GitHub Release `vX.Y.Z` exists and has uploaded assets,
- PyPI contains `multi-project-manager==X.Y.Z` or the workflow explicitly skipped upload because that version already exists,
- Docker publish succeeded or any failure is documented before handoff.

Check CI status after push:
```bash
SHA="$(git rev-parse HEAD)"
curl -sS -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/wangguanran/ProjectManager/actions/runs?per_page=30&branch=main" \
  | SHA="$SHA" python3 -c 'import os,sys,json; sha=os.environ["SHA"]; data=json.load(sys.stdin); runs=[r for r in data.get("workflow_runs",[]) if r.get("head_sha")==sha]; print([(r.get("name"),r.get("status"),r.get("conclusion")) for r in runs])'
```
