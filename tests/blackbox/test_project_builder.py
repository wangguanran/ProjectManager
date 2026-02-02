"""Blackbox tests for project diff/build."""

from __future__ import annotations

import glob
import os
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
    env = {"root_path": str(workspace_a), "projects_path": str(workspace_a / "projects"), "repositories": [{"name": "root", "path": str(workspace_a)}]}
    assert project_build(env, projects_info, "projA") is False


def test_build_006_build_hook_fail(workspace_a: Path) -> None:
    from src.__main__ import _load_all_projects, _load_common_config

    clear_hooks()
    register_hook(HookType.PRE_BUILD, "fail", lambda ctx: False, priority=HookPriority.HIGH, platform="platA")
    common, _ = _load_common_config(str(workspace_a / "projects"))
    projects_info = _load_all_projects(str(workspace_a / "projects"), common)
    env = {"root_path": str(workspace_a), "projects_path": str(workspace_a / "projects"), "repositories": [{"name": "root", "path": str(workspace_a)}]}
    assert project_build(env, projects_info, "projA") is False


def test_build_007_no_platform_skip_hooks(workspace_a: Path) -> None:
    from src.__main__ import _load_all_projects, _load_common_config

    clear_hooks()
    common, _ = _load_common_config(str(workspace_a / "projects"))
    projects_info = _load_all_projects(str(workspace_a / "projects"), common)
    # Remove platform for projA
    projects_info["projA"]["config"].pop("PROJECT_PLATFORM", None)
    projects_info["projA"]["config"].pop("PROJECT_PO_CONFIG", None)
    env = {"root_path": str(workspace_a), "projects_path": str(workspace_a / "projects"), "repositories": [(str(workspace_a), "root")]}
    assert project_build(env, projects_info, "projA") is True
