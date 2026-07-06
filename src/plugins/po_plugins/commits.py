"""
PO plugin: commits (git format-patch + git am -k --keep-cr).
"""

from __future__ import annotations

import os
import re
import subprocess
from typing import Any, Dict, List, Optional, Tuple

from src.log_manager import log, summarize_output

from .registry import (
    APPLY_PHASE_GLOBAL_PRE,
    REVERT_PHASE_GLOBAL_POST,
    register_simple_plugin,
)
from .runtime import PoPluginContext, PoPluginRuntime
from .utils import SKIPPED_COMMIT_STATUSES, extract_patch_targets, resolve_commit_reset_target
FORMAT_PATCH_SUBJECT_PREFIX_RE = re.compile(r"^\[PATCH(?:\s+\d+/\d+)?\]\s*")


def _strip_format_patch_subject_prefix(message: str) -> str:
    """Remove git format-patch default subject prefix from commit message."""
    if not message:
        return message
    lines = message.splitlines()
    if not lines:
        return message
    new_first = FORMAT_PATCH_SUBJECT_PREFIX_RE.sub("", lines[0], count=1)
    if new_first == lines[0]:
        return message
    lines[0] = new_first
    rebuilt = "\n".join(lines)
    if message.endswith("\n"):
        rebuilt += "\n"
    return rebuilt


def _amend_head_commit_message(repo_path: str, new_message: str) -> bool:
    result = subprocess.run(
        ["git", "commit", "--amend", "-m", new_message],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        log.error(
            "Failed to amend commit message in '%s': %s",
            repo_path,
            summarize_output(result.stderr),
        )
        return False
    return True


def _normalize_head_commit_subject_after_am(repo_path: str) -> bool:
    result = subprocess.run(
        ["git", "log", "-1", "--format=%B"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        log.error("Failed to read HEAD commit message in '%s'", repo_path)
        return False

    original_message = result.stdout
    normalized_message = _strip_format_patch_subject_prefix(original_message)
    if normalized_message == original_message:
        return True

    log.debug("Stripping format-patch [PATCH] prefix from HEAD commit in '%s'", repo_path)
    return _amend_head_commit_message(repo_path, normalized_message)


def _extract_original_commit_sha(patch_text: str) -> Optional[str]:
    match = re.search(r"^From ([0-9a-fA-F]{7,40})\b", patch_text, re.MULTILINE)
    if not match:
        return None
    return match.group(1).lower()


def _repo_history_contains_commit(repo_path: str, commit_sha: str) -> bool:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit_sha, "HEAD"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


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
        original_commit_sha = _extract_original_commit_sha(patch_text)

        if original_commit_sha and _repo_history_contains_commit(patch_target, original_commit_sha):
            log.info(
                "Commit patch '%s' already exists in history for repo '%s' via sha '%s'; skipping.",
                rel_path,
                repo_name,
                original_commit_sha,
            )
            record = runtime.get_repo_record(ctx, patch_target, repo_name)
            record["commits"].append(
                {
                    "patch_file": os.path.relpath(patch_file, start=ctx.po_path),
                    "targets": patch_targets,
                    "status": "already_in_history",
                    "original_commit_sha": original_commit_sha,
                }
            )
            continue

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
            ["git", "am", "-k", "--keep-cr", patch_file],
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
                        "original_commit_sha": original_commit_sha,
                    }
                )
                continue

            log.error("Failed to apply commit patch '%s': %s", patch_file, summarize_output(result.stderr))
            return False

        if not ctx.dry_run and not _normalize_head_commit_subject_after_am(patch_target):
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
                "original_commit_sha": original_commit_sha,
            }
        )

    return True


def _revert_commits(ctx: PoPluginContext, runtime: PoPluginRuntime) -> bool:
    """Remove commits applied by PO by resetting to the recorded pre-apply HEAD."""
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
            if commit_entry.get("status") in SKIPPED_COMMIT_STATUSES:
                continue

            head_after = commit_entry.get("head_after")
            reset_target = resolve_commit_reset_target(repo_path, commit_entry)
            if not reset_target:
                log.warning(
                    "No reset target recorded for commit entry in po '%s' repo '%s'; skipping",
                    ctx.po_name,
                    repo_name,
                )
                continue

            if head_after and not _repo_history_contains_commit(repo_path, head_after):
                log.warning(
                    "Applied commit '%s' is no longer in history for repo '%s'; skipping reset to '%s'",
                    head_after,
                    repo_name,
                    reset_target,
                )
                continue

            if ctx.dry_run:
                log.info("DRY-RUN: cd %s && git reset --hard %s", repo_path, reset_target)
                continue

            result = subprocess.run(
                ["git", "reset", "--hard", reset_target],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=False,
            )
            log.debug(
                "git reset --hard result: returncode=%s stdout=%s stderr=%s",
                result.returncode,
                summarize_output(result.stdout),
                summarize_output(result.stderr),
            )
            if result.returncode != 0:
                log.error(
                    "Failed to reset repo '%s' to '%s' for po '%s': %s",
                    repo_name,
                    reset_target,
                    ctx.po_name,
                    summarize_output(result.stderr),
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
