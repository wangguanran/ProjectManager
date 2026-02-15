"""Blackbox configuration tests aligned with docs/test_cases_zh.md."""

from __future__ import annotations

import json
from pathlib import Path

from .conftest import run_cli


def _read_latest_log(root: Path) -> str:
    log_path = root / ".cache" / "latest.log"
    if not log_path.exists():
        return ""
    return log_path.read_text(encoding="utf-8")


def _load_projects_json(root: Path) -> dict:
    projects_json = root / "projects" / "boardA" / "projects.json"
    assert projects_json.exists()
    return json.loads(projects_json.read_text(encoding="utf-8"))


def test_cfg_001_missing_common_ini(workspace_a: Path) -> None:
    common_ini = workspace_a / "projects" / "common" / "common.ini"
    common_ini.unlink()
    _ = run_cli(["po_list", "projA"], cwd=workspace_a)
    log_text = _read_latest_log(workspace_a)
    assert "common config not found" in log_text.lower()


def test_cfg_002_po_configs_loaded(workspace_a: Path) -> None:
    _ = run_cli(["po_list", "projA"], cwd=workspace_a)
    log_text = _read_latest_log(workspace_a)
    assert "po configurations" in log_text.lower()
    assert "po-po_base" in log_text


def test_cfg_003_inline_comment_stripped(workspace_a: Path) -> None:
    common_ini = workspace_a / "projects" / "common" / "common.ini"
    text = common_ini.read_text(encoding="utf-8")
    if "[common]" in text:
        parts = text.split("[common]", 1)
        updated = parts[0] + "[common]\nINLINE_KEY = value # comment\n" + parts[1]
    else:
        updated = text + "\n[common]\nINLINE_KEY = value # comment\n"
    common_ini.write_text(updated, encoding="utf-8")
    _ = run_cli(["po_list", "projA"], cwd=workspace_a)
    data = _load_projects_json(workspace_a)
    proj = next(item for item in data["projects"] if item["project_name"] == "projA")
    assert proj["config"]["INLINE_KEY"] == "value"


def test_cfg_004_projects_dir_missing(workspace_a: Path) -> None:
    projects = workspace_a / "projects"
    projects.rename(workspace_a / "projects_backup")
    _ = run_cli(["po_list", "projA"], cwd=workspace_a, check=False)
    log_text = _read_latest_log(workspace_a)
    assert "projects directory does not exist" in log_text.lower()


def test_cfg_005_board_without_ini(workspace_a: Path) -> None:
    empty_board = workspace_a / "projects" / "boardEmpty"
    empty_board.mkdir()
    _ = run_cli(["po_list", "projA"], cwd=workspace_a)
    log_text = _read_latest_log(workspace_a)
    assert "no ini file found" in log_text.lower()


def test_cfg_006_multiple_ini_files(workspace_a: Path) -> None:
    board_dir = workspace_a / "projects" / "boardMulti"
    board_dir.mkdir()
    (board_dir / "a.ini").write_text("[a]\nKEY=1\n", encoding="utf-8")
    (board_dir / "b.ini").write_text("[b]\nKEY=2\n", encoding="utf-8")
    result = run_cli(["po_list", "projA"], cwd=workspace_a, check=False)
    assert result.returncode != 0
    assert "Multiple ini files found" in result.stderr


def test_cfg_007_duplicate_key_skips_board(workspace_a: Path) -> None:
    board_dir = workspace_a / "projects" / "boardDup"
    board_dir.mkdir()
    (board_dir / "boardDup.ini").write_text(
        "[dup]\nPROJECT_NAME=one\nPROJECT_NAME=two\n",
        encoding="utf-8",
    )
    _ = run_cli(["po_list", "projA"], cwd=workspace_a)
    log_text = _read_latest_log(workspace_a)
    assert "duplicate key" in log_text.lower()


def test_cfg_008_config_inheritance_po_concat(workspace_a: Path) -> None:
    _ = run_cli(["po_list", "projA-sub"], cwd=workspace_a)
    data = _load_projects_json(workspace_a)
    proj = next(item for item in data["projects"] if item["project_name"] == "projA-sub")
    assert "PROJECT_PO_CONFIG" in proj["config"]
    assert "po_base" in proj["config"]["PROJECT_PO_CONFIG"]
    assert "po_sub" in proj["config"]["PROJECT_PO_CONFIG"]


def test_cfg_009_parent_children_relationship(workspace_a: Path) -> None:
    _ = run_cli(["po_list", "projA"], cwd=workspace_a)
    data = _load_projects_json(workspace_a)
    proj_a = next(item for item in data["projects"] if item["project_name"] == "projA")
    proj_sub = next(item for item in data["projects"] if item["project_name"] == "projA-sub")
    assert proj_sub["parent"] == "projA"
    assert "projA-sub" in proj_a["children"]


def test_cfg_010_projects_json_written(workspace_a: Path) -> None:
    _ = run_cli(["po_list", "projA"], cwd=workspace_a)
    projects_json = workspace_a / "projects" / "boardA" / "projects.json"
    assert projects_json.exists()
    data = json.loads(projects_json.read_text(encoding="utf-8"))
    assert Path(data["board_path"]).is_absolute() is False
    assert data["board_path"] == str(Path("projects") / "boardA")
    for project in data.get("projects", []):
        ini_file = project.get("ini_file")
        if ini_file:
            assert Path(ini_file).is_absolute() is False
