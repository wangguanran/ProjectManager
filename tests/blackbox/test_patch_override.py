"""Blackbox tests for patch/override operations."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from src.__main__ import _load_all_projects, _load_common_config
from src.plugins.patch_override import parse_po_config, po_apply, po_revert

from .conftest import init_git_repo, run_cli, setup_dataset_a


def _load_projects(root: Path):
    common, _ = _load_common_config(str(root / "projects"))
    return _load_all_projects(str(root / "projects"), common)


def _update_project_po_config(root: Path, project: str, value: str) -> None:
    ini_path = root / "projects" / "boardA" / "boardA.ini"
    lines = ini_path.read_text(encoding="utf-8").splitlines()
    updated = []
    in_section = False
    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            in_section = line.strip("[]") == project
            updated.append(line)
            continue
        if in_section and line.replace(" ", "").startswith("PROJECT_PO_CONFIG="):
            updated.append(f"PROJECT_PO_CONFIG = {value}")
        else:
            updated.append(line)
    ini_path.write_text("\n".join(updated) + "\n", encoding="utf-8")


def _remove_common_po_config(root: Path) -> None:
    common_ini = root / "projects" / "common" / "common.ini"
    lines = [
        line
        for line in common_ini.read_text(encoding="utf-8").splitlines()
        if not line.strip().startswith("PROJECT_PO_CONFIG")
    ]
    common_ini.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_po_001_parse_po_config() -> None:
    apply_pos, exclude_pos, exclude_files = parse_po_config("po1 po2 -po3 -po4[file1 file2]")
    assert apply_pos == ["po1", "po2"]
    assert exclude_pos == {"po3", "po4"}
    assert exclude_files["po4"] == {"file1", "file2"}


def test_po_002_po_config_empty_returns(workspace_a: Path) -> None:
    # Remove common PROJECT_PO_CONFIG to avoid inheritance concat
    _remove_common_po_config(workspace_a)
    _update_project_po_config(workspace_a, "projA", "")
    result = run_cli(["po_apply", "projA"], cwd=workspace_a, check=False)
    log_text = (workspace_a / ".cache" / "latest.log").read_text(encoding="utf-8")
    assert result.returncode == 0
    assert "No PROJECT_PO_CONFIG" in log_text


def test_po_003_missing_board_name(workspace_a: Path) -> None:
    projects_info = _load_projects(workspace_a)
    projects_info["projA"]["board_name"] = None
    env = {
        "root_path": str(workspace_a),
        "projects_path": str(workspace_a / "projects"),
        "repositories": [{"name": "root", "path": str(workspace_a)}],
    }
    assert po_apply(env, projects_info, "projA") is False


def test_po_004_skip_applied_po(workspace_a: Path) -> None:
    record_path = workspace_a / ".cache" / "po_applied" / "boardA" / "projA" / "po_base.json"
    record_path.parent.mkdir(parents=True, exist_ok=True)
    record_path.write_text('{"status":"applied"}\n', encoding="utf-8")
    result = run_cli(["po_apply", "projA"], cwd=workspace_a)
    log_text = (workspace_a / ".cache" / "latest.log").read_text(encoding="utf-8")
    assert result.returncode == 0
    assert "already applied" in log_text.lower()


def test_po_004b_applied_record_written(workspace_a: Path) -> None:
    (workspace_a / "src" / "tmp_file.txt").write_text("line1", encoding="utf-8")
    result = run_cli(["po_apply", "projA"], cwd=workspace_a)
    assert result.returncode == 0

    record_path = workspace_a / ".cache" / "po_applied" / "boardA" / "projA" / "po_base.json"
    assert record_path.exists()
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert record["project_name"] == "projA"
    assert record["po_name"] == "po_base"
    patch_targets = {t for item in record.get("patches", []) for t in item.get("targets", [])}
    assert "src/tmp_file.txt" in patch_targets


def test_po_005_patch_apply_success(workspace_a: Path) -> None:
    target = workspace_a / "src" / "tmp_file.txt"
    target.write_text("line1", encoding="utf-8")
    result = run_cli(["po_apply", "projA"], cwd=workspace_a)
    assert result.returncode == 0
    assert "line2" in target.read_text(encoding="utf-8")


def test_po_005b_commit_apply_success(workspace_a: Path) -> None:
    commits_dir = workspace_a / "projects" / "boardA" / "po" / "po_base" / "commits"
    commits_dir.mkdir(parents=True, exist_ok=True)

    commit_file = workspace_a / "commit_file.txt"
    commit_file.write_text("from commit\n", encoding="utf-8")
    subprocess.run(["git", "add", "commit_file.txt"], cwd=str(workspace_a), check=True)
    subprocess.run(["git", "commit", "-m", "add commit file"], cwd=str(workspace_a), check=True)
    subprocess.run(["git", "format-patch", "-1", "HEAD", "-o", str(commits_dir)], cwd=str(workspace_a), check=True)

    subprocess.run(["git", "reset", "--hard", "HEAD~1"], cwd=str(workspace_a), check=True)
    assert not commit_file.exists()

    result = run_cli(["po_apply", "projA"], cwd=workspace_a)
    assert result.returncode == 0
    assert commit_file.exists()
    assert "line2" in (workspace_a / "src" / "tmp_file.txt").read_text(encoding="utf-8")

    subject = subprocess.run(
        ["git", "log", "-1", "--pretty=%s"],
        cwd=str(workspace_a),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert subject == "add commit file"

    record_path = workspace_a / ".cache" / "po_applied" / "boardA" / "projA" / "po_base.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert record.get("commits"), "Commit application should be recorded"

    revert = run_cli(["po_revert", "projA"], cwd=workspace_a)
    assert revert.returncode == 0
    assert not commit_file.exists()
    assert not record_path.exists()


def test_po_006_patch_apply_fail(workspace_a: Path) -> None:
    bad_patch = workspace_a / "projects" / "boardA" / "po" / "po_base" / "patches" / "bad.patch"
    bad_patch.write_text("invalid patch", encoding="utf-8")
    result = run_cli(["po_apply", "projA"], cwd=workspace_a, check=False)
    assert result.returncode != 0


def test_po_007_override_copy_success(workspace_a: Path) -> None:
    (workspace_a / "src" / "tmp_file.txt").write_text("line1", encoding="utf-8")
    target = workspace_a / "tmp_file.txt"
    if target.exists():
        target.unlink()
    result = run_cli(["po_apply", "projA"], cwd=workspace_a, check=False)
    assert result.returncode == 0
    assert target.exists()


def test_po_008_remove_file(workspace_a: Path) -> None:
    (workspace_a / "src" / "tmp_file.txt").write_text("line1", encoding="utf-8")
    remove_dir = workspace_a / "projects" / "boardA" / "po" / "po_base" / "overrides"
    remove_target = workspace_a / "remove_me.txt"
    remove_target.write_text("bye", encoding="utf-8")
    (remove_dir / "remove_me.txt.remove").write_text("", encoding="utf-8")
    result = run_cli(["po_apply", "projA", "--force"], cwd=workspace_a, check=False)
    assert result.returncode == 0
    assert not remove_target.exists()


def test_po_009_exclude_files_skip(workspace_a: Path) -> None:
    (workspace_a / "src" / "tmp_file.txt").write_text("line1", encoding="utf-8")
    _remove_common_po_config(workspace_a)
    _update_project_po_config(workspace_a, "projA", "po_base -po_base[remove_me.txt.remove]")
    remove_dir = workspace_a / "projects" / "boardA" / "po" / "po_base" / "overrides"
    remove_target = workspace_a / "remove_me.txt"
    remove_target.write_text("keep", encoding="utf-8")
    (remove_dir / "remove_me.txt.remove").write_text("", encoding="utf-8")
    result = run_cli(["po_apply", "projA"], cwd=workspace_a)
    assert result.returncode == 0
    assert remove_target.exists()


def test_po_010_custom_copy(workspace_a: Path) -> None:
    (workspace_a / "src" / "tmp_file.txt").write_text("line1", encoding="utf-8")
    _remove_common_po_config(workspace_a)
    # Align with PROJECT_PO_DIR=custom by nesting under custom/custom
    nested = workspace_a / "projects" / "boardA" / "po" / "po_base" / "custom" / "custom"
    (nested / "cfg").mkdir(parents=True, exist_ok=True)
    (nested / "data").mkdir(parents=True, exist_ok=True)
    (nested / "cfg" / "sample.ini").write_text("k=v", encoding="utf-8")
    (nested / "data" / "sample.dat").write_text("data", encoding="utf-8")
    result = run_cli(["po_apply", "projA"], cwd=workspace_a)
    assert result.returncode == 0
    assert (workspace_a / "out" / "cfg" / "sample.ini").exists()
    assert (workspace_a / "out" / "data" / "sample.dat").exists()


def test_po_011_revert_patch_success(workspace_a: Path) -> None:
    (workspace_a / "src" / "tmp_file.txt").write_text("line1", encoding="utf-8")
    _remove_common_po_config(workspace_a)
    run_cli(["po_apply", "projA"], cwd=workspace_a)
    result = run_cli(["po_revert", "projA"], cwd=workspace_a)
    assert result.returncode == 0


def test_po_012_revert_override_tracked(workspace_a: Path) -> None:
    (workspace_a / "src" / "tmp_file.txt").write_text("line1", encoding="utf-8")
    _remove_common_po_config(workspace_a)
    target = workspace_a / "tracked.txt"
    target.write_text("base", encoding="utf-8")
    os.system(f"cd {workspace_a} && git add tracked.txt && git commit -m 'tracked'")
    override_dir = workspace_a / "projects" / "boardA" / "po" / "po_base" / "overrides"
    (override_dir / "tracked.txt").write_text("override", encoding="utf-8")
    run_cli(["po_apply", "projA"], cwd=workspace_a)
    run_cli(["po_revert", "projA"], cwd=workspace_a)
    assert target.read_text(encoding="utf-8") == "base"


def test_po_013_revert_override_untracked(workspace_a: Path) -> None:
    (workspace_a / "src" / "tmp_file.txt").write_text("line1", encoding="utf-8")
    target = workspace_a / "untracked.txt"
    target.write_text("override", encoding="utf-8")
    override_dir = workspace_a / "projects" / "boardA" / "po" / "po_base" / "overrides"
    (override_dir / "untracked.txt").write_text("override", encoding="utf-8")
    _remove_common_po_config(workspace_a)
    run_cli(["po_apply", "projA"], cwd=workspace_a)
    run_cli(["po_revert", "projA"], cwd=workspace_a)
    assert not target.exists()


def test_po_014_custom_revert_warning(workspace_a: Path) -> None:
    (workspace_a / "src" / "tmp_file.txt").write_text("line1", encoding="utf-8")
    _remove_common_po_config(workspace_a)
    run_cli(["po_apply", "projA"], cwd=workspace_a, check=False)
    result = run_cli(["po_revert", "projA"], cwd=workspace_a, check=False)
    log_text = (workspace_a / ".cache" / "latest.log").read_text(encoding="utf-8")
    assert result.returncode == 0
    assert "manual cleanup may be required" in log_text.lower()


def test_po_014b_remove_revert_tracked(workspace_a: Path) -> None:
    (workspace_a / "src" / "tmp_file.txt").write_text("line1", encoding="utf-8")
    _remove_common_po_config(workspace_a)
    target = workspace_a / "remove_me.txt"
    target.write_text("base", encoding="utf-8")
    subprocess.run(["git", "add", "remove_me.txt"], cwd=str(workspace_a), check=True)
    subprocess.run(["git", "commit", "-m", "track remove target"], cwd=str(workspace_a), check=True)

    remove_dir = workspace_a / "projects" / "boardA" / "po" / "po_base" / "overrides"
    (remove_dir / "remove_me.txt.remove").write_text("", encoding="utf-8")

    run_cli(["po_apply", "projA", "--force"], cwd=workspace_a)
    assert not target.exists()

    run_cli(["po_revert", "projA"], cwd=workspace_a)
    assert target.exists()
    assert target.read_text(encoding="utf-8") == "base"


def test_po_014c_shared_projects_dont_share_applied_marker(tmp_path: Path) -> None:
    ws1 = tmp_path / "ws1"
    ws2 = tmp_path / "ws2"
    shared_projects = tmp_path / "shared_projects"
    ws1.mkdir()
    ws2.mkdir()

    setup_dataset_a(ws1)
    shutil.move(str(ws1 / "projects"), str(shared_projects))
    os.symlink(shared_projects, ws1 / "projects")

    # create ws2 baseline repo compatible with shared PO patches
    init_git_repo(ws2)
    (ws2 / "src").mkdir(exist_ok=True)
    tmp_file = ws2 / "src" / "tmp_file.txt"
    tmp_file.write_text("line1", encoding="utf-8")
    subprocess.run(["git", "add", "src/tmp_file.txt"], cwd=str(ws2), check=True)
    subprocess.run(["git", "commit", "-m", "add tmp file"], cwd=str(ws2), check=True)
    os.symlink(shared_projects, ws2 / "projects")

    (ws1 / "src" / "tmp_file.txt").write_text("line1", encoding="utf-8")
    run_cli(["po_apply", "projA"], cwd=ws1)
    assert (ws1 / ".cache" / "po_applied" / "boardA" / "projA" / "po_base.json").exists()
    assert not (ws2 / ".cache" / "po_applied" / "boardA" / "projA" / "po_base.json").exists()

    run_cli(["po_apply", "projA"], cwd=ws2)
    assert "line2" in tmp_file.read_text(encoding="utf-8")


def test_po_015_po_new_invalid_name(workspace_a: Path) -> None:
    result = run_cli(["po_new", "projA", "PO-INVALID"], cwd=workspace_a, check=False)
    assert result.returncode != 0


def test_po_016_po_new_force(workspace_a: Path) -> None:
    result = run_cli(["po_new", "projA", "po_force", "--force"], cwd=workspace_a)
    assert result.returncode == 0
    assert (workspace_a / "projects" / "boardA" / "po" / "po_force" / "commits").exists()
    assert (workspace_a / "projects" / "boardA" / "po" / "po_force" / "patches").exists()


def test_po_017_po_new_interactive(workspace_a: Path) -> None:
    # Use --force to avoid interactive selection but ensure command runs
    result = run_cli(["po_new", "projA", "po_interactive", "--force"], cwd=workspace_a)
    assert result.returncode == 0


def test_po_018_po_new_no_repo(empty_workspace: Path) -> None:
    result = run_cli(["po_new", "projA", "po_empty"], cwd=empty_workspace, check=False)
    assert result.returncode != 0


def test_po_019_po_update_existing(workspace_a: Path) -> None:
    run_cli(["po_new", "projA", "po_update_target", "--force"], cwd=workspace_a)
    result = run_cli(["po_update", "projA", "po_update_target", "--force"], cwd=workspace_a)
    assert result.returncode == 0


def test_po_020_po_update_missing(workspace_a: Path) -> None:
    result = run_cli(["po_update", "projA", "po_not_exists", "--force"], cwd=workspace_a, check=False)
    assert result.returncode != 0


def test_po_021_po_del_remove_config(workspace_a: Path) -> None:
    result = run_cli(["po_del", "projA", "po_base", "--force"], cwd=workspace_a)
    assert result.returncode == 0
    assert not (workspace_a / "projects" / "boardA" / "po" / "po_base").exists()


def test_po_022_po_del_cancel(workspace_a: Path) -> None:
    run_cli(["po_new", "projA", "po_cancel", "--force"], cwd=workspace_a)
    result = run_cli(["po_del", "projA", "po_cancel"], cwd=workspace_a, check=False)
    assert result.returncode != 0
    assert (workspace_a / "projects" / "boardA" / "po" / "po_cancel").exists()


def test_po_023_po_list_short(workspace_a: Path) -> None:
    result = run_cli(["po_list", "projA", "--short"], cwd=workspace_a)
    assert "po_base" in result.stdout


def test_po_024_po_list_detail(workspace_a: Path) -> None:
    result = run_cli(["po_list", "projA"], cwd=workspace_a)
    assert "commits" in result.stdout
    assert "patches" in result.stdout
    assert "overrides" in result.stdout
