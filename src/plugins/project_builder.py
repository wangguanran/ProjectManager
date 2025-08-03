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
        log.debug("Starting project_diff for project: %s", project_name)
        _ = env
        _ = projects_info

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        log.debug("Generated timestamp: %s", ts)

        safe_project_name = "".join(
            c if c.isalnum() or c in ("-", "_") else "_" for c in str(project_name)
        )
        log.debug("Safe project name: %s", safe_project_name)

        diff_root = os.path.join(".cache", "build", safe_project_name, ts, "diff")
        log.debug("Diff root directory: %s", diff_root)
        os.makedirs(diff_root, exist_ok=True)
        log.debug("Created diff root directory")

        repositories = env.get("repositories", [])
        log.debug(
            "Found %d repositories: %s",
            len(repositories),
            [repo[1] for repo in repositories],
        )
        single_repo = len(repositories) == 1
        log.debug("Single repo mode: %s", single_repo)

        def is_tracked(repo_path, file_path):
            log.debug(
                "Checking if file is tracked: %s in repo: %s", file_path, repo_path
            )
            try:
                result = subprocess.run(
                    ["git", "ls-files", "--error-unmatch", file_path],
                    cwd=repo_path,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=True,
                )
                is_tracked_result = result.returncode == 0
                log.debug("File %s tracked status: %s", file_path, is_tracked_result)
                return is_tracked_result
            except (OSError, subprocess.SubprocessError) as e:
                log.debug("Error checking if file %s is tracked: %s", file_path, e)
                return False

        def save_file_snapshot(repo_path, file_path, out_dir, ref=None):
            log.debug(
                "Saving file snapshot: %s, ref: %s, out_dir: %s",
                file_path,
                ref,
                out_dir,
            )
            abs_file = os.path.join(repo_path, file_path)
            out_file = os.path.join(out_dir, file_path)
            log.debug("Absolute file path: %s, output file: %s", abs_file, out_file)

            os.makedirs(os.path.dirname(out_file), exist_ok=True)
            log.debug("Created output directory: %s", os.path.dirname(out_file))

            if ref is None:
                log.debug(
                    "Saving current working directory snapshot for: %s", file_path
                )
                if os.path.exists(abs_file):
                    if os.path.isfile(abs_file):
                        log.debug("Copying file: %s", file_path)
                        shutil.copy2(abs_file, out_file)
                        log.debug("Successfully copied file: %s", file_path)
                    elif os.path.isdir(abs_file):
                        log.debug("Copying directory: %s", file_path)
                        # For directories, copy the entire directory tree
                        if os.path.exists(out_file):
                            shutil.rmtree(out_file)
                            log.debug("Removed existing directory: %s", out_file)

                        # Exclude .git directory when copying
                        def ignore_git(directory, files):
                            _ = directory
                            _ = files
                            return [".git"]

                        shutil.copytree(abs_file, out_file, ignore=ignore_git)
                        log.debug("Successfully copied directory: %s", file_path)
                else:
                    log.debug("File does not exist: %s", abs_file)
            else:
                log.debug("Saving reference snapshot for: %s (ref: %s)", file_path, ref)
                if is_tracked(repo_path, file_path):
                    try:
                        # Check if this is a submodule
                        log.debug("Checking if file is submodule: %s", file_path)
                        result = subprocess.run(
                            ["git", "ls-files", "--stage", file_path],
                            cwd=repo_path,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL,
                            check=True,
                        )
                        mode = result.stdout.decode().split()[0]
                        log.debug("File mode: %s for %s", mode, file_path)

                        if mode == "160000":  # This is a submodule
                            log.debug("File is submodule: %s", file_path)
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
                            log.debug(
                                "Submodule commit hash: %s for %s",
                                commit_hash,
                                file_path,
                            )
                            with open(out_file, "w", encoding="utf-8") as f:
                                f.write(f"Subproject commit {commit_hash}\n")
                            log.debug("Created submodule reference file: %s", out_file)
                        else:
                            log.debug("File is regular file: %s", file_path)
                            # Regular file
                            with open(out_file, "wb") as f:
                                subprocess.run(
                                    ["git", "show", f"{ref}:{file_path}"],
                                    cwd=repo_path,
                                    stdout=f,
                                    stderr=subprocess.DEVNULL,
                                    check=True,
                                )
                            log.debug(
                                "Successfully saved regular file reference: %s",
                                out_file,
                            )
                    except subprocess.CalledProcessError as e:
                        log.debug(
                            "File doesn't exist in ref %s: %s, error: %s",
                            ref,
                            file_path,
                            e,
                        )
                else:
                    log.debug("File is not tracked: %s", file_path)

        def save_patch(repo_path, file_paths, out_dir, patch_name, staged=False):
            log.debug(
                "Saving patch: %s, staged: %s, files: %s",
                patch_name,
                staged,
                file_paths,
            )
            out_file = os.path.join(out_dir, patch_name)
            log.debug("Patch output file: %s", out_file)

            os.makedirs(os.path.dirname(out_file), exist_ok=True)
            log.debug("Created patch directory: %s", os.path.dirname(out_file))

            if staged:
                cmd = ["git", "diff", "--cached"] + file_paths
                log.debug("Using staged diff command: %s", cmd)
            else:
                cmd = ["git", "diff"] + file_paths
                log.debug("Using worktree diff command: %s", cmd)

            try:
                log.debug("Executing git diff command in repo: %s", repo_path)
                with open(out_file, "w", encoding="utf-8") as f:
                    subprocess.run(
                        cmd,
                        cwd=repo_path,
                        stdout=f,
                        stderr=subprocess.DEVNULL,
                        check=True,
                    )
                log.debug("Successfully created patch file: %s", out_file)
            except subprocess.CalledProcessError as e:
                log.debug(
                    "Git diff command failed for %s: %s, creating empty patch file",
                    patch_name,
                    e,
                )
                # If no diff exists, create an empty patch file
                with open(out_file, "w", encoding="utf-8") as f:
                    f.write("")
                log.debug("Created empty patch file: %s", out_file)

        def save_commits(repo_path, out_dir):
            log.debug("Saving commits for repo: %s, out_dir: %s", repo_path, out_dir)
            try:
                log.debug("Getting upstream branch for repo: %s", repo_path)
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
                log.debug("Upstream branch: %s", upstream)

                log.debug("Getting commits between %s and HEAD", upstream)
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
                log.debug("Found %d commits: %s", len(commits), commits)

                if not commits:
                    log.debug("No commits to save")
                    return

                log.debug("Creating commits directory: %s", out_dir)
                os.makedirs(out_dir, exist_ok=True)

                log.debug("Formatting patches from %s to HEAD", upstream)
                subprocess.run(
                    ["git", "format-patch", f"{upstream}..HEAD", "-o", out_dir],
                    cwd=repo_path,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=True,
                )
                log.debug("Successfully formatted patches in: %s", out_dir)
            except (OSError, subprocess.SubprocessError) as e:
                log.debug("Error saving commits: %s", e)

        log.debug("Creating diff directories: after, before, patch, commit")
        for d in ["after", "before", "patch", "commit"]:
            dpath = os.path.join(diff_root, d)
            log.debug("Processing directory: %s", dpath)
            if os.path.exists(dpath):
                log.debug("Removing existing directory: %s", dpath)
                shutil.rmtree(dpath)
            os.makedirs(dpath, exist_ok=True)
            log.debug("Created directory: %s", dpath)

        for idx, (repo_path, repo_name) in enumerate(repositories):
            log.debug(
                "Processing repo %d/%d: %s (path: %s)",
                idx + 1,
                len(repositories),
                repo_name,
                repo_path,
            )
            print(f"Processing repo {idx + 1}/{len(repositories)}: {repo_name}")

            original_cwd = os.getcwd()
            log.debug("Original working directory: %s", original_cwd)
            os.chdir(repo_path)
            log.debug("Changed to repo directory: %s", repo_path)

            log.debug("Getting staged files for repo: %s", repo_name)
            staged_files = (
                subprocess.check_output(["git", "diff", "--name-only", "--cached"])
                .decode()
                .strip()
                .splitlines()
            )
            log.debug("Staged files: %s", staged_files)

            log.debug("Getting working directory files for repo: %s", repo_name)
            working_files = (
                subprocess.check_output(
                    ["git", "ls-files", "--modified", "--others", "--exclude-standard"]
                )
                .decode()
                .strip()
                .splitlines()
            )
            log.debug("Working directory files: %s", working_files)

            all_files = set(staged_files) | set(working_files)
            file_list = [f for f in all_files if f.strip()]
            log.debug("Combined file list: %s", file_list)

            # Target directory: single repo put files directly under diff_root/after, etc.; multi-repo use repo_name subdirectory
            if single_repo:
                after_dir = os.path.join(diff_root, "after")
                before_dir = os.path.join(diff_root, "before")
                patch_dir = os.path.join(diff_root, "patch")
                commit_dir = os.path.join(diff_root, "commit")
                log.debug("Single repo mode - using direct directories")
            else:
                after_dir = os.path.join(diff_root, "after", repo_name)
                before_dir = os.path.join(diff_root, "before", repo_name)
                patch_dir = os.path.join(diff_root, "patch", repo_name)
                commit_dir = os.path.join(diff_root, "commit", repo_name)
                log.debug("Multi repo mode - using subdirectories")

            log.debug(
                "Directory paths - after: %s, before: %s, patch: %s, commit: %s",
                after_dir,
                before_dir,
                patch_dir,
                commit_dir,
            )

            log.debug("Saving file snapshots for %d files", len(file_list))
            for file_path in file_list:
                log.debug("Processing file: %s", file_path)
                save_file_snapshot(repo_path, file_path, after_dir)
                save_file_snapshot(repo_path, file_path, before_dir, ref="HEAD")

            if file_list:
                log.debug("Creating patch files for %d files", len(file_list))
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
            else:
                log.debug("No files to create patches for")

            log.debug("Saving commits for repo: %s", repo_name)
            save_commits(repo_path, commit_dir)

            os.chdir(original_cwd)
            log.debug("Restored working directory: %s", original_cwd)

        log.debug("Project diff completed, returning diff root: %s", diff_root)
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
