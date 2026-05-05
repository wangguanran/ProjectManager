"""Blackbox tests for board/project management."""

from __future__ import annotations

import json
import os
import shutil
from configparser import ConfigParser
from pathlib import Path

from .conftest import REPO_ROOT, run_cli


def _copy_template(target: Path) -> None:
    src = REPO_ROOT / "projects" / "template"
    if src.exists():
        shutil.copytree(src, target / "projects" / "template")


def test_pm_001_board_new_with_template(empty_workspace: Path) -> None:
    _copy_template(empty_workspace)
    result = run_cli(["board_new", "boardTest"], cwd=empty_workspace)
    assert result.returncode == 0
    board_dir = empty_workspace / "projects" / "boardTest"
    ini_path = board_dir / "boardTest.ini"
    po_dir = board_dir / "po"
    assert ini_path.exists()
    assert po_dir.exists()
    projects_json = board_dir / "projects.json"
    data = json.loads(projects_json.read_text(encoding="utf-8"))
    assert Path(data["board_path"]).is_absolute() is False
    assert data["board_path"] == str(Path("projects") / "boardTest")

    run_cli(["project_new", "app1"], cwd=empty_workspace)
    po_list_result = run_cli(["po_list", "app1", "--short"], cwd=empty_workspace)

    config = ConfigParser()
    config.optionxform = str
    config.read(ini_path, encoding="utf-8")
    po_config = config["boardTest"].get("PROJECT_PO_CONFIG", "").strip()
    copied_po_names = sorted(path.name for path in po_dir.iterdir() if path.is_dir())

    errors = []
    if po_config != "po_template":
        errors.append(f"PROJECT_PO_CONFIG should be po_template, got {po_config!r}")
    if copied_po_names != ["po_template"]:
        errors.append(f"copied PO dirs should be ['po_template'], got {copied_po_names!r}")
    if "po_template" not in po_list_result.stdout:
        errors.append(f"po_list app1 --short should show po_template, got: {po_list_result.stdout!r}")
    assert not errors, "\n".join(errors)


def test_pm_002_board_new_without_template(workspace_a: Path) -> None:
    template_dir = workspace_a / "projects" / "template"
    if template_dir.exists():
        shutil.rmtree(template_dir)
    result = run_cli(["board_new", "boardNoTpl"], cwd=workspace_a)
    assert result.returncode == 0
    board_dir = workspace_a / "projects" / "boardNoTpl"
    ini_path = board_dir / "boardNoTpl.ini"
    assert ini_path.exists()
    assert (board_dir / "po" / "po_template" / "patches").exists()

    projects_json = board_dir / "projects.json"
    data = json.loads(projects_json.read_text(encoding="utf-8"))
    assert Path(data["board_path"]).is_absolute() is False
    assert data["board_path"] == str(Path("projects") / "boardNoTpl")


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
    projects_json = workspace_a / "projects" / "boardA" / "projects.json"
    data = json.loads(projects_json.read_text(encoding="utf-8"))
    assert any(project.get("project_name") == "projA-new" for project in data["projects"])


def test_pm_009_project_new_creates_first_top_level_project(empty_workspace: Path) -> None:
    projects_dir = empty_workspace / "projects"
    board_dir = projects_dir / "board1"
    board_dir.mkdir(parents=True)
    ini_path = board_dir / "board1.ini"
    ini_path.write_text("[board1]\nPROJECT_NAME =\n", encoding="utf-8")

    result = run_cli(["project_new", "myproject"], cwd=empty_workspace)

    assert result.returncode == 0
    text = ini_path.read_text(encoding="utf-8")
    assert "[myproject]" in text
    assert "PROJECT_NAME = myproject" in text


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
