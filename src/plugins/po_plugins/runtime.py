"""
Runtime helpers for PO (Patch/Override) plugins.

This module centralizes:
- applied record placement under repo roots
- command execution + applied-record command logging
- repo mapping utilities shared across plugin types
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from src.log_manager import log, log_cmd_event

from .utils import po_applied_record_path, write_json_atomic


@dataclass
class PoPluginContext:
    project_name: str
    board_name: str
    po_name: str
    po_path: str
    po_commit_dir: str
    po_patch_dir: str
    po_override_dir: str
    po_custom_dir: str
    dry_run: bool
    force: bool
    exclude_files: Dict[str, set]
    applied_records: Dict[str, Dict[str, Any]]
    # When True, ignore existing applied record markers and apply again.
    reapply: bool = False


class PoPluginRuntime:
    def __init__(
        self,
        *,
        board_name: str,
        project_name: str,
        repositories: List[Tuple[str, str]],
        workspace_root: str,
        po_configs: Dict[str, Dict[str, Any]] | None = None,
    ) -> None:
        self.board_name = board_name
        self.project_name = project_name
        self.repositories = list(repositories or [])
        self.workspace_root = workspace_root
        self.po_configs: Dict[str, Dict[str, Any]] = dict(po_configs or {})

        self.repo_map: Dict[str, str] = {rname: repo_path for repo_path, rname in self.repositories}
        self.repo_path_to_name: Dict[str, str] = {
            os.path.abspath(repo_path): rname for repo_path, rname in self.repositories
        }

    def applied_record_path(self, repo_root: str, po_name: str) -> str:
        return po_applied_record_path(repo_root, self.board_name, self.project_name, po_name)

    def applied_record_exists(self, repo_root: str, po_name: str) -> bool:
        return os.path.isfile(self.applied_record_path(repo_root, po_name))

    def load_applied_record(self, repo_root: str, po_name: str) -> Optional[Dict[str, Any]]:
        record_path = self.applied_record_path(repo_root, po_name)
        if not os.path.exists(record_path):
            return None
        try:
            with open(record_path, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, ValueError) as e:
            log.warning("Failed to read applied record '%s': %s", record_path, e)
            return None

    @staticmethod
    def _format_command(command, cwd: str | None = None, description: str = "", shell: bool = False) -> Dict[str, Any]:
        if isinstance(command, list):
            cmd_str = " ".join(f'"{arg}"' if " " in arg else arg for arg in command)
        else:
            cmd_str = str(command)
        return {
            "description": description or "",
            "cmd": cmd_str,
            "cwd": cwd or "",
            "shell": bool(shell),
        }

    def get_repo_record(self, ctx: PoPluginContext, repo_root: str, repo_name: str) -> Dict[str, Any]:
        abs_repo_root = os.path.abspath(repo_root)
        record = ctx.applied_records.get(abs_repo_root)
        if record is None:
            record = {
                "schema_version": 2,
                "status": "applied",
                "applied_at": datetime.now().isoformat(),
                "project_name": ctx.project_name,
                "board_name": ctx.board_name,
                "po_name": ctx.po_name,
                "repo_name": repo_name,
                "repo_path": abs_repo_root,
                "commits": [],
                "patches": [],
                "overrides": [],
                "custom": [],
                "commands": [],
            }
            ctx.applied_records[abs_repo_root] = record
        return record

    def execute_command(
        self,
        ctx: PoPluginContext,
        repo_root: str,
        repo_name: str,
        command,
        *,
        cwd: str | None = None,
        description: str = "",
        shell: bool = False,
    ) -> subprocess.CompletedProcess:
        """Execute command and record it to repo-root applied record."""
        formatted = self._format_command(command, cwd=cwd, description=description, shell=shell)

        if getattr(ctx, "dry_run", False):
            log.info("DRY-RUN: %s", formatted["cmd"])
            return subprocess.CompletedProcess(args=command, returncode=0, stdout="", stderr="")

        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            shell=shell,
        )

        log_cmd_event(
            log,
            command=command,
            cwd=cwd,
            description=description,
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
        )

        formatted["returncode"] = result.returncode
        record = self.get_repo_record(ctx, repo_root, repo_name)
        record["commands"].append(formatted)
        return result

    def finalize_records(self, ctx: PoPluginContext) -> None:
        for repo_root, record in ctx.applied_records.items():
            record_path = self.applied_record_path(repo_root, ctx.po_name)
            write_json_atomic(record_path, record)

    def resolve_repo_for_target_path(self, target_path: str) -> Optional[Tuple[str, str, Optional[str]]]:
        """Best-effort map a custom target path to a repository root for record placement."""
        candidate = target_path
        if candidate.endswith(os.sep) and len(candidate) > 1:
            candidate = candidate.rstrip(os.sep)
        abs_target = candidate
        if not os.path.isabs(abs_target):
            abs_target = os.path.abspath(os.path.join(self.workspace_root, abs_target))
        abs_target_real = os.path.realpath(abs_target)

        best: Optional[Tuple[str, str, Optional[str]]] = None
        best_len = -1
        for repo_path, repo_name in self.repositories:
            repo_real = os.path.realpath(repo_path)
            try:
                common = os.path.commonpath([repo_real, abs_target_real])
            except ValueError:
                continue
            if common == repo_real and len(repo_real) > best_len:
                rel = os.path.relpath(abs_target_real, repo_real)
                best = (os.path.abspath(repo_path), repo_name, (rel if rel != "." else "."))
                best_len = len(repo_real)

        if best:
            return best

        root_repo_path = next((path for path, name in self.repositories if name == "root"), None)
        if root_repo_path:
            root_real = os.path.realpath(root_repo_path)
            try:
                if os.path.commonpath([root_real, abs_target_real]) == root_real:
                    rel = os.path.relpath(abs_target_real, root_real)
                    return os.path.abspath(root_repo_path), "root", (rel if rel != "." else ".")
            except ValueError:
                pass
            return os.path.abspath(root_repo_path), "root", None

        return None
