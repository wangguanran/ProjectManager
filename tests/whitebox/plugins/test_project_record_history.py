"""Behavior tests for project_record_history."""

import json
import os
import subprocess
from pathlib import Path

import pytest

from src.plugins import project_builder


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )


def _init_repo(repo: Path) -> None:
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    (repo / "base.txt").write_text("base\n", encoding="utf-8")
    _git(repo, "add", "base.txt")
    _git(repo, "commit", "-m", "base")


def _history_root(root: Path, timestamp: str) -> Path:
    return root / ".cache" / "build" / "demo" / timestamp / "history"


def _summary(root: Path, timestamp: str) -> dict:
    return json.loads((_history_root(root, timestamp) / "summary.json").read_text(encoding="utf-8"))


def test_record_history_without_upstream_uses_head_as_synced_history(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    env = {"repositories": [(str(repo), "root")], "root_path": str(tmp_path)}

    assert project_builder.project_record_history(env, {}, "demo", timestamp="no-upstream", keep_dir=True)

    history = _history_root(tmp_path, "no-upstream")
    summary = json.loads((history / "summary.json").read_text(encoding="utf-8"))
    record = summary["repositories"][0]
    assert record["status"] == "ok"
    assert record["upstream"] == ""
    assert record["synced_commit_count"] == 1
    assert record["local_commit_count"] == 0
    assert "no upstream configured" in (history / "repos" / "root" / "local_commits.txt").read_text(encoding="utf-8")


def test_record_history_archives_local_commits_and_roots_relative_artifact_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bare = tmp_path / "remote.git"
    _git(tmp_path, "init", "--bare", str(bare))
    repo = tmp_path / "repo"
    _init_repo(repo)
    _git(repo, "branch", "-M", "main")
    _git(repo, "remote", "add", "origin", str(bare))
    _git(repo, "push", "-u", "origin", "main")
    (repo / "local.txt").write_text("local\n", encoding="utf-8")
    _git(repo, "add", "local.txt")
    _git(repo, "commit", "-m", "local")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    env = {"repositories": [(str(repo), "platform/repo")], "root_path": str(tmp_path)}

    assert project_builder.project_record_history(
        env,
        {},
        "demo",
        timestamp="local",
        artifact_dir="artifacts",
        keep_dir=True,
    )

    archive = tmp_path / "artifacts" / "repo-history_demo_local.tar.gz"
    assert archive.is_file()
    history = _history_root(tmp_path, "local")
    record = json.loads((history / "summary.json").read_text(encoding="utf-8"))["repositories"][0]
    assert record["local_commit_count"] == 1
    assert record["local_patch_count"] == 1
    assert len(list((history / "repos" / "platform" / "repo" / "local_patches").glob("*.patch"))) == 1


def test_record_history_marks_format_patch_failure_as_partial(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bare = tmp_path / "remote.git"
    _git(tmp_path, "init", "--bare", str(bare))
    repo = tmp_path / "repo"
    _init_repo(repo)
    _git(repo, "branch", "-M", "main")
    _git(repo, "remote", "add", "origin", str(bare))
    _git(repo, "push", "-u", "origin", "main")
    (repo / "local.txt").write_text("local\n", encoding="utf-8")
    _git(repo, "add", "local.txt")
    _git(repo, "commit", "-m", "local")
    real_run = subprocess.run

    def fail_format_patch(*args, **kwargs):
        command = args[0]
        if command[:2] == ["git", "format-patch"]:
            return subprocess.CompletedProcess(command, 1, stdout="", stderr="synthetic failure")
        return real_run(*args, **kwargs)

    monkeypatch.setattr(project_builder.subprocess, "run", fail_format_patch)
    env = {"repositories": [(str(repo), "root")], "root_path": str(tmp_path)}

    assert project_builder.project_record_history(env, {}, "demo", timestamp="partial", keep_dir=True)

    history = _history_root(tmp_path, "partial")
    summary = json.loads((history / "summary.json").read_text(encoding="utf-8"))
    record = summary["repositories"][0]
    assert record["status"] == "partial"
    assert record["local_commit_count"] == 1
    assert record["local_patch_count"] == 0
    assert "synthetic failure" in record["error"]
    assert summary["partial_repository_count"] == 1


@pytest.mark.parametrize("artifact_dir", ["../outside", "nested/../../outside"])
def test_record_history_rejects_relative_artifact_escape(tmp_path: Path, artifact_dir: str) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    env = {"repositories": [(str(repo), "root")], "root_path": str(tmp_path)}

    assert not project_builder.project_record_history(
        env, {}, "demo", timestamp="artifact-escape", artifact_dir=artifact_dir
    )

    assert not (tmp_path / ".cache").exists()


def test_record_history_rejects_relative_artifact_symlink_escape(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    (tmp_path / "artifacts").symlink_to(outside, target_is_directory=True)
    env = {"repositories": [(str(repo), "root")], "root_path": str(tmp_path)}

    assert not project_builder.project_record_history(
        env, {}, "demo", timestamp="artifact-symlink", artifact_dir="artifacts"
    )

    assert not (tmp_path / ".cache").exists()
    assert list(outside.iterdir()) == []


def test_record_history_does_not_overwrite_existing_artifact(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    artifact = artifact_dir / "repo-history_demo_existing-artifact.tar.gz"
    artifact.write_text("preserve\n", encoding="utf-8")
    env = {"repositories": [(str(repo), "root")], "root_path": str(tmp_path)}

    assert not project_builder.project_record_history(
        env,
        {},
        "demo",
        timestamp="existing-artifact",
        artifact_dir="artifacts",
    )

    assert artifact.read_text(encoding="utf-8") == "preserve\n"


@pytest.mark.parametrize("existing_kind", ["directory", "symlink"])
def test_record_history_rejects_existing_timestamp_without_mixing_output(tmp_path: Path, existing_kind: str) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    timestamp_dir = tmp_path / ".cache" / "build" / "demo" / "reused"
    timestamp_dir.parent.mkdir(parents=True)
    if existing_kind == "directory":
        timestamp_dir.mkdir()
        sentinel = timestamp_dir / "sentinel.txt"
    else:
        outside = tmp_path / "outside-timestamp"
        outside.mkdir()
        timestamp_dir.symlink_to(outside, target_is_directory=True)
        sentinel = outside / "sentinel.txt"
    sentinel.write_text("preserve\n", encoding="utf-8")
    env = {"repositories": [(str(repo), "root")], "root_path": str(tmp_path)}

    assert not project_builder.project_record_history(env, {}, "demo", timestamp="reused")

    assert sentinel.read_text(encoding="utf-8") == "preserve\n"
    assert sorted(path.name for path in sentinel.parent.iterdir()) == ["sentinel.txt"]


def test_record_history_marks_upstream_query_failure_as_partial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    real_git_result = project_builder._git_result

    def fail_upstream_query(repo_path, args):
        if args and args[0] == "for-each-ref":
            return subprocess.CompletedProcess(["git", *args], 2, stdout="", stderr="synthetic upstream query failure")
        return real_git_result(repo_path, args)

    monkeypatch.setattr(project_builder, "_git_result", fail_upstream_query)
    env = {"repositories": [(str(repo), "root")], "root_path": str(tmp_path)}

    assert project_builder.project_record_history(env, {}, "demo", timestamp="upstream-failure", keep_dir=True)

    record = _summary(tmp_path, "upstream-failure")["repositories"][0]
    assert record["status"] == "partial"
    assert record["upstream"] == ""
    assert "synthetic upstream query failure" in record["error"]


def test_record_history_parent_symlink_swap_cannot_redirect_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    outside = tmp_path / "outside"
    outside.mkdir()
    real_open_dir = getattr(project_builder, "_open_or_create_dir_at", None)
    assert real_open_dir is not None
    swapped = False

    def swap_cache_after_open(parent_fd, name, **kwargs):
        nonlocal swapped
        result = real_open_dir(parent_fd, name, **kwargs)
        if name == ".cache" and not swapped:
            (tmp_path / ".cache").rename(tmp_path / ".cache-held")
            (tmp_path / ".cache").symlink_to(outside, target_is_directory=True)
            swapped = True
        return result

    monkeypatch.setattr(project_builder, "_open_or_create_dir_at", swap_cache_after_open)
    env = {"repositories": [(str(repo), "root")], "root_path": str(tmp_path)}

    assert not project_builder.project_record_history(env, {}, "demo", timestamp="swap")

    assert list(outside.iterdir()) == []
    assert not (tmp_path / ".cache-held" / "build" / "demo" / "swap").exists()


def test_record_history_post_publish_parent_swap_rolls_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    outside = tmp_path / "outside"
    outside.mkdir()
    real_verify = project_builder._verify_directory_chain
    verify_calls = 0

    def swap_after_publish(root_fd, identities):
        nonlocal verify_calls
        verify_calls += 1
        if verify_calls == 2:
            (tmp_path / ".cache").rename(tmp_path / ".cache-held")
            (tmp_path / ".cache").symlink_to(outside, target_is_directory=True)
        return real_verify(root_fd, identities)

    monkeypatch.setattr(project_builder, "_verify_directory_chain", swap_after_publish)
    env = {"repositories": [(str(repo), "root")], "root_path": str(tmp_path)}

    assert not project_builder.project_record_history(env, {}, "demo", timestamp="post-swap")
    assert list(outside.iterdir()) == []
    assert not (tmp_path / ".cache-held" / "build" / "demo" / "post-swap").exists()


def test_record_history_cleanup_does_not_remove_replacement_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    parent = tmp_path / ".cache" / "build" / "demo"

    def replace_stage_then_fail(*_args, **_kwargs):
        stage = next(path for path in parent.iterdir() if path.name.startswith(".replace-stage.tmp-"))
        stage.rename(parent / ".held-stage")
        stage.mkdir()
        (stage / "replacement-sentinel").write_text("keep", encoding="utf-8")
        raise project_builder.tarfile.TarError("synthetic staging failure")

    monkeypatch.setattr(project_builder, "_build_history_stage", replace_stage_then_fail)
    env = {"repositories": [(str(repo), "root")], "root_path": str(tmp_path)}

    assert not project_builder.project_record_history(env, {}, "demo", timestamp="replace-stage")
    replacement = next(path for path in parent.iterdir() if path.name.startswith(".replace-stage.tmp-"))
    assert (replacement / "replacement-sentinel").read_text(encoding="utf-8") == "keep"


def test_record_history_copy_cleanup_does_not_unlink_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    artifact_parent = tmp_path / "artifacts"

    def replace_copy_then_fail(_source, _destination):
        staged = next(path for path in artifact_parent.iterdir() if ".tmp-" in path.name)
        staged.rename(artifact_parent / ".held-copy")
        staged.write_text("replacement", encoding="utf-8")
        raise OSError("synthetic copy replacement")

    monkeypatch.setattr(project_builder.shutil, "copyfileobj", replace_copy_then_fail)
    env = {"repositories": [(str(repo), "root")], "root_path": str(tmp_path)}

    assert not project_builder.project_record_history(env, {}, "demo", timestamp="copy-swap", artifact_dir="artifacts")
    replacement = next(path for path in artifact_parent.iterdir() if ".tmp-" in path.name)
    assert replacement.read_text(encoding="utf-8") == "replacement"


def test_record_history_tar_failure_cleans_staging_and_allows_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    env = {"repositories": [(str(repo), "root")], "root_path": str(tmp_path)}
    real_tar_open = project_builder.tarfile.open

    def fail_tar(*_args, **_kwargs):
        raise project_builder.tarfile.TarError("synthetic tar failure")

    monkeypatch.setattr(project_builder.tarfile, "open", fail_tar)
    assert not project_builder.project_record_history(env, {}, "demo", timestamp="tar-retry")
    assert not (tmp_path / ".cache" / "build" / "demo" / "tar-retry").exists()

    monkeypatch.setattr(project_builder.tarfile, "open", real_tar_open)
    assert project_builder.project_record_history(env, {}, "demo", timestamp="tar-retry")


def test_record_history_successful_copy_inode_swap_is_not_published_or_followed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    artifact_parent = tmp_path / "artifacts"
    target = tmp_path / "metadata-target"
    target.write_text("unchanged", encoding="utf-8")
    target.chmod(0o600)
    os.utime(target, ns=(1_000_000_000, 1_000_000_000))
    original_stat = target.stat()
    real_copyfileobj = project_builder.shutil.copyfileobj

    def swap_after_successful_copy(source_handle, destination_handle):
        real_copyfileobj(source_handle, destination_handle)
        staged = next(path for path in artifact_parent.iterdir() if ".tmp-" in path.name)
        staged.rename(artifact_parent / ".held-original-copy")
        staged.symlink_to(target)

    monkeypatch.setattr(project_builder.shutil, "copyfileobj", swap_after_successful_copy)
    env = {"repositories": [(str(repo), "root")], "root_path": str(tmp_path)}

    assert not project_builder.project_record_history(
        env, {}, "demo", timestamp="copy-success-swap", artifact_dir="artifacts"
    )
    assert not (artifact_parent / "repo-history_demo_copy-success-swap.tar.gz").exists()
    assert target.read_text(encoding="utf-8") == "unchanged"
    final_stat = target.stat()
    assert final_stat.st_mode == original_stat.st_mode
    assert final_stat.st_mtime_ns == original_stat.st_mtime_ns


def test_record_history_artifact_staging_failure_cleans_and_allows_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    env = {"repositories": [(str(repo), "root")], "root_path": str(tmp_path)}
    real_copy = project_builder._copy_file_exclusive

    def fail_copy(_source, _destination):
        raise OSError("synthetic artifact staging failure")

    monkeypatch.setattr(project_builder, "_copy_file_exclusive", fail_copy)
    assert not project_builder.project_record_history(
        env, {}, "demo", timestamp="artifact-retry", artifact_dir="artifacts"
    )
    assert not (tmp_path / ".cache" / "build" / "demo" / "artifact-retry").exists()
    assert list((tmp_path / "artifacts").glob("repo-history_demo_artifact-retry.tar.gz")) == []

    monkeypatch.setattr(project_builder, "_copy_file_exclusive", real_copy)
    assert project_builder.project_record_history(env, {}, "demo", timestamp="artifact-retry", artifact_dir="artifacts")


def test_record_history_artifact_publish_failure_cleans_and_allows_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    env = {"repositories": [(str(repo), "root")], "root_path": str(tmp_path)}
    real_rename = project_builder._rename_noreplace

    def fail_artifact_publish(source_fd, source, destination_fd, destination):
        if destination.endswith(".tar.gz"):
            raise OSError("synthetic artifact publish failure")
        return real_rename(source_fd, source, destination_fd, destination)

    monkeypatch.setattr(project_builder, "_rename_noreplace", fail_artifact_publish)
    assert not project_builder.project_record_history(
        env, {}, "demo", timestamp="publish-retry", artifact_dir="artifacts"
    )
    assert not (tmp_path / ".cache" / "build" / "demo" / "publish-retry").exists()
    assert list((tmp_path / "artifacts").iterdir()) == []

    monkeypatch.setattr(project_builder, "_rename_noreplace", real_rename)
    assert project_builder.project_record_history(env, {}, "demo", timestamp="publish-retry", artifact_dir="artifacts")


@pytest.mark.parametrize(
    "error",
    [
        FileNotFoundError("git missing"),
        OSError("cwd vanished"),
        project_builder.subprocess.SubprocessError("spawn failed"),
    ],
)
def test_record_history_git_spawn_failure_is_partial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    real_run = project_builder.subprocess.run

    def fail_head(*args, **kwargs):
        if args[0][:3] == ["git", "rev-parse", "HEAD"]:
            raise error
        return real_run(*args, **kwargs)

    monkeypatch.setattr(project_builder.subprocess, "run", fail_head)
    env = {"repositories": [(str(repo), "root")], "root_path": str(tmp_path)}

    assert project_builder.project_record_history(env, {}, "demo", timestamp="git-spawn", keep_dir=True)

    record = _summary(tmp_path, "git-spawn")["repositories"][0]
    assert record["status"] == "partial"
    assert type(error).__name__ in record["error"]
    assert str(error) in record["error"]


def test_record_history_unsupported_atomic_platform_has_no_side_effects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    monkeypatch.setattr(project_builder, "_history_capabilities_available", lambda: False)
    env = {"repositories": [(str(repo), "root")], "root_path": str(tmp_path)}

    assert not project_builder.project_record_history(env, {}, "demo", timestamp="unsupported")
    assert not (tmp_path / ".cache").exists()


def test_record_history_rejects_absolute_artifact_directory_without_writes(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    absolute_artifact = tmp_path / "absolute-artifacts"
    env = {"repositories": [(str(repo), "root")], "root_path": str(tmp_path)}

    assert not project_builder.project_record_history(
        env, {}, "demo", timestamp="absolute", artifact_dir=str(absolute_artifact)
    )
    assert not absolute_artifact.exists()
    assert not (tmp_path / ".cache").exists()


@pytest.mark.parametrize(
    "repositories",
    [
        [("/unused/a", "../escape")],
        [("/unused/a", "repo"), ("/unused/b", "repo")],
        [("/unused/a", "Foo"), ("/unused/b", "foo")],
        [("/unused/a", "platform"), ("/unused/b", "platform/repo")],
        [("/unused/a", "platform/meta.json")],
        [("/unused/a", "local_patches")],
    ],
)
def test_record_history_rejects_unsafe_or_duplicate_repository_names(
    tmp_path: Path, repositories: list[tuple[str, str]]
) -> None:
    env = {"repositories": repositories, "root_path": str(tmp_path)}

    assert not project_builder.project_record_history(env, {}, "demo", timestamp="invalid", keep_dir=True)

    assert not (tmp_path / ".cache").exists()
