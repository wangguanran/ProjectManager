"""
Black-box CLI tests derived from docs/test_cases_en.md.

These tests exercise the real `python -m src ...` entrypoint in a temporary
workspace (cwd), with PYTHONPATH pointing to the repo source tree.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import toml

REPO_ROOT = Path(__file__).resolve().parents[2]


def _write_min_projects_tree(workdir: Path) -> None:
    # Minimal config for operations that need projects_info (e.g., po_list/project_build).
    (workdir / "projects" / "common").mkdir(parents=True, exist_ok=True)
    (workdir / "projects" / "common" / "common.ini").write_text(
        "\n".join(
            [
                "[common]",
                "PROJECT_PLATFORM = platA",
                "PROJECT_CUSTOMER = custA",
                "PROJECT_PO_CONFIG =",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    (workdir / "projects" / "boardA").mkdir(parents=True, exist_ok=True)
    (workdir / "projects" / "boardA" / "boardA.ini").write_text(
        "\n".join(
            [
                "[boardA]",
                "PROJECT_NAME = boardA",
                "PROJECT_PO_CONFIG =",
                "",
                "[projA]",
                "PROJECT_NAME = projA",
                "PROJECT_PLATFORM = platA",
                "PROJECT_CUSTOMER = custA",
                "PROJECT_PO_CONFIG =",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _run_cli(workdir: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    return subprocess.run(
        [sys.executable, "-m", "src", *args],
        cwd=str(workdir),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_help_shows_flags(tmp_path: Path) -> None:
    """CLI-001: `--help` shows operations and plugin flags."""
    _write_min_projects_tree(tmp_path)
    cp = _run_cli(tmp_path, "--help")
    assert cp.returncode == 0
    assert "supported operations" in (cp.stdout + cp.stderr)
    assert "--keep-diff-dir" in (cp.stdout + cp.stderr)
    assert "--short" in (cp.stdout + cp.stderr)


def test_cli_version_matches_pyproject(tmp_path: Path) -> None:
    """CLI-002: `--version` reads pyproject.toml."""
    _write_min_projects_tree(tmp_path)
    cp = _run_cli(tmp_path, "--version")
    assert cp.returncode == 0
    base_version = toml.load(str(REPO_ROOT / "pyproject.toml"))["project"]["version"]
    # May include a build suffix like +g<shortsha>.
    assert cp.stdout.strip().startswith(base_version)


def test_cli_upgrade_dry_run_without_projects_tree(tmp_path: Path) -> None:
    """CLI-010: `upgrade --dry-run` works without `projects/` directory."""
    cp = _run_cli(tmp_path, "upgrade", "--dry-run")
    assert cp.returncode == 0
    assert "common config not found" not in cp.stderr.lower()
    assert "projects directory does not exist" not in cp.stderr.lower()


def test_cli_exact_operation_executes(tmp_path: Path) -> None:
    """CLI-003/CLI-007: exact op match executes; `--short` is parsed as boolean flag."""
    _write_min_projects_tree(tmp_path)
    cp = _run_cli(tmp_path, "po_list", "projA", "--short")
    assert cp.returncode == 0


def test_cli_fuzzy_match_build_executes(tmp_path: Path) -> None:
    """CLI-004: fuzzy match (prefix) auto-corrects and executes."""
    _write_min_projects_tree(tmp_path)
    cp = _run_cli(tmp_path, "buil", "projA")
    assert cp.returncode == 0


def test_cli_fuzzy_match_ambiguity_warning(tmp_path: Path) -> None:
    """CLI-005: fuzzy match ambiguity warning shows candidates and still executes."""
    _write_min_projects_tree(tmp_path)
    cp = _run_cli(tmp_path, "po", "projA")
    assert cp.returncode == 0
    combined = cp.stdout + cp.stderr
    assert "Ambiguous operation" in combined
    assert "Possible matches" in combined
    assert "Using best match" in combined


def test_cli_unknown_operation_is_error(tmp_path: Path) -> None:
    """CLI-006: unknown operation triggers non-zero exit."""
    _write_min_projects_tree(tmp_path)
    cp = _run_cli(tmp_path, "unknown_op", "projA")
    assert cp.returncode != 0


def test_cli_unsupported_flag_causes_error(tmp_path: Path) -> None:
    """CLI-008: unsupported flag triggers TypeError -> non-zero exit."""
    _write_min_projects_tree(tmp_path)
    cp = _run_cli(tmp_path, "po_list", "projA", "--unknown-flag", "1")
    assert cp.returncode != 0


def test_cli_missing_required_args_is_error(tmp_path: Path) -> None:
    """CLI-009: missing required args shows error."""
    _write_min_projects_tree(tmp_path)
    cp = _run_cli(tmp_path, "project_new")
    assert cp.returncode != 0
