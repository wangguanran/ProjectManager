"""
PO plugin: patches (git apply).
"""

from __future__ import annotations

import os
import subprocess
from typing import Any, Dict, List

from src.log_manager import log, summarize_output

from .registry import APPLY_PHASE_PER_PO, REVERT_PHASE_PER_PO, register_simple_plugin
from .runtime import PoPluginContext, PoPluginRuntime
from .utils import extract_patch_targets


def _apply_patches(ctx: PoPluginContext, runtime: PoPluginRuntime) -> bool:
    log.debug("po_name: '%s', po_patch_dir: '%s'", ctx.po_name, ctx.po_patch_dir)
    if not os.path.isdir(ctx.po_patch_dir):
        log.debug("No patches dir for po: '%s'", ctx.po_name)
        return True
    log.debug("applying patches for po: '%s'", ctx.po_name)

    for current_dir, _, files in os.walk(ctx.po_patch_dir):
        for fname in files:
            if fname == ".gitkeep":
                continue
            rel_path = os.path.relpath(os.path.join(current_dir, fname), ctx.po_patch_dir)
            path_parts = rel_path.split(os.sep)
            if len(path_parts) == 1:
                repo_name = "root"
            elif len(path_parts) >= 2:
                repo_name = os.path.join(*path_parts[:-1])
            else:
                log.error("Invalid patch file path: '%s'", rel_path)
                return False

            if ctx.po_name in ctx.exclude_files and rel_path in ctx.exclude_files[ctx.po_name]:
                log.debug(
                    "patch file '%s' in po '%s' is excluded by config",
                    rel_path,
                    ctx.po_name,
                )
                continue

            patch_target = runtime.repo_map.get(repo_name)
            if not patch_target:
                log.error("Cannot find repo path for '%s'", repo_name)
                return False

            patch_file = os.path.join(current_dir, fname)
            log.debug("will apply patch: '%s' to repo: '%s'", patch_file, patch_target)
            if not ctx.reapply and runtime.applied_record_exists(patch_target, ctx.po_name):
                log.info(
                    "po '%s' already applied for repo '%s', skipping patch '%s'",
                    ctx.po_name,
                    repo_name,
                    rel_path,
                )
                continue

            try:
                with open(patch_file, "r", encoding="utf-8") as f:
                    patch_targets = extract_patch_targets(f.read())
            except OSError as e:
                log.error("Failed to read patch '%s': %s", patch_file, e)
                return False

            record = runtime.get_repo_record(ctx, patch_target, repo_name)
            record["patches"].append(
                {
                    "patch_file": os.path.relpath(patch_file, start=ctx.po_path),
                    "targets": patch_targets,
                }
            )

            result = runtime.execute_command(
                ctx,
                patch_target,
                repo_name,
                ["git", "apply", patch_file],
                cwd=patch_target,
                description=f"Apply patch {os.path.basename(patch_file)} to {repo_name}",
            )
            log.info("applying patch: '%s' to repo: '%s'", patch_file, patch_target)
            log.debug(
                "git apply result: returncode=%s stdout=%s stderr=%s",
                result.returncode,
                summarize_output(result.stdout),
                summarize_output(result.stderr),
            )
            if result.returncode != 0:
                already_applied = runtime.execute_command(
                    ctx,
                    patch_target,
                    repo_name,
                    ["git", "apply", "--reverse", "--check", patch_file],
                    cwd=patch_target,
                    description=f"Check patch already applied {os.path.basename(patch_file)} to {repo_name}",
                )
                if already_applied.returncode == 0:
                    log.info(
                        "Patch '%s' already applied for repo '%s' (record missing); skipping.",
                        rel_path,
                        repo_name,
                    )
                    continue

                log.error("Failed to apply patch '%s': %s", patch_file, summarize_output(result.stderr))
                return False

            log.info("patch applied successfully for repo: '%s'", patch_target)

    return True


def _revert_patches(ctx: PoPluginContext, runtime: PoPluginRuntime) -> bool:
    log.debug("po_name: '%s', po_patch_dir: '%s'", ctx.po_name, ctx.po_patch_dir)
    if not os.path.isdir(ctx.po_patch_dir):
        log.debug("No patches dir for po: '%s'", ctx.po_name)
        return True
    log.debug("reverting patches for po: '%s'", ctx.po_name)

    for current_dir, _, files in os.walk(ctx.po_patch_dir):
        log.debug("current_dir: '%s', files: '%s'", current_dir, files)
        for fname in files:
            if fname == ".gitkeep":
                continue
            log.debug("current_dir: '%s', fname: '%s'", current_dir, fname)
            rel_path = os.path.relpath(os.path.join(current_dir, fname), ctx.po_patch_dir)
            log.debug("patch rel_path: '%s'", rel_path)
            if ctx.po_name in ctx.exclude_files and rel_path in ctx.exclude_files[ctx.po_name]:
                log.debug(
                    "patch file '%s' in po '%s' is excluded by config",
                    rel_path,
                    ctx.po_name,
                )
                continue
            path_parts = rel_path.split(os.sep)
            if len(path_parts) == 1:
                repo_name = "root"
            elif len(path_parts) >= 2:
                repo_name = os.path.join(*path_parts[:-1])
            else:
                log.error("Invalid patch file path: '%s'", rel_path)
                return False

            patch_target = runtime.repo_map.get(repo_name)
            if not patch_target:
                log.error("Cannot find repo path for '%s'", repo_name)
                return False
            patch_file = os.path.join(current_dir, fname)
            log.info("reverting patch: '%s' from dir: '%s'", patch_file, patch_target)
            try:
                if ctx.dry_run:
                    log.info("DRY-RUN: cd %s && git apply --reverse %s", patch_target, patch_file)
                    continue
                result = subprocess.run(
                    ["git", "apply", "--reverse", patch_file],
                    cwd=patch_target,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                log.debug(
                    "git apply --reverse result: returncode=%s stdout=%s stderr=%s",
                    result.returncode,
                    summarize_output(result.stdout),
                    summarize_output(result.stderr),
                )
                if result.returncode != 0:
                    log.error("Failed to revert patch '%s': %s", patch_file, summarize_output(result.stderr))
                    return False
                log.info("patch reverted for dir: '%s'", patch_target)
            except subprocess.SubprocessError as e:
                log.error("Subprocess error reverting patch '%s': '%s'", patch_file, e)
                return False
            except OSError as e:
                log.error("OS error reverting patch '%s': '%s'", patch_file, e)
                return False
    return True


def _list_patches(po_path: str, _runtime: PoPluginRuntime) -> Dict[str, Any]:
    patches_dir = os.path.join(po_path, "patches")
    patch_files: List[str] = []
    if os.path.isdir(patches_dir):
        for root, _, files in os.walk(patches_dir):
            for f in files:
                if f == ".gitkeep":
                    continue
                rel_path = os.path.relpath(os.path.join(root, f), patches_dir)
                patch_files.append(rel_path)
    return {"patch_files": sorted(patch_files)}


def _ensure_patches_dir(po_path: str, force: bool) -> None:
    if not force:
        return
    os.makedirs(os.path.join(po_path, "patches"), exist_ok=True)


register_simple_plugin(
    name="patches",
    apply_phase=APPLY_PHASE_PER_PO,
    apply_order=20,
    revert_phase=REVERT_PHASE_PER_PO,
    revert_order=20,
    apply=_apply_patches,
    revert=_revert_patches,
    list_files=_list_patches,
    ensure_structure=_ensure_patches_dir,
)
