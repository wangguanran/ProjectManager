"""
Project build utility class for CLI operations.
"""

import os
import shutil
import subprocess
import tarfile
from datetime import datetime
from typing import Dict, Optional

from src.hooks import HookType, execute_hooks_with_fallback
from src.log_manager import log
from src.operations.registry import register

# from src.profiler import auto_profile  # unused
from src.plugins.patch_override import po_apply


@register(
    "project_diff",
    needs_repositories=True,
    desc="Generate after, before, patch, commit directories for all repositories or current repo, under a timestamped diff directory.",
)
def project_diff(env: Dict, projects_info: Dict, project_name: str, keep_diff_dir: bool = False) -> bool:
    """
    Generate after, before, patch, commit directories for all repositories or current repo, under a timestamped diff directory.
    Patch files are named changes_worktree.patch and changes_staged.patch.
    If single repo, do not create root subdirectory, put files directly under after, before, etc.
    Diff directory is .cache/build/{project_name}/{timestamp}/diff

    Args:
        env: Environment variables and configuration
        projects_info: Project information dictionary
        project_name: Name of the project
        keep_diff_dir (bool): If True, preserve the diff directory after creating tar.gz archive (default: False)
    """
    _ = projects_info  # Mark as intentionally unused

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_project_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in str(project_name))

    # Use absolute path to create diff_root in project root directory
    root_dir = os.getcwd()  # Store project root directory
    diff_root = os.path.join(root_dir, ".cache", "build", safe_project_name, ts, "diff")
    log.debug("Diff root directory: %s", diff_root)
    os.makedirs(diff_root, exist_ok=True)

    repositories = env.get("repositories", [])
    single_repo = len(repositories) == 1

    def is_tracked(repo_path, file_path):
        try:
            result = subprocess.run(
                ["git", "ls-files", "--error-unmatch", file_path],
                cwd=repo_path,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )
            return result.returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False

    def save_file_snapshot(repo_path, file_path, out_dir, ref=None):
        abs_file = os.path.join(repo_path, file_path)
        out_file = os.path.join(out_dir, file_path)
        os.makedirs(os.path.dirname(out_file), exist_ok=True)
        if ref is None:
            if os.path.exists(abs_file):
                if os.path.isfile(abs_file):
                    shutil.copy2(abs_file, out_file)
                elif os.path.isdir(abs_file):
                    # For directories, copy the entire directory tree
                    if os.path.exists(out_file):
                        shutil.rmtree(out_file)

                    # Exclude .git directory when copying
                    def ignore_git(directory, files):
                        _ = directory
                        _ = files
                        return [".git"]

                    shutil.copytree(abs_file, out_file, ignore=ignore_git)
        else:
            if is_tracked(repo_path, file_path):
                try:
                    # Check if this is a submodule
                    result = subprocess.run(
                        ["git", "ls-files", "--stage", file_path],
                        cwd=repo_path,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                        check=True,
                    )
                    mode = result.stdout.decode().split()[0]

                    if mode == "160000":  # This is a submodule
                        # For submodules, create a file with the commit hash
                        commit_hash = (
                            subprocess.check_output(
                                ["git", "rev-parse", f"{ref}:{file_path}"],
                                cwd=repo_path,
                                stderr=subprocess.DEVNULL,
                            )
                            .decode()
                            .strip()
                        )
                        with open(out_file, "w", encoding="utf-8") as f:
                            f.write(f"Subproject commit {commit_hash}\n")
                    else:
                        # Regular file
                        with open(out_file, "wb") as f:
                            subprocess.run(
                                ["git", "show", f"{ref}:{file_path}"],
                                cwd=repo_path,
                                stdout=f,
                                stderr=subprocess.DEVNULL,
                                check=True,
                            )
                except subprocess.CalledProcessError:
                    # File doesn't exist in the specified ref, skip it
                    pass

    def save_patch(repo_path, file_paths, out_dir, patch_name, staged=False):
        if staged:
            cmd = ["git", "diff", "--cached"] + file_paths
        else:
            cmd = ["git", "diff"] + file_paths

        # Get diff content first
        result = subprocess.run(
            cmd,
            cwd=repo_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        patch_content = result.stdout.decode("utf-8")

        # Only create file if patch content is not empty
        if patch_content.strip():
            out_file = os.path.join(out_dir, patch_name)
            os.makedirs(os.path.dirname(out_file), exist_ok=True)
            with open(out_file, "w", encoding="utf-8") as f:
                f.write(patch_content)

    def save_commits(repo_path, out_dir):
        try:
            upstream = (
                subprocess.check_output(
                    [
                        "git",
                        "rev-parse",
                        "--abbrev-ref",
                        "--symbolic-full-name",
                        "@{u}",
                    ],
                    cwd=repo_path,
                    stderr=subprocess.DEVNULL,
                )
                .decode()
                .strip()
            )
            commits = (
                subprocess.check_output(
                    ["git", "rev-list", f"{upstream}..HEAD"],
                    cwd=repo_path,
                    stderr=subprocess.DEVNULL,
                )
                .decode()
                .strip()
                .splitlines()
            )
            if not commits:
                return
            os.makedirs(out_dir, exist_ok=True)
            subprocess.run(
                ["git", "format-patch", f"{upstream}..HEAD", "-o", out_dir],
                cwd=repo_path,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )
        except (OSError, subprocess.SubprocessError):
            pass

    for d in ["after", "before", "patch", "commit"]:
        dpath = os.path.join(diff_root, d)
        if os.path.exists(dpath):
            shutil.rmtree(dpath)
        os.makedirs(dpath, exist_ok=True)

    for idx, (repo_path, repo_name) in enumerate(repositories):
        print(f"Processing repo {idx + 1}/{len(repositories)}: {repo_name}")
        original_cwd = os.getcwd()
        os.chdir(repo_path)
        staged_files = subprocess.check_output(["git", "diff", "--name-only", "--cached"]).decode().strip().splitlines()
        working_files = (
            subprocess.check_output(["git", "ls-files", "--modified", "--others", "--exclude-standard"])
            .decode()
            .strip()
            .splitlines()
        )
        all_files = set(staged_files) | set(working_files)
        file_list = [f for f in all_files if f.strip()]
        # Target directory: single repo put files directly under diff_root/after, etc.; multi-repo use repo_name subdirectory
        if single_repo:
            after_dir = os.path.join(diff_root, "after")
            before_dir = os.path.join(diff_root, "before")
            patch_dir = os.path.join(diff_root, "patch")
            commit_dir = os.path.join(diff_root, "commit")
        else:
            after_dir = os.path.join(diff_root, "after", repo_name)
            before_dir = os.path.join(diff_root, "before", repo_name)
            patch_dir = os.path.join(diff_root, "patch", repo_name)
            commit_dir = os.path.join(diff_root, "commit", repo_name)
        for file_path in file_list:
            save_file_snapshot(repo_path, file_path, after_dir)
            save_file_snapshot(repo_path, file_path, before_dir, ref="HEAD")
        if file_list:
            save_patch(
                repo_path,
                file_list,
                patch_dir,
                "changes_worktree.patch",
                staged=False,
            )
            save_patch(repo_path, file_list, patch_dir, "changes_staged.patch", staged=True)
        save_commits(repo_path, commit_dir)
        os.chdir(original_cwd)

    # Create tar.gz archive of the diff directory
    try:
        # Get the parent directory of diff_root (the timestamp directory)
        timestamp_dir = os.path.dirname(diff_root)
        archive_name = f"diff_{safe_project_name}_{ts}.tar.gz"
        archive_path = os.path.join(timestamp_dir, archive_name)

        log.info("Creating tar.gz archive: %s", archive_path)

        with tarfile.open(archive_path, "w:gz") as tar:
            # Add the diff directory to the archive
            tar.add(diff_root, arcname=os.path.basename(diff_root))

        log.info("Successfully created tar.gz archive: %s", archive_path)

        # Check keep_diff_dir parameter to determine whether to delete the diff directory
        # Default behavior: delete the diff directory after archiving
        # Use --keep-diff-dir flag to preserve the diff directory

        if not keep_diff_dir:
            # Remove the original diff directory after archiving (default behavior)
            shutil.rmtree(diff_root)
            log.info("Removed original diff directory after archiving")
        else:
            log.info("Keeping original diff directory as per --keep-diff-dir flag")

    except (OSError, tarfile.TarError, RuntimeError) as e:
        log.error("Failed to create tar.gz archive: %s", e)
        # Continue execution even if archiving fails

    return True


@register(
    "project_pre_build",
    needs_repositories=False,
    desc="Pre-build stage for the specified project.",
)
def project_pre_build(env: Dict, projects_info: Dict, project_name: str) -> bool:
    """
    Pre-build stage for the specified project.
    """
    log.info("Pre-build stage for project: %s", project_name)
    project_diff(env, projects_info, project_name)
    # Apply patch/override; failures are fatal
    try:
        result = po_apply(env, projects_info, project_name)
        if not result:
            log.error("po_apply failed for project: %s", project_name)
            return False
    except Exception as exc:  # pylint: disable=broad-except
        log.error("Exception during po_apply for %s: %s", project_name, exc)
        return False
    return True


@register(
    "project_do_build",
    needs_repositories=False,
    desc="Build stage for the specified project.",
)
def project_do_build(env: Dict, projects_info: Dict, project_name: str) -> bool:
    """
    Build stage for the specified project.
    """
    log.info("Build stage for project: %s", project_name)
    # TODO: implement build logic
    _ = env
    _ = projects_info
    return True


@register(
    "project_post_build",
    needs_repositories=False,
    desc="Post-build stage for the specified project.",
)
def project_post_build(env: Dict, projects_info: Dict, project_name: str) -> bool:
    """
    Post-build stage for the specified project.
    """
    log.info("Post-build stage for project: %s", project_name)
    # TODO: implement post-build logic
    _ = env
    _ = projects_info
    return True


@register(
    "project_build",
    needs_repositories=False,
    desc="Build the specified project, including pre-build, build, and post-build stages.",
)
def project_build(env: Dict, projects_info: Dict, project_name: str) -> bool:
    """
    Build the specified project, including pre-build, build, and post-build stages.

    Args:
        env: Environment variables and configuration
        projects_info: Project information dictionary
        project_name: Name of the project to build
    """
    # Get platform from project_info
    project_info = projects_info.get(project_name, {})
    platform = project_info.get("config", {}).get("PROJECT_PLATFORM")

    def create_context(env: Dict, projects_info: Dict, project_name: str, platform: Optional[str] = None) -> Dict:
        """Create context dictionary for hooks."""
        return {
            "env": env,
            "projects_info": projects_info,
            "project_name": project_name,
            "platform": platform,
            "timestamp": datetime.now().isoformat(),
        }

    def has_platform_hooks(hook_type: HookType, platform: str) -> bool:
        """Check if there are any hooks registered for the specified platform and hook type."""
        from src.hooks.registry import _platform_hooks

        return platform in _platform_hooks and hook_type.value in _platform_hooks[platform]

    # Create a single shared context for the entire build process
    shared_context = create_context(env, projects_info, project_name, platform)

    # Execute validation hooks if platform is specified and has hooks
    if platform and has_platform_hooks(HookType.VALIDATION, platform):
        validation_result = execute_hooks_with_fallback(HookType.VALIDATION, shared_context, platform)
        if not validation_result:
            log.error("Validation hooks failed, aborting build")
            return False

    # Execute pre-build hooks if platform is specified and has hooks
    if platform and has_platform_hooks(HookType.PRE_BUILD, platform):
        pre_build_result = execute_hooks_with_fallback(HookType.PRE_BUILD, shared_context, platform)
        if not pre_build_result:
            log.error("Pre-build hooks failed, aborting build")
            return False

    # Execute pre-build stage
    if not project_pre_build(env, projects_info, project_name):
        log.error("Pre-build failed for project: %s", project_name)
        return False

    # Execute build hooks if platform is specified and has hooks
    if platform and has_platform_hooks(HookType.BUILD, platform):
        build_result = execute_hooks_with_fallback(HookType.BUILD, shared_context, platform)
        if not build_result:
            log.error("Build hooks failed, aborting build")
            return False

    # Execute build stage
    if not project_do_build(env, projects_info, project_name):
        log.error("Build failed for project: %s", project_name)
        return False

    # Execute post-build hooks if platform is specified and has hooks
    if platform and has_platform_hooks(HookType.POST_BUILD, platform):
        post_build_result = execute_hooks_with_fallback(HookType.POST_BUILD, shared_context, platform)
        if not post_build_result:
            log.error("Post-build hooks failed, aborting build")
            return False

    # Execute post-build stage
    if not project_post_build(env, projects_info, project_name):
        log.error("Post-build failed for project: %s", project_name)
        return False

    log.info("Build succeeded for project: %s", project_name)
    return True
