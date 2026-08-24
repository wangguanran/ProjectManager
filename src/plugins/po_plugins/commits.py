"""
PO plugin: commits (git format-patch + git am -k --keep-cr).
"""

from __future__ import annotations

import os
import re
import subprocess
from typing import Any, Dict, List, Optional, Tuple, cast

from src.log_manager import log, summarize_output

from .registry import (
    APPLY_PHASE_GLOBAL_PRE,
    REVERT_PHASE_GLOBAL_POST,
    register_simple_plugin,
)
from .runtime import PoPluginContext, PoPluginRuntime
from .utils import (
    SKIPPED_COMMIT_STATUSES,
    extract_patch_targets,
    redact_patch_diagnostic,
    resolve_commit_reset_target,
)

FORMAT_PATCH_SUBJECT_PREFIX_RE = re.compile(
    r"^\[(?:(?:RFC\s+PATCH)|(?:PATCH(?:\s+RFC)?))(?:\s+v\d+)?(?:\s+\d+/\d+)?\]\s*"
)


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


def _amend_head_commit_message(
    repo_path: str,
    new_message: str,
    *,
    repo_name: str,
    rel_path: str,
    patch_file: str,
) -> bool:
    result = subprocess.run(
        ["git", "commit", "--amend", "-m", new_message],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        log.error(
            "Failed to amend commit message for patch '%s' in repo '%s': %s",
            rel_path,
            repo_name,
            summarize_output(
                redact_patch_diagnostic(
                    result.stderr,
                    patch_file=patch_file,
                    patch_target=repo_path,
                    rel_path=rel_path,
                    repo_name=repo_name,
                )
            ),
        )
        return False
    return True


def _normalize_head_commit_subject_after_am(
    repo_path: str,
    *,
    repo_name: str,
    rel_path: str,
    patch_file: str,
) -> bool:
    result = subprocess.run(
        ["git", "log", "-1", "--format=%B"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        log.error(
            "Failed to read HEAD commit message for patch '%s' in repo '%s': %s",
            rel_path,
            repo_name,
            summarize_output(
                redact_patch_diagnostic(
                    result.stderr,
                    patch_file=patch_file,
                    patch_target=repo_path,
                    rel_path=rel_path,
                    repo_name=repo_name,
                )
            ),
        )
        return False

    original_message = result.stdout
    normalized_message = _strip_format_patch_subject_prefix(original_message)
    if normalized_message == original_message:
        return True

    log.debug("Stripping format-patch [PATCH] prefix from HEAD commit")
    return _amend_head_commit_message(
        repo_path,
        normalized_message,
        repo_name=repo_name,
        rel_path=rel_path,
        patch_file=patch_file,
    )


def _resolve_commit(repo_path: str, revision: str) -> Optional[str]:
    if not revision:
        return None
    result = subprocess.run(
        ["git", "rev-parse", "--verify", f"{revision}^{{commit}}"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def inspect_commit_revert_chain(
    repo_path: str,
    po_name: str,
    commit_entries: List[Dict[str, Any]],
    expected_head: Optional[str] = None,
) -> Tuple[List[Dict[str, str]], Optional[str]]:
    """Validate that recorded commit entries form the current removable stack top."""
    active_entries = [entry for entry in commit_entries if entry.get("status") not in SKIPPED_COMMIT_STATUSES]
    if not active_entries:
        return [], expected_head
    current_head = expected_head or _resolve_commit(repo_path, "HEAD")
    blockers: List[Dict[str, str]] = []
    for entry in reversed(active_entries):
        head_after = str(entry.get("head_after") or "")
        reset_target = str(resolve_commit_reset_target(repo_path, entry) or "")
        reason = ""
        if not head_after:
            reason = "missing head_after"
        elif not _resolve_commit(repo_path, head_after):
            reason = f"head_after '{head_after}' is not a valid commit"
        elif not reset_target:
            reason = "missing reset target"
        elif not _resolve_commit(repo_path, reset_target):
            reason = f"reset target '{reset_target}' is not a valid commit"
        elif not current_head:
            reason = "cannot resolve current HEAD"
        elif head_after != current_head:
            reason = f"current stack top is '{current_head}', expected '{head_after}'"

        if reason:
            blockers.append(
                {
                    "po": po_name,
                    "repo": repo_path,
                    "head_after": head_after,
                    "reset_to": reset_target,
                    "reason": reason,
                }
            )
            break
        current_head = reset_target
    return blockers, current_head


def tracked_worktree_is_clean(repo_path: str) -> bool:
    """Return whether tracked staged and unstaged changes are absent."""
    for command in (["git", "diff", "--quiet"], ["git", "diff", "--cached", "--quiet"]):
        if subprocess.run(command, cwd=repo_path, capture_output=True, check=False).returncode != 0:
            return False
    return True


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
    log.debug("checking commit patches for po: '%s'", ctx.po_name)
    if not os.path.isdir(ctx.po_commit_dir):
        log.debug("No commits dir for po: '%s'", ctx.po_name)
        return True
    log.info("applying commits for po: '%s'", ctx.po_name)

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
            log.error(
                "Failed to read commit patch '%s' for repo '%s': %s",
                rel_path,
                repo_name,
                redact_patch_diagnostic(
                    e,
                    patch_file=patch_file,
                    patch_target=patch_target,
                    rel_path=rel_path,
                    repo_name=repo_name,
                ),
            )
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

        if ctx.dry_run:
            log.info("planned git am commit patch: '%s' to repo: '%s'", rel_path, repo_name)
            result = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        else:
            log.info("applying commit patch: '%s' to repo: '%s'", rel_path, repo_name)
            result = runtime.execute_command(
                ctx,
                patch_target,
                repo_name,
                ["git", "am", "-k", "--keep-cr", patch_file],
                cwd=patch_target,
                description=f"Apply commit patch {os.path.basename(patch_file)} to {repo_name}",
                log_command=["git", "am", "-k", "--keep-cr", rel_path],
                log_cwd=repo_name,
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
                log_command=["git", "am", "--abort"],
                log_cwd=repo_name,
            )

            already_applied = runtime.execute_command(
                ctx,
                patch_target,
                repo_name,
                ["git", "apply", "--reverse", "--check", patch_file],
                cwd=patch_target,
                description=f"Check commit patch already applied {os.path.basename(patch_file)} to {repo_name}",
                log_command=["git", "apply", "--reverse", "--check", rel_path],
                log_cwd=repo_name,
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

            log.error(
                "Failed to apply commit patch '%s' to repo '%s': %s",
                rel_path,
                repo_name,
                summarize_output(
                    redact_patch_diagnostic(
                        result.stderr,
                        patch_file=patch_file,
                        patch_target=patch_target,
                        rel_path=rel_path,
                        repo_name=repo_name,
                    )
                ),
            )
            return False

        if not ctx.dry_run and not _normalize_head_commit_subject_after_am(
            patch_target,
            repo_name=repo_name,
            rel_path=rel_path,
            patch_file=patch_file,
        ):
            record = runtime.get_repo_record(ctx, patch_target, repo_name)
            prior_commits = record.get("commits") or []
            rollback_target = (
                next(
                    (
                        entry.get("head_before")
                        for entry in prior_commits
                        if entry.get("status") not in SKIPPED_COMMIT_STATUSES
                        and entry.get("head_before")
                        and _resolve_commit(patch_target, str(entry["head_before"]))
                    ),
                    None,
                )
                or head_before
            )
            rollback = subprocess.run(
                (
                    ["git", "reset", "--hard", rollback_target]
                    if rollback_target
                    else ["git", "rev-parse", "--verify", "HEAD"]
                ),
                cwd=patch_target,
                capture_output=True,
                text=True,
                check=False,
            )
            if rollback_target and rollback.returncode == 0:
                log.error(
                    "Commit subject normalization failed for '%s'; restored repo '%s' to '%s'",
                    rel_path,
                    repo_name,
                    rollback_target,
                )
                return False

            recovery_head = _resolve_commit(patch_target, "HEAD")
            record["commits"].append(
                {
                    "patch_file": os.path.relpath(patch_file, start=ctx.po_path),
                    "targets": patch_targets,
                    "status": "normalization_failed",
                    "head_before": head_before,
                    "head_after": recovery_head,
                    "commit_shas": [recovery_head] if recovery_head else [],
                    "original_commit_sha": original_commit_sha,
                }
            )
            runtime.finalize_records(ctx)
            log.error(
                "Commit subject normalization failed for '%s' in repo '%s' and rollback failed; recovery state was recorded",
                rel_path,
                repo_name,
            )
            return False

        if not ctx.dry_run:
            log.info("commit patch applied successfully: '%s' to repo: '%s'", rel_path, repo_name)
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
        active_commits = [entry for entry in commits if entry.get("status") not in SKIPPED_COMMIT_STATUSES]
        if not active_commits:
            continue

        repo_path = record.get("repo_path") or repo_root
        log.info("reverting commits for po '%s' in repo '%s'", ctx.po_name, repo_name)

        blockers, _ = inspect_commit_revert_chain(repo_path, ctx.po_name, active_commits)
        if blockers:
            log.error(
                "Cannot safely revert commit po '%s' in repo '%s': %s", ctx.po_name, repo_name, blockers[0]["reason"]
            )
            return False
        if not ctx.dry_run and not tracked_worktree_is_clean(repo_path):
            log.error(
                "Cannot safely revert commit po '%s' in repo '%s': tracked worktree or index is dirty",
                ctx.po_name,
                repo_name,
            )
            return False

        for commit_entry in reversed(active_commits):
            reset_target = cast(str, resolve_commit_reset_target(repo_path, commit_entry))

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
