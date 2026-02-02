"""Blackbox tests for board/project management."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from .conftest import REPO_ROOT, run_cli


def _copy_template(target: Path) -> None:
    src = REPO_ROOT / "projects" / "template"
    if src.exists():
        shutil.copytree(src, target / "projects" / "template")


def test_pm_001_board_new_with_template(workspace_a: Path) -> None:
    _copy_template(workspace_a)
    result = run_cli(["board_new", "boardTest"], cwd=workspace_a)
    assert result.returncode == 0
    assert (workspace_a / "projects" / "boardTest" / "boardTest.ini").exists()
    assert (workspace_a / "projects" / "boardTest" / "po").exists()


def test_pm_002_board_new_without_template(workspace_a: Path) -> None:
    template_dir = workspace_a / "projects" / "template"
    if template_dir.exists():
        shutil.rmtree(template_dir)
    result = run_cli(["board_new", "boardNoTpl"], cwd=workspace_a)
    assert result.returncode == 0
    ini_path = workspace_a / "projects" / "boardNoTpl" / "boardNoTpl.ini"
    assert ini_path.exists()
    assert (workspace_a / "projects" / "boardNoTpl" / "po" / "po_template" / "patches").exists()


def test_pm_003_board_new_invalid_names(workspace_a: Path) -> None:
    for name in ["", ".", ".."]:
        result = run_cli(["board_new", name], cwd=workspace_a, check=False)
        assert result.returncode != 0


def test_pm_004_board_new_invalid_path(workspace_a: Path) -> None:
    for name in ["a/b", "/abs/path"]:
        result = run_cli(["board_new", name], cwd=workspace_a, check=False)
        assert result.returncode != 0


def test_pm_005_board_new_reserved_name(workspace_a: Path) -> None:
    result = run_cli(["board_new", "common"], cwd=workspace_a, check=False)
    assert result.returncode != 0


def test_pm_006_board_new_existing(workspace_a: Path) -> None:
    result = run_cli(["board_new", "boardA"], cwd=workspace_a, check=False)
    assert result.returncode != 0


def test_pm_007_board_del_removes_cache(workspace_a: Path) -> None:
    _copy_template(workspace_a)
    run_cli(["board_new", "boardDel"], cwd=workspace_a)
    run_cli(["board_del", "boardDel"], cwd=workspace_a)
    assert not (workspace_a / "projects" / "boardDel").exists()


def test_pm_008_board_del_protected(workspace_a: Path) -> None:
    from src.plugins.project_manager import board_del

    env = {
        "root_path": str(workspace_a),
        "projects_path": str(workspace_a / "projects"),
        "protected_boards": ["boardA"],
    }
    assert board_del(env, {}, "boardA") is False


def test_pm_009_project_new_append_section(workspace_a: Path) -> None:
    result = run_cli(["project_new", "projA-new"], cwd=workspace_a)
    assert result.returncode == 0
    ini_path = workspace_a / "projects" / "boardA" / "boardA.ini"
    text = ini_path.read_text(encoding="utf-8")
    assert "[projA-new]" in text


def test_pm_010_project_new_unknown_board(workspace_a: Path) -> None:
    result = run_cli(["project_new", "unknownProj"], cwd=workspace_a, check=False)
    assert result.returncode != 0


def test_pm_011_project_new_board_name_conflict(workspace_a: Path) -> None:
    result = run_cli(["project_new", "boardA"], cwd=workspace_a, check=False)
    assert result.returncode != 0


def test_pm_012_project_new_duplicate(workspace_a: Path) -> None:
    result = run_cli(["project_new", "projA"], cwd=workspace_a, check=False)
    assert result.returncode != 0


def test_pm_013_project_del_with_children(workspace_a: Path) -> None:
    run_cli(["project_del", "projA"], cwd=workspace_a)
    ini_path = workspace_a / "projects" / "boardA" / "boardA.ini"
    text = ini_path.read_text(encoding="utf-8")
    assert "[projA]" not in text
    assert "[projA-sub]" not in text


def test_pm_014_project_del_missing(workspace_a: Path) -> None:
    result = run_cli(["project_del", "not_exist_proj"], cwd=workspace_a, check=False)
    assert result.returncode != 0
    assert "board info" in result.stderr.lower() or "failed" in result.stderr.lower()
