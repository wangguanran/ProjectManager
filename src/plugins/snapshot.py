"""Workspace snapshot/lockfile operations for reproducibility."""

from __future__ import annotations

import json as jsonlib
import os
import subprocess
from typing import Any, Dict, List, Optional, Tuple

from src.log_manager import log
from src.operations.registry import register
from src.plugins.patch_override import parse_po_config


def _repo_head_sha(repo_path: str) -> str:
    if not os.path.isdir(os.path.join(repo_path, ".git")):
        return ""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _safe_relpath(path: str, *, start: str) -> str:
    rel = os.path.relpath(os.path.abspath(path), start=os.path.abspath(start))
    return "." if rel in ("", ".") else rel


def _write_text_atomic(path: str, text: str) -> None:
    out_dir = os.path.dirname(path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        handle.write(text)
    os.replace(tmp_path, path)


@register(
    "snapshot_create",
    needs_projects=True,
    needs_repositories=True,
    desc="Create deterministic workspace snapshot (repos + enabled POs).",
)
def snapshot_create(
    env: Dict[str, Any],
    projects_info: Dict[str, Any],
    project_name: str,
    out: str = "",
) -> bool:
    """
    Create a deterministic JSON snapshot of:
    - repository HEAD SHAs (for repositories discovered in the workspace)
    - enabled POs (resolved from PROJECT_PO_CONFIG) for the given project

    out (str): Optional output path. When empty, prints JSON to stdout.
    """
    root_path = str(env.get("root_path") or os.getcwd())
    repositories: List[Tuple[str, str]] = list(env.get("repositories", []) or [])

    project_info = projects_info.get(project_name, {}) if isinstance(projects_info, dict) else {}
    board_name = project_info.get("board_name") if isinstance(project_info, dict) else ""
    project_cfg = project_info.get("config", {}) if isinstance(project_info, dict) else {}

    po_config = str(project_cfg.get("PROJECT_PO_CONFIG", "") or "").strip()
    apply_pos, _exclude_pos, _exclude_files = parse_po_config(po_config)

    repo_items = []
    for repo_path, repo_name in sorted(repositories, key=lambda item: item[1]):
        repo_items.append(
            {
                "name": repo_name,
                "path": _safe_relpath(repo_path, start=root_path),
                "head": _repo_head_sha(repo_path),
            }
        )

    payload = {
        "schema_version": 1,
        "project_name": project_name,
        "board_name": str(board_name or ""),
        "pos": list(apply_pos),
        "repositories": repo_items,
    }
    text = jsonlib.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"

    out_path = str(out or "").strip()
    if out_path:
        _write_text_atomic(os.path.expanduser(out_path), text)
        log.info("Snapshot written to: %s", out_path)
        return True

    print(text, end="")
    return True


@register(
    "snapshot_validate",
    needs_projects=True,
    needs_repositories=True,
    desc="Validate current workspace against a snapshot (repos + enabled POs).",
)
def snapshot_validate(
    env: Dict[str, Any],
    projects_info: Dict[str, Any],
    snapshot_path: str,
    json: bool = False,
) -> bool:
    """
    Validate the current workspace against a snapshot created by `snapshot_create`.

    snapshot_path (str): Path to the snapshot JSON file.
    json (bool): Output machine-readable JSON report to stdout.
    """
    root_path = str(env.get("root_path") or os.getcwd())
    snapshot_path = os.path.expanduser(str(snapshot_path or "").strip())
    if not snapshot_path:
        log.error("snapshot_path is required")
        return False
    if not os.path.isfile(snapshot_path):
        log.error("Snapshot file not found: %s", snapshot_path)
        return False

    try:
        with open(snapshot_path, "r", encoding="utf-8") as handle:
            snapshot = jsonlib.load(handle)
    except (OSError, ValueError) as exc:
        log.error("Failed to read snapshot file '%s': %s", snapshot_path, exc)
        return False

    expected_project = str(snapshot.get("project_name") or "")
    expected_pos = list(snapshot.get("pos") or [])
    expected_repos = list(snapshot.get("repositories") or [])

    drift: Dict[str, Any] = {"repos": [], "pos": {}}

    # Validate enabled POs for the project in the snapshot.
    if expected_project:
        project_info = projects_info.get(expected_project, {}) if isinstance(projects_info, dict) else {}
        project_cfg = project_info.get("config", {}) if isinstance(project_info, dict) else {}
        current_po_config = str(project_cfg.get("PROJECT_PO_CONFIG", "") or "").strip()
        current_pos, _exclude_pos, _exclude_files = parse_po_config(current_po_config)

        missing = [p for p in expected_pos if p not in current_pos]
        extra = [p for p in current_pos if p not in expected_pos]
        if missing or extra:
            drift["pos"] = {
                "expected": expected_pos,
                "current": list(current_pos),
                "missing": missing,
                "extra": extra,
            }
    else:
        drift["pos"] = {"error": "snapshot missing project_name"}

    # Validate repositories
    current_repo_map = {name: path for path, name in (env.get("repositories", []) or [])}
    for repo in expected_repos:
        name = str(repo.get("name") or "")
        expected_head = str(repo.get("head") or "")
        if not name:
            continue
        current_path = current_repo_map.get(name)
        if not current_path:
            drift["repos"].append({"name": name, "status": "missing"})
            continue
        current_head = _repo_head_sha(current_path)
        if expected_head and current_head and expected_head != current_head:
            drift["repos"].append(
                {
                    "name": name,
                    "path": _safe_relpath(current_path, start=root_path),
                    "expected_head": expected_head,
                    "current_head": current_head,
                    "status": "head_mismatch",
                }
            )

    has_drift = bool(drift["repos"] or drift["pos"])
    report = {
        "schema_version": 1,
        "operation": "snapshot_validate",
        "snapshot_path": snapshot_path,
        "status": "drift" if has_drift else "ok",
        "project_name": expected_project,
        "drift": drift,
    }

    if json:
        print(jsonlib.dumps(report, indent=2, ensure_ascii=False))
    else:
        if not has_drift:
            print("Snapshot validation: OK")
        else:
            print("Snapshot validation: DRIFT detected")
            for item in drift.get("repos") or []:
                status = item.get("status")
                if status == "missing":
                    print(f"- repo missing: {item.get('name')}")
                elif status == "head_mismatch":
                    print(
                        f"- repo head mismatch: {item.get('name')} "
                        f"expected={item.get('expected_head')} current={item.get('current_head')}"
                    )
            pos_drift = drift.get("pos") or {}
            if pos_drift.get("missing") or pos_drift.get("extra"):
                print(f"- PO set drift: missing={pos_drift.get('missing')} extra={pos_drift.get('extra')}")

    return not has_drift
