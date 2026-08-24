"""
Project build utility class for CLI operations.
"""

import ctypes
import errno
import glob
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tarfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from src.hooks import HookType, execute_hooks_with_fallback
from src.log_manager import log, summarize_output
from src.operations.registry import register
from src.plan_utils import emit_plan_json, parse_emit_plan

# from src.profiler import auto_profile  # unused
from src.plugins.patch_override import build_po_apply_plan, po_apply


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "y", "on"}:
            return True
        if lowered in {"0", "false", "no", "n", "off"}:
            return False
        return default
    return bool(value)


def _normalise_repositories(repositories: Any) -> List[Tuple[str, str]]:
    """
    Normalize repositories to List[Tuple[path, name]].

    __main__ typically provides List[Tuple[str, str]], but some unit tests pass
    List[Dict[name, path]].
    """
    if not repositories:
        return []

    normalised: List[Tuple[str, str]] = []
    for item in repositories:
        if isinstance(item, (tuple, list)) and len(item) == 2:
            normalised.append((str(item[0]), str(item[1])))
            continue
        if isinstance(item, dict):
            name = item.get("name")
            path = item.get("path")
            if name and path:
                normalised.append((str(path), str(name)))
    return normalised


def _split_multiline_rules(value: str) -> List[str]:
    if not value:
        return []
    parts: List[str] = []
    for token in str(value).replace("\n", " ").split():
        if token == "\\":
            continue
        parts.append(token)
    return parts


def _safe_project_name(project_name: Any) -> str:
    return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in str(project_name))


def _normalise_profile(profile: Any) -> str:
    if profile is None:
        return "full"
    text = str(profile).strip().lower()
    if not text:
        return "full"
    if text in {"full", "all", "整编", "整编译"}:
        return "full"
    if text in {"single", "one", "module", "单编", "单编译"}:
        return "single"
    return text


def _resolve_cwd(root_path: str, configured: Any) -> str:
    configured_text = str(configured or "").strip()
    if not configured_text:
        return root_path
    if os.path.isabs(configured_text):
        return configured_text
    return os.path.join(root_path, configured_text)


def _safe_relpath(path: str) -> str:
    path = path.strip().lstrip("/\\")
    path = os.path.normpath(path)
    if path in {"", "."}:
        return ""
    if os.path.isabs(path):
        return ""
    if path.startswith("..") or f"{os.sep}.." in path:
        return ""
    return path


def _run_cmd(
    cmd: List[str],
    *,
    cwd: str,
    dry_run: bool,
    description: str,
) -> subprocess.CompletedProcess:
    log.info("%s (cwd=%s): %s", description, cwd, " ".join(cmd))
    if dry_run:
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)


@dataclass
class BuildContext:
    env: Dict[str, Any]
    projects_info: Dict[str, Any]
    project_name: str
    project_cfg: Dict[str, Any]
    platform: Optional[str]
    repositories: List[Tuple[str, str]]
    root_path: str
    build_ts: str
    build_root: str
    dry_run: bool
    force: bool
    profile: str
    repo: str
    target: str
    run_log: Dict[str, Any] = field(default_factory=dict)


def _format_cmd_template(cmd: str, ctx: BuildContext) -> str:
    fmt_ctx = {
        "project": ctx.project_name,
        "platform": ctx.platform or "",
        "profile": ctx.profile,
        "repo": ctx.repo,
        "target": ctx.target,
        "root_path": ctx.root_path,
        "build_root": ctx.build_root,
        "timestamp": ctx.build_ts,
    }
    try:
        return cmd.format(**fmt_ctx)
    except (KeyError, ValueError) as exc:
        log.debug("Command template format failed (%s); using raw cmd: %s", exc, cmd)
        return cmd


def build_project_diff_plan(
    env: Dict[str, Any],
    project_name: str,
    *,
    keep_diff_dir: bool = False,
    timestamp: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a machine-readable plan for project_diff without writing files/directories."""
    ts = str(timestamp).strip() if timestamp else datetime.now().strftime("%Y%m%d_%H%M%S")
    ts = re.sub(r"[^0-9A-Za-z_-]+", "_", ts) or datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_project_name = _safe_project_name(project_name)

    root_dir = os.path.abspath(str(env.get("root_path") or os.getcwd()))
    diff_root = os.path.join(root_dir, ".cache", "build", safe_project_name, ts, "diff")
    timestamp_dir = os.path.dirname(diff_root)
    archive_name = f"diff_{safe_project_name}_{ts}.tar.gz"
    archive_path = os.path.join(timestamp_dir, archive_name)

    repositories = sorted(_normalise_repositories(env.get("repositories", [])), key=lambda item: item[1])

    repo_plans: List[Dict[str, Any]] = []
    for repo_path, repo_name in repositories:
        staged_files: List[str] = []
        working_files: List[str] = []
        errors: List[str] = []

        staged = subprocess.run(
            ["git", "diff", "--name-only", "--cached"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=False,
        )
        if staged.returncode == 0 and staged.stdout.strip():
            staged_files = sorted({line.strip() for line in staged.stdout.splitlines() if line.strip()})
        elif staged.returncode != 0:
            errors.append(f"staged_files_error: {summarize_output(staged.stderr)}")

        working = subprocess.run(
            ["git", "ls-files", "--modified", "--others", "--exclude-standard"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=False,
        )
        if working.returncode == 0 and working.stdout.strip():
            working_files = sorted({line.strip() for line in working.stdout.splitlines() if line.strip()})
        elif working.returncode != 0:
            errors.append(f"working_files_error: {summarize_output(working.stderr)}")

        all_files = sorted(set(staged_files) | set(working_files))
        repo_plans.append(
            {
                "repo": repo_name,
                "path": os.path.relpath(os.path.abspath(repo_path), start=root_dir),
                "staged_files": staged_files,
                "working_files": working_files,
                "all_files": all_files,
                "errors": errors,
            }
        )

    return {
        "schema_version": 1,
        "generated_at": datetime.now().isoformat(),
        "operation": "project_diff",
        "project_name": project_name,
        "dry_run": True,
        "diff_root": os.path.relpath(diff_root, start=root_dir),
        "archive_path": os.path.relpath(archive_path, start=root_dir),
        "keep_diff_dir": bool(keep_diff_dir),
        "repositories": repo_plans,
    }


@register(
    "project_diff",
    needs_repositories=True,
    desc="Generate after, before, patch, commit directories for all repositories or current repo, under a timestamped diff directory.",
)
def project_diff(
    env: Dict,
    projects_info: Dict,
    project_name: str,
    keep_diff_dir: bool = False,
    dry_run: bool = False,
    emit_plan: Any = False,
    timestamp: Optional[str] = None,
) -> bool:
    """
    Generate after, before, patch, commit directories for all repositories or current repo, under a timestamped diff directory.
    Patch files are named changes_worktree.patch and changes_staged.patch.
    If single repo, do not create root subdirectory, put files directly under after, before, etc.
    Diff directory is .cache/build/{project_name}/{timestamp}/diff

    Args:
        env: Environment variables and configuration
        projects_info: Project information dictionary
        project_name: Name of the project
        timestamp (str): Override timestamp directory name (default: now)
        keep_diff_dir (bool): If True, preserve the diff directory after creating tar.gz archive (default: False)
        dry_run (bool): If True, only print planned actions without creating files/directories (default: False)
        emit_plan (bool|str): Emit a machine-readable JSON plan to stdout (true) or to the given path.
    """
    _ = projects_info  # Mark as intentionally unused

    emit_enabled, _ = parse_emit_plan(emit_plan)
    if emit_enabled:
        payload = build_project_diff_plan(env, project_name, keep_diff_dir=keep_diff_dir, timestamp=timestamp)
        emit_plan_json(payload, emit_plan)
        return True

    ts = str(timestamp).strip() if timestamp else datetime.now().strftime("%Y%m%d_%H%M%S")
    ts = re.sub(r"[^0-9A-Za-z_-]+", "_", ts) or datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_project_name = _safe_project_name(project_name)

    # Use absolute path to create diff_root in project root directory
    root_dir = env.get("root_path") or os.getcwd()  # Store project root directory
    diff_root = os.path.join(root_dir, ".cache", "build", safe_project_name, ts, "diff")
    log.debug("Diff root directory: %s", diff_root)

    repositories = _normalise_repositories(env.get("repositories", []))
    single_repo = len(repositories) == 1

    if keep_diff_dir and dry_run:
        log.info("DRY-RUN: --keep-diff-dir is set, but no diff output will be generated in dry-run mode.")

    if dry_run:
        log.info("DRY-RUN: would create diff root: %s", diff_root)
        for repo_path, repo_name in repositories:
            log.info("DRY-RUN: would diff repo '%s' at '%s'", repo_name, repo_path)
        return True

    os.makedirs(diff_root, exist_ok=True)

    # repositories/single_repo defined above

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
        staged_files = (
            subprocess.check_output(
                ["git", "diff", "--name-only", "--cached"],
                cwd=repo_path,
            )
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


def _repo_sync(ctx: BuildContext) -> bool:
    if not ctx.repositories:
        log.info("No repositories found; skipping sync step.")
        return True

    cmd = str(ctx.project_cfg.get("PROJECT_SYNC_CMD", "")).strip()
    if cmd:
        cwd = _resolve_cwd(ctx.root_path, ctx.project_cfg.get("PROJECT_SYNC_CWD", ""))
        cmd = _format_cmd_template(cmd, ctx)
        result = _run_cmd(shlex.split(cmd), cwd=cwd, dry_run=ctx.dry_run, description="Sync repositories")
        if result.returncode != 0:
            log.error("Sync command failed (code=%s): %s", result.returncode, summarize_output(result.stderr))
            return False
        return True

    manifest = os.path.join(ctx.root_path, ".repo", "manifest.xml")
    if os.path.exists(manifest) and shutil.which("repo"):
        result = _run_cmd(["repo", "sync"], cwd=ctx.root_path, dry_run=ctx.dry_run, description="repo sync")
        if result.returncode != 0:
            log.error("repo sync failed (code=%s): %s", result.returncode, summarize_output(result.stderr))
            return False
        return True

    for repo_path, repo_name in ctx.repositories:
        if not os.path.isdir(os.path.join(repo_path, ".git")):
            log.debug("Skipping sync for non-git repo '%s' at '%s'", repo_name, repo_path)
            continue

        if not ctx.force:
            dirty = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=False,
            )
            if dirty.returncode == 0 and dirty.stdout.strip():
                log.error("Repo '%s' is dirty; use --force or --clean first.", repo_name)
                return False

        upstream = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=False,
        )
        if upstream.returncode != 0:
            log.info("Repo '%s' has no upstream; skipping git pull.", repo_name)
            continue

        result = _run_cmd(
            ["git", "pull", "--rebase"],
            cwd=repo_path,
            dry_run=ctx.dry_run,
            description=f"git pull {repo_name}",
        )
        if result.returncode != 0:
            log.error(
                "git pull failed for '%s' (code=%s): %s",
                repo_name,
                result.returncode,
                summarize_output(result.stderr),
            )
            return False

    return True


def _repo_clean(ctx: BuildContext) -> bool:
    if not ctx.repositories:
        log.info("No repositories found; skipping clean step.")
        return True

    if not ctx.force and not ctx.dry_run:
        log.error("Refusing to clean repositories without --force.")
        return False

    excludes = [
        "projects",
        ".repo",
        os.path.join(".cache", "po_applied"),
    ]
    extra_excludes = _split_multiline_rules(str(ctx.project_cfg.get("PROJECT_CLEAN_EXCLUDE", "")))
    excludes.extend(extra_excludes)
    excludes = [e for e in excludes if e]

    for repo_path, repo_name in ctx.repositories:
        if not os.path.isdir(os.path.join(repo_path, ".git")):
            log.debug("Skipping clean for non-git repo '%s' at '%s'", repo_name, repo_path)
            continue

        reset_result = _run_cmd(
            ["git", "reset", "--hard", "HEAD"],
            cwd=repo_path,
            dry_run=ctx.dry_run,
            description=f"Clean reset {repo_name}",
        )
        if reset_result.returncode != 0:
            log.error(
                "git reset failed for '%s' (code=%s): %s",
                repo_name,
                reset_result.returncode,
                summarize_output(reset_result.stderr),
            )
            return False

        clean_cmd = ["git", "clean", "-fdx"]
        for pattern in excludes:
            clean_cmd.extend(["-e", pattern])
        clean_result = _run_cmd(
            clean_cmd,
            cwd=repo_path,
            dry_run=ctx.dry_run,
            description=f"Clean untracked {repo_name}",
        )
        if clean_result.returncode != 0:
            log.error(
                "git clean failed for '%s' (code=%s): %s",
                repo_name,
                clean_result.returncode,
                summarize_output(clean_result.stderr),
            )
            return False

    return True


def _glob_base_dir(pattern: str) -> str:
    wildcard_positions = [pattern.find(ch) for ch in ("*", "?", "[") if pattern.find(ch) != -1]
    if not wildcard_positions:
        return os.path.dirname(pattern)
    prefix = pattern[: min(wildcard_positions)]
    return os.path.dirname(prefix) if prefix else ""


def _copy_artifact(src_path: str, dest_path: str) -> None:
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)

    if os.path.isdir(src_path):
        if os.path.exists(dest_path):
            shutil.rmtree(dest_path)

        def _ignore(directory: str, names: List[str]) -> List[str]:
            _ = directory
            return [".git"] if ".git" in names else []

        shutil.copytree(src_path, dest_path, ignore=_ignore)
        return

    shutil.copy2(src_path, dest_path)


def _collect_artifacts(ctx: BuildContext, rules_override: Optional[str] = None) -> bool:
    raw_rules = (
        rules_override if rules_override is not None else str(ctx.project_cfg.get("PROJECT_BUILD_ARTIFACTS", ""))
    )
    rules = _split_multiline_rules(raw_rules)
    if not rules:
        return True

    artifacts_root = os.path.join(ctx.build_root, "artifacts")
    if ctx.dry_run:
        log.info("DRY-RUN: would collect artifacts into: %s", artifacts_root)
    else:
        os.makedirs(artifacts_root, exist_ok=True)

    copied: List[Dict[str, str]] = []

    for rule in rules:
        if rule.startswith("path:"):
            parts = rule.split(":", 2)
            if len(parts) != 3:
                log.error("Invalid artifact rule (path): %s", rule)
                return False
            _, src_rel, dest_dir = parts
            src_rel_safe = _safe_relpath(src_rel)
            if not src_rel_safe:
                log.error("Unsafe artifact source path: %s", src_rel)
                return False
            dest_dir_is_dir = dest_dir.endswith("/") or dest_dir.endswith("\\") or dest_dir == ""
            dest_dir_safe = _safe_relpath(dest_dir)
            if dest_dir and not dest_dir_safe:
                log.error("Unsafe artifact dest path: %s", dest_dir)
                return False

            src_abs = os.path.join(ctx.root_path, src_rel_safe)
            if not os.path.exists(src_abs):
                log.error("Artifact source does not exist: %s", src_rel_safe)
                return False

            if dest_dir_is_dir:
                dest_rel = (
                    os.path.join(dest_dir_safe, os.path.basename(src_rel_safe))
                    if dest_dir_safe
                    else os.path.basename(src_rel_safe)
                )
            else:
                dest_rel = dest_dir_safe

            dest_rel_safe = _safe_relpath(dest_rel) if dest_rel else ""
            dest_abs = os.path.join(artifacts_root, dest_rel_safe)

            if ctx.dry_run:
                log.info("DRY-RUN: would copy %s -> %s", src_abs, dest_abs)
            else:
                _copy_artifact(src_abs, dest_abs)
            copied.append({"rule": rule, "src": src_rel_safe, "dest": dest_rel_safe})
            continue

        if rule.startswith("glob:"):
            parts = rule.split(":", 2)
            if len(parts) != 3:
                log.error("Invalid artifact rule (glob): %s", rule)
                return False
            _, pattern, dest_dir = parts
            pattern_safe = _safe_relpath(pattern)
            if pattern and not pattern_safe:
                log.error("Unsafe artifact glob pattern: %s", pattern)
                return False
            dest_dir_safe = _safe_relpath(dest_dir)
            if dest_dir and not dest_dir_safe:
                log.error("Unsafe artifact dest path: %s", dest_dir)
                return False

            base_dir = _glob_base_dir(pattern_safe)
            base_dir_safe = _safe_relpath(base_dir) if base_dir else ""
            base_abs = os.path.join(ctx.root_path, base_dir_safe) if base_dir_safe else ctx.root_path
            matches = glob.glob(os.path.join(ctx.root_path, pattern_safe), recursive=True)
            if not matches:
                log.warning("No artifact matches for glob rule: %s", rule)
                continue

            for match in sorted(set(matches)):
                rel_from_base = os.path.relpath(match, base_abs)
                rel_from_base_safe = _safe_relpath(rel_from_base)
                if not rel_from_base_safe:
                    log.error("Unsafe artifact match path: %s", match)
                    return False
                dest_rel = os.path.join(dest_dir_safe, rel_from_base_safe) if dest_dir_safe else rel_from_base_safe
                dest_rel_safe = _safe_relpath(dest_rel)
                if dest_rel and not dest_rel_safe:
                    log.error("Unsafe artifact dest path: %s", dest_rel)
                    return False
                dest_abs = os.path.join(artifacts_root, dest_rel_safe)

                if ctx.dry_run:
                    log.info("DRY-RUN: would copy %s -> %s", match, dest_abs)
                else:
                    _copy_artifact(match, dest_abs)
                src_rel = _safe_relpath(os.path.relpath(match, ctx.root_path))
                if not src_rel:
                    log.error("Unsafe artifact match path: %s", match)
                    return False
                copied.append({"rule": rule, "src": src_rel, "dest": dest_rel_safe})
            continue

        if rule.startswith("manifest:"):
            parts = rule.split(":", 2)
            if len(parts) != 3:
                log.error("Invalid artifact rule (manifest): %s", rule)
                return False
            _, manifest_rel, dest_dir = parts
            manifest_safe = _safe_relpath(manifest_rel)
            if not manifest_safe:
                log.error("Unsafe manifest path: %s", manifest_rel)
                return False
            dest_dir_safe = _safe_relpath(dest_dir)
            if dest_dir and not dest_dir_safe:
                log.error("Unsafe artifact dest path: %s", dest_dir)
                return False

            manifest_abs = os.path.join(ctx.root_path, manifest_safe)
            if not os.path.exists(manifest_abs):
                log.error("Manifest does not exist: %s", manifest_safe)
                return False

            with open(manifest_abs, "r", encoding="utf-8") as handle:
                lines = [line.strip() for line in handle.read().splitlines()]

            for entry in [line for line in lines if line and not line.startswith("#")]:
                entry_safe = _safe_relpath(entry)
                if not entry_safe:
                    log.error("Unsafe manifest entry: %s", entry)
                    return False
                src_abs = os.path.join(ctx.root_path, entry_safe)
                if not os.path.exists(src_abs):
                    log.error("Manifest entry does not exist: %s", entry_safe)
                    return False
                dest_rel = os.path.join(dest_dir_safe, entry_safe) if dest_dir_safe else entry_safe
                dest_rel_safe = _safe_relpath(dest_rel)
                if dest_rel and not dest_rel_safe:
                    log.error("Unsafe artifact dest path: %s", dest_rel)
                    return False
                dest_abs = os.path.join(artifacts_root, dest_rel_safe)

                if ctx.dry_run:
                    log.info("DRY-RUN: would copy %s -> %s", src_abs, dest_abs)
                else:
                    _copy_artifact(src_abs, dest_abs)
                copied.append({"rule": rule, "src": entry_safe, "dest": dest_rel_safe})
            continue

        if rule.startswith("regex@"):
            prefix, _, rest = rule.partition(":")
            if not rest:
                log.error("Invalid artifact rule (regex): %s", rule)
                return False
            root_rel = prefix[len("regex@") :]
            root_rel_safe = _safe_relpath(root_rel)
            if not root_rel_safe:
                log.error("Unsafe regex root path: %s", root_rel)
                return False
            if ":" not in rest:
                log.error("Invalid artifact rule (regex): %s", rule)
                return False
            pattern, dest_dir = rest.rsplit(":", 1)
            pattern = pattern.strip()
            dest_dir = dest_dir.strip()
            if not pattern or not dest_dir:
                log.error("Invalid artifact rule (regex): %s", rule)
                return False
            dest_dir_safe = _safe_relpath(dest_dir)
            if dest_dir and not dest_dir_safe:
                log.error("Unsafe artifact dest path: %s", dest_dir)
                return False

            root_abs = os.path.join(ctx.root_path, root_rel_safe)
            if not os.path.isdir(root_abs):
                log.error("Regex root directory does not exist: %s", root_rel_safe)
                return False

            try:
                compiled = re.compile(pattern.replace("\\\\", "\\"))
            except re.error as exc:
                log.error("Invalid regex pattern '%s': %s", pattern, exc)
                return False

            matches: List[str] = []
            for current_root, _, files in os.walk(root_abs):
                for fname in files:
                    abs_path = os.path.join(current_root, fname)
                    rel_from_root = os.path.relpath(abs_path, root_abs)
                    rel_posix = rel_from_root.replace(os.sep, "/")
                    if compiled.search(rel_posix):
                        matches.append(rel_from_root)

            if not matches:
                log.warning("No artifact matches for regex rule: %s", rule)
                continue

            for rel_from_root in sorted(set(matches)):
                rel_safe = _safe_relpath(rel_from_root)
                if not rel_safe:
                    log.error("Unsafe regex match path: %s", rel_from_root)
                    return False
                src_abs = os.path.join(root_abs, rel_safe)
                dest_rel = os.path.join(dest_dir_safe, rel_safe) if dest_dir_safe else rel_safe
                dest_rel_safe = _safe_relpath(dest_rel)
                if dest_rel and not dest_rel_safe:
                    log.error("Unsafe artifact dest path: %s", dest_rel)
                    return False
                dest_abs = os.path.join(artifacts_root, dest_rel_safe)

                if ctx.dry_run:
                    log.info("DRY-RUN: would copy %s -> %s", src_abs, dest_abs)
                else:
                    _copy_artifact(src_abs, dest_abs)
                copied.append({"rule": rule, "src": os.path.join(root_rel_safe, rel_safe), "dest": dest_rel_safe})
            continue

        log.error("Unknown artifact rule type: %s", rule)
        return False

    if copied and not ctx.dry_run:
        manifest_path = os.path.join(artifacts_root, "manifest.json")
        payload = {
            "schema_version": 1,
            "project": ctx.project_name,
            "timestamp": ctx.build_ts,
            "items": copied,
        }
        with open(manifest_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")

    return True


def _git_result(repo_path: str, args: List[str]) -> subprocess.CompletedProcess:
    command = ["git", *args]
    try:
        return subprocess.run(
            command,
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return subprocess.CompletedProcess(
            command,
            127,
            stdout="",
            stderr=f"{type(exc).__name__}: {exc}",
        )


def _repo_upstream(repo_path: str) -> Tuple[str, Optional[Tuple[str, subprocess.CompletedProcess]]]:
    branch_result = _git_result(repo_path, ["symbolic-ref", "--quiet", "--short", "HEAD"])
    if branch_result.returncode == 1:
        return "", None
    if branch_result.returncode != 0:
        return "", ("git symbolic-ref HEAD", branch_result)

    branch = branch_result.stdout.strip()
    upstream_result = _git_result(
        repo_path,
        ["for-each-ref", "--format=%(upstream:short)", f"refs/heads/{branch}"],
    )
    if upstream_result.returncode != 0:
        return "", ("git upstream query", upstream_result)

    upstream = upstream_result.stdout.strip()
    if not upstream:
        return "", None

    verify_result = _git_result(repo_path, ["rev-parse", "--verify", upstream])
    if verify_result.returncode != 0:
        return "", (f"git verify upstream {upstream}", verify_result)
    return upstream, None


def _write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def _mark_history_partial(item: Dict[str, Any], operation: str, result: subprocess.CompletedProcess) -> None:
    detail = (result.stderr or result.stdout or f"{operation} failed").strip()[:500]
    error = f"{operation}: {detail}"
    item["status"] = "partial"
    item["error"] = "; ".join(filter(None, [item.get("error", ""), error]))


def _safe_history_repo_name(repo_name: str) -> str:
    name = str(repo_name).strip().replace("\\", "/")
    parts = name.split("/")
    if not name or any(part in {"", ".", ".."} for part in parts):
        return ""
    return os.path.join(*parts)


_HISTORY_RESERVED_COMPONENTS = {
    "history",
    "local_commits.txt",
    "local_patches",
    "meta.json",
    "repos",
    "summary.json",
    "repo-history",
}


def _preflight_history_repo_names(repositories: List[Tuple[str, str]]) -> Optional[List[str]]:
    safe_names: List[str] = []
    folded_parts: List[Tuple[str, ...]] = []
    for _, repo_name in repositories:
        safe_name = _safe_history_repo_name(repo_name)
        parts = tuple(part.casefold() for part in safe_name.split(os.sep)) if safe_name else ()
        if not safe_name:
            log.error("Unsafe repository name for history output: %s", repo_name)
            return None
        if any(part in _HISTORY_RESERVED_COMPONENTS for part in parts):
            log.error("Reserved repository name for history output: %s", repo_name)
            return None
        for existing in folded_parts:
            common_len = min(len(parts), len(existing))
            if parts[:common_len] == existing[:common_len]:
                log.error("Colliding repository name for history output: %s", repo_name)
                return None
        safe_names.append(safe_name)
        folded_parts.append(parts)
    return safe_names


_O_DIRECTORY = getattr(os, "O_DIRECTORY", None)
_O_NOFOLLOW = getattr(os, "O_NOFOLLOW", None)


def _history_capabilities_available() -> bool:
    if _O_DIRECTORY is None or _O_NOFOLLOW is None:
        return False
    required_dir_fd = {os.open, os.mkdir, os.stat, os.unlink, os.rmdir}
    if not required_dir_fd.issubset(os.supports_dir_fd):
        return False
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform.startswith("linux") and hasattr(libc, "renameat2"):
        rename = libc.renameat2
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        result = rename(-1, b"probe", -1, b"probe", 1)
    elif sys.platform == "darwin" and hasattr(libc, "renameatx_np"):
        rename = libc.renameatx_np
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        result = rename(-1, b"probe", -1, b"probe", 0x00000004)
    else:
        return False
    return result == -1 and ctypes.get_errno() == errno.EBADF


def _directory_open_flags() -> int:
    if _O_DIRECTORY is None or _O_NOFOLLOW is None:
        raise OSError(errno.ENOTSUP, "safe directory-open flags are unavailable")
    return os.O_RDONLY | _O_DIRECTORY | _O_NOFOLLOW


def _open_or_create_dir_at(parent_fd: int, name: str, *, create: bool = True) -> int:
    """Open one directory component without following a symlink."""
    if not name or name in {".", ".."} or os.sep in name or (os.altsep and os.altsep in name):
        raise ValueError(f"unsafe directory component: {name!r}")
    if create:
        try:
            os.mkdir(name, mode=0o755, dir_fd=parent_fd)
        except FileExistsError:
            pass
    return os.open(name, _directory_open_flags(), dir_fd=parent_fd)


def _open_directory_chain(
    root_fd: int, components: List[str], *, create: bool
) -> Tuple[int, List[Tuple[str, int, int]]]:
    current_fd = os.dup(root_fd)
    identities: List[Tuple[str, int, int]] = []
    try:
        for component in components:
            next_fd = _open_or_create_dir_at(current_fd, component, create=create)
            os.close(current_fd)
            current_fd = next_fd
            current_stat = os.fstat(current_fd)
            identities.append((component, current_stat.st_dev, current_stat.st_ino))
        return current_fd, identities
    except Exception:
        os.close(current_fd)
        raise


def _verify_directory_chain(root_fd: int, identities: List[Tuple[str, int, int]]) -> bool:
    current_fd = os.dup(root_fd)
    try:
        for component, expected_dev, expected_ino in identities:
            next_fd = _open_or_create_dir_at(current_fd, component, create=False)
            os.close(current_fd)
            current_fd = next_fd
            current_stat = os.fstat(current_fd)
            if (current_stat.st_dev, current_stat.st_ino) != (expected_dev, expected_ino):
                return False
        return True
    except (OSError, ValueError):
        return False
    finally:
        os.close(current_fd)


def _directory_fd_path(directory_fd: int) -> str:
    for prefix in (f"/proc/{os.getpid()}/fd", "/dev/fd"):
        candidate = os.path.join(prefix, str(directory_fd))
        if os.path.exists(candidate):
            return candidate
    raise OSError(errno.ENOTSUP, "directory descriptor paths are unavailable")


def _clear_directory_fd(directory_fd: int) -> None:
    for name in os.listdir(directory_fd):
        entry_stat = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if stat.S_ISDIR(entry_stat.st_mode):
            child_fd = os.open(name, _directory_open_flags(), dir_fd=directory_fd)
            try:
                _clear_directory_fd(child_fd)
            finally:
                os.close(child_fd)
            os.rmdir(name, dir_fd=directory_fd)
        else:
            os.unlink(name, dir_fd=directory_fd)


def _path_matches_identity(parent_fd: int, name: str, identity: Tuple[int, int]) -> bool:
    try:
        current = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except OSError:
        return False
    return (current.st_dev, current.st_ino) == identity


def _remove_private_directory(
    parent_fd: int,
    name: str,
    directory_fd: Optional[int],
    identity: Optional[Tuple[int, int]],
) -> None:
    if directory_fd is None or identity is None:
        return
    opened = os.fstat(directory_fd)
    if (opened.st_dev, opened.st_ino) != identity or not _path_matches_identity(parent_fd, name, identity):
        return
    try:
        _clear_directory_fd(directory_fd)
        if _path_matches_identity(parent_fd, name, identity):
            os.rmdir(name, dir_fd=parent_fd)
    except FileNotFoundError:
        pass
    except OSError as exc:
        log.warning("Failed to clean private history staging directory: %s", exc)


def _rename_noreplace(source_fd: int, source: str, destination_fd: int, destination: str) -> None:
    """Atomically rename within trusted parents, refusing to replace a destination."""
    libc = ctypes.CDLL(None, use_errno=True)
    encoded_source = os.fsencode(source)
    encoded_destination = os.fsencode(destination)
    if sys.platform.startswith("linux") and hasattr(libc, "renameat2"):
        rename = libc.renameat2
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        result = rename(source_fd, encoded_source, destination_fd, encoded_destination, 1)
    elif sys.platform == "darwin" and hasattr(libc, "renameatx_np"):
        rename = libc.renameatx_np
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        result = rename(source_fd, encoded_source, destination_fd, encoded_destination, 0x00000004)
    else:
        raise OSError(errno.ENOTSUP, "atomic no-replace rename is unavailable")
    if result != 0:
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number), destination)


def _copy_file_exclusive(source: str, destination: str) -> Tuple[int, int]:
    destination_fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
    opened_stat = os.fstat(destination_fd)
    identity = (opened_stat.st_dev, opened_stat.st_ino)
    try:
        with open(source, "rb") as source_handle, os.fdopen(os.dup(destination_fd), "wb") as destination_handle:
            shutil.copyfileobj(source_handle, destination_handle)
        os.fsync(destination_fd)
        current = os.stat(destination, follow_symlinks=False)
        if (current.st_dev, current.st_ino) != identity:
            raise OSError(errno.ESTALE, "artifact staging path changed during copy")
        return identity
    except (OSError, shutil.Error):
        try:
            current = os.stat(destination, follow_symlinks=False)
            if (current.st_dev, current.st_ino) == identity:
                os.unlink(destination)
        except FileNotFoundError:
            pass
        raise
    finally:
        os.close(destination_fd)


def _build_history_stage(
    stage_root: str,
    root_dir: str,
    repositories: List[Tuple[str, str]],
    safe_repo_names: List[str],
    project_name: str,
    ts: str,
    synced_limit: int,
    archive_name: str,
    keep_dir: bool,
) -> Tuple[Dict[str, Any], str]:
    history_root = os.path.join(stage_root, "history")
    os.mkdir(history_root)
    repos_dir = os.path.join(history_root, "repos")
    os.mkdir(repos_dir)
    summary_repos: List[Dict[str, Any]] = []
    log_format = "%H%x09%h%x09%ad%x09%an%x09%s"
    date_fmt = "iso-strict"

    for idx, ((repo_path, repo_name), safe_repo_name) in enumerate(zip(repositories, safe_repo_names)):
        log.info("Recording history %s/%s: %s", idx + 1, len(repositories), repo_name)
        repo_out = os.path.join(repos_dir, safe_repo_name)
        os.makedirs(repo_out, exist_ok=True)
        item: Dict[str, Any] = {
            "name": repo_name,
            "path": os.path.relpath(repo_path, start=root_dir) if os.path.isabs(repo_path) else repo_path,
            "git": False,
            "head": "",
            "upstream": "",
            "synced_commit_count": 0,
            "local_commit_count": 0,
            "local_patch_count": 0,
            "status": "ok",
            "error": "",
        }
        git_marker = os.path.join(repo_path, ".git")
        if not (os.path.isdir(git_marker) or os.path.isfile(git_marker)):
            item["status"] = "skipped"
            item["error"] = "not a git repository"
            summary_repos.append(item)
            _write_text(os.path.join(repo_out, "meta.json"), json.dumps(item, indent=2, ensure_ascii=False) + "\n")
            continue

        item["git"] = True
        head_result = _git_result(repo_path, ["rev-parse", "HEAD"])
        if head_result.returncode != 0:
            _mark_history_partial(item, "rev-parse HEAD", head_result)
            summary_repos.append(item)
            _write_text(os.path.join(repo_out, "meta.json"), json.dumps(item, indent=2, ensure_ascii=False) + "\n")
            continue
        item["head"] = head_result.stdout.strip()
        upstream, upstream_error = _repo_upstream(repo_path)
        item["upstream"] = upstream
        if upstream_error:
            operation, result = upstream_error
            _mark_history_partial(item, operation, result)

        synced_ref = upstream or "HEAD"
        synced_result = _git_result(
            repo_path,
            ["log", synced_ref, f"--max-count={synced_limit}", f"--format={log_format}", f"--date={date_fmt}"],
        )
        if synced_result.returncode != 0:
            _mark_history_partial(item, f"git log {synced_ref}", synced_result)
        synced_log = synced_result.stdout if synced_result.returncode == 0 else ""
        _write_text(os.path.join(repo_out, "synced_commits.txt"), synced_log)
        item["synced_commit_count"] = len([line for line in synced_log.splitlines() if line.strip()])

        local_shas: List[str] = []
        if upstream:
            local_result = _git_result(repo_path, ["rev-list", "--reverse", f"{upstream}..HEAD"])
            if local_result.returncode != 0:
                _mark_history_partial(item, f"git rev-list {upstream}..HEAD", local_result)
            local_list = local_result.stdout.strip() if local_result.returncode == 0 else ""
            local_shas = [line for line in local_list.splitlines() if line.strip()]
            local_log_result = _git_result(
                repo_path,
                ["log", f"{upstream}..HEAD", "--reverse", f"--format={log_format}", f"--date={date_fmt}"],
            )
            if local_log_result.returncode != 0:
                _mark_history_partial(item, f"git log {upstream}..HEAD", local_log_result)
            local_log = local_log_result.stdout if local_log_result.returncode == 0 else ""
            _write_text(os.path.join(repo_out, "local_commits.txt"), local_log)
            item["local_commit_count"] = len(local_shas)

            if local_shas:
                patch_dir = os.path.join(repo_out, "local_patches")
                os.makedirs(patch_dir, exist_ok=True)
                result = _git_result(repo_path, ["format-patch", f"{upstream}..HEAD", "-o", patch_dir])
                if result.returncode != 0:
                    _mark_history_partial(item, "git format-patch", result)
                    log.warning("format-patch failed for %s: %s", repo_name, item["error"])
                else:
                    item["local_patch_count"] = len([name for name in os.listdir(patch_dir) if name.endswith(".patch")])
        elif upstream_error:
            _write_text(
                os.path.join(repo_out, "local_commits.txt"),
                "# upstream query failed; local temporary commits cannot be distinguished\n",
            )
        else:
            _write_text(
                os.path.join(repo_out, "local_commits.txt"),
                "# no upstream configured; local temporary commits cannot be distinguished\n",
            )

        _write_text(os.path.join(repo_out, "meta.json"), json.dumps(item, indent=2, ensure_ascii=False) + "\n")
        summary_repos.append(item)

    summary = {
        "schema_version": 1,
        "operation": "project_record_history",
        "project_name": project_name,
        "timestamp": ts,
        "synced_max": synced_limit,
        "repository_count": len(summary_repos),
        "local_commit_repos": sum(1 for repo in summary_repos if repo.get("local_commit_count", 0) > 0),
        "partial_repository_count": sum(1 for repo in summary_repos if repo.get("status") == "partial"),
        "repositories": summary_repos,
    }
    _write_text(os.path.join(history_root, "summary.json"), json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    archive_path = os.path.join(stage_root, archive_name)
    log.info("Creating private history archive: %s", archive_path)
    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(history_root, arcname="history")
    if not keep_dir:
        shutil.rmtree(history_root)
    return summary, archive_path


@register(
    "project_record_history",
    needs_repositories=True,
    desc="Record per-repo commit history after po_apply; archive patches for local commits ahead of upstream.",
)
def project_record_history(
    env: Dict,
    projects_info: Dict,
    project_name: str,
    timestamp: Optional[str] = None,
    synced_max: int = 50,
    artifact_dir: str = "",
    dry_run: bool = False,
    keep_dir: bool = False,
) -> bool:
    """Record repository history and publish complete outputs atomically."""
    _ = projects_info
    ts = str(timestamp).strip() if timestamp else datetime.now().strftime("%Y%m%d_%H%M%S")
    ts = re.sub(r"[^0-9A-Za-z_-]+", "_", ts) or datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_project_name = _safe_project_name(project_name)
    root_dir = os.path.realpath(os.path.abspath(str(env.get("root_path") or os.getcwd())))
    repositories = _normalise_repositories(env.get("repositories", []))
    safe_repo_names = _preflight_history_repo_names(repositories)
    if safe_repo_names is None:
        return False

    artifact = str(artifact_dir or "").strip()
    artifact_components: Optional[List[str]] = None
    absolute_artifact = ""
    if artifact:
        if os.path.isabs(artifact):
            log.error("Absolute artifact directories are not supported: %s", artifact)
            return False
        else:
            safe_artifact = _safe_relpath(artifact)
            if not safe_artifact:
                log.error("Unsafe relative artifact directory: %s", artifact)
                return False
            artifact_components = safe_artifact.split(os.sep)

    try:
        synced_limit = max(1, int(synced_max))
    except (TypeError, ValueError):
        synced_limit = 50
    archive_name = f"repo-history_{safe_project_name}_{ts}.tar.gz"
    if not dry_run and not _history_capabilities_available():
        log.error("Safe descriptor-relative atomic publication is unavailable on this platform")
        return False
    if dry_run:
        log.info("DRY-RUN: would privately build and publish history timestamp: %s", ts)
        log.info("DRY-RUN: synced_max=%s artifact_dir=%s keep_dir=%s", synced_limit, artifact or "(none)", keep_dir)
        for repo_path, repo_name in repositories:
            log.info("DRY-RUN: would record history for repo '%s' at '%s'", repo_name, repo_path)
        return True

    root_fd: Optional[int] = None
    timestamp_parent_fd: Optional[int] = None
    artifact_parent_fd: Optional[int] = None
    stage_fd: Optional[int] = None
    timestamp_chain: List[Tuple[str, int, int]] = []
    artifact_chain: List[Tuple[str, int, int]] = []
    stage_name = f".{ts}.tmp-{uuid.uuid4().hex}"
    artifact_stage_name = f".{archive_name}.tmp-{uuid.uuid4().hex}"
    artifact_published = False
    artifact_identity: Optional[Tuple[int, int]] = None
    timestamp_identity: Optional[Tuple[int, int]] = None
    timestamp_published = False
    publication_valid = False
    try:
        root_fd = os.open(root_dir, _directory_open_flags())
        _directory_fd_path(root_fd)
        if artifact:
            if artifact_components is not None:
                artifact_parent_fd, artifact_chain = _open_directory_chain(root_fd, artifact_components, create=True)
            else:
                raise OSError(errno.ENOTSUP, "absolute artifact directories are unsupported")
            try:
                os.stat(archive_name, dir_fd=artifact_parent_fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                log.error("History artifact already exists: %s", archive_name)
                return False

        timestamp_parent_fd, timestamp_chain = _open_directory_chain(
            root_fd, [".cache", "build", safe_project_name], create=True
        )
        try:
            os.stat(ts, dir_fd=timestamp_parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            log.error("History timestamp output already exists: %s", ts)
            return False

        os.mkdir(stage_name, mode=0o700, dir_fd=timestamp_parent_fd)
        stage_fd = os.open(stage_name, _directory_open_flags(), dir_fd=timestamp_parent_fd)
        stage_stat = os.fstat(stage_fd)
        timestamp_identity = (stage_stat.st_dev, stage_stat.st_ino)
        stage_root = _directory_fd_path(stage_fd)
        summary, archive_path = _build_history_stage(
            stage_root,
            root_dir,
            repositories,
            safe_repo_names,
            project_name,
            ts,
            synced_limit,
            archive_name,
            _coerce_bool(keep_dir, False),
        )

        if artifact:
            assert artifact_parent_fd is not None
            artifact_stage_path = os.path.join(_directory_fd_path(artifact_parent_fd), artifact_stage_name)
            artifact_identity = _copy_file_exclusive(archive_path, artifact_stage_path)
            if not _path_matches_identity(artifact_parent_fd, artifact_stage_name, artifact_identity):
                raise OSError(errno.ESTALE, "artifact staging path changed before publication")

        if not _verify_directory_chain(root_fd, timestamp_chain):
            raise OSError(errno.ESTALE, "history output directory changed before publication")
        if artifact_components is not None and not _verify_directory_chain(root_fd, artifact_chain):
            raise OSError(errno.ESTALE, "artifact output directory changed before publication")

        if artifact_parent_fd is not None:
            _rename_noreplace(artifact_parent_fd, artifact_stage_name, artifact_parent_fd, archive_name)
            artifact_published = True
        _rename_noreplace(timestamp_parent_fd, stage_name, timestamp_parent_fd, ts)
        timestamp_published = True
        timestamp_reachable = timestamp_identity is not None and _path_matches_identity(
            timestamp_parent_fd, ts, timestamp_identity
        )
        artifact_reachable = artifact_parent_fd is None or (
            artifact_identity is not None
            and _path_matches_identity(artifact_parent_fd, archive_name, artifact_identity)
        )
        if (
            not _verify_directory_chain(root_fd, timestamp_chain)
            or (artifact_components is not None and not _verify_directory_chain(root_fd, artifact_chain))
            or not timestamp_reachable
            or not artifact_reachable
        ):
            raise OSError(errno.ESTALE, "published history output is no longer reachable through requested paths")
        publication_valid = True
        log.info(
            "History recorded: repos=%s local_commit_repos=%s archive=%s",
            summary["repository_count"],
            summary["local_commit_repos"],
            archive_name,
        )
        return True
    except (OSError, shutil.Error, tarfile.TarError, RuntimeError, ValueError) as exc:
        log.error("Failed to record or publish history atomically: %s", exc)
        return False
    finally:
        if artifact_parent_fd is not None:
            artifact_name = archive_name if artifact_published else artifact_stage_name
            if not publication_valid and artifact_identity is not None:
                try:
                    if _path_matches_identity(artifact_parent_fd, artifact_name, artifact_identity):
                        os.unlink(artifact_name, dir_fd=artifact_parent_fd)
                except FileNotFoundError:
                    pass
            os.close(artifact_parent_fd)
        if stage_fd is not None:
            if not publication_valid and timestamp_parent_fd is not None:
                timestamp_name = ts if timestamp_published else stage_name
                _remove_private_directory(timestamp_parent_fd, timestamp_name, stage_fd, timestamp_identity)
            os.close(stage_fd)
        if timestamp_parent_fd is not None:
            os.close(timestamp_parent_fd)
        if root_fd is not None:
            os.close(root_fd)


@register(
    "project_pre_build",
    needs_repositories=True,
    desc="Pre-build stage for the specified project.",
)
def project_pre_build(
    env: Dict,
    projects_info: Dict,
    project_name: str,
    timestamp: Optional[str] = None,
    no_po: bool = False,
    no_diff: bool = False,
    dry_run: bool = False,
    force: bool = False,
) -> bool:
    """
    Pre-build stage for the specified project.

    timestamp (str): Shared timestamp for diff/artifacts directory.
    no_po (bool): Skip po_apply (default: False).
    no_diff (bool): Skip project_diff (default: False).
    dry_run (bool): Print planned actions without writing (default: False).
    force (bool): Force destructive actions for po_apply (default: False).
    """
    log.info("Pre-build stage for project: %s", project_name)
    if not _coerce_bool(no_po, False):
        # Apply patch/override; failures are fatal
        try:
            result = po_apply(
                env, projects_info, project_name, dry_run=_coerce_bool(dry_run, False), force=_coerce_bool(force, False)
            )
            if not result:
                log.error("po_apply failed for project: %s", project_name)
                return False
        except Exception as exc:  # pylint: disable=broad-except
            log.error("Exception during po_apply for %s: %s", project_name, exc)
            return False
    else:
        log.info("Skipping po_apply (--no-po).")

    if not _coerce_bool(no_diff, False):
        project_diff(env, projects_info, project_name, timestamp=timestamp, dry_run=_coerce_bool(dry_run, False))
    else:
        log.info("Skipping project_diff (--no-diff).")
    return True


@register(
    "project_do_build",
    needs_repositories=False,
    desc="Build stage for the specified project.",
)
def project_do_build(
    env: Dict,
    projects_info: Dict,
    project_name: str,
    profile: str = "full",
    repo: str = "",
    target: str = "",
    dry_run: bool = False,
) -> bool:
    """
    Build stage for the specified project.

    profile (str): Build profile, e.g. `full` (整编) or `single` (单编).
    repo (str): Repo name/module for single build (optional).
    target (str): Target name for single build (optional).
    dry_run (bool): If True, only print planned actions (default: False).
    """
    log.info("Build stage for project: %s", project_name)
    project_info = projects_info.get(project_name, {}) if isinstance(projects_info, dict) else {}
    project_cfg = project_info.get("config", {}) if isinstance(project_info, dict) else {}

    profile_norm = _normalise_profile(profile)
    repo_text = str(repo or "")
    target_text = str(target or "")

    cmd = ""
    if profile_norm == "single":
        cmd = (
            str(project_cfg.get("PROJECT_BUILD_SINGLE_CMD", "")).strip()
            or str(project_cfg.get("PROJECT_BUILD_CMD_SINGLE", "")).strip()
        )
    elif profile_norm == "full":
        cmd = (
            str(project_cfg.get("PROJECT_BUILD_FULL_CMD", "")).strip()
            or str(project_cfg.get("PROJECT_BUILD_CMD_FULL", "")).strip()
        )
    cmd = cmd or str(project_cfg.get("PROJECT_BUILD_CMD", "")).strip()
    if not cmd:
        # Debug-friendly hint without leaking full command content (commands may contain tokens).
        full_cmd = str(project_cfg.get("PROJECT_BUILD_FULL_CMD", "")).strip()
        full_cmd_legacy = str(project_cfg.get("PROJECT_BUILD_CMD_FULL", "")).strip()
        single_cmd = str(project_cfg.get("PROJECT_BUILD_SINGLE_CMD", "")).strip()
        single_cmd_legacy = str(project_cfg.get("PROJECT_BUILD_CMD_SINGLE", "")).strip()
        generic_cmd = str(project_cfg.get("PROJECT_BUILD_CMD", "")).strip()
        build_keys = sorted(k for k in project_cfg.keys() if "BUILD" in k)
        log.debug(
            "Build cmd missing (project=%s profile=%s repo=%s target=%s cfg_keys=%d build_keys=%s has_full=%s has_full_legacy=%s has_single=%s has_single_legacy=%s has_generic=%s)",
            project_name,
            profile_norm,
            repo_text,
            target_text,
            len(project_cfg) if isinstance(project_cfg, dict) else -1,
            build_keys,
            bool(full_cmd),
            bool(full_cmd_legacy),
            bool(single_cmd),
            bool(single_cmd_legacy),
            bool(generic_cmd),
        )
        log.info("No PROJECT_BUILD_CMD configured for project: %s (skipping build stage)", project_name)
        return True

    root_path = env.get("root_path") or os.getcwd()
    build_cwd = str(project_cfg.get("PROJECT_BUILD_CWD", "")).strip()
    cwd = _resolve_cwd(str(root_path), build_cwd)

    build_ts = str(env.get("build_ts") or datetime.now().strftime("%Y%m%d_%H%M%S"))
    build_root = str(env.get("build_root") or "")

    cmd = _format_cmd_template(
        cmd,
        BuildContext(
            env=dict(env),
            projects_info=dict(projects_info) if isinstance(projects_info, dict) else {},
            project_name=project_name,
            project_cfg=project_cfg,
            platform=str(project_cfg.get("PROJECT_PLATFORM", "")).strip() or None,
            repositories=[],
            root_path=str(root_path),
            build_ts=build_ts,
            build_root=build_root,
            dry_run=_coerce_bool(dry_run, False),
            force=False,
            profile=profile_norm,
            repo=repo_text,
            target=target_text,
        ),
    )

    log.info("Running build command (cwd=%s): %s", cwd, cmd)
    if _coerce_bool(dry_run, False):
        log.info("DRY-RUN: skipping build execution.")
        return True
    try:
        result = subprocess.run(
            shlex.split(cmd),
            cwd=cwd,
            check=False,
        )
    except (OSError, ValueError) as exc:
        log.error("Failed to run build command: %s", exc)
        return False

    if result.returncode != 0:
        log.error("Build command failed with return code %s", result.returncode)
        return False
    return True


@register(
    "project_post_build",
    needs_repositories=False,
    desc="Post-build stage for the specified project.",
)
def project_post_build(
    env: Dict,
    projects_info: Dict,
    project_name: str,
    profile: str = "full",
    repo: str = "",
    target: str = "",
    dry_run: bool = False,
) -> bool:
    """
    Post-build stage for the specified project.

    profile (str): Build profile, e.g. `full` or `single`.
    repo (str): Repo name/module for single build (optional).
    target (str): Target name for single build (optional).
    dry_run (bool): If True, only print planned actions (default: False).
    """
    log.info("Post-build stage for project: %s", project_name)
    project_info = projects_info.get(project_name, {}) if isinstance(projects_info, dict) else {}
    project_cfg = project_info.get("config", {}) if isinstance(project_info, dict) else {}

    cmd = str(project_cfg.get("PROJECT_POST_BUILD_CMD", "")).strip()
    if not cmd:
        log.info("No PROJECT_POST_BUILD_CMD configured for project: %s (skipping post-build stage)", project_name)
        return True

    root_path = env.get("root_path") or os.getcwd()
    post_cwd = str(project_cfg.get("PROJECT_POST_BUILD_CWD", "")).strip()
    cwd = _resolve_cwd(str(root_path), post_cwd)

    profile_norm = _normalise_profile(profile)
    repo_text = str(repo or "")
    target_text = str(target or "")
    build_ts = str(env.get("build_ts") or datetime.now().strftime("%Y%m%d_%H%M%S"))
    build_root = str(env.get("build_root") or "")
    cmd = _format_cmd_template(
        cmd,
        BuildContext(
            env=dict(env),
            projects_info=dict(projects_info) if isinstance(projects_info, dict) else {},
            project_name=project_name,
            project_cfg=project_cfg,
            platform=str(project_cfg.get("PROJECT_PLATFORM", "")).strip() or None,
            repositories=[],
            root_path=str(root_path),
            build_ts=build_ts,
            build_root=build_root,
            dry_run=_coerce_bool(dry_run, False),
            force=False,
            profile=profile_norm,
            repo=repo_text,
            target=target_text,
        ),
    )

    log.info("Running post-build command (cwd=%s): %s", cwd, cmd)
    if _coerce_bool(dry_run, False):
        log.info("DRY-RUN: skipping post-build execution.")
        return True
    try:
        result = subprocess.run(
            shlex.split(cmd),
            cwd=cwd,
            check=False,
        )
    except (OSError, ValueError) as exc:
        log.error("Failed to run post-build command: %s", exc)
        return False

    if result.returncode != 0:
        log.error("Post-build command failed with return code %s", result.returncode)
        return False
    return True


def build_project_build_plan(
    env: Dict[str, Any],
    projects_info: Dict[str, Any],
    project_name: str,
    *,
    sync: bool = False,
    clean: bool = False,
    profile: str = "full",
    repo: str = "",
    target: str = "",
    force: bool = False,
    no_po: bool = False,
    no_diff: bool = False,
) -> Dict[str, Any]:
    """Build a machine-readable plan for project_build without executing hooks/commands."""
    project_info = projects_info.get(project_name, {}) if isinstance(projects_info, dict) else {}
    project_cfg = project_info.get("config", {}) if isinstance(project_info, dict) else {}
    platform = str(project_cfg.get("PROJECT_PLATFORM", "")).strip() or None

    root_path = os.path.abspath(str(env.get("root_path") or os.getcwd()))
    build_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_project_name = _safe_project_name(project_name)
    build_root = os.path.join(root_path, ".cache", "build", safe_project_name, build_ts)

    ctx = BuildContext(
        env=dict(env),
        projects_info=dict(projects_info) if isinstance(projects_info, dict) else {},
        project_name=project_name,
        project_cfg=project_cfg,
        platform=platform,
        repositories=sorted(_normalise_repositories(env.get("repositories", [])), key=lambda item: item[1]),
        root_path=root_path,
        build_ts=build_ts,
        build_root=build_root,
        dry_run=True,
        force=_coerce_bool(force, False),
        profile=_normalise_profile(profile),
        repo=str(repo or ""),
        target=str(target or ""),
    )

    steps: List[Dict[str, Any]] = []

    # Clean plan
    if _coerce_bool(clean, False):
        excludes = [
            "projects",
            ".repo",
            os.path.join(".cache", "po_applied"),
        ]
        excludes.extend(_split_multiline_rules(str(project_cfg.get("PROJECT_CLEAN_EXCLUDE", ""))))
        excludes = [e for e in excludes if e]

        per_repo: List[Dict[str, Any]] = []
        for repo_path, repo_name in ctx.repositories:
            is_git = os.path.isdir(os.path.join(repo_path, ".git"))
            per_repo.append(
                {
                    "repo": repo_name,
                    "path": os.path.relpath(os.path.abspath(repo_path), start=root_path),
                    "is_git": bool(is_git),
                    "commands": (
                        []
                        if not is_git
                        else [
                            {"cmd": "git reset --hard HEAD"},
                            {"cmd": "git clean -fdx " + " ".join(f"-e {p}" for p in excludes)},
                        ]
                    ),
                }
            )
        steps.append(
            {
                "name": "repo_clean",
                "requires_force": True,
                "force_enabled": bool(_coerce_bool(force, False)),
                "excludes": excludes,
                "repositories": per_repo,
            }
        )

    # Sync plan
    if _coerce_bool(sync, False):
        sync_cmd = str(project_cfg.get("PROJECT_SYNC_CMD", "")).strip()
        if sync_cmd:
            cwd = _resolve_cwd(ctx.root_path, project_cfg.get("PROJECT_SYNC_CWD", ""))
            formatted = _format_cmd_template(sync_cmd, ctx)
            steps.append(
                {
                    "name": "repo_sync",
                    "mode": "command",
                    "cwd": os.path.relpath(os.path.abspath(cwd), start=root_path),
                    "cmd": formatted,
                }
            )
        else:
            manifest = os.path.join(ctx.root_path, ".repo", "manifest.xml")
            if os.path.exists(manifest) and shutil.which("repo"):
                steps.append({"name": "repo_sync", "mode": "repo", "cwd": ".", "cmd": "repo sync"})
            else:
                per_repo = []
                for repo_path, repo_name in ctx.repositories:
                    if not os.path.isdir(os.path.join(repo_path, ".git")):
                        continue
                    upstream = subprocess.run(
                        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
                        cwd=repo_path,
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    has_upstream = upstream.returncode == 0 and upstream.stdout.strip()
                    per_repo.append(
                        {
                            "repo": repo_name,
                            "path": os.path.relpath(os.path.abspath(repo_path), start=root_path),
                            "has_upstream": bool(has_upstream),
                            "cmd": "git pull --rebase" if has_upstream else "(skip: no upstream)",
                        }
                    )
                steps.append({"name": "repo_sync", "mode": "git", "repositories": per_repo})

    # Pre-build plan (po_apply + project_diff)
    pre_build: Dict[str, Any] = {"name": "pre_build", "timestamp": build_ts, "steps": []}
    if not _coerce_bool(no_po, False):
        pre_build["steps"].append(
            {
                "operation": "po_apply",
                "plan": build_po_apply_plan(env, projects_info, project_name, force=_coerce_bool(force, False)),
            }
        )
    else:
        pre_build["steps"].append({"operation": "po_apply", "skipped": True})

    if not _coerce_bool(no_diff, False):
        pre_build["steps"].append(
            {
                "operation": "project_diff",
                "plan": build_project_diff_plan(env, project_name, timestamp=build_ts),
            }
        )
    else:
        pre_build["steps"].append({"operation": "project_diff", "skipped": True})

    steps.append(pre_build)

    # Build stage plan
    profile_norm = _normalise_profile(profile)
    cmd = ""
    if profile_norm == "single":
        cmd = (
            str(project_cfg.get("PROJECT_BUILD_SINGLE_CMD", "")).strip()
            or str(project_cfg.get("PROJECT_BUILD_CMD_SINGLE", "")).strip()
        )
    elif profile_norm == "full":
        cmd = (
            str(project_cfg.get("PROJECT_BUILD_FULL_CMD", "")).strip()
            or str(project_cfg.get("PROJECT_BUILD_CMD_FULL", "")).strip()
        )
    cmd = cmd or str(project_cfg.get("PROJECT_BUILD_CMD", "")).strip()
    if cmd:
        build_cwd = _resolve_cwd(root_path, str(project_cfg.get("PROJECT_BUILD_CWD", "")).strip())
        steps.append(
            {
                "name": "build",
                "cwd": os.path.relpath(os.path.abspath(build_cwd), start=root_path),
                "cmd": _format_cmd_template(cmd, ctx),
                "profile": profile_norm,
                "repo": str(repo or ""),
                "target": str(target or ""),
            }
        )
    else:
        steps.append({"name": "build", "skipped": True, "reason": "PROJECT_BUILD_CMD not configured"})

    # Post-build stage plan
    post_cmd = str(project_cfg.get("PROJECT_POST_BUILD_CMD", "")).strip()
    if post_cmd:
        post_cwd = _resolve_cwd(root_path, str(project_cfg.get("PROJECT_POST_BUILD_CWD", "")).strip())
        steps.append(
            {
                "name": "post_build",
                "cwd": os.path.relpath(os.path.abspath(post_cwd), start=root_path),
                "cmd": _format_cmd_template(post_cmd, ctx),
            }
        )
    else:
        steps.append({"name": "post_build", "skipped": True})

    # Artifact collection plan
    raw_rules = str(project_cfg.get("PROJECT_BUILD_ARTIFACTS", ""))
    rules = _split_multiline_rules(raw_rules)
    steps.append(
        {
            "name": "collect_artifacts",
            "artifacts_root": os.path.relpath(os.path.join(build_root, "artifacts"), start=root_path),
            "rules": rules,
        }
    )

    return {
        "schema_version": 1,
        "generated_at": datetime.now().isoformat(),
        "operation": "project_build",
        "project_name": project_name,
        "platform": platform,
        "dry_run": True,
        "build_root": os.path.relpath(build_root, start=root_path),
        "timestamp": build_ts,
        "flags": {
            "sync": bool(_coerce_bool(sync, False)),
            "clean": bool(_coerce_bool(clean, False)),
            "profile": profile_norm,
            "repo": str(repo or ""),
            "target": str(target or ""),
            "force": bool(_coerce_bool(force, False)),
            "no_po": bool(_coerce_bool(no_po, False)),
            "no_diff": bool(_coerce_bool(no_diff, False)),
        },
        "repositories": [
            {"name": repo_name, "path": os.path.relpath(os.path.abspath(repo_path), start=root_path)}
            for repo_path, repo_name in ctx.repositories
        ],
        "steps": steps,
    }


@register(
    "project_build",
    needs_repositories=True,
    desc="Build the specified project, including pre-build, build, and post-build stages.",
)
def project_build(
    env: Dict,
    projects_info: Dict,
    project_name: str,
    sync: bool = False,
    clean: bool = False,
    profile: str = "full",
    repo: str = "",
    target: str = "",
    dry_run: bool = False,
    emit_plan: Any = False,
    force: bool = False,
    no_po: bool = False,
    no_diff: bool = False,
) -> bool:
    """
    Build the specified project, including pre-build, build, and post-build stages.

    Args:
        env: Environment variables and configuration
        projects_info: Project information dictionary
        project_name: Name of the project to build

    sync (bool): Sync repositories before build (default: False).
    clean (bool): Clean repositories before build (requires --force) (default: False).
    profile (str): Build profile, `full` (整编) or `single` (单编) (default: full).
    repo (str): Repo/module for single build (optional).
    target (str): Target for single build (optional).
    dry_run (bool): If True, only print planned actions (default: False).
    emit_plan (bool|str): Emit a machine-readable JSON plan to stdout (true) or to the given path.
    force (bool): Allow destructive actions (needed for --clean) (default: False).
    no_po (bool): Skip po_apply stage (default: False).
    no_diff (bool): Skip project_diff stage (default: False).
    """
    project_info = projects_info.get(project_name, {}) if isinstance(projects_info, dict) else {}
    project_cfg = project_info.get("config", {}) if isinstance(project_info, dict) else {}
    platform = str(project_cfg.get("PROJECT_PLATFORM", "")).strip() or None

    root_path = os.path.abspath(str(env.get("root_path") or os.getcwd()))
    build_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_project_name = _safe_project_name(project_name)
    build_root = os.path.join(root_path, ".cache", "build", safe_project_name, build_ts)

    ctx = BuildContext(
        env=env,
        projects_info=projects_info,
        project_name=project_name,
        project_cfg=project_cfg,
        platform=platform,
        repositories=_normalise_repositories(env.get("repositories", [])),
        root_path=root_path,
        build_ts=build_ts,
        build_root=build_root,
        dry_run=_coerce_bool(dry_run, False),
        force=_coerce_bool(force, False),
        profile=_normalise_profile(profile),
        repo=str(repo or ""),
        target=str(target or ""),
    )

    emit_enabled, _ = parse_emit_plan(emit_plan)
    if emit_enabled:
        payload = build_project_build_plan(
            env,
            projects_info,
            project_name,
            sync=sync,
            clean=clean,
            profile=profile,
            repo=repo,
            target=target,
            force=force,
            no_po=no_po,
            no_diff=no_diff,
        )
        emit_plan_json(payload, emit_plan)
        return True

    # Expose build metadata to hooks/steps via env for this run.
    env["build_ts"] = ctx.build_ts
    env["build_root"] = ctx.build_root

    def create_context(env: Dict, projects_info: Dict, project_name: str, platform: Optional[str] = None) -> Dict:
        """Create context dictionary for hooks."""
        return {
            "env": env,
            "projects_info": projects_info,
            "project_name": project_name,
            "platform": platform,
            "timestamp": datetime.now().isoformat(),
            "build_ts": ctx.build_ts,
            "build_root": ctx.build_root,
            "profile": ctx.profile,
            "repo": ctx.repo,
            "target": ctx.target,
            "dry_run": ctx.dry_run,
            "force": ctx.force,
        }

    def has_platform_hooks(hook_type: HookType, platform: str) -> bool:
        """Check if there are any hooks registered for the specified platform and hook type."""
        from src.hooks.registry import _platform_hooks

        return platform in _platform_hooks and hook_type.value in _platform_hooks[platform]

    # Create a single shared context for the entire build process
    shared_context = create_context(env, projects_info, project_name, platform)

    if _coerce_bool(clean, False):
        if not _repo_clean(ctx):
            return False

    if _coerce_bool(sync, False):
        if not _repo_sync(ctx):
            return False

    # Execute validation hooks if platform is specified and has hooks
    if platform and has_platform_hooks(HookType.VALIDATION, platform):
        validation_result = execute_hooks_with_fallback(HookType.VALIDATION, shared_context, platform)
        if not validation_result:
            log.error("Validation hooks failed, aborting build")
            return False

    # Execute pre-build stage
    if not project_pre_build(
        env,
        projects_info,
        project_name,
        timestamp=ctx.build_ts,
        no_po=no_po,
        no_diff=no_diff,
        dry_run=ctx.dry_run,
        force=ctx.force,
    ):
        log.error("Pre-build failed for project: %s", project_name)
        return False

    # Execute pre-build hooks if platform is specified and has hooks
    if platform and has_platform_hooks(HookType.PRE_BUILD, platform):
        pre_build_result = execute_hooks_with_fallback(HookType.PRE_BUILD, shared_context, platform)
        if not pre_build_result:
            log.error("Pre-build hooks failed, aborting build")
            return False

    # Execute build hooks if platform is specified and has hooks
    if platform and has_platform_hooks(HookType.BUILD, platform):
        build_result = execute_hooks_with_fallback(HookType.BUILD, shared_context, platform)
        if not build_result:
            log.error("Build hooks failed, aborting build")
            return False

    # Execute build stage
    if not project_do_build(
        env,
        projects_info,
        project_name,
        profile=ctx.profile,
        repo=ctx.repo,
        target=ctx.target,
        dry_run=ctx.dry_run,
    ):
        log.error("Build failed for project: %s", project_name)
        return False

    # Execute post-build hooks if platform is specified and has hooks
    if platform and has_platform_hooks(HookType.POST_BUILD, platform):
        post_build_result = execute_hooks_with_fallback(HookType.POST_BUILD, shared_context, platform)
        if not post_build_result:
            log.error("Post-build hooks failed, aborting build")
            return False

    # Execute post-build stage
    if not project_post_build(
        env,
        projects_info,
        project_name,
        profile=ctx.profile,
        repo=ctx.repo,
        target=ctx.target,
        dry_run=ctx.dry_run,
    ):
        log.error("Post-build failed for project: %s", project_name)
        return False

    if not _collect_artifacts(ctx):
        return False

    log.info("Build succeeded for project: %s", project_name)
    return True
