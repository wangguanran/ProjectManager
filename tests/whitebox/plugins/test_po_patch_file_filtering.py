"""Behavior tests for PO patch artifact filtering."""

import subprocess
from pathlib import Path

from src.plugins.po_plugins import commits, patches
from src.plugins.po_plugins.runtime import PoPluginContext, PoPluginRuntime


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )


def _context(tmp_path: Path) -> tuple[PoPluginContext, PoPluginRuntime]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    (repo / "base.txt").write_text("base\n", encoding="utf-8")
    _git(repo, "add", "base.txt")
    _git(repo, "commit", "-m", "base")
    po_path = tmp_path / "po"
    commits_dir = po_path / "commits"
    patches_dir = po_path / "patches"
    commits_dir.mkdir(parents=True)
    patches_dir.mkdir()
    runtime = PoPluginRuntime(
        board_name="board",
        project_name="project",
        repositories=[(str(repo), "root")],
        workspace_root=str(tmp_path),
    )
    context = PoPluginContext(
        project_name="project",
        board_name="board",
        po_name="po",
        po_path=str(po_path),
        po_commit_dir=str(commits_dir),
        po_patch_dir=str(patches_dir),
        po_override_dir=str(po_path / "overrides"),
        po_custom_dir=str(po_path / "custom"),
        dry_run=False,
        force=False,
        exclude_files={},
        applied_records={},
    )
    return context, runtime


def test_patch_apply_and_revert_ignore_non_patch_files(tmp_path: Path) -> None:
    context, runtime = _context(tmp_path)
    repo = Path(runtime.repositories[0][0])
    (repo / "base.txt").write_text("changed\n", encoding="utf-8")
    patch_text = _git(repo, "diff", "--", "base.txt").stdout
    patch_dir = Path(context.po_patch_dir)
    (patch_dir / "valid.patch").write_text(patch_text, encoding="utf-8")
    (patch_dir / "README.md").write_text("documentation, not a patch\n", encoding="utf-8")
    (patch_dir / "ignored.PATCH").write_text(patch_text, encoding="utf-8")
    _git(repo, "checkout", "--", "base.txt")

    assert patches._apply_patches(context, runtime) is True
    assert (repo / "base.txt").read_text(encoding="utf-8") == "changed\n"
    record = context.applied_records[str(repo.resolve())]
    assert len(record["commands"]) == 1
    assert record["commands"][0]["cmd"].endswith("valid.patch")
    assert [entry["patch_file"] for entry in record["patches"]] == ["patches/valid.patch"]
    assert patches._list_patches(context.po_path, runtime) == {"patch_files": ["valid.patch"]}

    assert patches._revert_patches(context, runtime) is True
    assert (repo / "base.txt").read_text(encoding="utf-8") == "base\n"


def test_patch_list_only_reports_patch_files(tmp_path: Path) -> None:
    context, runtime = _context(tmp_path)
    nested = Path(context.po_patch_dir) / "platform"
    nested.mkdir()
    (nested / "change.patch").write_text("patch\n", encoding="utf-8")
    (nested / "README.md").write_text("notes\n", encoding="utf-8")
    (nested / "ignored.PATCH").write_text("patch\n", encoding="utf-8")

    assert patches._list_patches(context.po_path, runtime) == {"patch_files": ["platform/change.patch"]}


def test_commit_apply_list_and_revert_ignore_non_patch_files(tmp_path: Path) -> None:
    context, runtime = _context(tmp_path)
    repo = Path(runtime.repositories[0][0])
    base_head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    (repo / "commit.txt").write_text("commit\n", encoding="utf-8")
    _git(repo, "add", "commit.txt")
    _git(repo, "commit", "-m", "local commit")
    patch_text = _git(repo, "format-patch", "-1", "HEAD", "--stdout").stdout
    _git(repo, "reset", "--hard", base_head)
    commit_dir = Path(context.po_commit_dir)
    (commit_dir / "0001-valid.patch").write_text(patch_text, encoding="utf-8")
    (commit_dir / "README.md").write_text("documentation, not a format-patch\n", encoding="utf-8")
    (commit_dir / "0002-ignored.PATCH").write_text(patch_text, encoding="utf-8")

    assert commits._apply_commits(context, runtime) is True
    assert (repo / "commit.txt").read_text(encoding="utf-8") == "commit\n"
    record = context.applied_records[str(repo.resolve())]
    assert len(record["commands"]) == 1
    assert record["commands"][0]["cmd"].endswith("0001-valid.patch")
    assert [entry["patch_file"] for entry in record["commits"]] == ["commits/0001-valid.patch"]
    assert commits._list_commits(context.po_path, runtime) == {"commit_files": ["0001-valid.patch"]}

    runtime.finalize_records(context)
    assert commits._revert_commits(context, runtime) is True
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == base_head
    assert not (repo / "commit.txt").exists()


def test_commit_list_only_reports_patch_files(tmp_path: Path) -> None:
    context, runtime = _context(tmp_path)
    nested = Path(context.po_commit_dir) / "platform"
    nested.mkdir()
    (nested / "0001-change.patch").write_text("patch\n", encoding="utf-8")
    (nested / "README.md").write_text("notes\n", encoding="utf-8")
    (nested / "0002-ignored.PATCH").write_text("patch\n", encoding="utf-8")

    assert commits._list_commits(context.po_path, runtime) == {"commit_files": ["platform/0001-change.patch"]}
