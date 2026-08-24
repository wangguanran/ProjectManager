from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.plugins import patch_override
from src.plugins.po_plugins import commits
from src.plugins.po_plugins.runtime import PoPluginContext, PoPluginRuntime


@pytest.mark.parametrize(
    ("subject", "expected"),
    [
        ("[PATCH] subject", "subject"),
        ("[PATCH 1/2] subject", "subject"),
        ("[PATCH v2] subject", "subject"),
        ("[PATCH v2 1/2] subject", "subject"),
        ("[RFC PATCH] subject", "subject"),
        ("[RFC PATCH v3 2/4] subject", "subject"),
        ("[PATCH RFC v2 1/3] subject", "subject"),
        ("ordinary subject", "ordinary subject"),
    ],
)
def test_strip_format_patch_subject_prefix_variants(subject: str, expected: str) -> None:
    assert commits._strip_format_patch_subject_prefix(subject) == expected


def test_amend_failure_preserves_git_reason_without_absolute_paths(tmp_path, monkeypatch, caplog) -> None:
    repo = tmp_path / "repo"
    patch_file = tmp_path / "po" / "commits" / "001-change.patch"
    git_error = f"fatal: Unable to create '{repo}/.git/index.lock': File exists while applying {patch_file}"
    monkeypatch.setattr(
        commits.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout="", stderr=git_error),
    )

    assert (
        commits._amend_head_commit_message(
            str(repo),
            "normalized subject",
            repo_name="root",
            rel_path="001-change.patch",
            patch_file=str(patch_file),
        )
        is False
    )

    assert "index.lock" in caplog.text
    assert "File exists" in caplog.text
    assert "001-change.patch" in caplog.text
    assert "repo 'root'" in caplog.text
    assert str(tmp_path) not in caplog.text


def test_apply_commits_rolls_back_when_subject_amend_fails(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
    (repo / "base.txt").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "base.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "base"], cwd=repo, check=True)
    base_head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()

    (repo / "added.txt").write_text("added\n", encoding="utf-8")
    subprocess.run(["git", "add", "added.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "added"], cwd=repo, check=True)
    po_path = tmp_path / "po"
    commits_dir = po_path / "commits"
    commits_dir.mkdir(parents=True)
    skipped_patch = subprocess.run(
        ["git", "format-patch", "-1", "HEAD", "--stdout"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    (commits_dir / "001-skipped.patch").write_text(skipped_patch, encoding="utf-8")
    subprocess.run(["git", "reset", "--hard", base_head], cwd=repo, check=True)

    runtime = PoPluginRuntime(
        board_name="board",
        project_name="project",
        repositories=[(str(repo), "root")],
        workspace_root=str(tmp_path),
    )
    ctx = PoPluginContext(
        project_name="project",
        board_name="board",
        po_name="po",
        po_path=str(po_path),
        po_commit_dir=str(commits_dir),
        po_patch_dir=str(po_path / "patches"),
        po_override_dir=str(po_path / "overrides"),
        po_custom_dir=str(po_path / "custom"),
        dry_run=False,
        force=False,
        exclude_files={},
        applied_records={},
    )
    monkeypatch.setattr(commits, "_normalize_head_commit_subject_after_am", lambda _repo, **_kwargs: False)

    assert commits._apply_commits(ctx, runtime) is False
    assert (
        subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
        ).stdout.strip()
        == base_head
    )
    assert not (repo / "added.txt").exists()
    assert not runtime.applied_record_exists(str(repo), "po")


def test_apply_commits_rolls_back_all_patches_when_second_amend_fails(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
    (repo / "base.txt").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "base.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "base"], cwd=repo, check=True)
    base_head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    po_path = tmp_path / "po"
    commits_dir = po_path / "commits"
    commits_dir.mkdir(parents=True)
    for index in (1, 2):
        filename = f"added-{index}.txt"
        (repo / filename).write_text(f"added {index}\n", encoding="utf-8")
        subprocess.run(["git", "add", filename], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", f"added {index}"], cwd=repo, check=True)
        active_patch = subprocess.run(
            ["git", "format-patch", "-1", "HEAD", "--stdout"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        (commits_dir / f"00{index}-active-{index}.patch").write_text(active_patch, encoding="utf-8")
    subprocess.run(["git", "reset", "--hard", base_head], cwd=repo, check=True)
    runtime = PoPluginRuntime(
        board_name="board",
        project_name="project",
        repositories=[(str(repo), "root")],
        workspace_root=str(tmp_path),
    )
    ctx = PoPluginContext(
        project_name="project",
        board_name="board",
        po_name="po",
        po_path=str(po_path),
        po_commit_dir=str(commits_dir),
        po_patch_dir=str(po_path / "patches"),
        po_override_dir=str(po_path / "overrides"),
        po_custom_dir=str(po_path / "custom"),
        dry_run=False,
        force=False,
        exclude_files={},
        applied_records={},
    )
    outcomes = iter([True, False])
    monkeypatch.setattr(
        commits,
        "_normalize_head_commit_subject_after_am",
        lambda _repo, **_kwargs: next(outcomes),
    )

    assert commits._apply_commits(ctx, runtime) is False
    assert (
        subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
        ).stdout.strip()
        == base_head
    )
    assert not (repo / "added-1.txt").exists()
    assert not (repo / "added-2.txt").exists()
    assert not runtime.applied_record_exists(str(repo), "po")


def test_apply_commits_rollback_ignores_skipped_entry_before_active_commits(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
    (repo / "base.txt").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "base.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "base"], cwd=repo, check=True)
    po_path = tmp_path / "po"
    commits_dir = po_path / "commits"
    commits_dir.mkdir(parents=True)

    (repo / "skipped.txt").write_text("already in history\n", encoding="utf-8")
    subprocess.run(["git", "add", "skipped.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "skipped"], cwd=repo, check=True)
    skipped_patch = subprocess.run(
        ["git", "format-patch", "-1", "HEAD", "--stdout"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    (commits_dir / "001-skipped.patch").write_text(skipped_patch, encoding="utf-8")
    start_head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()

    for index in (2, 3):
        filename = f"active-{index}.txt"
        (repo / filename).write_text(f"active {index}\n", encoding="utf-8")
        subprocess.run(["git", "add", filename], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", f"active {index}"], cwd=repo, check=True)
        active_patch = subprocess.run(
            ["git", "format-patch", "-1", "HEAD", "--stdout"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        (commits_dir / f"00{index}-active-{index}.patch").write_text(active_patch, encoding="utf-8")
    subprocess.run(["git", "reset", "--hard", start_head], cwd=repo, check=True)

    runtime = PoPluginRuntime(
        board_name="board",
        project_name="project",
        repositories=[(str(repo), "root")],
        workspace_root=str(tmp_path),
    )
    ctx = PoPluginContext(
        project_name="project",
        board_name="board",
        po_name="po",
        po_path=str(po_path),
        po_commit_dir=str(commits_dir),
        po_patch_dir=str(po_path / "patches"),
        po_override_dir=str(po_path / "overrides"),
        po_custom_dir=str(po_path / "custom"),
        dry_run=False,
        force=False,
        exclude_files={},
        applied_records={},
    )
    outcomes = iter([True, False])
    monkeypatch.setattr(
        commits,
        "_normalize_head_commit_subject_after_am",
        lambda _repo, **_kwargs: next(outcomes),
    )

    assert commits._apply_commits(ctx, runtime) is False
    assert (
        subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
        ).stdout.strip()
        == start_head
    )
    assert (repo / "skipped.txt").exists()
    assert not (repo / "active-2.txt").exists()
    assert not (repo / "active-3.txt").exists()
    assert not runtime.applied_record_exists(str(repo), "po")


def test_po_revert_defers_all_record_cleanup_until_all_commit_plugins_succeed(tmp_path, monkeypatch) -> None:
    projects_path = tmp_path / "projects"
    for po_name in ("po_a", "po_b"):
        (projects_path / "board" / "po" / po_name).mkdir(parents=True)
    repo = tmp_path / "repo"
    repo.mkdir()
    runtime = PoPluginRuntime(
        board_name="board",
        project_name="project",
        repositories=[(str(repo), "root")],
        workspace_root=str(tmp_path),
    )
    for po_name in ("po_a", "po_b"):
        record_path = runtime.applied_record_path(str(repo), po_name)
        Path(record_path).parent.mkdir(parents=True, exist_ok=True)
        Path(record_path).write_text('{"commits": []}\n', encoding="utf-8")

    plugin = SimpleNamespace(
        name="commits",
        revert_phase="global_post",
        revert_order=100,
        revert=lambda ctx, _runtime: ctx.po_name != "po_a",
    )
    monkeypatch.setattr(patch_override, "get_po_plugins", lambda: [plugin])
    env = {"projects_path": str(projects_path), "repositories": [(str(repo), "root")], "po_configs": {}}
    projects_info = {"project": {"board_name": "board", "config": {"PROJECT_PO_CONFIG": "po_a po_b"}}}

    assert patch_override.po_revert(env, projects_info, "project") is False
    assert runtime.applied_record_exists(str(repo), "po_a")
    assert runtime.applied_record_exists(str(repo), "po_b")


def test_po_revert_reports_record_cleanup_failure(tmp_path, monkeypatch) -> None:
    projects_path = tmp_path / "projects"
    (projects_path / "board" / "po" / "po_a").mkdir(parents=True)
    repo = tmp_path / "repo"
    repo.mkdir()
    runtime = PoPluginRuntime(
        board_name="board",
        project_name="project",
        repositories=[(str(repo), "root")],
        workspace_root=str(tmp_path),
    )
    record_path = Path(runtime.applied_record_path(str(repo), "po_a"))
    record_path.parent.mkdir(parents=True)
    record_path.write_text('{"commits": []}\n', encoding="utf-8")
    monkeypatch.setattr(patch_override, "get_po_plugins", lambda: [])
    monkeypatch.setattr(patch_override.os, "remove", lambda _path: (_ for _ in ()).throw(OSError("blocked")))
    env = {"projects_path": str(projects_path), "repositories": [(str(repo), "root")], "po_configs": {}}
    projects_info = {"project": {"board_name": "board", "config": {"PROJECT_PO_CONFIG": "po_a"}}}

    assert patch_override.po_revert(env, projects_info, "project") is False
    assert record_path.exists()
