"""Blackbox tests for project diff/build."""

from __future__ import annotations

import glob
import os
import sys
from pathlib import Path

from src.hooks import HookPriority, HookType, clear_hooks, register_hook
from src.plugins.project_builder import project_build

from .conftest import run_cli
from .conftest import workspace_a as _workspace_a


def _latest_diff_dir(root: Path, project: str) -> Path:
    pattern = root / ".cache" / "build" / project / "*" / "diff"
    candidates = sorted(Path(p) for p in glob.glob(str(pattern)))
    assert candidates
    return candidates[-1]


def test_build_001_single_repo_diff_structure(workspace_a: Path) -> None:
    _ = run_cli(["project_diff", "projA", "--keep-diff-dir"], cwd=workspace_a, check=False)
    diff_dir = _latest_diff_dir(workspace_a, "projA")
    assert (diff_dir / "after").exists()
    assert (diff_dir / "before").exists()
    assert (diff_dir / "patch").exists()
    assert (diff_dir / "commit").exists()


def test_build_002_multi_repo_diff_structure(workspace_b: Path) -> None:
    # introduce changes in repos to populate diff snapshots
    (workspace_b / "repo1" / "a.txt").write_text("r1-mod", encoding="utf-8")
    (workspace_b / "repo2" / "b.txt").write_text("r2-mod", encoding="utf-8")
    _ = run_cli(["project_diff", "projA", "--keep-diff-dir"], cwd=workspace_b, check=False)
    diff_dir = _latest_diff_dir(workspace_b, "projA")
    assert (diff_dir / "after" / "repo1").exists()
    assert (diff_dir / "before" / "repo2").exists()


def test_build_003_no_changes_no_patch(tmp_path: Path) -> None:
    from .conftest import setup_dataset_a

    setup_dataset_a(tmp_path)
    # Clean repo by committing changes
    (tmp_path / "src" / "tmp_file.txt").write_text("line1\nline2", encoding="utf-8")
    os.system(f"cd {tmp_path} && git add src/tmp_file.txt && git commit -m 'clean'")
    _ = run_cli(["project_diff", "projA", "--keep-diff-dir"], cwd=tmp_path, check=False)
    diff_dir = _latest_diff_dir(tmp_path, "projA")
    patch_dir = diff_dir / "patch"
    if patch_dir.exists():
        patch_files = list(patch_dir.glob("**/*.patch"))
        assert not patch_files


def test_build_004_keep_diff_dir(workspace_a: Path) -> None:
    _ = run_cli(["project_diff", "projA", "--keep-diff-dir"], cwd=workspace_a, check=False)
    diff_dir = _latest_diff_dir(workspace_a, "projA")
    assert diff_dir.exists()


def test_build_005_validation_hook_fail(workspace_a: Path) -> None:
    from src.__main__ import _load_all_projects, _load_common_config

    clear_hooks()
    register_hook(HookType.VALIDATION, "fail", lambda ctx: False, priority=HookPriority.HIGH, platform="platA")
    common, _ = _load_common_config(str(workspace_a / "projects"))
    projects_info = _load_all_projects(str(workspace_a / "projects"), common)
    env = {
        "root_path": str(workspace_a),
        "projects_path": str(workspace_a / "projects"),
        "repositories": [{"name": "root", "path": str(workspace_a)}],
    }
    assert project_build(env, projects_info, "projA") is False


def test_build_006_build_hook_fail(workspace_a: Path) -> None:
    from src.__main__ import _load_all_projects, _load_common_config

    clear_hooks()
    register_hook(HookType.PRE_BUILD, "fail", lambda ctx: False, priority=HookPriority.HIGH, platform="platA")
    common, _ = _load_common_config(str(workspace_a / "projects"))
    projects_info = _load_all_projects(str(workspace_a / "projects"), common)
    env = {
        "root_path": str(workspace_a),
        "projects_path": str(workspace_a / "projects"),
        "repositories": [{"name": "root", "path": str(workspace_a)}],
    }
    assert project_build(env, projects_info, "projA") is False


def test_build_007_no_platform_skip_hooks(workspace_a: Path) -> None:
    from src.__main__ import _load_all_projects, _load_common_config

    clear_hooks()
    common, _ = _load_common_config(str(workspace_a / "projects"))
    projects_info = _load_all_projects(str(workspace_a / "projects"), common)
    # Remove platform for projA
    projects_info["projA"]["config"].pop("PROJECT_PLATFORM", None)
    projects_info["projA"]["config"].pop("PROJECT_PO_CONFIG", None)
    env = {
        "root_path": str(workspace_a),
        "projects_path": str(workspace_a / "projects"),
        "repositories": [(str(workspace_a), "root")],
    }
    assert project_build(env, projects_info, "projA") is True


def _set_project_config(root: Path, project: str, updates: dict[str, str]) -> None:
    ini_path = root / "projects" / "boardA" / "boardA.ini"
    lines = ini_path.read_text(encoding="utf-8").splitlines()
    updated: list[str] = []
    in_section = False
    pending = dict(updates)
    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            if in_section and pending:
                for key, value in pending.items():
                    updated.append(f"{key} = {value}")
                pending.clear()
            in_section = line.strip("[]") == project
            updated.append(line)
            continue

        if in_section:
            replaced = False
            for key in list(pending.keys()):
                if line.replace(" ", "").startswith(f"{key}="):
                    updated.append(f"{key} = {pending.pop(key)}")
                    replaced = True
                    break
            if replaced:
                continue

        updated.append(line)

    if in_section and pending:
        for key, value in pending.items():
            updated.append(f"{key} = {value}")

    ini_path.write_text("\n".join(updated) + "\n", encoding="utf-8")


def test_build_008_sync_runs_project_sync_cmd(workspace_a: Path) -> None:
    marker = workspace_a / "sync.marker"
    cmd = "touch sync.marker"
    _set_project_config(workspace_a, "projA", {"PROJECT_SYNC_CMD": cmd})

    result = run_cli(["project_build", "projA", "--sync", "--no-po", "--no-diff"], cwd=workspace_a, check=False)
    assert result.returncode == 0
    assert marker.exists()


def test_build_009_clean_requires_force_and_excludes_projects(workspace_a: Path) -> None:
    junk = workspace_a / "junk.txt"
    junk.write_text("junk", encoding="utf-8")

    applied_record = workspace_a / ".cache" / "po_applied" / "boardA" / "projA" / "po_dummy.json"
    applied_record.parent.mkdir(parents=True, exist_ok=True)
    applied_record.write_text("{}", encoding="utf-8")

    fail_result = run_cli(["project_build", "projA", "--clean", "--no-po", "--no-diff"], cwd=workspace_a, check=False)
    assert fail_result.returncode != 0
    assert junk.exists()

    ok_result = run_cli(
        ["project_build", "projA", "--clean", "--force", "--no-po", "--no-diff"],
        cwd=workspace_a,
        check=False,
    )
    assert ok_result.returncode == 0
    assert not junk.exists()
    assert (workspace_a / "projects").exists()
    assert applied_record.exists()


def test_build_010_profile_dispatch(workspace_a: Path) -> None:
    full_marker = workspace_a / "full.marker"
    single_marker = workspace_a / "single-r1-t1.marker"
    full_cmd = f'{sys.executable} -c "open(\\"full.marker\\", \\"a\\").close()"'
    single_cmd = f'{sys.executable} -c "open(\\"single-{{repo}}-{{target}}.marker\\", \\"a\\").close()"'
    _set_project_config(
        workspace_a,
        "projA",
        {
            "PROJECT_BUILD_FULL_CMD": full_cmd,
            "PROJECT_BUILD_SINGLE_CMD": single_cmd,
        },
    )

    result_full = run_cli(
        ["project_build", "projA", "--profile", "full", "--no-po", "--no-diff"], cwd=workspace_a, check=False
    )
    assert result_full.returncode == 0
    assert full_marker.exists()
    if single_marker.exists():
        single_marker.unlink()

    result_single = run_cli(
        ["project_build", "projA", "--profile", "single", "--repo", "r1", "--target", "t1", "--no-po", "--no-diff"],
        cwd=workspace_a,
        check=False,
    )
    assert result_single.returncode == 0
    assert single_marker.exists()
