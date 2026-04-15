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

from src.execution import execution_step, make_step_id
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
from src.plugins.po_plugins.utils import (
    extract_original_commit_sha,
    extract_patch_targets,
)
from src.plugins.po_plugins.utils import (
    po_applied_record_path as _po_applied_record_path,
)
from src.plugins.po_plugins.utils import repo_history_contains_commit

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


def _build_commit_apply_action(
    runtime: PoPluginRuntime,
    *,
    repo_root: str,
    po_name: str,
    patch_abs: str,
    source: str,
    reapply: bool,
) -> Dict[str, Any]:
    patch_text = ""
    try:
        with open(patch_abs, "r", encoding="utf-8") as handle:
            patch_text = handle.read()
    except OSError:
        patch_text = ""

    targets = extract_patch_targets(patch_text) if patch_text else []
    original_commit_sha = extract_original_commit_sha(patch_text) if patch_text else None
    action: Dict[str, Any] = {
        "po": po_name,
        "source": source,
        "targets": targets,
    }
    if original_commit_sha:
        action["original_commit_sha"] = original_commit_sha

    if not reapply and runtime.applied_record_exists(repo_root, po_name):
        action["type"] = "commit_skip"
        action["reason"] = "already_applied_record_exists"
        return action

    if original_commit_sha and repo_history_contains_commit(repo_root, original_commit_sha):
        action["type"] = "commit_skip"
        action["reason"] = "already_in_history"
        return action

    action["type"] = "commit_apply"
    return action


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
        env=env,
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
            repo_root = runtime.repo_map.get(repo_name, "")
            actions_by_repo.setdefault(repo_name, []).append(
                _build_commit_apply_action(
                    runtime,
                    repo_root=repo_root,
                    po_name=po_name,
                    patch_abs=patch_abs,
                    source=f"commits/{rel_path}",
                    reapply=bool(reapply),
                )
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
        env=env,
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
                if entry.get("status") in {"already_applied", "already_in_history"}:
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

            with execution_step(
                env,
                make_step_id("po_apply", project_name, ctx.po_name, plugin.name),
                f"PO {ctx.po_name}: apply {plugin.name}",
            ):
                if not plugin.apply(ctx, runtime):
                    log.error("po apply aborted due to error in po: '%s'", ctx.po_name)
                    return False

    # Stage 2: apply per-po plugins (may dirty working tree).
    for ctx in ctxs:
        log.info("po '%s' starting to apply patch and override%s", ctx.po_name, " (dry-run)" if dry_run else "")

        for plugin in per_po_plugins:
            with execution_step(
                env,
                make_step_id("po_apply", project_name, ctx.po_name, plugin.name),
                f"PO {ctx.po_name}: apply {plugin.name}",
            ):
                if not plugin.apply(ctx, runtime):
                    log.error("po apply aborted due to error in po: '%s'", ctx.po_name)
                    return False

        with execution_step(
            env,
            make_step_id("po_apply", project_name, ctx.po_name, "finalize"),
            f"PO {ctx.po_name}: finalize applied records",
        ):
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
        env=env,
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
            with execution_step(
                env,
                make_step_id("po_revert", project_name, po_name, plugin.name),
                f"PO {po_name}: revert {plugin.name}",
            ):
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
            with execution_step(
                env,
                make_step_id("po_revert", project_name, po_name, plugin.name),
                f"PO {po_name}: revert {plugin.name}",
            ):
                if not plugin.revert(ctx, runtime):
                    log.error("po revert aborted due to commit revert error in po: '%s'", po_name)
                    return False

        # Clear applied flag so the PO can be applied again after a successful revert.
        with execution_step(
            env,
            make_step_id("po_revert", project_name, po_name, "finalize"),
            f"PO {po_name}: finalize revert",
        ):
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


ModifiedFile = Tuple[str, str, str]


def _confirm_po_creation(po_name: str, po_path: str, board_path: str) -> bool:
    """Show PO creation details and confirm with the user."""
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


def _load_ignore_patterns(project_cfg: Dict[str, Any]) -> List[str]:
    """Load ignore patterns from project configuration and the workspace .gitignore."""
    patterns: List[str] = []

    if project_cfg:
        po_ignore_config = str(project_cfg.get("PROJECT_PO_IGNORE", "") or "").strip()
        log.debug("po_ignore_config: '%s'", po_ignore_config)
        if po_ignore_config:
            config_patterns = [p.strip() for p in po_ignore_config.split() if p.strip()]
            patterns.extend(config_patterns)

            enhanced_patterns = []
            for pattern in config_patterns:
                if any(char in pattern for char in ["*", "?", "[", "]"]):
                    continue
                enhanced_patterns.extend(
                    [
                        f"*{pattern}*",
                        f"*{pattern}/*",
                        f"*/{pattern}/*",
                        f"*/{pattern}",
                    ]
                )
            patterns.extend(enhanced_patterns)
            log.debug("Loaded ignore patterns from project config: %s", config_patterns)
            log.debug("Added enhanced patterns for path containment: %s", enhanced_patterns)

    gitignore_file = os.path.join(os.getcwd(), ".gitignore")
    if os.path.exists(gitignore_file):
        try:
            with open(gitignore_file, "r", encoding="utf-8") as file_obj:
                for line in file_obj:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        patterns.append(line)
            log.debug("Loaded ignore patterns from file: %s", gitignore_file)
        except OSError as exc:
            log.warning("Failed to read ignore file %s: %s", gitignore_file, exc)

    log.debug("Loaded ignore patterns: %s", patterns)
    return patterns


def _get_modified_files(repo_path: str, repo_name: str, ignore_patterns: List[str]) -> Optional[List[ModifiedFile]]:
    """Get modified files in one repository, including staged, working, and deleted paths."""
    modified_files: List[ModifiedFile] = []

    try:
        staged_result = subprocess.run(
            ["git", "diff", "--name-only", "--cached"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=False,
        )
        working_result = subprocess.run(
            ["git", "ls-files", "--modified", "--others", "--exclude-standard"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=False,
        )
        deleted_result = subprocess.run(
            ["git", "ls-files", "--deleted"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        log.error("Failed to get modified files for repository %s: %s", repo_name, exc)
        print(f"Warning: Failed to get modified files for repository {repo_name}: {exc}")
        return None

    staged_files = set(staged_result.stdout.strip().splitlines()) if staged_result.stdout.strip() else set()
    working_files = set(working_result.stdout.strip().splitlines()) if working_result.stdout.strip() else set()
    deleted_files = set(deleted_result.stdout.strip().splitlines()) if deleted_result.stdout.strip() else set()

    def is_ignored(file_path: str) -> bool:
        full_path = f"{repo_name}/{file_path}" if repo_name != "root" else file_path
        for pattern in ignore_patterns:
            if fnmatch.fnmatch(file_path, pattern) or fnmatch.fnmatch(full_path, pattern):
                return True
        return False

    for file_path in staged_files | working_files | deleted_files:
        if not file_path.strip() or is_ignored(file_path):
            continue

        status_result = subprocess.run(
            ["git", "status", "--porcelain", file_path],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=False,
        )
        if status_result.returncode == 0 and status_result.stdout.strip():
            status = status_result.stdout.strip()[:2]
            if file_path in deleted_files:
                status = f"{status} (staged+deleted)" if file_path in staged_files else f"{status} (deleted)"
            elif file_path in staged_files and file_path in working_files:
                status = f"{status} (staged+modified)"
            elif file_path in staged_files:
                status = f"{status} (staged)"
            else:
                status = f"{status} (working)"
        else:
            status = "?? (unknown)"

        modified_files.append((repo_name, file_path, status))

    return modified_files


def _scan_po_modified_files(
    repositories: List[Tuple[str, str]], project_cfg: Dict[str, Any]
) -> Optional[List[ModifiedFile]]:
    """Collect modified files across all project repositories."""
    ignore_patterns = _load_ignore_patterns(project_cfg)
    all_modified_files: List[ModifiedFile] = []

    for repo_path, repo_name in repositories:
        modified_files = _get_modified_files(repo_path, repo_name, ignore_patterns)
        if modified_files is None:
            return None
        if modified_files:
            all_modified_files.extend(modified_files)

    return all_modified_files


def _find_repo_path_by_name(repositories: List[Tuple[str, str]], repo_name: str) -> Optional[str]:
    """Find the repository root path for a named repo."""
    for repo_path, current_name in repositories:
        if current_name == repo_name:
            return repo_path
    return None


def _create_patch_for_file(
    repositories: List[Tuple[str, str]],
    repo_name: str,
    file_path: str,
    patches_dir: str,
    *,
    force: bool = False,
) -> bool:
    """Create a patch file for one modified file."""
    repo_path = _find_repo_path_by_name(repositories, repo_name)
    if not repo_path:
        return False

    try:
        staged_result = subprocess.run(
            ["git", "diff", "--name-only", "--cached"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        log.error("Failed to inspect staged files for %s: %s", file_path, exc)
        return False

    staged_files = staged_result.stdout.strip().splitlines() if staged_result.stdout.strip() else []
    is_staged = file_path in staged_files
    use_staged = is_staged and force

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

    default_filename = os.path.basename(file_path)
    filename = default_filename
    if not force:
        print(f"    Default patch name: {default_filename}.patch")
        custom_name = input("    Enter custom patch name (or press Enter for default): ").strip()
        if custom_name:
            filename = custom_name[:-6] if custom_name.endswith(".patch") else custom_name

    patch_file_path = (
        os.path.join(patches_dir, f"{filename}.patch")
        if repo_name == "root"
        else os.path.join(patches_dir, repo_name, f"{filename}.patch")
    )
    os.makedirs(os.path.dirname(patch_file_path), exist_ok=True)

    try:
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
    except (OSError, subprocess.SubprocessError) as exc:
        log.error("Failed to create patch for file %s: %s", file_path, exc)
        return False

    if result.returncode == 0 and result.stdout.strip():
        with open(patch_file_path, "w", encoding="utf-8") as file_obj:
            file_obj.write(result.stdout)
        return True

    print(f"    Warning: No changes found for {file_path}")
    return False


def _create_override_for_file(
    repositories: List[Tuple[str, str]],
    repo_name: str,
    file_path: str,
    overrides_dir: str,
) -> bool:
    """Copy one modified file into the PO overrides tree."""
    repo_path = _find_repo_path_by_name(repositories, repo_name)
    if not repo_path:
        return False

    src_file = os.path.join(repo_path, file_path)
    if not os.path.exists(src_file):
        print(f"    Warning: File {file_path} does not exist")
        return False

    dest_file = (
        os.path.join(overrides_dir, file_path)
        if repo_name == "root"
        else os.path.join(overrides_dir, repo_name, file_path)
    )
    os.makedirs(os.path.dirname(dest_file), exist_ok=True)

    try:
        shutil.copy2(src_file, dest_file)
    except (OSError, shutil.Error) as exc:
        log.error("Failed to create override for file %s: %s", file_path, exc)
        return False
    return True


def _create_remove_file_for_deleted_file(
    repo_name: str,
    file_path: str,
    overrides_dir: str,
    all_file_infos: Optional[List[ModifiedFile]] = None,
) -> bool:
    """Create a .remove or .gitkeep marker for deleted content."""
    deleted_files_in_same_dir = []
    for other_repo, other_path, other_status in all_file_infos or []:
        if other_repo != repo_name or other_path == file_path or "deleted" not in other_status:
            continue
        if os.path.dirname(other_path) == os.path.dirname(file_path):
            deleted_files_in_same_dir.append(other_path)

    is_directory_deletion = len(deleted_files_in_same_dir) > 0

    try:
        if is_directory_deletion:
            dir_path = os.path.dirname(file_path)
            if repo_name == "root":
                dest_dir = os.path.join(overrides_dir, dir_path) if dir_path else overrides_dir
            else:
                dest_dir = (
                    os.path.join(overrides_dir, repo_name, dir_path)
                    if dir_path
                    else os.path.join(overrides_dir, repo_name)
                )
            os.makedirs(dest_dir, exist_ok=True)
            gitkeep_file = os.path.join(dest_dir, ".gitkeep")
            with open(gitkeep_file, "w", encoding="utf-8") as file_obj:
                file_obj.write("# Directory preservation marker\n")
                file_obj.write(f"# Original directory: {dir_path}\n")
                file_obj.write(f"# Repository: {repo_name}\n")
                file_obj.write(f"# Created by po_new on {datetime.now().isoformat()}\n")
                file_obj.write("# This directory was deleted, .gitkeep prevents it from being removed\n")
            return True

        dest_file = (
            os.path.join(overrides_dir, f"{file_path}.remove")
            if repo_name == "root"
            else os.path.join(overrides_dir, repo_name, f"{file_path}.remove")
        )
        os.makedirs(os.path.dirname(dest_file), exist_ok=True)
        with open(dest_file, "w", encoding="utf-8") as file_obj:
            file_obj.write(f"# Remove marker for deleted file: {file_path}\n")
            file_obj.write(f"# This file was deleted from repository: {repo_name}\n")
            file_obj.write(f"# Created by po_new on {datetime.now().isoformat()}\n")
        return True
    except OSError as exc:
        log.error("Failed to create remove file for %s: %s", file_path, exc)
        return False


def _batch_create_patches(file_infos: List[ModifiedFile], po_path: str, repositories: List[Tuple[str, str]]) -> int:
    """Create patch files for the selected modified files."""
    patches_dir = os.path.join(po_path, "patches")
    success_count = 0

    print("  Creating patches for all selected files...")
    for repo_name, file_path, _ in file_infos:
        if _create_patch_for_file(repositories, repo_name, file_path, patches_dir, force=True):
            print(f"    ✓ Created patch for {file_path}")
            success_count += 1
        else:
            print(f"    ✗ Failed to create patch for {file_path}")

    print(f"  Completed: {success_count}/{len(file_infos)} patches created")
    return success_count


def _batch_create_overrides(file_infos: List[ModifiedFile], po_path: str, repositories: List[Tuple[str, str]]) -> int:
    """Create override files for the selected modified files."""
    overrides_dir = os.path.join(po_path, "overrides")
    success_count = 0

    print("  Creating overrides for all selected files...")
    for repo_name, file_path, _ in file_infos:
        if _create_override_for_file(repositories, repo_name, file_path, overrides_dir):
            print(f"    ✓ Created override for {file_path}")
            success_count += 1
        else:
            print(f"    ✗ Failed to create override for {file_path}")

    print(f"  Completed: {success_count}/{len(file_infos)} overrides created")
    return success_count


def _batch_create_remove_files(file_infos: List[ModifiedFile], po_path: str) -> int:
    """Create remove markers for deleted files from the selection."""
    overrides_dir = os.path.join(po_path, "overrides")
    success_count = 0
    deleted_total = len([item for item in file_infos if "deleted" in item[2]])

    print("  Creating remove files for deleted files...")
    for repo_name, file_path, status in file_infos:
        if "deleted" not in status:
            print(f"    - Skipped {file_path} (not deleted)")
            continue
        if _create_remove_file_for_deleted_file(repo_name, file_path, overrides_dir, file_infos):
            print(f"    ✓ Created remove file for {file_path}")
            success_count += 1
        else:
            print(f"    ✗ Failed to create remove file for {file_path}")

    print(f"  Completed: {success_count}/{deleted_total} remove files created")
    return success_count


def _apply_po_selection(
    file_infos: List[ModifiedFile],
    po_path: str,
    action: str,
    repositories: List[Tuple[str, str]],
) -> bool:
    """Write the selected PO files to disk using one shared action."""
    if action == "skip":
        print("Skipped selected files.")
        return True

    os.makedirs(po_path, exist_ok=True)
    log.info("Created po directory: '%s'", po_path)

    if action == "patches":
        _batch_create_patches(file_infos, po_path, repositories)
        return True
    if action == "overrides":
        _batch_create_overrides(file_infos, po_path, repositories)
        return True
    if action == "remove":
        _batch_create_remove_files(file_infos, po_path)
        return True

    log.error("Unknown PO selection action: %s", action)
    return False


def _process_multiple_files(file_infos: List[ModifiedFile], po_path: str, repositories: List[Tuple[str, str]]) -> int:
    """Process one or more files with a single shared action."""
    if not file_infos:
        return 0

    print(f"\nFiles to process ({len(file_infos)}):")
    for index, (repo_name, file_path, status) in enumerate(file_infos, 1):
        print(f"  {index:2d}. [{repo_name}] {file_path} ({status})")

    has_deleted_files = any("deleted" in status for _repo_name, _file_path, status in file_infos)
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
                return _batch_create_patches(file_infos, po_path, repositories)
            if choice == "2":
                return _batch_create_overrides(file_infos, po_path, repositories)
            if choice == "3":
                return _batch_create_remove_files(file_infos, po_path)
            if choice == "4":
                print("  - Skipped all files")
                return 0
            print("Invalid choice. Please enter 1, 2, 3, or 4.")
            continue

        choice = input("Choice (1/2/3): ").strip()
        if choice == "1":
            return _batch_create_patches(file_infos, po_path, repositories)
        if choice == "2":
            return _batch_create_overrides(file_infos, po_path, repositories)
        if choice == "3":
            print("  - Skipped all files")
            return 0
        print("Invalid choice. Please enter 1, 2, or 3.")


def _run_console_po_file_selection(
    po_path: str,
    repositories: List[Tuple[str, str]],
    project_cfg: Dict[str, Any],
) -> bool:
    """Interactive console file selection for PO creation/update."""
    print("\n=== File Selection for PO ===")
    print("Scanning for modified files in repositories...")

    if not repositories:
        print("No git repositories found.")
        return True

    project_config = project_cfg.get("config", {}) if isinstance(project_cfg, dict) else {}
    all_modified_files = _scan_po_modified_files(repositories, project_config)
    if all_modified_files is None:
        return False
    if not all_modified_files:
        print("No modified files found in any repository.")
        return True

    processed_files: set[ModifiedFile] = set()
    remaining_files = all_modified_files.copy()

    while True:
        print(f"\n=== File Selection (Remaining: {len(remaining_files)}/{len(all_modified_files)}) ===")
        if remaining_files:
            print("Remaining files to process:")
            for index, (repo_name, file_path, status) in enumerate(remaining_files, 1):
                print(f"  {index:2d}. [{repo_name}] {file_path} ({status})")
        else:
            print("All files have been processed!")
            break

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
            return True

        if selection.lower() == "all":
            files_to_process = remaining_files.copy()
            processed_count = _process_multiple_files(files_to_process, po_path, repositories)
            if processed_count > 0:
                for file_info in files_to_process:
                    processed_files.add(file_info)
            remaining_files.clear()
            continue

        try:
            values = selection.replace(",", " ").split()
            valid_indices = []
            for number in values:
                index = int(number) - 1
                if 0 <= index < len(remaining_files):
                    valid_indices.append(index)
                else:
                    print(f"Invalid file number: {number}")

            if not valid_indices:
                print("No valid file numbers provided")
                continue

            selected_files = [remaining_files[index] for index in valid_indices]
            processed_count = _process_multiple_files(selected_files, po_path, repositories)
            for index in sorted(set(valid_indices), reverse=True):
                remaining_files.pop(index)
            if processed_count > 0:
                for file_info in selected_files:
                    processed_files.add(file_info)
        except ValueError:
            print("Invalid input. Please enter a number, 'all', or 'q'.")

    return True


def prepare_po_textual_selection(
    env: Dict[str, Any],
    projects_info: Dict[str, Any],
    project_name: str,
    po_name: str,
    *,
    update_mode: bool = False,
) -> Optional[Dict[str, Any]]:
    """Collect Textual pre-selection state for `po_new` / `po_update` before the execution shell starts."""
    project_cfg = projects_info.get(project_name, {}) if isinstance(projects_info, dict) else {}
    board_name = project_cfg.get("board_name") if isinstance(project_cfg, dict) else None
    if not board_name:
        return None

    repositories = env.get("repositories", [])
    board_path = os.path.join(env["projects_path"], board_name)
    po_path = os.path.join(board_path, "po", po_name)

    if not repositories:
        return {
            "project_name": project_name,
            "po_name": po_name,
            "po_path": po_path,
            "status": "noop",
            "message": "No git repositories found.",
        }

    project_config = project_cfg.get("config", {}) if isinstance(project_cfg, dict) else {}
    modified_files = _scan_po_modified_files(repositories, project_config)
    if modified_files is None:
        return {
            "project_name": project_name,
            "po_name": po_name,
            "po_path": po_path,
            "status": "error",
            "message": "Failed to scan modified files.",
        }
    if not modified_files:
        return {
            "project_name": project_name,
            "po_name": po_name,
            "po_path": po_path,
            "status": "noop",
            "message": "No modified files found in any repository.",
        }

    from src.execution_textual import run_po_selection_dialog

    result = run_po_selection_dialog(
        po_name=po_name,
        po_path=po_path,
        modified_files=modified_files,
        update_mode=update_mode,
    )
    status = str(result.get("status") or "cancelled")
    payload: Dict[str, Any] = {
        "project_name": project_name,
        "po_name": po_name,
        "po_path": po_path,
        "status": status,
    }

    if status == "apply":
        indexes = [int(index) for index in result.get("selected_indexes", [])]
        payload["action"] = str(result.get("action") or "patches")
        payload["selected_files"] = [modified_files[index] for index in indexes]
        return payload
    if status == "skip":
        payload["message"] = "Skipped selected files."
        return payload
    if status == "noop":
        payload["message"] = "No files selected."
        return payload

    payload["message"] = "Cancelled."
    return payload


def _consume_po_textual_selection(env: Dict[str, Any], project_name: str, po_name: str) -> Optional[Dict[str, Any]]:
    """Pop the prepared Textual PO selection if it matches this invocation."""
    payload = env.pop("po_textual_selection", None)
    if not isinstance(payload, dict):
        return None
    if payload.get("project_name") != project_name or payload.get("po_name") != po_name:
        return None
    return payload


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
    _ = tui  # `--tui` remains a compatibility alias for the default Textual flow.
    log.info("start po_new for project: '%s', po_name: '%s'", project_name, po_name)
    if not re.match(r"^po[a-z0-9_]*$", po_name):
        log.error(
            "po_name '%s' is invalid. It must start with 'po' and only contain lowercase letters, digits, and underscores.",
            po_name,
        )
        return False
    project_cfg = projects_info.get(project_name, {}) if isinstance(projects_info, dict) else {}
    board_name = project_cfg.get("board_name") if isinstance(project_cfg, dict) else None
    board_path = project_cfg.get("board_path") if isinstance(project_cfg, dict) else None
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

    selection_plan = _consume_po_textual_selection(env, project_name, po_name)

    if not force and selection_plan is None:
        if not _confirm_po_creation(po_name, po_path, board_path):
            log.info("po_new cancelled by user")
            return False

    try:
        repositories = env.get("repositories", [])
        if selection_plan is not None:
            message = selection_plan.get("message")
            if message:
                print(message)
            if selection_plan.get("status") == "error":
                return False
            if selection_plan.get("status") != "apply":
                log.info(
                    "po_new finished without writing files for project: '%s', po_name: '%s'", project_name, po_name
                )
                return True

            action = str(selection_plan.get("action") or "patches")
            selected_files = selection_plan.get("selected_files", [])
            with execution_step(
                env,
                make_step_id("po_new", project_name, po_name, action),
                f"PO {po_name}: create {action}",
            ):
                if not _apply_po_selection(selected_files, po_path, action, repositories):
                    return False
        elif not force:
            if not _run_console_po_file_selection(po_path, repositories, project_cfg):
                return False

        if force:
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

    except OSError as exc:
        log.error("Failed to create po directory structure for '%s': '%s'", po_name, exc)
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
        env=env,
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
        env=env,
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
        for item in po_infos:
            print(f"  {item['name']}")
    else:
        for item in po_infos:
            print(f"\nPO: {item['name']}")
            print("  commits:")
            if item.get("commit_files"):
                for cf in item["commit_files"]:
                    print(f"    - {cf}")
            else:
                print("    (none)")
            print("  patches:")
            if item["patch_files"]:
                for pf in item["patch_files"]:
                    print(f"    - {pf}")
            else:
                print("    (none)")
            print("  overrides:")
            if item["override_files"]:
                for of in item["override_files"]:
                    print(f"    - {of}")
            else:
                print("    (none)")

            # Show custom directories if any
            if item["custom_dirs"]:
                for custom_dir_info in item["custom_dirs"]:
                    print(f"  {custom_dir_info['section']} ({custom_dir_info['dir']}):")
                    print(f"    file copy config: {custom_dir_info['file_copy_config']}")
                    print("    files:")
                    if custom_dir_info["files"]:
                        for cf in custom_dir_info["files"]:
                            print(f"      - {cf}")
                    else:
                        print("      (none)")
    return po_infos
