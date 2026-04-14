"""
Shared helpers for PO (Patch/Override) plugin implementations.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from typing import Any, Dict, List


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


def extract_original_commit_sha(patch_text: str) -> str | None:
    """Extract the leading `From <sha>` commit id from a format-patch payload."""
    match = re.search(r"^From ([0-9a-fA-F]{7,40})\b", patch_text, re.MULTILINE)
    if not match:
        return None
    return match.group(1).lower()


def repo_history_contains_commit(repo_path: str, commit_sha: str) -> bool:
    """Return True when `commit_sha` is reachable from the repository HEAD."""
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit_sha, "HEAD"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0
