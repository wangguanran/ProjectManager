"""
PO plugin: custom file copy rules (PROJECT_PO_DIR / PROJECT_PO_FILE_COPY).
"""

from __future__ import annotations

import glob
import os
from typing import Any, Dict, List

from src.log_manager import log

from .registry import APPLY_PHASE_PER_PO, REVERT_PHASE_PER_PO, register_simple_plugin
from .runtime import PoPluginContext, PoPluginRuntime


def _apply_custom(ctx: PoPluginContext, runtime: PoPluginRuntime) -> bool:
    log.debug("po_name: '%s', po_custom_dir: '%s'", ctx.po_name, ctx.po_custom_dir)
    if not os.path.isdir(ctx.po_custom_dir):
        log.debug("No custom dir for po: '%s'", ctx.po_name)
        return True
    log.debug("applying custom for po: '%s'", ctx.po_name)

    if not isinstance(runtime.po_configs, dict) or not runtime.po_configs:
        log.debug("No po_configs provided for custom apply of po: '%s'", ctx.po_name)
        return True

    def _execute_file_copy(section_name: str, section_custom_dir: str, source_pattern: str, target_path: str) -> bool:
        """Execute a single file copy operation with wildcard and directory support.

        - Expands *, ?, [], and ** patterns via glob (no shell).
        - Uses `cp -rf` with shell=False to handle file/dir copies safely.
        """
        log.debug("Executing file copy: source='%s', target='%s'", source_pattern, target_path)

        abs_pattern = os.path.join(section_custom_dir, source_pattern)
        record_repo = runtime.resolve_repo_for_target_path(target_path)
        if record_repo is None:
            record_repo_root = runtime.workspace_root
            record_repo_name = "workspace"
            path_in_repo = None
        else:
            record_repo_root, record_repo_name, path_in_repo = record_repo

        if not ctx.reapply and runtime.applied_record_exists(record_repo_root, ctx.po_name):
            log.info(
                "po '%s' already applied for repo '%s', skipping custom copy to '%s'",
                ctx.po_name,
                record_repo_name,
                target_path,
            )
            return True

        record = runtime.get_repo_record(ctx, record_repo_root, record_repo_name)
        record["custom"].append(
            {
                "section": section_name,
                "source": source_pattern,
                "target": target_path,
                "path_in_repo": path_in_repo,
            }
        )

        try:
            matches = glob.glob(abs_pattern, recursive=True)
            if not matches:
                log.error("No files matched pattern '%s' (abs: '%s')", source_pattern, abs_pattern)
                return False

            # Determine a stable base directory so we can preserve relative paths when using patterns
            # like "data/**/file" (without relying on shell expansion).
            glob_markers = ["*", "?", "["]
            first_marker = min(
                (abs_pattern.find(m) for m in glob_markers if m in abs_pattern),
                default=-1,
            )
            if first_marker == -1:
                base_dir = os.path.dirname(abs_pattern)
            else:
                base_dir = os.path.dirname(abs_pattern[:first_marker])
            if not base_dir:
                base_dir = section_custom_dir

            # Determine if target should be treated as a directory.
            target_is_dir = target_path.endswith(os.sep) or os.path.isdir(target_path) or len(matches) > 1
            if not ctx.dry_run and target_is_dir and not os.path.exists(target_path):
                os.makedirs(target_path.rstrip(os.sep), exist_ok=True)

            for src in matches:
                if target_is_dir:
                    rel = os.path.relpath(src, base_dir)
                    dest = os.path.join(target_path, rel)
                else:
                    dest = target_path

                dest_dir = os.path.dirname(dest)
                if not ctx.dry_run and dest_dir:
                    os.makedirs(dest_dir, exist_ok=True)

                result = runtime.execute_command(
                    ctx,
                    record_repo_root,
                    record_repo_name,
                    ["cp", "-rf", src, dest],
                    description="Copy custom file",
                    shell=False,
                )
                if result.returncode != 0:
                    log.error("Failed to copy '%s' to '%s': %s", src, dest, result.stderr)
                    return False

            return True
        except OSError as e:
            log.error("Failed to copy '%s' to '%s': %s", abs_pattern, target_path, e)
            return False

    for section_name, section_config in runtime.po_configs.items():
        # Only apply the configuration that matches the current PO name.
        if section_name != f"po-{ctx.po_name}":
            continue

        po_config_dict = section_config
        po_subdir = str(po_config_dict.get("PROJECT_PO_DIR", "") or "").rstrip("/")

        # `PROJECT_PO_DIR` is relative to the PO root (not to `custom/`).
        po_root = os.path.dirname(ctx.po_custom_dir)
        section_custom_dir = os.path.join(po_root, po_subdir) if po_subdir else ctx.po_custom_dir
        if not os.path.isdir(section_custom_dir):
            log.debug(
                "Custom directory '%s' not found for po '%s' (section '%s')",
                section_custom_dir,
                ctx.po_name,
                section_name,
            )
            continue

        log.info(
            "Processing custom po '%s' with directory '%s' (from section '%s')",
            ctx.po_name,
            (
                os.path.relpath(section_custom_dir, start=os.path.join(os.path.dirname(ctx.po_custom_dir), ctx.po_name))
                if os.path.isdir(section_custom_dir)
                else section_custom_dir
            ),
            section_name,
        )

        file_copy_config = str(po_config_dict.get("PROJECT_PO_FILE_COPY", "") or "")
        if not file_copy_config:
            log.warning(
                "No PROJECT_PO_FILE_COPY configuration found for po: '%s' (section '%s')",
                ctx.po_name,
                section_name,
            )
            continue

        log.debug("File copy config for po '%s': '%s'", ctx.po_name, file_copy_config)

        # Parse file copy configuration
        copy_rules: List[tuple[str, str]] = []
        for line in file_copy_config.split("\\"):
            line = line.strip()
            if not line:
                continue
            if ":" in line:
                source, target = line.split(":", 1)
                copy_rules.append((source.strip(), target.strip()))

        # Execute file copy operations for this section
        for source_pattern, target_path in copy_rules:
            if not _execute_file_copy(section_name, section_custom_dir, source_pattern, target_path):
                log.error(
                    "Failed to execute file copy for po: '%s', source: '%s', target: '%s'",
                    ctx.po_name,
                    source_pattern,
                    target_path,
                )
                return False

    return True


def _revert_custom(ctx: PoPluginContext, runtime: PoPluginRuntime) -> bool:
    # For custom po, we can't easily revert file copies: log a warning that manual cleanup may be needed.
    for section_name, section_config in runtime.po_configs.items():
        if not section_name.startswith("po-"):
            continue
        expected_po_name = section_name[3:]
        if expected_po_name != ctx.po_name:
            continue

        file_copy_config = str(section_config.get("PROJECT_PO_FILE_COPY", "") or "")
        if not file_copy_config:
            log.warning("No PROJECT_PO_FILE_COPY configuration found for po: '%s'", ctx.po_name)
            continue

        target_paths = set()
        for line in file_copy_config.split("\\"):
            line = line.strip()
            if not line:
                continue
            if ":" in line:
                _, target = line.split(":", 1)
                target_paths.add(target.strip())

        log.warning(
            "Custom po '%s' files were copied to multiple locations. Manual cleanup may be required:", ctx.po_name
        )
        for target_path in target_paths:
            log.warning("  - Target: %s", target_path)

    return True


def _list_custom(po_path: str, runtime: PoPluginRuntime) -> Dict[str, Any]:
    custom_dirs = []
    po_name = os.path.basename(po_path.rstrip("/\\"))

    for section_name, section_config in runtime.po_configs.items():
        if not section_name.startswith("po-"):
            continue
        expected_po_name = section_name[3:]
        if expected_po_name != po_name:
            continue
        po_subdir = str(section_config.get("PROJECT_PO_DIR", "") or "").rstrip("/")
        if not po_subdir:
            continue
        custom_dir = os.path.join(po_path, po_subdir)
        custom_files: List[str] = []
        if os.path.isdir(custom_dir):
            for root, _, files in os.walk(custom_dir):
                for f in files:
                    if f == ".gitkeep":
                        continue
                    rel_path = os.path.relpath(os.path.join(root, f), custom_dir)
                    custom_files.append(rel_path)
        custom_dirs.append(
            {
                "section": section_name,
                "dir": po_subdir,
                "files": sorted(custom_files),
                "file_copy_config": str(section_config.get("PROJECT_PO_FILE_COPY", "") or ""),
            }
        )

    return {"custom_dirs": custom_dirs}


register_simple_plugin(
    name="custom",
    apply_phase=APPLY_PHASE_PER_PO,
    apply_order=40,
    revert_phase=REVERT_PHASE_PER_PO,
    revert_order=40,
    apply=_apply_custom,
    revert=_revert_custom,
    list_files=_list_custom,
)
