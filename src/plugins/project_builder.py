"""Project build utility class for CLI operations."""

from __future__ import annotations

import os
import shutil
import subprocess
import tarfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, Optional, Sequence

from src.hooks import HookType, execute_hooks_with_fallback
from src.log_manager import log
from src.operations.registry import register

# from src.profiler import auto_profile  # unused
from src.plugins.patch_override import po_apply


@dataclass(frozen=True)
class DiffLayout:
    """Path layout for generated diff artefacts."""

    root: Path
    after: Path
    before: Path
    patch: Path
    commit: Path


def _safe_run(cmd: Sequence[str], cwd: Path, *, capture_output: bool = False) -> subprocess.CompletedProcess:
    """Run a git command, raising errors with suppressed stderr noise."""

    return subprocess.run(
        list(cmd),
        cwd=str(cwd),
        stdout=subprocess.PIPE if capture_output else subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
    )


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@register(
    "project_diff",
    needs_repositories=True,
    desc="Generate after, before, patch, commit directories for all repositories or current repo, under a timestamped diff directory.",
)
def project_diff(env: Dict, projects_info: Dict, project_name: str, keep_diff_dir: bool = False) -> bool:
    """Generate snapshots, patches, and commit exports for all repositories."""

    _ = projects_info

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_project_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in str(project_name))

    root_dir = Path.cwd()
    diff_root = root_dir / ".cache" / "build" / safe_project_name / timestamp / "diff"
    log.debug("Diff root directory: %s", diff_root)
    diff_root.mkdir(parents=True, exist_ok=True)

    layout = DiffLayout(
        root=diff_root,
        after=diff_root / "after",
        before=diff_root / "before",
        patch=diff_root / "patch",
        commit=diff_root / "commit",
    )

    repositories = env.get("repositories", [])
    single_repo = len(repositories) == 1

    def is_tracked(repo_path: Path, file_path: str) -> bool:
        try:
            _safe_run(["git", "ls-files", "--error-unmatch", file_path], repo_path)
            return True
        except (OSError, subprocess.SubprocessError):
            return False

    def save_file_snapshot(repo_path: Path, file_path: str, out_dir: Path, ref: Optional[str] = None) -> None:
        abs_file = repo_path / file_path
        out_file = out_dir / file_path
        out_file.parent.mkdir(parents=True, exist_ok=True)
        if ref is None:
            if abs_file.exists():
                if abs_file.is_file():
                    shutil.copy2(abs_file, out_file)
                elif abs_file.is_dir():
                    if out_file.exists():
                        shutil.rmtree(out_file)

                    def ignore_git(_: str, __: Iterable[str]) -> Sequence[str]:
                        return (".git",)

                    shutil.copytree(abs_file, out_file, ignore=ignore_git)
        elif is_tracked(repo_path, file_path):
            try:
                result = _safe_run(["git", "ls-files", "--stage", file_path], repo_path, capture_output=True)
                mode = result.stdout.decode().split()[0]
                if mode == "160000":
                    commit_hash = (
                        subprocess.check_output(
                            ["git", "rev-parse", f"{ref}:{file_path}"],
                            cwd=str(repo_path),
                            stderr=subprocess.DEVNULL,
                        )
                        .decode()
                        .strip()
                    )
                    _write_text(out_file, f"Subproject commit {commit_hash}\n")
                else:
                    with out_file.open("wb") as handle:
                        subprocess.run(
                            ["git", "show", f"{ref}:{file_path}"],
                            cwd=str(repo_path),
                            stdout=handle,
                            stderr=subprocess.DEVNULL,
                            check=True,
                        )
            except subprocess.CalledProcessError:
                pass

    def save_patch(repo_path: Path, file_paths: Sequence[str], out_dir: Path, patch_name: str, staged: bool = False) -> None:
        cmd = ["git", "diff", "--cached"] if staged else ["git", "diff"]
        cmd.extend(file_paths)
        result = _safe_run(cmd, repo_path, capture_output=True)
        patch_content = result.stdout.decode("utf-8")
        if patch_content.strip():
            _write_text(out_dir / patch_name, patch_content)

    def save_commits(repo_path: Path, out_dir: Path) -> None:
        try:
            upstream = subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
                cwd=str(repo_path),
                stderr=subprocess.DEVNULL,
            ).decode().strip()
            commits = subprocess.check_output(
                ["git", "rev-list", f"{upstream}..HEAD"],
                cwd=str(repo_path),
                stderr=subprocess.DEVNULL,
            ).decode().strip().splitlines()
            if not commits:
                return
            out_dir.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                ["git", "format-patch", f"{upstream}..HEAD", "-o", str(out_dir)],
                cwd=str(repo_path),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )
        except (OSError, subprocess.SubprocessError):
            pass

    for directory in (layout.after, layout.before, layout.patch, layout.commit):
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir(parents=True, exist_ok=True)

    for idx, (repo_path, repo_name) in enumerate(repositories):
        print(f"Processing repo {idx + 1}/{len(repositories)}: {repo_name}")
        repo_path_obj = Path(repo_path)
        staged_files = (
            subprocess.check_output(["git", "diff", "--name-only", "--cached"], cwd=repo_path)
            .decode()
            .strip()
            .splitlines()
        )
        working_files = (
            subprocess.check_output(
                ["git", "ls-files", "--modified", "--others", "--exclude-standard"],
                cwd=repo_path,
            )
            .decode()
            .strip()
            .splitlines()
        )
        file_paths = sorted({path for path in staged_files + working_files if path.strip()})

        if single_repo:
            repo_after = layout.after
            repo_before = layout.before
            repo_patch = layout.patch
            repo_commit = layout.commit
        else:
            repo_after = layout.after / repo_name
            repo_before = layout.before / repo_name
            repo_patch = layout.patch / repo_name
            repo_commit = layout.commit / repo_name

        for file_path in file_paths:
            save_file_snapshot(repo_path_obj, file_path, repo_after)
            save_file_snapshot(repo_path_obj, file_path, repo_before, ref="HEAD")

        if file_paths:
            save_patch(repo_path_obj, file_paths, repo_patch, "changes_worktree.patch", staged=False)
            save_patch(repo_path_obj, file_paths, repo_patch, "changes_staged.patch", staged=True)
        save_commits(repo_path_obj, repo_commit)

    try:
        timestamp_dir = diff_root.parent
        archive_name = f"diff_{safe_project_name}_{timestamp}.tar.gz"
        archive_path = timestamp_dir / archive_name
        log.info("Creating tar.gz archive: %s", archive_path)
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(str(diff_root), arcname=diff_root.name)
        log.info("Successfully created tar.gz archive: %s", archive_path)
        if not keep_diff_dir:
            shutil.rmtree(diff_root)
            log.info("Removed original diff directory after archiving")
        else:
            log.info("Keeping original diff directory as per --keep-diff-dir flag")
    except (OSError, tarfile.TarError, RuntimeError) as exc:
        log.error("Failed to create tar.gz archive: %s", exc)

    return True


@register(
    "project_pre_build",
    needs_repositories=False,
    desc="Pre-build stage for the specified project.",
)
def project_pre_build(env: Dict, projects_info: Dict, project_name: str) -> bool:
    """Pre-build stage for the specified project."""

    log.info("Pre-build stage for project: %s", project_name)
    try:
        result = po_apply(env, projects_info, project_name)
        if not result:
            log.error("po_apply failed for project: %s", project_name)
            return False
    except Exception as exc:  # pylint: disable=broad-except
        log.error("Exception during po_apply for %s: %s", project_name, exc)
        return False
    project_diff(env, projects_info, project_name)
    return True


@register(
    "project_do_build",
    needs_repositories=False,
    desc="Build stage for the specified project.",
)
def project_do_build(env: Dict, projects_info: Dict, project_name: str) -> bool:
    """Build stage for the specified project."""

    log.info("Build stage for project: %s", project_name)
    _ = env
    _ = projects_info
    return True


@register(
    "project_post_build",
    needs_repositories=False,
    desc="Post-build stage for the specified project.",
)
def project_post_build(env: Dict, projects_info: Dict, project_name: str) -> bool:
    """Post-build stage for the specified project."""

    log.info("Post-build stage for project: %s", project_name)
    _ = env
    _ = projects_info
    return True


@register(
    "project_build",
    needs_repositories=False,
    desc="Build the specified project, including pre-build, build, and post-build stages.",
)
def project_build(env: Dict, projects_info: Dict, project_name: str) -> bool:
    """Build the specified project and execute relevant hooks."""

    project_info = projects_info.get(project_name, {})
    platform = project_info.get("config", {}).get("PROJECT_PLATFORM")

    def create_context(platform_name: Optional[str] = None) -> Dict:
        return {
            "env": env,
            "projects_info": projects_info,
            "project_name": project_name,
            "platform": platform_name,
            "timestamp": datetime.now().isoformat(),
        }

    def has_platform_hooks(hook_type: HookType, platform_name: str) -> bool:
        from src.hooks.registry import _platform_hooks  # pylint: disable=protected-access

        platform_hooks = _platform_hooks.get(platform_name, {})
        return bool(platform_hooks.get(hook_type.value))

    shared_context = create_context(platform)

    if platform and has_platform_hooks(HookType.VALIDATION, platform):
        validation_result = execute_hooks_with_fallback(HookType.VALIDATION, shared_context, platform)
        if not validation_result:
            log.error("Validation hooks failed, aborting build")
            return False

    if not project_pre_build(env, projects_info, project_name):
        log.error("Pre-build failed for project: %s", project_name)
        return False

    if platform and has_platform_hooks(HookType.PRE_BUILD, platform):
        pre_build_result = execute_hooks_with_fallback(HookType.PRE_BUILD, shared_context, platform)
        if not pre_build_result:
            log.error("Pre-build hooks failed, aborting build")
            return False

    if platform and has_platform_hooks(HookType.BUILD, platform):
        build_result = execute_hooks_with_fallback(HookType.BUILD, shared_context, platform)
        if not build_result:
            log.error("Build hooks failed, aborting build")
            return False

    if not project_do_build(env, projects_info, project_name):
        log.error("Build failed for project: %s", project_name)
        return False

    if platform and has_platform_hooks(HookType.POST_BUILD, platform):
        post_build_result = execute_hooks_with_fallback(HookType.POST_BUILD, shared_context, platform)
        if not post_build_result:
            log.error("Post-build hooks failed, aborting build")
            return False

    if not project_post_build(env, projects_info, project_name):
        log.error("Post-build failed for project: %s", project_name)
        return False

    return True
