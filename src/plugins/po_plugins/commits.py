"""
PO plugin: commits (git format-patch + git am).
"""

from __future__ import annotations

import os
import subprocess
from typing import Any, Dict, List, Tuple

from src.log_manager import log

from .registry import (
    APPLY_PHASE_GLOBAL_PRE,
    REVERT_PHASE_GLOBAL_POST,
    register_simple_plugin,
)
from .runtime import PoPluginContext, PoPluginRuntime
from .utils import extract_patch_targets


def _apply_commits(ctx: PoPluginContext, runtime: PoPluginRuntime) -> bool:
    log.debug("po_name: '%s', po_commit_dir: '%s'", ctx.po_name, ctx.po_commit_dir)
    if not os.path.isdir(ctx.po_commit_dir):
        log.debug("No commits dir for po: '%s'", ctx.po_name)
        return True
    log.debug("applying commits for po: '%s'", ctx.po_name)

    commit_files: List[Tuple[str, str]] = []
    for current_dir, _, files in os.walk(ctx.po_commit_dir):
        for fname in files:
            if fname == ".gitkeep":
                continue
            patch_file = os.path.join(current_dir, fname)
            rel_path = os.path.relpath(patch_file, ctx.po_commit_dir)
            commit_files.append((rel_path, patch_file))

    for rel_path, patch_file in sorted(commit_files, key=lambda item: item[0]):
        path_parts = rel_path.split(os.sep)
        if len(path_parts) == 1:
            repo_name = "root"
        elif len(path_parts) >= 2:
            repo_name = os.path.join(*path_parts[:-1])
        else:
            log.error("Invalid commit file path: '%s'", rel_path)
            return False

        if ctx.po_name in ctx.exclude_files and rel_path in ctx.exclude_files[ctx.po_name]:
            log.debug(
                "commit file '%s' in po '%s' is excluded by config",
                rel_path,
                ctx.po_name,
            )
            continue

        patch_target = runtime.repo_map.get(repo_name)
        if not patch_target:
            log.error("Cannot find repo path for '%s'", repo_name)
            return False

        if not ctx.reapply and runtime.applied_record_exists(patch_target, ctx.po_name):
            log.info(
                "po '%s' already applied for repo '%s', skipping commit '%s'",
                ctx.po_name,
                repo_name,
                rel_path,
            )
            continue

        try:
            with open(patch_file, "r", encoding="utf-8") as f:
                patch_text = f.read()
        except OSError as e:
            log.error("Failed to read commit patch '%s': %s", patch_file, e)
            return False

        patch_targets = extract_patch_targets(patch_text)

        head_before = None
        if not ctx.dry_run:
            head_before_result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=patch_target,
                capture_output=True,
                text=True,
                check=False,
            )
            if head_before_result.returncode == 0:
                head_before = head_before_result.stdout.strip()

        result = runtime.execute_command(
            ctx,
            patch_target,
            repo_name,
            ["git", "am", patch_file],
            cwd=patch_target,
            description=f"Apply commit patch {os.path.basename(patch_file)} to {repo_name}",
        )
        if result.returncode != 0:
            # Make sure we clean up am state before continuing.
            runtime.execute_command(
                ctx,
                patch_target,
                repo_name,
                ["git", "am", "--abort"],
                cwd=patch_target,
                description=f"Abort failed git am for {os.path.basename(patch_file)}",
            )

            already_applied = runtime.execute_command(
                ctx,
                patch_target,
                repo_name,
                ["git", "apply", "--reverse", "--check", patch_file],
                cwd=patch_target,
                description=f"Check commit patch already applied {os.path.basename(patch_file)} to {repo_name}",
            )
            if already_applied.returncode == 0:
                log.info(
                    "Commit patch '%s' already applied for repo '%s' (record missing); skipping.",
                    rel_path,
                    repo_name,
                )
                record = runtime.get_repo_record(ctx, patch_target, repo_name)
                record["commits"].append(
                    {
                        "patch_file": os.path.relpath(patch_file, start=ctx.po_path),
                        "targets": patch_targets,
                        "status": "already_applied",
                    }
                )
                continue

            log.error("Failed to apply commit patch '%s': '%s'", patch_file, result.stderr)
            return False

        head_after = head_before
        if not ctx.dry_run:
            head_after_result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=patch_target,
                capture_output=True,
                text=True,
                check=False,
            )
            if head_after_result.returncode == 0:
                head_after = head_after_result.stdout.strip()

        commit_shas: List[str] = []
        if head_before and head_after and head_before != head_after and not ctx.dry_run:
            rev_list = subprocess.run(
                ["git", "rev-list", "--reverse", f"{head_before}..{head_after}"],
                cwd=patch_target,
                capture_output=True,
                text=True,
                check=False,
            )
            if rev_list.returncode == 0 and rev_list.stdout.strip():
                commit_shas = [line.strip() for line in rev_list.stdout.splitlines() if line.strip()]

        if not commit_shas and head_after:
            commit_shas = [head_after]

        record = runtime.get_repo_record(ctx, patch_target, repo_name)
        record["commits"].append(
            {
                "patch_file": os.path.relpath(patch_file, start=ctx.po_path),
                "targets": patch_targets,
                "head_before": head_before,
                "head_after": head_after,
                "commit_shas": commit_shas,
            }
        )

    return True


def _revert_commits(ctx: PoPluginContext, runtime: PoPluginRuntime) -> bool:
    """Revert commits applied by PO (git revert)."""
    for repo_root, repo_name in runtime.repositories or []:
        record = runtime.load_applied_record(repo_root, ctx.po_name)
        if not record:
            continue
        commits = record.get("commits") or []
        if not commits:
            continue

        repo_path = record.get("repo_path") or repo_root
        log.info("reverting commits for po '%s' in repo '%s'", ctx.po_name, repo_name)

        for commit_entry in reversed(commits):
            if commit_entry.get("status") == "already_applied":
                continue
            shas = commit_entry.get("commit_shas") or []
            if not shas and commit_entry.get("head_after"):
                shas = [commit_entry["head_after"]]

            for sha in reversed(shas):
                if not sha:
                    continue
                if ctx.dry_run:
                    log.info("DRY-RUN: cd %s && git revert --no-edit %s", repo_path, sha)
                    continue

                result = subprocess.run(
                    ["git", "revert", "--no-edit", sha],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                log.debug(
                    "git revert result: returncode: '%s', stdout: '%s', stderr: '%s'",
                    result.returncode,
                    result.stdout,
                    result.stderr,
                )
                if result.returncode != 0:
                    log.error(
                        "Failed to revert commit '%s' for po '%s' in repo '%s': %s",
                        sha,
                        ctx.po_name,
                        repo_name,
                        result.stderr,
                    )
                    # Best-effort cleanup of revert state.
                    subprocess.run(
                        ["git", "revert", "--abort"],
                        cwd=repo_path,
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    return False

    return True


def _list_commits(po_path: str, _runtime: PoPluginRuntime) -> Dict[str, Any]:
    commits_dir = os.path.join(po_path, "commits")
    commit_files: List[str] = []
    if os.path.isdir(commits_dir):
        for root, _, files in os.walk(commits_dir):
            for f in files:
                if f == ".gitkeep":
                    continue
                rel_path = os.path.relpath(os.path.join(root, f), commits_dir)
                commit_files.append(rel_path)
    return {"commit_files": sorted(commit_files)}


def _ensure_commits_dir(po_path: str, force: bool) -> None:
    if not force:
        return
    os.makedirs(os.path.join(po_path, "commits"), exist_ok=True)


register_simple_plugin(
    name="commits",
    apply_phase=APPLY_PHASE_GLOBAL_PRE,
    apply_order=10,
    revert_phase=REVERT_PHASE_GLOBAL_POST,
    revert_order=100,
    apply=_apply_commits,
    revert=_revert_commits,
    list_files=_list_commits,
    ensure_structure=_ensure_commits_dir,
)
