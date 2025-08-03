"""
Project build utility class for CLI operations.
"""

import os
import shutil
import subprocess
from datetime import datetime

from src.log_manager import log
from src.profiler import auto_profile


@auto_profile
class ProjectBuilder:
    """
    Project build utility class. All methods are static and stateless.
    """

    OPERATION_META = {
        "project_diff": {"needs_repositories": True},
        "project_pre_build": {"needs_repositories": False},
        "project_do_build": {"needs_repositories": False},
        "project_post_build": {"needs_repositories": False},
        "project_build": {"needs_repositories": False},
    }

    def __init__(self):
        raise NotImplementedError(
            "ProjectBuilder is a utility class and cannot be instantiated."
        )

    @staticmethod
    def project_diff(env, projects_info, project_name):
        """
        Generate after, before, patch, commit directories for all repositories or current repo, under a timestamped diff directory.
        Patch files are named changes_worktree.patch and changes_staged.patch.
        If single repo, do not create root subdirectory, put files directly under after, before, etc.
        Diff directory is .cache/build/{project_name}/{timestamp}/diff
        """
        _ = env
        _ = projects_info

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_project_name = "".join(
            c if c.isalnum() or c in ("-", "_") else "_" for c in str(project_name)
        )
        diff_root = os.path.join(".cache", "build", safe_project_name, ts, "diff")
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
                        shutil.copytree(abs_file, out_file)
            else:
                if is_tracked(repo_path, file_path):
                    with open(out_file, "wb") as f:
                        subprocess.run(
                            ["git", "show", f"{ref}:{file_path}"],
                            cwd=repo_path,
                            stdout=f,
                            stderr=subprocess.DEVNULL,
                            check=True,
                        )

        def save_patch(repo_path, file_paths, out_dir, patch_name, staged=False):
            out_file = os.path.join(out_dir, patch_name)
            os.makedirs(os.path.dirname(out_file), exist_ok=True)
            if staged:
                cmd = ["git", "diff", "--cached"] + file_paths
            else:
                cmd = ["git", "diff"] + file_paths
            with open(out_file, "w", encoding="utf-8") as f:
                subprocess.run(
                    cmd, cwd=repo_path, stdout=f, stderr=subprocess.DEVNULL, check=True
                )

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
            staged_files = (
                subprocess.check_output(["git", "diff", "--name-only", "--cached"])
                .decode()
                .strip()
                .splitlines()
            )
            working_files = (
                subprocess.check_output(
                    ["git", "ls-files", "--modified", "--others", "--exclude-standard"]
                )
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
                save_patch(
                    repo_path, file_list, patch_dir, "changes_staged.patch", staged=True
                )
            save_commits(repo_path, commit_dir)
            os.chdir(original_cwd)
        return diff_root

    @staticmethod
    def project_pre_build(env, projects_info, project_name):
        """
        Pre-build stage for the specified project.
        """
        log.info("Pre-build stage for project: %s", project_name)
        print(f"Pre-build stage for project: {project_name}")
        ProjectBuilder.project_diff(env, projects_info, project_name)
        return True

    @staticmethod
    def project_do_build(env, projects_info, project_name):
        """
        Build stage for the specified project.
        """
        log.info("Build stage for project: %s", project_name)
        print(f"Build stage for project: {project_name}")
        # TODO: implement build logic
        _ = env
        _ = projects_info
        return True

    @staticmethod
    def project_post_build(env, projects_info, project_name):
        """
        Post-build stage for the specified project.
        """
        log.info("Post-build stage for project: %s", project_name)
        print(f"Post-build stage for project: {project_name}")
        # TODO: implement post-build logic
        _ = env
        _ = projects_info
        return True

    @staticmethod
    def project_build(env, projects_info, project_name):
        """
        Build the specified project, including pre-build, build, and post-build stages.
        """
        if not ProjectBuilder.project_pre_build(env, projects_info, project_name):
            log.error("Pre-build failed for project: %s", project_name)
            print(f"Pre-build failed for project: {project_name}")
            return False
        if not ProjectBuilder.project_do_build(env, projects_info, project_name):
            log.error("Build failed for project: %s", project_name)
            print(f"Build failed for project: {project_name}")
            return False
        if not ProjectBuilder.project_post_build(env, projects_info, project_name):
            log.error("Post-build failed for project: %s", project_name)
            print(f"Post-build failed for project: {project_name}")
            return False
        log.info("Build succeeded for project: %s", project_name)
        print(f"Build succeeded for project: {project_name}")
        return True
