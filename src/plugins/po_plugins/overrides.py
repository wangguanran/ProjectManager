"""
PO plugin: overrides (cp/rm into repo working tree).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any, Dict, List, Tuple

from src.log_manager import log, summarize_output

from .registry import APPLY_PHASE_PER_PO, REVERT_PHASE_PER_PO, register_simple_plugin
from .runtime import PoPluginContext, PoPluginRuntime


def _apply_overrides(ctx: PoPluginContext, runtime: PoPluginRuntime) -> bool:
    log.debug("po_name: '%s', po_override_dir: '%s'", ctx.po_name, ctx.po_override_dir)
    if not os.path.isdir(ctx.po_override_dir):
        log.debug("No overrides dir for po: '%s'", ctx.po_name)
        return True
    log.debug("applying overrides for po: '%s'", ctx.po_name)

    repo_names = sorted(
        [name for name in runtime.repo_map.keys() if name != "root"],
        key=lambda x: len(x),
        reverse=True,
    )

    def _split_repo_prefix(rel_path: str) -> Tuple[str, str]:
        """Return (repo_name, dest_rel_in_repo) for an overrides rel_path."""
        root_prefix = f"root{os.sep}"
        if rel_path.startswith(root_prefix):
            return "root", rel_path[len(root_prefix) :]

        for repo_name in repo_names:
            prefix = f"{repo_name}{os.sep}"
            if rel_path.startswith(prefix):
                return repo_name, rel_path[len(prefix) :]
            if rel_path == repo_name:
                return repo_name, ""

        return "root", rel_path

    def _safe_dest_rel(dest_rel: str) -> str:
        # Normalize and prevent escaping repo_root. Keep it relative.
        dest_rel = dest_rel.strip()
        dest_rel = dest_rel.lstrip("/\\")
        dest_rel = os.path.normpath(dest_rel)
        if dest_rel in ("", "."):
            return ""
        if os.path.isabs(dest_rel):
            return ""
        if dest_rel.startswith("..") or f"{os.sep}.." in dest_rel:
            return ""
        return dest_rel

    def _validate_in_repo(repo_root: str, dest_rel: str) -> None:
        repo_root_real = os.path.realpath(repo_root)
        dest_abs = os.path.realpath(os.path.join(repo_root, dest_rel))
        if os.path.commonpath([repo_root_real, dest_abs]) != repo_root_real:
            raise ValueError(f"override target escapes repo_root: {dest_rel}")

    # 1) Group files by repo_root before copying/deleting
    repo_to_files: Dict[str, List[Tuple[str, str, bool]]] = {}  # (src_file, dest_rel, is_remove)
    for current_dir, _, files in os.walk(ctx.po_override_dir):
        for fname in files:
            if fname == ".gitkeep":
                continue
            rel_path = os.path.relpath(os.path.join(current_dir, fname), ctx.po_override_dir)
            log.debug("override rel_path: '%s'", rel_path)
            if ctx.po_name in ctx.exclude_files and rel_path in ctx.exclude_files[ctx.po_name]:
                log.debug(
                    "override file '%s' in po '%s' is excluded by config",
                    rel_path,
                    ctx.po_name,
                )
                continue
            src_file = os.path.join(current_dir, fname)

            # Check if this is a remove operation
            is_remove = fname.endswith(".remove")
            repo_name, dest_rel = _split_repo_prefix(rel_path)
            if is_remove:
                dest_rel = dest_rel[:-7]  # Remove '.remove' suffix
                log.debug("remove operation detected for file: '%s'", dest_rel)
            dest_rel = _safe_dest_rel(dest_rel)
            if not dest_rel:
                log.error("Invalid override target path derived from '%s'", rel_path)
                return False

            repo_root = runtime.repo_map.get(repo_name)
            if not repo_root:
                log.error("Cannot find repo path for override target repo '%s' (from '%s')", repo_name, rel_path)
                return False

            repo_to_files.setdefault(repo_root, []).append((src_file, dest_rel, is_remove))

    # 2) Perform copies/deletes per repo_root (with applied record gating)
    for repo_root, file_list in repo_to_files.items():
        repo_root_abs = os.path.abspath(repo_root)
        record_repo_name = runtime.repo_path_to_name.get(repo_root_abs, "unknown")
        if not ctx.reapply and runtime.applied_record_exists(repo_root_abs, ctx.po_name):
            log.info("po '%s' already applied for repo '%s', skipping overrides", ctx.po_name, record_repo_name)
            continue

        log.debug("override repo_root: '%s'", repo_root)
        for src_file, dest_rel, is_remove in file_list:
            log.debug("override src_file: '%s', dest_rel: '%s', is_remove: %s", src_file, dest_rel, is_remove)
            try:
                _validate_in_repo(repo_root, dest_rel)
            except ValueError as e:
                log.error("%s", e)
                return False

            record = runtime.get_repo_record(ctx, repo_root_abs, record_repo_name)
            record["overrides"].append(
                {
                    "operation": "remove" if is_remove else "copy",
                    "po_source": os.path.relpath(src_file, start=ctx.po_path),
                    "path_in_repo": dest_rel,
                }
            )

            if is_remove:
                # Perform delete operation
                try:
                    if not ctx.force and not ctx.dry_run:
                        log.error(
                            "Refusing to remove '%s' without --force (override .remove safeguard)",
                            dest_rel,
                        )
                        return False

                    # Check if target file exists
                    if os.path.exists(os.path.join(repo_root, dest_rel)):
                        # Use execute_command for delete operation
                        result = runtime.execute_command(
                            ctx,
                            repo_root_abs,
                            record_repo_name,
                            ["rm", "-rf", dest_rel],
                            cwd=repo_root,
                            description=f"Remove file {dest_rel}",
                        )

                        if result.returncode != 0:
                            log.error("Failed to remove file '%s': %s", dest_rel, summarize_output(result.stderr))
                            return False

                        log.info("Removed file '%s' (repo_root=%s)", dest_rel, repo_root)
                    else:
                        log.debug("File '%s' does not exist, skipping removal", dest_rel)
                except OSError as e:
                    log.error("Failed to remove file '%s': '%s'", dest_rel, e)
                    return False
            else:
                # Perform copy operation
                dest_dir = os.path.dirname(dest_rel)
                if not ctx.dry_run and dest_dir:
                    os.makedirs(os.path.join(repo_root, dest_dir), exist_ok=True)
                try:
                    # Use execute_command for copy operation
                    result = runtime.execute_command(
                        ctx,
                        repo_root_abs,
                        record_repo_name,
                        ["cp", "-rf", src_file, dest_rel],
                        cwd=repo_root,
                        description="Copy override file",
                    )

                    if result.returncode != 0:
                        log.error(
                            "Failed to copy override file '%s' to '%s': %s",
                            src_file,
                            dest_rel,
                            summarize_output(result.stderr),
                        )
                        return False

                    log.info("Copied override file '%s' to '%s' (repo_root=%s)", src_file, dest_rel, repo_root)
                except OSError as e:
                    log.error("Failed to copy override file '%s' to '%s': '%s'", src_file, dest_rel, e)
                    return False

    return True


def _revert_overrides(ctx: PoPluginContext, runtime: PoPluginRuntime) -> bool:
    log.debug("po_name: '%s', po_override_dir: '%s'", ctx.po_name, ctx.po_override_dir)
    if not os.path.isdir(ctx.po_override_dir):
        log.debug("No overrides dir for po: '%s'", ctx.po_name)
        return True
    log.debug("reverting overrides for po: '%s'", ctx.po_name)

    repo_names = sorted(
        [name for name in runtime.repo_map.keys() if name != "root"],
        key=lambda x: len(x),
        reverse=True,
    )

    def _split_repo_prefix(rel_path: str) -> Tuple[str, str]:
        root_prefix = f"root{os.sep}"
        if rel_path.startswith(root_prefix):
            return "root", rel_path[len(root_prefix) :]
        for repo_name in repo_names:
            prefix = f"{repo_name}{os.sep}"
            if rel_path.startswith(prefix):
                return repo_name, rel_path[len(prefix) :]
            if rel_path == repo_name:
                return repo_name, ""
        return "root", rel_path

    def _safe_dest_rel(dest_rel: str) -> str:
        dest_rel = dest_rel.strip()
        dest_rel = dest_rel.lstrip("/\\")
        dest_rel = os.path.normpath(dest_rel)
        if dest_rel in ("", "."):
            return ""
        if os.path.isabs(dest_rel):
            return ""
        if dest_rel.startswith("..") or f"{os.sep}.." in dest_rel:
            return ""
        return dest_rel

    def _validate_in_repo(repo_root: str, dest_rel: str) -> None:
        repo_root_real = os.path.realpath(repo_root)
        dest_abs = os.path.realpath(os.path.join(repo_root, dest_rel))
        if os.path.commonpath([repo_root_real, dest_abs]) != repo_root_real:
            raise ValueError(f"override target escapes repo_root: {dest_rel}")

    for current_dir, _, files in os.walk(ctx.po_override_dir):
        for fname in files:
            if fname == ".gitkeep":
                continue
            rel_path = os.path.relpath(os.path.join(current_dir, fname), ctx.po_override_dir)
            log.debug("override rel_path: '%s'", rel_path)
            if ctx.po_name in ctx.exclude_files and rel_path in ctx.exclude_files[ctx.po_name]:
                log.debug(
                    "override file '%s' in po '%s' is excluded by config",
                    rel_path,
                    ctx.po_name,
                )
                continue

            repo_name, dest_rel = _split_repo_prefix(rel_path)
            if fname.endswith(".remove"):
                dest_rel = dest_rel[:-7]
            dest_rel = _safe_dest_rel(dest_rel)
            if not dest_rel:
                log.error("Invalid override target path derived from '%s'", rel_path)
                return False

            repo_root = runtime.repo_map.get(repo_name)
            if not repo_root:
                log.error("Cannot find repo path for override target repo '%s' (from '%s')", repo_name, rel_path)
                return False

            try:
                _validate_in_repo(repo_root, dest_rel)
            except ValueError as e:
                log.error("%s", e)
                return False

            dest_abs = os.path.join(repo_root, dest_rel)
            log.debug("override dest_abs: '%s'", dest_abs)
            log.info("reverting override file: '%s' (repo_root=%s)", dest_rel, repo_root)
            try:
                result = subprocess.run(
                    ["git", "ls-files", "--error-unmatch", dest_rel],
                    cwd=repo_root,
                    capture_output=True,
                    text=True,
                    check=False,
                )

                if result.returncode == 0:
                    if ctx.dry_run:
                        log.info("DRY-RUN: cd %s && git checkout -- %s", repo_root, dest_rel)
                        continue
                    result = subprocess.run(
                        ["git", "checkout", "--", dest_rel],
                        cwd=repo_root,
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    log.debug(
                        "git checkout result: returncode=%s stdout=%s stderr=%s",
                        result.returncode,
                        summarize_output(result.stdout),
                        summarize_output(result.stderr),
                    )
                    if result.returncode != 0:
                        log.error("Failed to revert override file '%s': %s", dest_rel, summarize_output(result.stderr))
                        return False
                elif os.path.exists(dest_abs):
                    log.debug("File '%s' is not tracked by git, deleting directly", dest_rel)
                    if ctx.dry_run:
                        log.info("DRY-RUN: cd %s && rm -rf %s", repo_root, dest_rel)
                        continue
                    if os.path.isdir(dest_abs):
                        shutil.rmtree(dest_abs)
                    else:
                        os.remove(dest_abs)
                else:
                    log.debug("Override file '%s' does not exist, skipping", dest_abs)
                    continue

                log.info("override reverted for dir: '%s', file: '%s'", repo_root, dest_rel)
            except subprocess.SubprocessError as e:
                log.error("Subprocess error reverting override file '%s': '%s'", dest_rel, e)
                return False
            except OSError as e:
                log.error("OS error reverting override file '%s': '%s'", dest_rel, e)
                return False
    return True


def _list_overrides(po_path: str, _runtime: PoPluginRuntime) -> Dict[str, Any]:
    overrides_dir = os.path.join(po_path, "overrides")
    override_files: List[str] = []
    if os.path.isdir(overrides_dir):
        for root, _, files in os.walk(overrides_dir):
            for f in files:
                if f == ".gitkeep":
                    continue
                rel_path = os.path.relpath(os.path.join(root, f), overrides_dir)
                override_files.append(rel_path)
    return {"override_files": sorted(override_files)}


def _ensure_overrides_dir(po_path: str, force: bool) -> None:
    if not force:
        return
    os.makedirs(os.path.join(po_path, "overrides"), exist_ok=True)


register_simple_plugin(
    name="overrides",
    apply_phase=APPLY_PHASE_PER_PO,
    apply_order=30,
    revert_phase=REVERT_PHASE_PER_PO,
    revert_order=30,
    apply=_apply_overrides,
    revert=_revert_overrides,
    list_files=_list_overrides,
    ensure_structure=_ensure_overrides_dir,
)
