"""Blackbox CLI tests aligned with docs/test_cases_zh.md."""

from __future__ import annotations

import re
from pathlib import Path

from .conftest import run_cli


def _read_latest_log(root: Path) -> str:
    log_path = root / ".cache" / "latest.log"
    if not log_path.exists():
        return ""
    return log_path.read_text(encoding="utf-8")


def test_cli_001_help_lists_operations(workspace_a: Path) -> None:
    result = run_cli(["--help"], cwd=workspace_a)
    assert "supported operations" in result.stdout


def test_cli_002_version_matches_pyproject(workspace_a: Path) -> None:
    result = run_cli(["--version"], cwd=workspace_a)
    version = result.stdout.strip()
    assert re.fullmatch(r"0\.0\.11(\+g[0-9a-f]{7})?", version)


def test_cli_002a_version_no_projects_dir_no_warnings(empty_workspace: Path) -> None:
    result = run_cli(["--version"], cwd=empty_workspace)
    assert "common config not found" not in result.stderr.lower()
    assert "projects directory does not exist" not in result.stderr.lower()


def test_cli_002b_help_no_projects_dir_no_warnings(empty_workspace: Path) -> None:
    result = run_cli(["--help"], cwd=empty_workspace)
    assert "common config not found" not in result.stderr.lower()
    assert "projects directory does not exist" not in result.stderr.lower()


def test_cli_003_exact_operation_runs(workspace_a: Path) -> None:
    result = run_cli(["po_list", "projA", "--short"], cwd=workspace_a)
    assert "po_base" in result.stdout


def test_cli_004_fuzzy_match_build(workspace_a: Path) -> None:
    _ = run_cli(["buil", "projA"], cwd=workspace_a, check=False)
    log_text = _read_latest_log(workspace_a)
    assert "Fuzzy match: 'buil' -> 'project_build'" in log_text


def test_cli_005_ambiguous_fuzzy_match(workspace_a: Path) -> None:
    _ = run_cli(["po", "projA"], cwd=workspace_a, check=False)
    log_text = _read_latest_log(workspace_a)
    assert "Ambiguous operation 'po'" in log_text
    assert "Using best match" in log_text


def test_cli_006_unknown_operation_suggestion(workspace_a: Path) -> None:
    result = run_cli(["unknown_op", "projA"], cwd=workspace_a, check=False)
    assert result.returncode != 0
    assert "Unknown operation" in result.stderr


def test_cli_007_short_flag_parsed(workspace_a: Path) -> None:
    result = run_cli(["po_list", "projA", "--short"], cwd=workspace_a)
    assert "patches" not in result.stdout


def test_cli_008_unsupported_param_raises(workspace_a: Path) -> None:
    result = run_cli(["po_list", "projA", "--unknown-flag", "1"], cwd=workspace_a, check=False)
    assert result.returncode != 0
    assert "unexpected keyword argument" in result.stderr


def test_cli_009_missing_required_param(workspace_a: Path) -> None:
    result = run_cli(["project_new"], cwd=workspace_a, check=False)
    assert result.returncode != 0
    assert "required" in result.stderr.lower()
