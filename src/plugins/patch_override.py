"""
Patch and override operations for project management.
"""

import fnmatch
import json as jsonlib
import os
import re
import shutil
import subprocess
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from src.log_manager import log
from src.operations.registry import register
from src.plan_utils import emit_plan_json, parse_emit_plan
from src.plugins.po_plugins.registry import (
    APPLY_PHASE_GLOBAL_PRE,
    APPLY_PHASE_PER_PO,
    REVERT_PHASE_GLOBAL_POST,
    REVERT_PHASE_PER_PO,
    get_po_plugins,
)
from src.plugins.po_plugins.runtime import PoPluginContext, PoPluginRuntime
from src.plugins.po_plugins.utils import extract_patch_targets
from src.plugins.po_plugins.utils import (
    po_applied_record_path as _po_applied_record_path,
)

# from src.profiler import auto_profile  # unused


def parse_po_config(po_config):
    """Parse PROJECT_PO_CONFIG string into components.

    Returns a tuple of (apply_pos: list[str], exclude_pos: set[str], exclude_files: dict[str, set[str]]).
    """
    apply_pos = []
    exclude_pos = set()
    exclude_files = {}
    tokens = re.findall(r"-?\w+(?:\[[^\]]+\])?", po_config)
    for token in tokens:
        is_exclude_po = token.startswith("-")
        token_body = token[1:] if is_exclude_po else token

        # Support both:
        # - "po1" => apply po1
        # - "-po1" => exclude po1
        # - "po1[fileA fileB]" => apply po1 but exclude listed files for this PO
        # - "-po1[fileA fileB]" => exclude po1 and also exclude listed files (kept for consistency)
        if "[" in token_body:
            match = re.match(r"^(\w+)\[([^\]]+)\]$", token_body)
            if not match:
                continue
            po_name, files = match.groups()
            file_list = set(f.strip() for f in files.split() if f.strip())
            if file_list:
                exclude_files.setdefault(po_name, set()).update(file_list)
        else:
            po_name = token_body

        if is_exclude_po:
            exclude_pos.add(po_name)
        else:
            apply_pos.append(po_name)

    # Filter apply_pos to exclude items in exclude_pos
    apply_pos = [po_name for po_name in apply_pos if po_name not in exclude_pos]

    # Dedupe apply_pos while preserving order (config inheritance may concatenate).
    seen = set()
    deduped_apply_pos = []
    for po_name in apply_pos:
        if po_name in seen:
            continue
        seen.add(po_name)
        deduped_apply_pos.append(po_name)
    apply_pos = deduped_apply_pos

    return apply_pos, exclude_pos, exclude_files


def _parse_po_filter(po_filter: str) -> List[str]:
    """
    Parse `--po` filter input into a list of PO names.

    Accepts comma and/or whitespace separated values, for example:
    - "po_a"
    - "po_a,po_b"
    - "po_a po_b"
    """
    text = str(po_filter or "").strip()
    if not text:
        return []
    tokens = [t.strip() for t in re.split(r"[,\s]+", text) if t.strip()]
    seen = set()
    out: List[str] = []
    for token in tokens:
        if token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def _filter_pos_from_config(apply_pos: List[str], requested_pos: List[str]) -> Optional[List[str]]:
    """Filter apply_pos based on requested_pos; return None on invalid request."""
    if not requested_pos:
        return list(apply_pos)
    allowed = set(apply_pos)
    unknown = sorted(set(requested_pos) - allowed)
    if unknown:
        log.error(
            "Unknown PO(s) requested via --po (not enabled by PROJECT_PO_CONFIG): %s",
            ", ".join(unknown),
        )
        return None
    requested = set(requested_pos)
    return [po_name for po_name in apply_pos if po_name in requested]


def _repo_name_from_po_relpath(rel_path: str) -> str:
    parts = rel_path.split(os.sep)
    if len(parts) <= 1:
        return "root"
    return os.path.join(*parts[:-1])


def _read_patch_targets_best_effort(abs_patch_path: str) -> List[str]:
    try:
        with open(abs_patch_path, "r", encoding="utf-8") as handle:
            return extract_patch_targets(handle.read())
    except OSError:
        return []


def _split_override_repo_prefix(rel_path: str, repo_names: List[str]) -> Tuple[str, str]:
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


def build_po_apply_plan(
    env: Dict[str, Any],
    projects_info: Dict[str, Any],
    project_name: str,
    *,
    force: bool = False,
    reapply: bool = False,
    po: str = "",
) -> Dict[str, Any]:
    """Build a machine-readable plan for po_apply without mutating repositories."""
    projects_path = env["projects_path"]
    project_info = projects_info.get(project_name, {}) if isinstance(projects_info, dict) else {}
    project_cfg = project_info.get("config", {}) if isinstance(project_info, dict) else {}
    board_name = project_info.get("board_name") if isinstance(project_info, dict) else None
    if not board_name:
        raise ValueError(f"Cannot find board name for project: {project_name}")

    board_path = os.path.join(projects_path, board_name)
    po_dir = os.path.join(board_path, "po")
    po_config = str(project_cfg.get("PROJECT_PO_CONFIG", "") or "").strip()
    apply_pos, _exclude_pos, exclude_files = parse_po_config(po_config)
    requested_pos = _parse_po_filter(po)
    filtered = _filter_pos_from_config(apply_pos, requested_pos)
    if filtered is None:
        raise ValueError(f"Unknown PO(s) requested via --po: {po}")
    apply_pos = filtered

    repositories = env.get("repositories", [])
    runtime = PoPluginRuntime(
        board_name=board_name,
        project_name=project_name,
        repositories=repositories,
        workspace_root=os.getcwd(),
        po_configs=env.get("po_configs", {}),
    )

    plugins = get_po_plugins()
    plugins = sorted(plugins, key=lambda plugin: (plugin.apply_phase, plugin.apply_order, plugin.name))

    repo_names = sorted(
        [name for name in runtime.repo_map.keys() if name != "root"], key=lambda x: len(x), reverse=True
    )
    repo_entries = sorted(runtime.repositories or [], key=lambda item: item[1])
    workspace_root = os.path.abspath(runtime.workspace_root)

    actions_by_repo: Dict[str, List[Dict[str, Any]]] = {repo_name: [] for _repo_path, repo_name in repo_entries}
    if "root" not in actions_by_repo:
        actions_by_repo["root"] = []

    po_items: List[Dict[str, Any]] = []
    for po_name in apply_pos:
        po_path = os.path.join(po_dir, po_name)
        plugin_files: Dict[str, Any] = {}

        for plugin in plugins:
            files = plugin.list_files(po_path, runtime) or {}
            # Filter excluded files for this PO, matching plugin relpaths.
            excluded = exclude_files.get(po_name, set())
            if excluded:
                if "commit_files" in files:
                    files["commit_files"] = [p for p in files["commit_files"] if p not in excluded]
                if "patch_files" in files:
                    files["patch_files"] = [p for p in files["patch_files"] if p not in excluded]
                if "override_files" in files:
                    files["override_files"] = [p for p in files["override_files"] if p not in excluded]
            plugin_files[plugin.name] = files

        # commits -> per-repo actions
        for rel_path in plugin_files.get("commits", {}).get("commit_files", []) or []:
            repo_name = _repo_name_from_po_relpath(rel_path)
            patch_abs = os.path.join(po_path, "commits", rel_path)
            actions_by_repo.setdefault(repo_name, []).append(
                {
                    "type": "commit_apply",
                    "po": po_name,
                    "source": f"commits/{rel_path}",
                    "targets": _read_patch_targets_best_effort(patch_abs),
                }
            )

        # patches -> per-repo actions
        for rel_path in plugin_files.get("patches", {}).get("patch_files", []) or []:
            repo_name = _repo_name_from_po_relpath(rel_path)
            patch_abs = os.path.join(po_path, "patches", rel_path)
            actions_by_repo.setdefault(repo_name, []).append(
                {
                    "type": "patch_apply",
                    "po": po_name,
                    "source": f"patches/{rel_path}",
                    "targets": _read_patch_targets_best_effort(patch_abs),
                }
            )

        # overrides -> per-repo actions
        for rel_path in plugin_files.get("overrides", {}).get("override_files", []) or []:
            repo_name, dest_rel = _split_override_repo_prefix(rel_path, repo_names)
            is_remove = rel_path.endswith(".remove")
            if is_remove and dest_rel.endswith(".remove"):
                dest_rel = dest_rel[: -len(".remove")]
            actions_by_repo.setdefault(repo_name, []).append(
                {
                    "type": "override_remove" if is_remove else "override_copy",
                    "po": po_name,
                    "source": f"overrides/{rel_path}",
                    "path_in_repo": dest_rel,
                }
            )

        po_items.append(
            {
                "po": po_name,
                "path": os.path.relpath(po_path, start=workspace_root),
                "plugins": plugin_files,
            }
        )

    # Stable ordering for per-repo actions.
    for repo_name, actions in list(actions_by_repo.items()):
        actions_by_repo[repo_name] = sorted(
            actions,
            key=lambda item: (str(item.get("po", "")), str(item.get("type", "")), str(item.get("source", ""))),
        )

    return {
        "schema_version": 1,
        "generated_at": datetime.now().isoformat(),
        "operation": "po_apply",
        "project_name": project_name,
        "board_name": board_name,
        "dry_run": True,
        "flags": {
            "force": bool(force),
            "reapply": bool(reapply),
            "po": str(po or ""),
        },
        "repositories": [
            {"name": repo_name, "path": os.path.relpath(repo_path, start=workspace_root)}
            for repo_path, repo_name in repo_entries
        ],
        "pos": po_items,
        "per_repo_actions": [
            {"repo": repo_name, "actions": actions_by_repo.get(repo_name, [])} for _repo_path, repo_name in repo_entries
        ]
        + ([{"repo": "root", "actions": actions_by_repo.get("root", [])}] if not repo_entries else []),
    }


def build_po_revert_plan(
    env: Dict[str, Any],
    projects_info: Dict[str, Any],
    project_name: str,
    *,
    po: str = "",
) -> Dict[str, Any]:
    """Build a machine-readable plan for po_revert without mutating repositories."""
    projects_path = env["projects_path"]
    project_info = projects_info.get(project_name, {}) if isinstance(projects_info, dict) else {}
    project_cfg = project_info.get("config", {}) if isinstance(project_info, dict) else {}
    board_name = project_info.get("board_name") if isinstance(project_info, dict) else None
    if not board_name:
        raise ValueError(f"Cannot find board name for project: {project_name}")

    board_path = os.path.join(projects_path, board_name)
    po_dir = os.path.join(board_path, "po")
    po_config = str(project_cfg.get("PROJECT_PO_CONFIG", "") or "").strip()
    apply_pos, _exclude_pos, exclude_files = parse_po_config(po_config)
    requested_pos = _parse_po_filter(po)
    filtered = _filter_pos_from_config(apply_pos, requested_pos)
    if filtered is None:
        raise ValueError(f"Unknown PO(s) requested via --po: {po}")
    apply_pos = filtered

    repositories = env.get("repositories", [])
    runtime = PoPluginRuntime(
        board_name=board_name,
        project_name=project_name,
        repositories=repositories,
        workspace_root=os.getcwd(),
        po_configs=env.get("po_configs", {}),
    )

    plugins = get_po_plugins()
    plugins = sorted(plugins, key=lambda plugin: (plugin.revert_phase, plugin.revert_order, plugin.name))

    repo_names = sorted(
        [name for name in runtime.repo_map.keys() if name != "root"], key=lambda x: len(x), reverse=True
    )
    repo_entries = sorted(runtime.repositories or [], key=lambda item: item[1])
    workspace_root = os.path.abspath(runtime.workspace_root)

    actions_by_repo: Dict[str, List[Dict[str, Any]]] = {repo_name: [] for _repo_path, repo_name in repo_entries}
    if "root" not in actions_by_repo:
        actions_by_repo["root"] = []

    po_items: List[Dict[str, Any]] = []
    for po_name in reversed(apply_pos):
        po_path = os.path.join(po_dir, po_name)
        plugin_files: Dict[str, Any] = {}

        for plugin in plugins:
            files = plugin.list_files(po_path, runtime) or {}
            excluded = exclude_files.get(po_name, set())
            if excluded and "override_files" in files:
                files["override_files"] = [p for p in files["override_files"] if p not in excluded]
            if excluded and "patch_files" in files:
                files["patch_files"] = [p for p in files["patch_files"] if p not in excluded]
            plugin_files[plugin.name] = files

        # patches revert
        for rel_path in plugin_files.get("patches", {}).get("patch_files", []) or []:
            repo_name = _repo_name_from_po_relpath(rel_path)
            actions_by_repo.setdefault(repo_name, []).append(
                {
                    "type": "patch_reverse",
                    "po": po_name,
                    "source": f"patches/{rel_path}",
                }
            )

        # overrides revert
        for rel_path in plugin_files.get("overrides", {}).get("override_files", []) or []:
            repo_name, dest_rel = _split_override_repo_prefix(rel_path, repo_names)
            if rel_path.endswith(".remove") and dest_rel.endswith(".remove"):
                dest_rel = dest_rel[: -len(".remove")]
            actions_by_repo.setdefault(repo_name, []).append(
                {
                    "type": "override_revert",
                    "po": po_name,
                    "source": f"overrides/{rel_path}",
                    "path_in_repo": dest_rel,
                }
            )

        po_items.append(
            {
                "po": po_name,
                "path": os.path.relpath(po_path, start=workspace_root),
                "plugins": plugin_files,
            }
        )

    # commits revert uses applied records, not PO directory listing.
    for repo_root, repo_name in repo_entries:
        for po_name in reversed(apply_pos):
            record = runtime.load_applied_record(repo_root, po_name)
            commits = (record or {}).get("commits") or []
            for entry in reversed(commits):
                if entry.get("status") == "already_applied":
                    continue
                shas = entry.get("commit_shas") or []
                if not shas and entry.get("head_after"):
                    shas = [entry["head_after"]]
                for sha in reversed([s for s in shas if s]):
                    actions_by_repo.setdefault(repo_name, []).append(
                        {
                            "type": "commit_revert",
                            "po": po_name,
                            "sha": sha,
                        }
                    )

    # Cleanup actions (what po_revert would remove when not in dry-run).
    for repo_root, repo_name in repo_entries:
        for po_name in reversed(apply_pos):
            record_path = _po_applied_record_path(repo_root, board_name, project_name, po_name)
            actions_by_repo.setdefault(repo_name, []).append(
                {
                    "type": "remove_applied_record",
                    "po": po_name,
                    "path": os.path.relpath(record_path, start=workspace_root),
                }
            )

    # Stable ordering for per-repo actions.
    for repo_name, actions in list(actions_by_repo.items()):
        actions_by_repo[repo_name] = sorted(
            actions,
            key=lambda item: (
                str(item.get("po", "")),
                str(item.get("type", "")),
                str(item.get("source", "")),
                str(item.get("sha", "")),
            ),
        )

    return {
        "schema_version": 1,
        "generated_at": datetime.now().isoformat(),
        "operation": "po_revert",
        "project_name": project_name,
        "board_name": board_name,
        "dry_run": True,
        "flags": {
            "po": str(po or ""),
        },
        "repositories": [
            {"name": repo_name, "path": os.path.relpath(repo_path, start=workspace_root)}
            for repo_path, repo_name in repo_entries
        ],
        "pos": po_items,
        "per_repo_actions": [
            {"repo": repo_name, "actions": actions_by_repo.get(repo_name, [])} for _repo_path, repo_name in repo_entries
        ]
        + ([{"repo": "root", "actions": actions_by_repo.get("root", [])}] if not repo_entries else []),
    }


@register("po_apply", needs_repositories=True, desc="Apply patch and override for a project")
def po_apply(
    env: Dict,
    projects_info: Dict,
    project_name: str,
    dry_run: bool = False,
    force: bool = False,
    reapply: bool = False,
    po: str = "",
    emit_plan: Any = False,
) -> bool:
    """
    Apply patch/override/commits for the specified project.
    Args:
        env (dict): Global environment dict.
        projects_info (dict): All projects info.
        project_name (str): Project name.
        dry_run (bool): If True, only print planned actions without modifying files.
        emit_plan (bool|str): Emit a machine-readable JSON plan to stdout (true) or to the given path.
        force (bool): If True, allow destructive operations like override .remove deletions.
        reapply (bool): If True, apply POs even if applied records already exist (overwrites them after success).
        po (str): Optional PO filter; only apply these POs (comma/space separated) from PROJECT_PO_CONFIG.
    Returns:
        bool: True if success, otherwise False.
    """
    projects_path = env["projects_path"]
    log.info("start po_apply for project: '%s'", project_name)
    project_info = projects_info.get(project_name, {}) if isinstance(projects_info, dict) else {}
    project_cfg = project_info.get("config", {}) if isinstance(project_info, dict) else {}
    board_name = project_info.get("board_name") if isinstance(project_info, dict) else None
    if not board_name:
        log.error("Cannot find board name for project: '%s'", project_name)
        return False

    board_path = os.path.join(projects_path, board_name)
    po_dir = os.path.join(board_path, "po")
    po_config = str(project_cfg.get("PROJECT_PO_CONFIG", "") or "").strip()
    emit_enabled, _ = parse_emit_plan(emit_plan)
    if not po_config:
        if emit_enabled:
            payload = build_po_apply_plan(env, projects_info, project_name, force=force, reapply=reapply, po=po)
            emit_plan_json(payload, emit_plan)
            return True
        log.warning("No PROJECT_PO_CONFIG found for '%s'", project_name)
        return True

    apply_pos, exclude_pos, exclude_files = parse_po_config(po_config)
    requested_pos = _parse_po_filter(po)
    filtered = _filter_pos_from_config(apply_pos, requested_pos)
    if filtered is None:
        return False
    if requested_pos:
        log.info(
            "Applying selected POs for project '%s': %s",
            project_name,
            ", ".join(filtered) if filtered else "(none)",
        )
    apply_pos = filtered
    if emit_enabled:
        payload = build_po_apply_plan(env, projects_info, project_name, force=force, reapply=reapply, po=po)
        emit_plan_json(payload, emit_plan)
        return True

    if not apply_pos:
        log.warning("No POs selected for '%s' after --po filter; nothing to do.", project_name)
        return True

    log.debug("po_dir: '%s'", po_dir)
    if apply_pos:
        log.debug("apply_pos: %s", str(apply_pos))
    if exclude_pos:
        log.debug("exclude_pos: %s", str(exclude_pos))
    if exclude_files:
        log.debug("exclude_files: %s", str(exclude_files))

    repositories = env.get("repositories", [])
    runtime = PoPluginRuntime(
        board_name=board_name,
        project_name=project_name,
        repositories=repositories,
        workspace_root=os.getcwd(),
        po_configs=env.get("po_configs", {}),
    )

    plugins = get_po_plugins()
    global_pre_plugins = sorted(
        [plugin for plugin in plugins if plugin.apply_phase == APPLY_PHASE_GLOBAL_PRE],
        key=lambda plugin: plugin.apply_order,
    )
    per_po_plugins = sorted(
        [plugin for plugin in plugins if plugin.apply_phase == APPLY_PHASE_PER_PO],
        key=lambda plugin: plugin.apply_order,
    )

    if reapply:
        log.info("--reapply enabled: ignoring existing applied record markers")

    ctxs: List[PoPluginContext] = []
    for po_name in apply_pos:
        po_path = os.path.join(po_dir, po_name)
        ctxs.append(
            PoPluginContext(
                project_name=project_name,
                board_name=board_name,
                po_name=po_name,
                po_path=po_path,
                po_commit_dir=os.path.join(po_path, "commits"),
                po_patch_dir=os.path.join(po_path, "patches"),
                po_override_dir=os.path.join(po_path, "overrides"),
                po_custom_dir=os.path.join(po_path, "custom"),
                dry_run=dry_run,
                force=force,
                reapply=reapply,
                exclude_files=exclude_files,
                applied_records={},
            )
        )

    # Stage 1: apply global-pre plugins (git am requires clean index).
    for plugin in global_pre_plugins:
        for ctx in ctxs:
            suffix = " (dry-run)" if dry_run else ""
            if plugin.name == "commits":
                log.info("po '%s' starting to apply commits%s", ctx.po_name, suffix)
            else:
                log.info("po '%s' starting to apply %s%s", ctx.po_name, plugin.name, suffix)

            if not plugin.apply(ctx, runtime):
                log.error("po apply aborted due to error in po: '%s'", ctx.po_name)
                return False

    # Stage 2: apply per-po plugins (may dirty working tree).
    for ctx in ctxs:
        log.info("po '%s' starting to apply patch and override%s", ctx.po_name, " (dry-run)" if dry_run else "")

        for plugin in per_po_plugins:
            if not plugin.apply(ctx, runtime):
                log.error("po apply aborted due to error in po: '%s'", ctx.po_name)
                return False

        if not dry_run and ctx.applied_records:
            try:
                runtime.finalize_records(ctx)
            except OSError as exc:
                log.error("Failed to finalize applied record for po '%s': '%s'", ctx.po_name, exc)
                return False

        log.info("po '%s' has been processed", ctx.po_name)

    log.info("po apply finished for project: '%s'", project_name)
    return True


@register(
    "po_revert",
    needs_repositories=True,
    desc="Revert patch/override/commits for a project",
)
def po_revert(
    env: Dict,
    projects_info: Dict,
    project_name: str,
    dry_run: bool = False,
    po: str = "",
    emit_plan: Any = False,
) -> bool:
    """
    Revert patch/override/commits for the specified project.
    Args:
        env (dict): Global environment dict.
        projects_info (dict): All projects info.
        project_name (str): Project name.
        dry_run (bool): If True, only print planned actions without modifying files.
        emit_plan (bool|str): Emit a machine-readable JSON plan to stdout (true) or to the given path.
        po (str): Optional PO filter; only revert these POs (comma/space separated) from PROJECT_PO_CONFIG.
    Returns:
        bool: True if success, otherwise False.
    """
    projects_path = env["projects_path"]
    log.info("start po_revert for project: '%s'", project_name)
    project_info = projects_info.get(project_name, {}) if isinstance(projects_info, dict) else {}
    project_cfg = project_info.get("config", {}) if isinstance(project_info, dict) else {}
    board_name = project_info.get("board_name") if isinstance(project_info, dict) else None
    if not board_name:
        log.error("Cannot find board name for project: '%s'", project_name)
        return False

    board_path = os.path.join(projects_path, board_name)
    po_dir = os.path.join(board_path, "po")
    po_config = str(project_cfg.get("PROJECT_PO_CONFIG", "") or "").strip()
    emit_enabled, _ = parse_emit_plan(emit_plan)
    if not po_config:
        if emit_enabled:
            payload = build_po_revert_plan(env, projects_info, project_name, po=po)
            emit_plan_json(payload, emit_plan)
            return True
        log.warning("No PROJECT_PO_CONFIG found for '%s'", project_name)
        return True

    apply_pos, exclude_pos, exclude_files = parse_po_config(po_config)
    requested_pos = _parse_po_filter(po)
    filtered = _filter_pos_from_config(apply_pos, requested_pos)
    if filtered is None:
        return False
    if requested_pos:
        log.info(
            "Reverting selected POs for project '%s': %s",
            project_name,
            ", ".join(filtered) if filtered else "(none)",
        )
    apply_pos = filtered
    if emit_enabled:
        payload = build_po_revert_plan(env, projects_info, project_name, po=po)
        emit_plan_json(payload, emit_plan)
        return True

    if not apply_pos:
        log.warning("No POs selected for '%s' after --po filter; nothing to do.", project_name)
        return True

    log.debug("projects_info: %s", str(projects_info.get(project_name, {})))
    log.debug("po_dir: '%s'", po_dir)
    if apply_pos:
        log.debug("apply_pos: %s", str(apply_pos))
    if exclude_pos:
        log.debug("exclude_pos: %s", str(exclude_pos))
    if exclude_files:
        log.debug("exclude_files: %s", str(exclude_files))

    repositories = env.get("repositories", [])
    runtime = PoPluginRuntime(
        board_name=board_name,
        project_name=project_name,
        repositories=repositories,
        workspace_root=os.getcwd(),
        po_configs=env.get("po_configs", {}),
    )

    plugins = get_po_plugins()
    per_po_plugins = sorted(
        [plugin for plugin in plugins if plugin.revert_phase == REVERT_PHASE_PER_PO],
        key=lambda plugin: plugin.revert_order,
    )
    global_post_plugins = sorted(
        [plugin for plugin in plugins if plugin.revert_phase == REVERT_PHASE_GLOBAL_POST],
        key=lambda plugin: plugin.revert_order,
    )

    # Stage 1: revert patches/overrides/custom first (these may leave the repo dirty).
    for po_name in reversed(apply_pos):
        po_path = os.path.join(po_dir, po_name)
        ctx = PoPluginContext(
            project_name=project_name,
            board_name=board_name,
            po_name=po_name,
            po_path=po_path,
            po_commit_dir=os.path.join(po_path, "commits"),
            po_patch_dir=os.path.join(po_path, "patches"),
            po_override_dir=os.path.join(po_path, "overrides"),
            po_custom_dir=os.path.join(po_path, "custom"),
            dry_run=dry_run,
            force=False,
            exclude_files=exclude_files,
            applied_records={},
        )

        for plugin in per_po_plugins:
            if not plugin.revert(ctx, runtime):
                log.error("po revert aborted due to %s error in po: '%s'", plugin.name, po_name)
                return False

    # Stage 2: revert commit patches (git revert requires clean index).
    for po_name in reversed(apply_pos):
        po_path = os.path.join(po_dir, po_name)
        ctx = PoPluginContext(
            project_name=project_name,
            board_name=board_name,
            po_name=po_name,
            po_path=po_path,
            po_commit_dir=os.path.join(po_path, "commits"),
            po_patch_dir=os.path.join(po_path, "patches"),
            po_override_dir=os.path.join(po_path, "overrides"),
            po_custom_dir=os.path.join(po_path, "custom"),
            dry_run=dry_run,
            force=False,
            exclude_files=exclude_files,
            applied_records={},
        )

        for plugin in global_post_plugins:
            if not plugin.revert(ctx, runtime):
                log.error("po revert aborted due to commit revert error in po: '%s'", po_name)
                return False

        # Clear applied flag so the PO can be applied again after a successful revert.
        po_applied_flag_path = os.path.join(po_dir, po_name, "po_applied")
        if not dry_run and os.path.isfile(po_applied_flag_path):
            try:
                os.remove(po_applied_flag_path)
                log.debug("Removed po_applied flag: '%s'", po_applied_flag_path)
            except OSError as e:
                log.warning("Failed to remove po_applied flag '%s': %s", po_applied_flag_path, e)

        log.info("po '%s' has been reverted", po_name)
        if not dry_run:
            for repo_path, _repo_name in repositories or []:
                record_path = _po_applied_record_path(repo_path, board_name, project_name, po_name)
                try:
                    if os.path.exists(record_path):
                        os.remove(record_path)
                except OSError:
                    # Best-effort cleanup only.
                    pass

    log.info("po revert finished for project: '%s'", project_name)
    return True


@register(
    "po_analyze",
    needs_repositories=True,
    desc="Analyze PO conflicts (overlapping patch/override targets) for a project.",
)
def po_analyze(
    env: Dict[str, Any],
    projects_info: Dict[str, Any],
    project_name: str,
    po: str = "",
    json: bool = False,
    strict: bool = False,
) -> bool:
    """
    Analyze enabled POs for conflicts (overlapping patch targets and override targets).

    po (str): Optional PO filter; only analyze these POs (comma/space separated) from PROJECT_PO_CONFIG.
    json (bool): Output machine-readable JSON to stdout.
    strict (bool): Exit non-zero (return False) when conflicts are detected.
    """

    try:
        plan = build_po_apply_plan(env, projects_info, project_name, po=po)
    except ValueError as exc:
        log.error("Failed to build PO plan for analysis: %s", exc)
        return False

    per_repo = plan.get("per_repo_actions") or []

    override_map: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
    patch_map: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}

    def _key(repo_name: str, path_in_repo: str) -> str:
        repo_name = str(repo_name or "root")
        path_in_repo = str(path_in_repo or "").lstrip("/\\")
        if not path_in_repo:
            return ""
        return path_in_repo if repo_name == "root" else f"{repo_name}/{path_in_repo}"

    for repo_entry in per_repo:
        repo_name = repo_entry.get("repo") or "root"
        for action in repo_entry.get("actions") or []:
            action_type = str(action.get("type") or "")
            po_name = str(action.get("po") or "")
            if not po_name or not action_type:
                continue

            if action_type.startswith("override_"):
                key = _key(repo_name, action.get("path_in_repo") or "")
                if not key:
                    continue
                override_map.setdefault(key, {}).setdefault(po_name, []).append(action)
                continue

            if action_type in {"patch_apply", "commit_apply"}:
                for target in action.get("targets") or []:
                    key = _key(repo_name, target)
                    if not key:
                        continue
                    patch_map.setdefault(key, {}).setdefault(po_name, []).append(action)

    override_conflicts = [
        {"path": path, "pos": sorted(po_map.keys())}
        for path, po_map in sorted(override_map.items(), key=lambda item: item[0])
        if len(po_map) > 1
    ]
    patch_conflicts = [
        {"path": path, "pos": sorted(po_map.keys())}
        for path, po_map in sorted(patch_map.items(), key=lambda item: item[0])
        if len(po_map) > 1
    ]

    has_conflicts = bool(override_conflicts or patch_conflicts)
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now().isoformat(),
        "operation": "po_analyze",
        "project_name": project_name,
        "board_name": plan.get("board_name") or "",
        "pos": [item.get("po") for item in (plan.get("pos") or []) if item.get("po")],
        "conflicts": {
            "overrides": override_conflicts,
            "patches": patch_conflicts,
        },
        "summary": {
            "override_conflict_count": len(override_conflicts),
            "patch_conflict_count": len(patch_conflicts),
            "has_conflicts": has_conflicts,
        },
    }

    if json:
        print(jsonlib.dumps(payload, indent=2, ensure_ascii=False))
    else:
        if not has_conflicts:
            print("No PO conflicts detected.")
        else:
            print("PO conflicts detected:")
            for item in override_conflicts:
                print(f"- override conflict: {item['path']} (POs: {', '.join(item['pos'])})")
            for item in patch_conflicts:
                print(f"- patch conflict: {item['path']} (POs: {', '.join(item['pos'])})")

    if strict and has_conflicts:
        return False
    return True


@register("po_new", needs_repositories=True, desc="Create a new PO for a project")
def po_new(
    env: Dict,
    projects_info: Dict,
    project_name: str,
    po_name: str,
    force: bool = False,
    tui: bool = False,
    po_check_exists: bool = False,
) -> bool:
    """
    Create a new PO (patch and override) directory structure for the specified project.
    Args:
        env (dict): Global environment dict.
        projects_info (dict): All projects info.
        project_name (str): Project name.
        po_name (str): Name of the new PO to create.
        force (bool): If True, skip confirmation prompt.
        po_check_exists (bool): When True, require the PO directory to already exist (used by update path).
    Returns:
        bool: True if success, otherwise False.
    """
    log.info("start po_new for project: '%s', po_name: '%s'", project_name, po_name)
    if not re.match(r"^po[a-z0-9_]*$", po_name):
        log.error(
            "po_name '%s' is invalid. It must start with 'po' and only contain lowercase letters, digits, and underscores.",
            po_name,
        )
        return False
    project_cfg = projects_info.get(project_name, {})
    board_name = project_cfg.get("board_name")
    board_path = project_cfg.get("board_path")
    if not board_name or not board_path:
        log.error("Board info missing for project '%s'", project_name)
        return False

    board_path = os.path.join(env["projects_path"], board_name)
    po_dir = os.path.join(board_path, "po")

    # Create po directory if it doesn't exist
    if not os.path.exists(po_dir):
        try:
            os.makedirs(po_dir, exist_ok=True)
            log.info("Created po directory: '%s'", po_dir)
        except OSError as e:
            log.error("Failed to create po directory '%s': '%s'", po_dir, e)
            return False

    # Create the new po directory structure
    po_path = os.path.join(po_dir, po_name)

    # Existence checks differ for new vs update
    if po_check_exists:
        if not os.path.exists(po_path):
            log.error("PO directory '%s' does not exist for update", po_path)
            return False
    else:
        if os.path.exists(po_path):
            log.error("PO directory '%s' already exists", po_path)
            return False

    # Define helper functions as local functions
    def __confirm_creation(po_name, po_path, board_path):
        """Show creation information and ask for user confirmation."""
        print("\n=== PO Creation Confirmation ===")
        print(f"PO Name: {po_name}")
        print(f"PO Path: {po_path}")
        print(f"Board Path: {board_path}")

        print("\nThis will create:")
        print("  1. PO directory structure with patches/ and overrides/ subdirectories")
        print("  2. Option to select modified files to include in the PO")

        while True:
            response = input(f"\nDo you want to create PO '{po_name}'? (yes/no): ").strip().lower()
            if response in ["yes", "y"]:
                return True
            if response in ["no", "n"]:
                return False
            print("Please enter 'yes' or 'no'.")

    def __get_modified_files(repo_path, repo_name, ignore_patterns):
        """Get modified files in a repository including staged files, with ignore support."""
        modified_files = []
        try:
            # Get staged files (files in index)
            staged_result = subprocess.run(
                ["git", "diff", "--name-only", "--cached"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=False,
            )

            staged_files = set()
            if staged_result.returncode == 0 and staged_result.stdout.strip():
                staged_files = set(staged_result.stdout.strip().split("\n"))

            # Get modified and untracked files (files in working directory)
            working_result = subprocess.run(
                ["git", "ls-files", "--modified", "--others", "--exclude-standard"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=False,
            )

            working_files = set()
            if working_result.returncode == 0 and working_result.stdout.strip():
                working_files = set(working_result.stdout.strip().split("\n"))

            # Get deleted files (files that were tracked but are now missing)
            deleted_result = subprocess.run(
                ["git", "ls-files", "--deleted"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=False,
            )

            deleted_files = set()
            if deleted_result.returncode == 0 and deleted_result.stdout.strip():
                deleted_files = set(deleted_result.stdout.strip().split("\n"))

            # Process all files
            all_files = staged_files | working_files | deleted_files

            def is_ignored(file_path):
                # Create full path for matching: repo_name/file_path
                full_path = f"{repo_name}/{file_path}" if repo_name != "root" else file_path

                for pattern in ignore_patterns:
                    if fnmatch.fnmatch(file_path, pattern) or fnmatch.fnmatch(full_path, pattern):
                        return True
                return False

            for file_path in all_files:
                if not file_path.strip():
                    continue
                if is_ignored(file_path):
                    continue

                # Determine file status
                status_result = subprocess.run(
                    ["git", "status", "--porcelain", file_path],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    check=False,
                )

                if status_result.returncode == 0 and status_result.stdout.strip():
                    status = status_result.stdout.strip()[:2]

                    # Enhance status description for better understanding
                    if file_path in deleted_files:
                        if file_path in staged_files:
                            status = f"{status} (staged+deleted)"
                        else:
                            status = f"{status} (deleted)"
                    elif file_path in staged_files and file_path in working_files:
                        status = f"{status} (staged+modified)"
                    elif file_path in staged_files:
                        status = f"{status} (staged)"
                    else:
                        status = f"{status} (working)"
                else:
                    status = "?? (unknown)"

                modified_files.append((repo_name, file_path, status))

        except (OSError, subprocess.SubprocessError) as e:
            log.error("Failed to get modified files for repository %s: %s", repo_name, e)
            print(f"Warning: Failed to get modified files for repository {repo_name}: {e}")
            return None

        return modified_files

    def __find_repo_path_by_name(repo_name):
        """Find repository path by name."""
        # 直接用env['repositories']
        for repo_path, rname in env.get("repositories", []):
            if rname == repo_name:
                return repo_path
        return None

    def __create_patch_for_file(repo_name, file_path, patches_dir, force=False):
        """Create a patch file for the specified file."""
        try:
            # Find the repository path
            repo_path = __find_repo_path_by_name(repo_name)
            if not repo_path:
                return False

            # Check if file is staged
            staged_result = subprocess.run(
                ["git", "diff", "--name-only", "--cached"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=False,
            )

            is_staged = False
            if staged_result.returncode == 0 and staged_result.stdout.strip():
                staged_files = staged_result.stdout.strip().split("\n")
                is_staged = file_path in staged_files

            # Determine patch source (staged vs working directory)
            use_staged = False
            if is_staged and not force:
                print(f"    File {file_path} is staged. Choose patch source:")
                print("      1. Use staged changes (git diff --cached)")
                print("      2. Use working directory changes (git diff)")

                while True:
                    choice = input("    Choice (1/2): ").strip()
                    if choice == "1":
                        use_staged = True
                        break
                    if choice == "2":
                        use_staged = False
                        break
                    print("    Invalid choice. Please enter 1 or 2.")
            elif is_staged and force:
                # In force mode, default to staged for staged files
                use_staged = True

            # Ask user for custom patch name
            default_filename = os.path.basename(file_path)
            print(f"    Default patch name: {default_filename}.patch")
            custom_name = input("    Enter custom patch name (or press Enter for default): ").strip()

            if custom_name:
                # Remove .patch extension if user included it
                if custom_name.endswith(".patch"):
                    custom_name = custom_name[:-6]
                filename = custom_name
            else:
                filename = default_filename

            # Create patch file path: patches_dir/repo_name/file_path.patch
            if repo_name == "root":
                # For root repository, patch is based on root directory, use only filename
                patch_file_path = os.path.join(patches_dir, f"{filename}.patch")
            else:
                # For other repositories, patch is based on repo root directory, use only filename
                patch_file_path = os.path.join(patches_dir, repo_name, f"{filename}.patch")

            # Create patches directory and subdirectories if they don't exist
            os.makedirs(os.path.dirname(patch_file_path), exist_ok=True)

            # Generate patch using appropriate git diff command
            if use_staged:
                result = subprocess.run(
                    ["git", "diff", "--cached", "--", file_path],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                print(f"    Generating patch from staged changes for {file_path}")
            else:
                result = subprocess.run(
                    ["git", "diff", "--", file_path],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                print(f"    Generating patch from working directory for {file_path}")

            if result.returncode == 0 and result.stdout.strip():
                # Write patch file
                with open(patch_file_path, "w", encoding="utf-8") as f:
                    f.write(result.stdout)

                return True
            print(f"    Warning: No changes found for {file_path}")
            return False

        except (OSError, subprocess.SubprocessError) as e:
            log.error("Failed to create patch for file %s: %s", file_path, e)
            return False

    def __create_override_for_file(repo_name, file_path, overrides_dir):
        """Create an override file for the specified file."""
        try:
            # Find the repository path
            repo_path = __find_repo_path_by_name(repo_name)
            if not repo_path:
                return False

            # Source file path
            src_file = os.path.join(repo_path, file_path)
            if not os.path.exists(src_file):
                print(f"    Warning: File {file_path} does not exist")
                return False

            # Destination file path in overrides directory
            if repo_name == "root":
                # For root repository, use the full relative path
                dest_file = os.path.join(overrides_dir, file_path)
            else:
                dest_file = os.path.join(overrides_dir, repo_name, file_path)

            # Create overrides directory and subdirectories if they don't exist
            os.makedirs(os.path.dirname(dest_file), exist_ok=True)

            # Copy file
            shutil.copy2(src_file, dest_file)
            return True

        except (OSError, shutil.Error) as e:
            log.error("Failed to create override for file %s: %s", file_path, e)
            return False

    def __create_remove_file_for_deleted_file(repo_name, file_path, overrides_dir, all_file_infos=None):
        """Create a .remove file for a deleted file or .gitkeep for deleted directory."""
        try:
            # Check if this is a directory deletion by looking for other deleted files in the same directory
            # This is a heuristic approach - if multiple files in the same directory are deleted,
            # it might indicate a directory deletion
            deleted_files_in_same_dir = []
            if all_file_infos:
                for other_repo, other_path, other_status in all_file_infos:
                    if other_repo == repo_name and "deleted" in other_status:
                        other_dir = os.path.dirname(other_path)
                        current_dir = os.path.dirname(file_path)
                        if other_dir == current_dir and other_path != file_path:
                            deleted_files_in_same_dir.append(other_path)

            # If there are multiple deleted files in the same directory, treat as directory deletion
            is_directory_deletion = len(deleted_files_in_same_dir) > 0

            if is_directory_deletion:
                # For directory deletion, create .gitkeep file to preserve the directory structure
                dir_path = os.path.dirname(file_path)
                if repo_name == "root":
                    dest_dir = os.path.join(overrides_dir, dir_path) if dir_path else overrides_dir
                else:
                    dest_dir = (
                        os.path.join(overrides_dir, repo_name, dir_path)
                        if dir_path
                        else os.path.join(overrides_dir, repo_name)
                    )

                # Create directory structure
                os.makedirs(dest_dir, exist_ok=True)

                # Create .gitkeep file
                gitkeep_file = os.path.join(dest_dir, ".gitkeep")
                with open(gitkeep_file, "w", encoding="utf-8") as f:
                    f.write("# Directory preservation marker\n")
                    f.write(f"# Original directory: {dir_path}\n")
                    f.write(f"# Repository: {repo_name}\n")
                    f.write(f"# Created by po_new on {__import__('datetime').datetime.now().isoformat()}\n")
                    f.write("# This directory was deleted, .gitkeep prevents it from being removed\n")

                return True

            # For individual file deletion, create .remove file
            if repo_name == "root":
                # For root repository, use the full relative path
                dest_file = os.path.join(overrides_dir, f"{file_path}.remove")
            else:
                dest_file = os.path.join(overrides_dir, repo_name, f"{file_path}.remove")

            # Create overrides directory and subdirectories if they don't exist
            os.makedirs(os.path.dirname(dest_file), exist_ok=True)

            # Create empty .remove file as a marker
            with open(dest_file, "w", encoding="utf-8") as f:
                f.write(f"# Remove marker for deleted file: {file_path}\n")
                f.write(f"# This file was deleted from repository: {repo_name}\n")
                f.write(f"# Created by po_new on {__import__('datetime').datetime.now().isoformat()}\n")

            return True

        except (OSError, IOError) as e:
            log.error("Failed to create remove file for %s: %s", file_path, e)
            return False

    def __process_multiple_files(file_infos, po_path):
        """Process multiple files with a single choice for all files."""
        if not file_infos:
            return 0

        # Create po directory when first file is selected
        os.makedirs(po_path, exist_ok=True)
        log.info("Created po directory: '%s'", po_path)

        # Show all files to be processed
        print(f"\nFiles to process ({len(file_infos)}):")
        for i, (repo_name, file_path, status) in enumerate(file_infos, 1):
            print(f"  {i:2d}. [{repo_name}] {file_path} ({status})")

        # Check if there are any deleted files
        has_deleted_files = any("deleted" in status for _, _, status in file_infos)

        print("\nChoose action for ALL selected files:")
        print("  1. Create patches (for tracked files with modifications)")
        print("  2. Create overrides (for any file)")
        if has_deleted_files:
            print("  3. Create remove files (for deleted files)")
            print("  4. Skip all files")
        else:
            print("  3. Skip all files")

        while True:
            if has_deleted_files:
                choice = input("Choice (1/2/3/4): ").strip()
                if choice == "1":
                    return __batch_create_patches(file_infos, po_path)
                if choice == "2":
                    return __batch_create_overrides(file_infos, po_path)
                if choice == "3":
                    return __batch_create_remove_files(file_infos, po_path)
                if choice == "4":
                    print("  - Skipped all files")
                    return 0
                print("Invalid choice. Please enter 1, 2, 3, or 4.")
            else:
                choice = input("Choice (1/2/3): ").strip()
                if choice == "1":
                    return __batch_create_patches(file_infos, po_path)
                if choice == "2":
                    return __batch_create_overrides(file_infos, po_path)
                if choice == "3":
                    print("  - Skipped all files")
                    return 0
                print("Invalid choice. Please enter 1, 2, or 3.")

    def __batch_create_patches(file_infos, po_path):
        """Create patches for multiple files."""
        patches_dir = os.path.join(po_path, "patches")
        success_count = 0

        print("  Creating patches for all selected files...")
        for repo_name, file_path, _ in file_infos:
            if __create_patch_for_file(repo_name, file_path, patches_dir, force=True):
                print(f"    ✓ Created patch for {file_path}")
                success_count += 1
            else:
                print(f"    ✗ Failed to create patch for {file_path}")

        print(f"  Completed: {success_count}/{len(file_infos)} patches created")
        return success_count

    def __batch_create_overrides(file_infos, po_path):
        """Create overrides for multiple files."""
        overrides_dir = os.path.join(po_path, "overrides")
        success_count = 0

        print("  Creating overrides for all selected files...")
        for repo_name, file_path, _ in file_infos:
            if __create_override_for_file(repo_name, file_path, overrides_dir):
                print(f"    ✓ Created override for {file_path}")
                success_count += 1
            else:
                print(f"    ✗ Failed to create override for {file_path}")

        print(f"  Completed: {success_count}/{len(file_infos)} overrides created")
        return success_count

    def __batch_create_remove_files(file_infos, po_path):
        """Create remove files for deleted files."""
        overrides_dir = os.path.join(po_path, "overrides")
        success_count = 0

        print("  Creating remove files for deleted files...")
        for repo_name, file_path, status in file_infos:
            if "deleted" in status:
                if __create_remove_file_for_deleted_file(repo_name, file_path, overrides_dir, file_infos):
                    print(f"    ✓ Created remove file for {file_path}")
                    success_count += 1
                else:
                    print(f"    ✗ Failed to create remove file for {file_path}")
            else:
                print(f"    - Skipped {file_path} (not deleted)")

        print(f"  Completed: {success_count}/{len([f for f in file_infos if 'deleted' in f[2]])} remove files created")
        return success_count

    def __interactive_file_selection(po_path, repositories, project_cfg):
        """Interactive file selection for PO creation."""
        print("\n=== File Selection for PO ===")
        print("Scanning for modified files in repositories...")

        # 直接使用传入的repositories参数
        if not repositories:
            print("No git repositories found.")
            return

        # Load ignore patterns once for all repositories
        # project_cfg contains the full project info, config is in project_cfg["config"]
        project_config = project_cfg.get("config", {}) if isinstance(project_cfg, dict) else {}
        ignore_patterns = __load_ignore_patterns(project_config)

        all_modified_files = []
        for repo_path, repo_name in repositories:
            modified_files = __get_modified_files(repo_path, repo_name, ignore_patterns)
            if modified_files is None:
                return
            if modified_files:
                all_modified_files.extend(modified_files)

        if not all_modified_files:
            print("No modified files found in any repository.")
            return

        # Track processed files
        processed_files = set()
        remaining_files = all_modified_files.copy()

        while True:
            print(f"\n=== File Selection (Remaining: {len(remaining_files)}/{len(all_modified_files)}) ===")

            # Show remaining files
            if remaining_files:
                print("Remaining files to process:")
                for i, (repo_name, file_path, status) in enumerate(remaining_files, 1):
                    print(f"  {i:2d}. [{repo_name}] {file_path} ({status})")
            else:
                print("All files have been processed!")
                break

            # Show processed files summary
            if processed_files:
                print(f"\nProcessed files ({len(processed_files)}):")
                for repo_name, file_path, status in sorted(processed_files):
                    print(f"  ✓ [{repo_name}] {file_path} ({status})")

            print("\nOptions:")
            print("  Enter file number to process (e.g., '1')")
            print("  Enter multiple numbers separated by comma or space (e.g., '1,3,5' or '1 3 5')")
            print("  Enter 'all' to process all remaining files")
            print("  Enter 'q' to quit and finish")

            selection = input("\nSelection: ").strip()
            if selection.lower() == "q":
                print("File selection finished.")
                break

            if selection.lower() == "all":
                # Process all remaining files
                files_to_process = remaining_files.copy()
                processed_count = __process_multiple_files(files_to_process, po_path)
                if processed_count > 0:
                    for file_info in files_to_process:
                        processed_files.add(file_info)
                remaining_files.clear()
                continue

            try:
                # Check if input contains multiple numbers (e.g., "1,3,5" or "1 3 5")
                if "," in selection or " " in selection:
                    # Split by comma or space and process multiple files
                    separators = [",", " "]
                    numbers = selection
                    for sep in separators:
                        if sep in numbers:
                            numbers = numbers.replace(sep, " ")
                    number_list = numbers.split()

                    # Validate all numbers first
                    valid_indices = []
                    for num_str in number_list:
                        try:
                            index = int(num_str) - 1
                            if 0 <= index < len(remaining_files):
                                valid_indices.append(index)
                            else:
                                print(f"Invalid file number: {num_str}")
                        except ValueError:
                            print(f"Invalid number format: {num_str}")

                    if valid_indices:
                        # Get all selected files
                        selected_files = [remaining_files[index] for index in valid_indices]

                        # Process all files with single choice
                        processed_count = __process_multiple_files(selected_files, po_path)

                        # Remove processed files from remaining_files
                        valid_indices.sort(reverse=True)
                        for index in valid_indices:
                            remaining_files.pop(index)

                        # Add to processed_files if any were successfully processed
                        if processed_count > 0:
                            for file_info in selected_files:
                                processed_files.add(file_info)
                    else:
                        print("No valid file numbers provided")
                else:
                    # Single number processing - treat as single file selection
                    index = int(selection) - 1
                    if 0 <= index < len(remaining_files):
                        file_info = remaining_files[index]
                        processed_count = __process_multiple_files([file_info], po_path)
                        if processed_count > 0:
                            processed_files.add(file_info)
                        remaining_files.pop(index)
                    else:
                        print("Invalid file number. Please try again.")
            except ValueError:
                print("Invalid input. Please enter a number, 'all', or 'q'.")

    def __load_ignore_patterns(project_cfg):
        """Load ignore patterns from project configuration or .gitignore."""
        patterns = []

        # First, try to get ignore patterns from project configuration
        log.debug("project_cfg type: %s, content: %s", type(project_cfg), project_cfg)
        if project_cfg:
            po_ignore_config = project_cfg.get("PROJECT_PO_IGNORE", "").strip()
            log.debug("po_ignore_config: '%s'", po_ignore_config)
            if po_ignore_config:
                config_patterns = [p.strip() for p in po_ignore_config.split() if p.strip()]
                patterns.extend(config_patterns)

                # Add enhanced patterns for path containment matching
                enhanced_patterns = []
                for pattern in config_patterns:
                    # Skip patterns that already contain wildcards or special characters
                    if any(char in pattern for char in ["*", "?", "[", "]"]):
                        continue

                    # Add patterns to match repositories and files containing the pattern in their path
                    enhanced_patterns.extend(
                        [
                            # Match any path containing the pattern
                            f"*{pattern}*",
                            # Match directories starting with the pattern
                            f"*{pattern}/*",
                            # Match directories containing the pattern
                            f"*/{pattern}/*",
                            # Match files/directories ending with the pattern
                            f"*/{pattern}",
                        ]
                    )

                patterns.extend(enhanced_patterns)
                log.debug(
                    "Loaded ignore patterns from project config: %s",
                    config_patterns,
                )
                log.debug(
                    "Added enhanced patterns for path containment: %s",
                    enhanced_patterns,
                )

        # Then load from .gitignore file
        gitignore_file = os.path.join(os.getcwd(), ".gitignore")
        if os.path.exists(gitignore_file):
            try:
                with open(gitignore_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            patterns.append(line)
                log.debug("Loaded ignore patterns from file: %s", gitignore_file)
            except OSError as e:
                log.warning("Failed to read ignore file %s: %s", gitignore_file, e)

        log.debug("Loaded ignore patterns: %s", patterns)
        return patterns

    # Show creation information and ask for confirmation
    if not force:
        if not __confirm_creation(po_name, po_path, board_path):
            log.info("po_new cancelled by user")
            return False

    try:
        # Interactive file selection first
        if not force:
            if tui:
                from src.tui_utils import tui_available

                ok, msg = tui_available()
                if not ok:
                    log.error("%s", msg)
                    print(msg)
                    return False
                print("NOTE: --tui is enabled, but TUI UI is not implemented yet; falling back to prompt-based flow.")

            # Pass env["repositories"] and project_cfg for interactive selection.
            __interactive_file_selection(po_path, env.get("repositories", []), project_cfg)

        # In force mode, create empty directory structure
        if force:
            # Create po directory
            os.makedirs(po_path, exist_ok=True)
            log.info("Created po directory: '%s'", po_path)

            for plugin in get_po_plugins():
                plugin.ensure_structure(po_path, True)

        log.info(
            "po_new finished for project: '%s', po_name: '%s'",
            project_name,
            po_name,
        )
        return True

    except OSError as e:
        log.error("Failed to create po directory structure for '%s': '%s'", po_name, e)
        return False


@register("po_update", needs_repositories=True, desc="Update an existing PO for a project")
def po_update(
    env: Dict, projects_info: Dict, project_name: str, po_name: str, force: bool = False, tui: bool = False
) -> bool:
    """
    Update an existing PO directory structure (must already exist).
    Reuses po_new with po_update=True to leverage the same workflow.
    """
    return po_new(env, projects_info, project_name, po_name, force=force, tui=tui, po_check_exists=True)


@register("po_del", needs_repositories=True, desc="Delete a PO for a project")
def po_del(env: Dict, projects_info: Dict, project_name: str, po_name: str, force: bool = False) -> bool:
    """
    Delete the specified PO directory and remove it from all project configurations.
    Args:
        env (dict): Global environment dict.
        projects_info (dict): All projects info.
        project_name (str): Project name.
        po_name (str): Name of the PO to delete.
        force (bool): If True, skip confirmation prompt.
    Returns:
        bool: True if success, otherwise False.
    """
    log.info("start po_del for project: '%s', po_name: '%s'", project_name, po_name)

    # Validate po_name format
    if not re.match(r"^po[a-z0-9_]*$", po_name):
        log.error(
            "po_name '%s' is invalid. It must start with 'po' and only contain lowercase letters, digits, and underscores.",
            po_name,
        )
        return False

    project_cfg = projects_info.get(project_name, {})
    board_name = project_cfg.get("board_name")
    board_path = project_cfg.get("board_path")
    if not board_name or not board_path:
        log.error("Board info missing for project '%s'", project_name)
        return False

    board_path = os.path.join(env["projects_path"], board_name)
    po_dir = os.path.join(board_path, "po")
    po_path = os.path.join(po_dir, po_name)

    # Check if PO directory exists
    if not os.path.exists(po_path):
        log.error("PO directory '%s' does not exist", po_path)
        return False

    # Define helper functions as local functions
    def __confirm_deletion(po_name, po_path):
        """Show deletion information and ask for user confirmation."""
        print("\n=== PO Deletion Confirmation ===")
        print(f"PO Name: {po_name}")
        print(f"PO Path: {po_path}")

        # Show directory contents
        if os.path.exists(po_path):
            print("\nDirectory contents:")
            __print_directory_tree(po_path, prefix="  ")

        # Show which projects use this PO
        using_projects = __find_projects_using_po(po_name, projects_info)
        if using_projects:
            print("\nProjects using this PO:")
            for project in using_projects:
                print(f"  - {project}")
        else:
            print("\nNo projects are currently using this PO.")

        print("\nWARNING: This action will:")
        print("  1. Permanently delete the PO directory and all its contents")
        print("  2. Remove this PO from all project configurations")
        print("  3. This action cannot be undone!")

        while True:
            response = input(f"\nAre you sure you want to delete PO '{po_name}'? (yes/no): ").strip().lower()
            if response in ["yes", "y"]:
                return True
            if response in ["no", "n"]:
                return False
            print("Please enter 'yes' or 'no'.")

    def __print_directory_tree(path, prefix="", max_depth=3, current_depth=0):
        """Print a tree representation of directory contents."""
        if current_depth >= max_depth:
            print(f"{prefix}... (max depth reached)")
            return

        try:
            items = os.listdir(path)
            for i, item in enumerate(sorted(items)):
                item_path = os.path.join(path, item)
                is_last = i == len(items) - 1
                current_prefix = prefix + ("└── " if is_last else "├── ")

                if os.path.isdir(item_path):
                    print(f"{current_prefix}{item}/")
                    next_prefix = prefix + ("    " if is_last else "│   ")
                    __print_directory_tree(item_path, next_prefix, max_depth, current_depth + 1)
                else:
                    size = os.path.getsize(item_path)
                    print(f"{current_prefix}{item} ({size} bytes)")
        except OSError as e:
            print(f"{prefix}Error reading directory: {e}")

    def __find_projects_using_po(po_name, projects_info):
        """Find all projects that use the specified PO."""
        using_projects = []
        for project_name, project_cfg in projects_info.items():
            config = project_cfg.get("config", {}) if isinstance(project_cfg, dict) else {}
            po_config = str(config.get("PROJECT_PO_CONFIG", "")).strip()
            if not po_config:
                continue

            # Check if this PO is used in the config
            tokens = re.findall(r"-?\w+(?:\[[^\]]+\])?", po_config)
            for token in tokens:
                base = token.lstrip("-")
                base = base.split("[", 1)[0]
                if base == po_name:
                    using_projects.append(project_name)
                    break

        return using_projects

    def __remove_po_from_config_string(config_string, po_name):
        """Remove the specified PO from a PROJECT_PO_CONFIG string."""
        if not config_string:
            return config_string
        tokens = re.findall(r"-?\w+(?:\[[^\]]+\])?", config_string)
        updated_tokens = []
        for token in tokens:
            # Remove leading '-' and trailing '[...]' for comparison
            base = token.lstrip("-")
            base = base.split("[", 1)[0]
            if base != po_name:
                updated_tokens.append(token)
            else:
                log.debug(
                    "Removing PO '%s' from config string token: '%s'",
                    po_name,
                    token,
                )
        return " ".join(updated_tokens)

    def __update_ini_file(ini_file, projects, po_name):
        """Update the ini file to remove the specified PO from all project configurations."""
        log.debug("Updating ini file: '%s' to remove PO '%s'", ini_file, po_name)

        try:
            # Read the current ini file
            with open(ini_file, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # Parse the file and update PROJECT_PO_CONFIG lines
            updated_lines = []
            current_section = None
            in_project_section = False

            for line in lines:
                stripped_line = line.strip()

                # Check if this is a section header
                if stripped_line.startswith("[") and stripped_line.endswith("]"):
                    current_section = stripped_line[1:-1].strip()
                    in_project_section = current_section in projects
                    updated_lines.append(line)
                    continue

                # If we're in a project section and this is a PROJECT_PO_CONFIG line
                if in_project_section and stripped_line.replace(" ", "").startswith("PROJECT_PO_CONFIG="):
                    # Parse the current config and remove the PO
                    config_value = line.split("=", 1)[1].strip()
                    updated_config = __remove_po_from_config_string(config_value, po_name)
                    # Update the line
                    updated_lines.append(f"PROJECT_PO_CONFIG={updated_config}\n")
                    log.debug(
                        "Updated PROJECT_PO_CONFIG for project '%s': '%s' -> '%s'",
                        current_section,
                        config_value,
                        updated_config,
                    )
                else:
                    updated_lines.append(line)

            # Write the updated file
            with open(ini_file, "w", encoding="utf-8") as f:
                f.writelines(updated_lines)

            log.info("Updated ini file: '%s'", ini_file)
            return True

        except OSError as e:
            log.error("Failed to update ini file '%s': '%s'", ini_file, e)
            return False

    def __remove_po_from_configs(po_name, projects_info):
        """Remove the specified PO from all project configurations."""
        log.debug("Removing PO '%s' from all project configurations", po_name)

        # Group projects by their board and ini file
        board_configs = {}
        for project_name, project_cfg in projects_info.items():
            board_name = project_cfg.get("board_name")
            ini_file = project_cfg.get("ini_file")
            if not board_name or not ini_file:
                continue
            if board_name not in board_configs:
                board_configs[board_name] = {}
            if ini_file not in board_configs[board_name]:
                board_configs[board_name][ini_file] = []
            board_configs[board_name][ini_file].append(project_name)

        # Process each ini file
        for board_name, ini_files in board_configs.items():
            for ini_file, projects in ini_files.items():
                if not __update_ini_file(ini_file, projects, po_name):
                    return False

        return True

    # Show what will be deleted and ask for confirmation
    if not force:
        if not __confirm_deletion(po_name, po_path):
            log.info("po_del cancelled by user")
            return False

    # First, remove the PO from all project configurations
    if not __remove_po_from_configs(po_name, projects_info):
        log.error("Failed to remove PO '%s' from project configurations", po_name)
        return False

    # Then delete the PO directory
    try:
        shutil.rmtree(po_path)
        log.info("Deleted PO directory: '%s'", po_path)

        # Check if po directory is now empty and remove it if so
        if os.path.exists(po_dir) and not os.listdir(po_dir):
            os.rmdir(po_dir)
            log.info("Removed empty po directory: '%s'", po_dir)

    except OSError as e:
        log.error("Failed to delete PO directory '%s': '%s'", po_path, e)
        return False

    for repo_path, _repo_name in env.get("repositories", []) or []:
        record_path = _po_applied_record_path(repo_path, board_name, project_name, po_name)
        try:
            if os.path.exists(record_path):
                os.remove(record_path)
        except OSError:
            pass

    log.info("po_del finished for project: '%s', po_name: '%s'", project_name, po_name)
    return True


@register("po_status", needs_repositories=True, desc="Show applied record status for a project")
def po_status(
    env: Dict,
    projects_info: Dict,
    project_name: str,
    po: str = "",
    short: bool = False,
    json: bool = False,
) -> List[dict]:
    """
    Show applied record status for configured POs of the specified project.

    Args:
        env (dict): Global environment dict.
        projects_info (dict): All projects info.
        project_name (str): Project name.
        po (str): Optional PO filter; only show these POs (comma/space separated) from PROJECT_PO_CONFIG.
        short (bool): If True, only print per-PO summary.
        json (bool): If True, print JSON output to stdout.
    Returns:
        list: List of dicts with per-PO applied record status.
    """
    log.info("start po_status for project: '%s'", project_name)
    project_info = projects_info.get(project_name, {}) if isinstance(projects_info, dict) else {}
    project_cfg = project_info.get("config", {}) if isinstance(project_info, dict) else {}
    board_name = project_info.get("board_name") if isinstance(project_info, dict) else None
    if not board_name:
        log.error("Cannot find board name for project: '%s'", project_name)
        return []

    board_path = os.path.join(env["projects_path"], board_name)
    po_dir = os.path.join(board_path, "po")
    if not os.path.isdir(po_dir):
        log.warning("No po directory found for '%s'", project_name)
        return []

    po_config = str(project_cfg.get("PROJECT_PO_CONFIG", "") or "").strip()
    if not po_config:
        log.warning("No PROJECT_PO_CONFIG found for '%s'", project_name)
        return []

    apply_pos, _, _ = parse_po_config(po_config)
    requested_pos = _parse_po_filter(po)
    filtered = _filter_pos_from_config(apply_pos, requested_pos)
    if filtered is None:
        return []
    apply_pos = filtered
    if not apply_pos:
        log.warning("No POs selected for '%s' after --po filter; nothing to do.", project_name)
        return []

    runtime = PoPluginRuntime(
        board_name=board_name,
        project_name=project_name,
        repositories=env.get("repositories", []),
        workspace_root=os.getcwd(),
        po_configs=env.get("po_configs", {}),
    )

    repo_entries = sorted(runtime.repositories, key=lambda item: (item[1] != "root", item[1]))

    items: List[dict] = []
    for po_name in sorted(apply_pos):
        rows: List[dict] = []
        applied_count = 0

        for repo_path, repo_name in repo_entries:
            record_path = runtime.applied_record_path(repo_path, po_name)
            exists = os.path.isfile(record_path)
            record = runtime.load_applied_record(repo_path, po_name) if exists else None

            row_status = "missing"
            applied_at = None
            record_ok = False
            counts = None
            if exists:
                applied_count += 1
                if record is None:
                    row_status = "unreadable"
                else:
                    record_ok = True
                    row_status = str(record.get("status") or "applied")
                    applied_at = record.get("applied_at")
                    counts = {
                        "commits": len(record.get("commits") or []),
                        "patches": len(record.get("patches") or []),
                        "overrides": len(record.get("overrides") or []),
                        "custom": len(record.get("custom") or []),
                        "commands": len(record.get("commands") or []),
                    }

            rows.append(
                {
                    "repo_name": repo_name,
                    "repo_path": os.path.abspath(repo_path),
                    "record_path": record_path,
                    "record_exists": exists,
                    "record_ok": record_ok,
                    "status": row_status,
                    "applied_at": applied_at,
                    "counts": counts,
                }
            )

        # Workspace-level record (used by custom copies that don't map into repos).
        workspace_record_path = runtime.applied_record_path(runtime.workspace_root, po_name)
        if os.path.isfile(workspace_record_path):
            record = runtime.load_applied_record(runtime.workspace_root, po_name)
            row_status = "unreadable" if record is None else str(record.get("status") or "applied")
            applied_at = None
            record_ok = False
            counts = None
            if record is not None:
                record_ok = True
                applied_at = record.get("applied_at")
                counts = {
                    "commits": len(record.get("commits") or []),
                    "patches": len(record.get("patches") or []),
                    "overrides": len(record.get("overrides") or []),
                    "custom": len(record.get("custom") or []),
                    "commands": len(record.get("commands") or []),
                }

            rows.append(
                {
                    "repo_name": "workspace",
                    "repo_path": runtime.workspace_root,
                    "record_path": workspace_record_path,
                    "record_exists": True,
                    "record_ok": record_ok,
                    "status": row_status,
                    "applied_at": applied_at,
                    "counts": counts,
                }
            )
            applied_count += 1

        items.append(
            {
                "name": po_name,
                "repo_count": len(rows),
                "applied_record_count": applied_count,
                "repos": rows,
            }
        )

    if json:
        payload = {
            "schema_version": 1,
            "project_name": project_name,
            "board_name": board_name,
            "items": items,
        }
        print(jsonlib.dumps(payload, indent=2, ensure_ascii=False))
        return items

    print(f"\nPO status for project: {project_name} (board: {board_name})")
    print("  Note: missing records may mean the PO was not applied, or it did not target that repo.")
    for item in items:
        name = item["name"]
        applied = item["applied_record_count"]
        total = item["repo_count"]
        print(f"\nPO: {name}  applied records: {applied}/{total}")
        if short:
            continue
        for row in item["repos"]:
            repo_name = row["repo_name"]
            if not row["record_exists"]:
                print(f"  - {repo_name}: not applied")
                continue
            applied_at = row.get("applied_at") or ""
            status = row.get("status") or "applied"
            if applied_at:
                print(f"  - {repo_name}: {status} (applied_at={applied_at})")
            else:
                print(f"  - {repo_name}: {status}")

    return items


@register("po_clear", needs_repositories=True, desc="Clear applied record markers for a project")
def po_clear(
    env: Dict,
    projects_info: Dict,
    project_name: str,
    po: str = "",
    dry_run: bool = False,
) -> bool:
    """
    Clear applied record markers for configured POs of the specified project.

    Notes:
    - This does NOT revert any file changes. It only removes applied record markers.
    - Use `po_revert` if you want to revert changes.

    Args:
        env (dict): Global environment dict.
        projects_info (dict): All projects info.
        project_name (str): Project name.
        po (str): Optional PO filter; only clear these POs (comma/space separated) from PROJECT_PO_CONFIG.
        dry_run (bool): If True, only print planned actions without deleting files.
    Returns:
        bool: True if success, otherwise False.
    """
    log.info("start po_clear for project: '%s'", project_name)
    project_info = projects_info.get(project_name, {}) if isinstance(projects_info, dict) else {}
    project_cfg = project_info.get("config", {}) if isinstance(project_info, dict) else {}
    board_name = project_info.get("board_name") if isinstance(project_info, dict) else None
    if not board_name:
        log.error("Cannot find board name for project: '%s'", project_name)
        return False

    projects_path = env["projects_path"]
    board_path = os.path.join(projects_path, board_name)
    po_dir = os.path.join(board_path, "po")

    po_config = str(project_cfg.get("PROJECT_PO_CONFIG", "") or "").strip()
    if not po_config:
        log.warning("No PROJECT_PO_CONFIG found for '%s'", project_name)
        return True

    apply_pos, _, _ = parse_po_config(po_config)
    requested_pos = _parse_po_filter(po)
    filtered = _filter_pos_from_config(apply_pos, requested_pos)
    if filtered is None:
        return False
    apply_pos = filtered
    if not apply_pos:
        log.warning("No POs selected for '%s' after --po filter; nothing to do.", project_name)
        return True

    repositories = env.get("repositories", []) or []
    roots = {os.path.abspath(repo_path) for repo_path, _repo_name in repositories}
    roots.add(os.path.abspath(os.getcwd()))

    for po_name in apply_pos:
        legacy_flag = os.path.join(po_dir, po_name, "po_applied")
        if os.path.isfile(legacy_flag):
            if dry_run:
                log.info("DRY-RUN: would remove legacy marker: %s", legacy_flag)
            else:
                try:
                    os.remove(legacy_flag)
                    log.info("Removed legacy marker: %s", legacy_flag)
                except OSError as exc:
                    log.warning("Failed to remove legacy marker '%s': %s", legacy_flag, exc)

        for root in sorted(roots):
            record_path = _po_applied_record_path(root, board_name, project_name, po_name)
            if not os.path.exists(record_path):
                continue
            if dry_run:
                log.info("DRY-RUN: would remove applied record: %s", record_path)
                continue
            try:
                os.remove(record_path)
                log.info("Removed applied record: %s", record_path)
            except OSError as exc:
                log.warning("Failed to remove applied record '%s': %s", record_path, exc)

    log.info("po_clear finished for project: '%s'", project_name)
    return True


@register("po_list", needs_repositories=False, desc="List configured POs for a project")
def po_list(
    env: Dict,
    projects_info: Dict,
    project_name: str,
    short: bool = False,
    po: str = "",
    json: bool = False,
) -> List[dict]:
    """
    List all enabled PO (patch/override) directories for the specified project.
    Args:
        env (dict): Global environment dict.
        projects_info (dict): All projects info.
        project_name (str): Project name.
        short (bool): If True, only list po names, not details.
        po (str): Optional PO filter; only list these POs (comma/space separated) from PROJECT_PO_CONFIG.
        json (bool): If True, print JSON output to stdout.
    Returns:
        list: List of dicts with PO info (name, commit_files, patch_files, override_files)
    """
    log.info("start po_list for project: '%s'", project_name)
    project_info = projects_info.get(project_name, {})
    project_cfg = project_info.get("config", {})
    board_name = project_info.get("board_name")
    if not board_name:
        log.error("Cannot find board name for project: '%s'", project_name)
        return []

    board_path = os.path.join(env["projects_path"], board_name)
    po_dir = os.path.join(board_path, "po")
    if not os.path.isdir(po_dir):
        log.warning("No po directory found for '%s'", project_name)
        return []

    # Get po configurations from env
    po_configs = env.get("po_configs", {})

    # Get enabled pos from config
    po_config = project_cfg.get("PROJECT_PO_CONFIG", "").strip()
    apply_pos = []
    if po_config:
        apply_pos, _, _ = parse_po_config(po_config)
    requested_pos = _parse_po_filter(po)
    filtered = _filter_pos_from_config(apply_pos, requested_pos)
    if filtered is None:
        return []
    apply_pos = filtered

    runtime = PoPluginRuntime(
        board_name=board_name,
        project_name=project_name,
        repositories=env.get("repositories", []),
        workspace_root=os.getcwd(),
        po_configs=po_configs,
    )
    plugins = get_po_plugins()

    # Only list POs enabled in configuration
    po_infos = []
    for po_name in sorted(apply_pos):
        po_path = os.path.join(po_dir, po_name)
        if not os.path.isdir(po_path):
            continue

        po_info = {
            "name": po_name,
            "commit_files": [],
            "patch_files": [],
            "override_files": [],
            "custom_dirs": [],
        }
        for plugin in plugins:
            po_info.update(plugin.list_files(po_path, runtime))
        po_infos.append(po_info)

    if json:
        payload = {
            "schema_version": 1,
            "project_name": project_name,
            "board_name": board_name,
            "items": po_infos,
        }
        print(jsonlib.dumps(payload, indent=2, ensure_ascii=False))
        return po_infos

    # Print summary
    print(f"\nConfigured PO list for project: {project_name} (board: {board_name})")
    if not po_infos:
        print("  No configured PO found.")
    elif short:
        for po in po_infos:
            print(f"  {po['name']}")
    else:
        for po in po_infos:
            print(f"\nPO: {po['name']}")
            print("  commits:")
            if po.get("commit_files"):
                for cf in po["commit_files"]:
                    print(f"    - {cf}")
            else:
                print("    (none)")
            print("  patches:")
            if po["patch_files"]:
                for pf in po["patch_files"]:
                    print(f"    - {pf}")
            else:
                print("    (none)")
            print("  overrides:")
            if po["override_files"]:
                for of in po["override_files"]:
                    print(f"    - {of}")
            else:
                print("    (none)")

            # Show custom directories if any
            if po["custom_dirs"]:
                for custom_dir_info in po["custom_dirs"]:
                    print(f"  {custom_dir_info['section']} ({custom_dir_info['dir']}):")
                    print(f"    file copy config: {custom_dir_info['file_copy_config']}")
                    print("    files:")
                    if custom_dir_info["files"]:
                        for cf in custom_dir_info["files"]:
                            print(f"      - {cf}")
                    else:
                        print("      (none)")
    return po_infos
