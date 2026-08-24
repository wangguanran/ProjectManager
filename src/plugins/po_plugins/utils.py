"""
Shared helpers for PO (Patch/Override) plugin implementations.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from typing import Any, Dict, List, Optional

SKIPPED_COMMIT_STATUSES = {"already_applied", "already_in_history"}


def redact_patch_diagnostic(
    value: object,
    *,
    patch_file: str,
    patch_target: str,
    rel_path: str,
    repo_name: str,
) -> str:
    """Replace apply-time absolute paths with their safe diagnostic labels."""
    text = str(value or "")
    for sensitive, replacement in ((patch_file, rel_path), (patch_target, repo_name)):
        if sensitive:
            text = text.replace(sensitive, replacement)
    return text


def safe_cache_segment(value: str) -> str:
    value = str(value or "").strip()
    if not value:
        return "_"
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value)


def po_applied_record_path(repo_path: str, board_name: str, project_name: str, po_name: str) -> str:
    """
    Where to store the applied marker/record for a PO.

    The record lives under each target repository root to avoid cross-workspace
    false positives when multiple workspaces share the same `projects/`
    directory.
    """
    repo_root = os.path.abspath(repo_path)
    return os.path.join(
        repo_root,
        ".cache",
        "po_applied",
        safe_cache_segment(board_name),
        safe_cache_segment(project_name),
        f"{safe_cache_segment(po_name)}.json",
    )


def write_json_atomic(path: str, payload: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    os.replace(tmp_path, path)


def extract_patch_targets(patch_text: str) -> List[str]:
    targets: List[str] = []
    for line in patch_text.splitlines():
        if not line.startswith("diff --git "):
            continue
        parts = line.split()
        if len(parts) < 4:
            continue
        a_path = parts[2]
        b_path = parts[3]
        if a_path.startswith("a/"):
            a_path = a_path[2:]
        if b_path.startswith("b/"):
            b_path = b_path[2:]
        if b_path and b_path != "/dev/null":
            targets.append(b_path)
        elif a_path and a_path != "/dev/null":
            targets.append(a_path)
    return sorted(set(targets))


def resolve_commit_reset_target(repo_path: str, commit_entry: Dict[str, Any]) -> Optional[str]:
    """Return the commit to reset --hard to when undoing a PO-applied commit patch."""
    head_before = commit_entry.get("head_before")
    if head_before:
        return head_before

    shas = commit_entry.get("commit_shas") or []
    if not shas and commit_entry.get("head_after"):
        shas = [commit_entry["head_after"]]
    if not shas:
        return None

    parent_result = subprocess.run(
        ["git", "rev-parse", f"{shas[0]}^"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=False,
    )
    if parent_result.returncode != 0:
        return None
    return parent_result.stdout.strip()
