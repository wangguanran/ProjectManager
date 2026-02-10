"""
Patch and override operations for project management.
"""

import fnmatch
import glob
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from src.log_manager import log, log_cmd_event
from src.operations.registry import register

# from src.profiler import auto_profile  # unused


def _safe_cache_segment(value: str) -> str:
    value = str(value or "").strip()
    if not value:
        return "_"
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value)


def _po_applied_record_path(repo_path: str, board_name: str, project_name: str, po_name: str) -> str:
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
        _safe_cache_segment(board_name),
        _safe_cache_segment(project_name),
        f"{_safe_cache_segment(po_name)}.json",
    )


def _write_json_atomic(path: str, payload: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    os.replace(tmp_path, path)


def _extract_patch_targets(patch_text: str) -> List[str]:
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

    return apply_pos, exclude_pos, exclude_files


@register("po_apply", needs_repositories=True, desc="Apply patch and override for a project")
def po_apply(
    env: Dict,
    projects_info: Dict,
    project_name: str,
    dry_run: bool = False,
    force: bool = False,
) -> bool:
    """
    Apply patch and override for the specified project.
    Args:
        env (dict): Global environment dict.
        projects_info (dict): All projects info.
        project_name (str): Project name.
    Returns:
        bool: True if success, otherwise False.
    """
    projects_path = env["projects_path"]
    log.info("start po_apply for project: '%s'", project_name)
    project_info = projects_info.get(project_name, {})
    project_cfg = project_info.get("config", {})
    board_name = project_info.get("board_name")
    if not board_name:
        log.error("Cannot find board name for project: '%s'", project_name)
        return False
    board_path = os.path.join(projects_path, board_name)
    po_dir = os.path.join(board_path, "po")
    po_config = project_cfg.get("PROJECT_PO_CONFIG", "").strip()
    if not po_config:
        log.warning("No PROJECT_PO_CONFIG found for '%s'", project_name)
        return True
    apply_pos, exclude_pos, exclude_files = parse_po_config(po_config)
    log.debug("po_dir: '%s'", po_dir)
    if apply_pos:
        log.debug("apply_pos: %s", str(apply_pos))
    if exclude_pos:
        log.debug("exclude_pos: %s", str(exclude_pos))
    if exclude_files:
        log.debug("exclude_files: %s", str(exclude_files))

    # Use repositories from env
    repositories = env.get("repositories", [])
    workspace_root = os.getcwd()

    def __applied_record_exists(repo_root: str, po_name: str) -> bool:
        record_path = _po_applied_record_path(repo_root, board_name, project_name, po_name)
        return os.path.isfile(record_path)

    def __format_command(command, cwd=None, description="", shell=False):
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

    def __get_repo_record(ctx, repo_root: str, repo_name: str) -> Dict[str, Any]:
        abs_repo_root = os.path.abspath(repo_root)
        record = ctx.applied_records.get(abs_repo_root)
        if record is None:
            record = {
                "schema_version": 1,
                "status": "applied",
                "applied_at": datetime.now().isoformat(),
                "project_name": ctx.project_name,
                "board_name": ctx.board_name,
                "po_name": ctx.po_name,
                "repo_name": repo_name,
                "repo_path": abs_repo_root,
                "patches": [],
                "overrides": [],
                "custom": [],
                "commands": [],
            }
            ctx.applied_records[abs_repo_root] = record
        return record

    def __execute_command(ctx, repo_root: str, repo_name: str, command, cwd=None, description="", shell=False):
        """Execute command and record it to repo-root applied record."""
        formatted = __format_command(command, cwd=cwd, description=description, shell=shell)

        try:
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
            record = __get_repo_record(ctx, repo_root, repo_name)
            record["commands"].append(formatted)
            return result

        except Exception as e:  # pylint: disable=broad-except
            log.error("Command execution failed: %s", e)
            raise

    @dataclass
    class PoApplyContext:
        """Context container for po_apply execution.

        Holds frequently used paths and configuration for a single PO during apply:
        - project_name: current project name
        - board_name: current board name
        - po_name: current PO name
        - po_path: path to po/<po_name>
        - po_patch_dir: directory containing patch files (po/<po_name>/patches)
        - po_override_dir: directory containing override files (po/<po_name>/overrides)
        - po_custom_dir: unified custom root directory (po/<po_name>/custom)
        - exclude_files: mapping of PO name to a set of excluded relative file paths
        - po_configs: custom configuration sections from env used to drive custom apply
        - applied_records: per-repository applied records to be persisted on success
        """

        project_name: str
        board_name: str
        po_name: str
        po_path: str
        po_patch_dir: str
        po_override_dir: str
        po_custom_dir: str
        dry_run: bool
        force: bool
        exclude_files: Dict[str, set]
        po_configs: Dict
        repositories: List[Tuple[str, str]]
        workspace_root: str
        applied_records: Dict[str, Dict[str, Any]]

    def __resolve_repo_for_target_path(target_path: str) -> Optional[Tuple[str, str, Optional[str]]]:
        """Best-effort map a custom target path to a repository root for record placement."""
        candidate = target_path
        if candidate.endswith(os.sep) and len(candidate) > 1:
            candidate = candidate.rstrip(os.sep)
        abs_target = candidate
        if not os.path.isabs(abs_target):
            abs_target = os.path.abspath(os.path.join(workspace_root, abs_target))
        abs_target_real = os.path.realpath(abs_target)

        best: Optional[Tuple[str, str, Optional[str]]] = None
        best_len = -1
        for repo_path, repo_name in repositories:
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

        root_repo_path = next((path for path, name in repositories if name == "root"), None)
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

    def __apply_patch(ctx: PoApplyContext):
        """Apply patches for the specified po."""
        log.debug("po_name: '%s', po_patch_dir: '%s'", ctx.po_name, ctx.po_patch_dir)
        if not os.path.isdir(ctx.po_patch_dir):
            log.debug("No patches dir for po: '%s'", ctx.po_name)
            return True
        log.debug("applying patches for po: '%s'", ctx.po_name)

        def find_repo_path_by_name(repo_name):
            for repo_path, rname in repositories:
                if rname == repo_name:
                    return repo_path
            return None

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
                patch_target = find_repo_path_by_name(repo_name)
                if not patch_target:
                    log.error("Cannot find repo path for '%s'", repo_name)
                    return False
                patch_file = os.path.join(current_dir, fname)
                log.debug("will apply patch: '%s' to repo: '%s'", patch_file, patch_target)
                if __applied_record_exists(patch_target, ctx.po_name):
                    log.info(
                        "po '%s' already applied for repo '%s', skipping patch '%s'", ctx.po_name, repo_name, rel_path
                    )
                    continue

                try:
                    with open(patch_file, "r", encoding="utf-8") as f:
                        patch_targets = _extract_patch_targets(f.read())
                except OSError as e:
                    log.error("Failed to read patch '%s': %s", patch_file, e)
                    return False

                record = __get_repo_record(ctx, patch_target, repo_name)
                record["patches"].append(
                    {
                        "patch_file": os.path.relpath(patch_file, start=ctx.po_path),
                        "targets": patch_targets,
                    }
                )
                try:
                    result = __execute_command(
                        ctx,
                        patch_target,
                        repo_name,
                        ["git", "apply", patch_file],
                        cwd=patch_target,
                        description=f"Apply patch {os.path.basename(patch_file)} to {repo_name}",
                    )
                    log.info("applying patch: '%s' to repo: '%s'", patch_file, patch_target)
                    log.debug(
                        "git apply result: returncode: '%s', stdout: '%s', stderr: '%s'",
                        result.returncode,
                        result.stdout,
                        result.stderr,
                    )
                    if result.returncode != 0:
                        log.error(
                            "Failed to apply patch '%s': '%s'",
                            patch_file,
                            result.stderr,
                        )
                        return False
                    log.info("patch applied successfully for repo: '%s'", patch_target)
                except subprocess.SubprocessError as e:
                    log.error("Subprocess error applying patch '%s': '%s'", patch_file, e)
                    return False
                except OSError as e:
                    log.error("OS error applying patch '%s': '%s'", patch_file, e)
                    return False

        return True

    def __apply_override(ctx: PoApplyContext):
        """Apply overrides for the specified po."""
        log.debug("po_name: '%s', po_override_dir: '%s'", ctx.po_name, ctx.po_override_dir)
        if not os.path.isdir(ctx.po_override_dir):
            log.debug("No overrides dir for po: '%s'", ctx.po_name)
            return True
        log.debug("applying overrides for po: '%s'", ctx.po_name)

        repo_map = {rname: repo_path for repo_path, rname in repositories}
        repo_path_to_name = {os.path.abspath(repo_path): rname for repo_path, rname in repositories}
        repo_names = sorted(
            [name for name in repo_map.keys() if name != "root"],
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

                repo_root = repo_map.get(repo_name)
                if not repo_root:
                    log.error("Cannot find repo path for override target repo '%s' (from '%s')", repo_name, rel_path)
                    return False

                repo_to_files.setdefault(repo_root, []).append((src_file, dest_rel, is_remove))

        # 2) Perform copies/deletes per repo_root (with applied record gating)
        for repo_root, file_list in repo_to_files.items():
            repo_root_abs = os.path.abspath(repo_root)
            record_repo_name = repo_path_to_name.get(repo_root_abs, "unknown")
            if __applied_record_exists(repo_root_abs, ctx.po_name):
                log.info("po '%s' already applied for repo '%s', skipping overrides", ctx.po_name, record_repo_name)
                continue

            log.debug(
                "override repo_root: '%s'",
                repo_root,
            )
            for src_file, dest_rel, is_remove in file_list:
                log.debug("override src_file: '%s', dest_rel: '%s', is_remove: %s", src_file, dest_rel, is_remove)
                try:
                    _validate_in_repo(repo_root, dest_rel)
                except ValueError as e:
                    log.error("%s", e)
                    return False

                record = __get_repo_record(ctx, repo_root_abs, record_repo_name)
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
                            # Use __execute_command for delete operation
                            result = __execute_command(
                                ctx,
                                repo_root_abs,
                                record_repo_name,
                                ["rm", "-rf", dest_rel],
                                cwd=repo_root,
                                description=f"Remove file {dest_rel}",
                            )

                            if result.returncode != 0:
                                log.error("Failed to remove file '%s': %s", dest_rel, result.stderr)
                                return False

                            log.info("Removed file '%s' (repo_root=%s)", dest_rel, repo_root)
                        else:
                            log.debug("File '%s' does not exist, skipping removal", dest_rel)
                    except OSError as e:
                        log.error(
                            "Failed to remove file '%s': '%s'",
                            dest_rel,
                            e,
                        )
                        return False
                else:
                    # Perform copy operation
                    dest_dir = os.path.dirname(dest_rel)
                    if not ctx.dry_run and dest_dir:
                        os.makedirs(os.path.join(repo_root, dest_dir), exist_ok=True)
                    try:
                        # Use __execute_command for copy operation
                        result = __execute_command(
                            ctx,
                            repo_root_abs,
                            record_repo_name,
                            ["cp", "-rf", src_file, dest_rel],
                            cwd=repo_root,
                            description="Copy override file",
                        )

                        if result.returncode != 0:
                            log.error(
                                "Failed to copy override file '%s' to '%s': %s", src_file, dest_rel, result.stderr
                            )
                            return False

                        log.info("Copied override file '%s' to '%s' (repo_root=%s)", src_file, dest_rel, repo_root)
                    except OSError as e:
                        log.error(
                            "Failed to copy override file '%s' to '%s': '%s'",
                            src_file,
                            dest_rel,
                            e,
                        )
                        return False

        return True

    def __apply_custom(ctx: PoApplyContext):
        """Apply all custom configurations for the specified po.

        - All custom files are expected under po/<po_name>/custom[/subdir]
        - Each section in po_configs may specify PROJECT_PO_DIR as a subdir under custom
        - PROJECT_PO_FILE_COPY rules are executed relative to the resolved custom subdir
        """
        log.debug("po_name: '%s', po_custom_dir: '%s'", ctx.po_name, ctx.po_custom_dir)
        if not os.path.isdir(ctx.po_custom_dir):
            log.debug("No custom dir for po: '%s'", ctx.po_name)
            return True
        log.debug("applying custom for po: '%s'", ctx.po_name)

        if not isinstance(ctx.po_configs, dict) or not ctx.po_configs:
            log.debug("No po_configs provided for custom apply of po: '%s'", ctx.po_name)
            return True

        def __execute_file_copy(ctx, section_name, section_custom_dir, source_pattern, target_path):
            """Execute a single file copy operation with wildcard and directory support.

            - Expands *, ?, [], and ** patterns via glob (no shell).
            - Uses `cp -rf` with shell=False to handle file/dir copies safely.
            """
            log.debug("Executing file copy: source='%s', target='%s'", source_pattern, target_path)

            abs_pattern = os.path.join(section_custom_dir, source_pattern)
            record_repo = __resolve_repo_for_target_path(target_path)
            if record_repo is None:
                record_repo_root = workspace_root
                record_repo_name = "workspace"
                path_in_repo = None
            else:
                record_repo_root, record_repo_name, path_in_repo = record_repo

            if __applied_record_exists(record_repo_root, ctx.po_name):
                log.info(
                    "po '%s' already applied for repo '%s', skipping custom copy to '%s'",
                    ctx.po_name,
                    record_repo_name,
                    target_path,
                )
                return True

            record = __get_repo_record(ctx, record_repo_root, record_repo_name)
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

                    result = __execute_command(
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

        for section_name, section_config in ctx.po_configs.items():
            # Only apply the configuration that matches the current PO name.
            if section_name != f"po-{ctx.po_name}":
                continue

            po_config_dict = section_config
            po_subdir = po_config_dict.get("PROJECT_PO_DIR", "").rstrip("/")

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
                    os.path.relpath(
                        section_custom_dir, start=os.path.join(os.path.dirname(ctx.po_custom_dir), ctx.po_name)
                    )
                    if os.path.isdir(section_custom_dir)
                    else section_custom_dir
                ),
                section_name,
            )

            file_copy_config = po_config_dict.get("PROJECT_PO_FILE_COPY", "")
            if not file_copy_config:
                log.warning(
                    "No PROJECT_PO_FILE_COPY configuration found for po: '%s' (section '%s')",
                    ctx.po_name,
                    section_name,
                )
                continue

            log.debug("File copy config for po '%s': '%s'", ctx.po_name, file_copy_config)

            # Parse file copy configuration
            copy_rules = []
            for line in file_copy_config.split("\\"):
                line = line.strip()
                if not line:
                    continue
                if ":" in line:
                    source, target = line.split(":", 1)
                    copy_rules.append((source.strip(), target.strip()))

            # Execute file copy operations for this section
            for source_pattern, target_path in copy_rules:
                if not __execute_file_copy(ctx, section_name, section_custom_dir, source_pattern, target_path):
                    log.error(
                        "Failed to execute file copy for po: '%s', source: '%s', target: '%s'",
                        ctx.po_name,
                        source_pattern,
                        target_path,
                    )
                    return False

        return True

    for po_name in apply_pos:
        po_path = os.path.join(po_dir, po_name)
        log.info("po '%s' starting to apply patch and override%s", po_name, " (dry-run)" if dry_run else "")

        ctx = PoApplyContext(
            project_name=project_name,
            board_name=board_name,
            po_name=po_name,
            po_path=po_path,
            po_patch_dir=os.path.join(po_path, "patches"),
            po_override_dir=os.path.join(po_path, "overrides"),
            po_custom_dir=os.path.join(po_path, "custom"),
            dry_run=dry_run,
            force=force,
            exclude_files=exclude_files,
            po_configs=env.get("po_configs", {}),
            repositories=repositories,
            workspace_root=workspace_root,
            applied_records={},
        )

        ok = __apply_patch(ctx) and __apply_override(ctx) and __apply_custom(ctx)
        if not ok:
            log.error("po apply aborted due to error in po: '%s'", po_name)
            return False

        if not dry_run and ctx.applied_records:
            try:
                for repo_root, record in ctx.applied_records.items():
                    record_path = _po_applied_record_path(repo_root, board_name, project_name, po_name)
                    _write_json_atomic(record_path, record)
            except OSError as e:
                log.error("Failed to finalize applied record for po '%s': '%s'", po_name, e)
                return False

        log.info("po '%s' has been processed", po_name)
    log.info("po apply finished for project: '%s'", project_name)
    return True


@register(
    "po_revert",
    needs_repositories=True,
    desc="Revert patch and override for a project",
)
def po_revert(env: Dict, projects_info: Dict, project_name: str, dry_run: bool = False) -> bool:
    """
    Revert patch and override for the specified project.
    Args:
        env (dict): Global environment dict.
        projects_info (dict): All projects info.
        project_name (str): Project name.
    Returns:
        bool: True if success, otherwise False.
    """
    projects_path = env["projects_path"]
    log.info("start po_revert for project: '%s'", project_name)
    project_info = projects_info.get(project_name, {})
    project_cfg = project_info.get("config", {})
    board_name = project_info.get("board_name")
    if not board_name:
        log.error("Cannot find board name for project: '%s'", project_name)
        return False
    board_path = os.path.join(projects_path, board_name)
    po_dir = os.path.join(board_path, "po")
    po_config = project_cfg.get("PROJECT_PO_CONFIG", "").strip()
    if not po_config:
        log.warning("No PROJECT_PO_CONFIG found for '%s'", project_name)
        return True
    apply_pos, exclude_pos, exclude_files = parse_po_config(po_config)
    log.debug("projects_info: %s", str(projects_info.get(project_name, {})))
    log.debug("po_dir: '%s'", po_dir)
    if apply_pos:
        log.debug("apply_pos: %s", str(apply_pos))
    if exclude_pos:
        log.debug("exclude_pos: %s", str(exclude_pos))
    if exclude_files:
        log.debug("exclude_files: %s", str(exclude_files))

    # Use repositories from env
    repositories = env.get("repositories", [])

    def __revert_patch(po_name, po_patch_dir, exclude_files):
        """Revert patches for the specified po."""
        log.debug("po_name: '%s', po_patch_dir: '%s'", po_name, po_patch_dir)
        if not os.path.isdir(po_patch_dir):
            log.debug("No patches dir for po: '%s'", po_name)
            return True
        log.debug("reverting patches for po: '%s'", po_name)
        for current_dir, _, files in os.walk(po_patch_dir):
            log.debug("current_dir: '%s', files: '%s'", current_dir, files)
            for fname in files:
                if fname == ".gitkeep":
                    continue
                log.debug("current_dir: '%s', fname: '%s'", current_dir, fname)
                rel_path = os.path.relpath(os.path.join(current_dir, fname), po_patch_dir)
                log.debug("patch rel_path: '%s'", rel_path)
                if po_name in exclude_files and rel_path in exclude_files[po_name]:
                    log.debug(
                        "patch file '%s' in po '%s' is excluded by config",
                        rel_path,
                        po_name,
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

                def find_repo_path_by_name(repo_name):
                    for repo_path, rname in repositories:
                        if rname == repo_name:
                            return repo_path
                    return None

                patch_target = find_repo_path_by_name(repo_name)
                if not patch_target:
                    log.error("Cannot find repo path for '%s'", repo_name)
                    return False
                patch_file = os.path.join(current_dir, fname)
                log.info("reverting patch: '%s' from dir: '%s'", patch_file, patch_target)
                try:
                    if dry_run:
                        log.info(
                            "DRY-RUN: cd %s && git apply --reverse %s",
                            patch_target,
                            patch_file,
                        )
                        continue
                    result = subprocess.run(
                        ["git", "apply", "--reverse", patch_file],
                        cwd=patch_target,
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    log.debug(
                        "git apply --reverse result: returncode: '%s', stdout: '%s', stderr: '%s'",
                        result.returncode,
                        result.stdout,
                        result.stderr,
                    )
                    if result.returncode != 0:
                        log.error(
                            "Failed to revert patch '%s': '%s'",
                            patch_file,
                            result.stderr,
                        )
                        return False
                    log.info(
                        "patch reverted for dir: '%s'",
                        patch_target,
                    )
                except subprocess.SubprocessError as e:
                    log.error("Subprocess error reverting patch '%s': '%s'", patch_file, e)
                    return False
                except OSError as e:
                    log.error("OS error reverting patch '%s': '%s'", patch_file, e)
                    return False
        return True

    def __revert_override(po_name, po_override_dir, exclude_files):
        """Revert overrides for the specified po."""
        log.debug("po_name: '%s', po_override_dir: '%s'", po_name, po_override_dir)
        if not os.path.isdir(po_override_dir):
            log.debug("No overrides dir for po: '%s'", po_name)
            return True
        log.debug("reverting overrides for po: '%s'", po_name)
        repo_map = {rname: repo_path for repo_path, rname in repositories}
        repo_names = sorted(
            [name for name in repo_map.keys() if name != "root"],
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

        for current_dir, _, files in os.walk(po_override_dir):
            for fname in files:
                if fname == ".gitkeep":
                    continue
                rel_path = os.path.relpath(os.path.join(current_dir, fname), po_override_dir)
                log.debug("override rel_path: '%s'", rel_path)
                if po_name in exclude_files and rel_path in exclude_files[po_name]:
                    log.debug(
                        "override file '%s' in po '%s' is excluded by config",
                        rel_path,
                        po_name,
                    )
                    continue

                repo_name, dest_rel = _split_repo_prefix(rel_path)
                if fname.endswith(".remove"):
                    dest_rel = dest_rel[:-7]
                dest_rel = _safe_dest_rel(dest_rel)
                if not dest_rel:
                    log.error("Invalid override target path derived from '%s'", rel_path)
                    return False

                repo_root = repo_map.get(repo_name)
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
                        if dry_run:
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
                            "git checkout result: returncode: '%s', stdout: '%s', stderr: '%s'",
                            result.returncode,
                            result.stdout,
                            result.stderr,
                        )
                        if result.returncode != 0:
                            log.error(
                                "Failed to revert override file '%s': '%s'",
                                dest_rel,
                                result.stderr,
                            )
                            return False
                    elif os.path.exists(dest_abs):
                        log.debug(
                            "File '%s' is not tracked by git, deleting directly",
                            dest_rel,
                        )
                        if dry_run:
                            log.info("DRY-RUN: cd %s && rm -rf %s", repo_root, dest_rel)
                            continue
                        if os.path.isdir(dest_abs):
                            shutil.rmtree(dest_abs)
                        else:
                            os.remove(dest_abs)
                    else:
                        log.debug("Override file '%s' does not exist, skipping", dest_abs)
                        continue

                    log.info(
                        "override reverted for dir: '%s', file: '%s'",
                        repo_root,
                        dest_rel,
                    )
                except subprocess.SubprocessError as e:
                    log.error(
                        "Subprocess error reverting override file '%s': '%s'",
                        dest_rel,
                        e,
                    )
                    return False
                except OSError as e:
                    log.error(
                        "OS error reverting override file '%s': '%s'",
                        dest_rel,
                        e,
                    )
                    return False
        return True

    def __revert_custom_po(po_name, po_custom_dir, po_config_dict):
        """Revert custom po configuration for the specified po."""
        log.debug("po_name: '%s', po_custom_dir: '%s'", po_name, po_custom_dir)

        file_copy_config = po_config_dict.get("PROJECT_PO_FILE_COPY", "")
        if not file_copy_config:
            log.warning("No PROJECT_PO_FILE_COPY configuration found for po: '%s'", po_name)
            return True

        log.debug("File copy config for po '%s': '%s'", po_name, file_copy_config)

        # Parse file copy configuration to get target paths
        target_paths = set()
        for line in file_copy_config.split("\\"):
            line = line.strip()
            if not line:
                continue
            if ":" in line:
                _, target = line.split(":", 1)
                target_paths.add(target.strip())

        # For custom po, we can't easily revert file copies
        # Just log a warning that manual cleanup may be needed
        log.warning("Custom po '%s' files were copied to multiple locations. Manual cleanup may be required:", po_name)
        for target_path in target_paths:
            log.warning("  - Target: %s", target_path)

        return True

    # Get po configurations from env
    po_configs = env.get("po_configs", {})

    for po_name in apply_pos:
        # Always process standard patches and overrides
        po_patch_dir = os.path.join(po_dir, po_name, "patches")
        if not __revert_patch(po_name, po_patch_dir, exclude_files):
            log.error("po revert aborted due to patch error in po: '%s'", po_name)
            return False
        po_override_dir = os.path.join(po_dir, po_name, "overrides")
        if not __revert_override(po_name, po_override_dir, exclude_files):
            log.error("po revert aborted due to override error in po: '%s'", po_name)
            return False

        # Check for custom po configurations in common.ini
        for section_name, section_config in po_configs.items():
            if section_name.startswith("po-"):
                # Only apply configurations that match the current po_name
                expected_po_name = section_name[3:]  # Remove "po-" prefix
                if expected_po_name == po_name:
                    po_config_dict = section_config
                    po_subdir = po_config_dict.get("PROJECT_PO_DIR", "").rstrip("/")
                    if po_subdir:
                        po_custom_dir = os.path.join(po_dir, po_name, po_subdir)
                        if os.path.isdir(po_custom_dir):
                            log.info(
                                "Processing custom po '%s' with directory '%s' (from section '%s')",
                                po_name,
                                po_subdir,
                                section_name,
                            )
                            if not __revert_custom_po(po_name, po_custom_dir, po_config_dict):
                                log.error("po revert aborted due to custom po error in po: '%s'", po_name)
                                return False

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


@register("po_new", needs_repositories=True, desc="Create a new PO for a project")
def po_new(
    env: Dict,
    projects_info: Dict,
    project_name: str,
    po_name: str,
    force: bool = False,
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
    patches_dir = os.path.join(po_path, "patches")
    overrides_dir = os.path.join(po_path, "overrides")

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
            # Change to repository directory
            original_cwd = os.getcwd()
            os.chdir(repo_path)

            # Get staged files (files in index)
            staged_result = subprocess.run(
                ["git", "diff", "--name-only", "--cached"],
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

            # Return to original directory
            os.chdir(original_cwd)

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

            # Change to repository directory
            original_cwd = os.getcwd()
            os.chdir(repo_path)

            # Check if file is staged
            staged_result = subprocess.run(
                ["git", "diff", "--name-only", "--cached"],
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
                    capture_output=True,
                    text=True,
                    check=False,
                )
                print(f"    Generating patch from staged changes for {file_path}")
            else:
                result = subprocess.run(
                    ["git", "diff", "--", file_path],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                print(f"    Generating patch from working directory for {file_path}")

            if result.returncode == 0 and result.stdout.strip():
                # Write patch file
                with open(patch_file_path, "w", encoding="utf-8") as f:
                    f.write(result.stdout)

                # Return to original directory
                os.chdir(original_cwd)
                return True
            print(f"    Warning: No changes found for {file_path}")
            os.chdir(original_cwd)
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
            # 传入env['repositories']和project_cfg
            __interactive_file_selection(po_path, env.get("repositories", []), project_cfg)

        # In force mode, create empty directory structure
        if force:
            # Create po directory
            os.makedirs(po_path, exist_ok=True)
            log.info("Created po directory: '%s'", po_path)

            # Create patches directory (force mode creates empty directories)
            os.makedirs(patches_dir, exist_ok=True)

            # Create overrides directory (force mode creates empty directories)
            os.makedirs(overrides_dir, exist_ok=True)

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
def po_update(env: Dict, projects_info: Dict, project_name: str, po_name: str, force: bool = False) -> bool:
    """
    Update an existing PO directory structure (must already exist).
    Reuses po_new with po_update=True to leverage the same workflow.
    """
    return po_new(env, projects_info, project_name, po_name, force=force, po_check_exists=True)


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
            po_config = project_cfg.get("PROJECT_PO_CONFIG", "").strip()
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


@register("po_list", needs_repositories=False, desc="List configured POs for a project")
def po_list(env: Dict, projects_info: Dict, project_name: str, short: bool = False) -> List[dict]:
    """
    List all enabled PO (patch/override) directories for the specified project.
    Args:
        env (dict): Global environment dict.
        projects_info (dict): All projects info.
        project_name (str): Project name.
        short (bool): If True, only list po names, not details.
    Returns:
        list: List of dicts with PO info (name, patch_files, override_files)
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

    # Only list POs enabled in configuration
    po_infos = []
    for po_name in sorted(apply_pos):
        po_path = os.path.join(po_dir, po_name)
        if not os.path.isdir(po_path):
            continue

        # Always check standard patches and overrides
        patches_dir = os.path.join(po_path, "patches")
        overrides_dir = os.path.join(po_path, "overrides")
        patch_files = []
        override_files = []
        if os.path.isdir(patches_dir):
            for root, _, files in os.walk(patches_dir):
                for f in files:
                    if f == ".gitkeep":
                        continue
                    rel_path = os.path.relpath(os.path.join(root, f), patches_dir)
                    patch_files.append(rel_path)
        if os.path.isdir(overrides_dir):
            for root, _, files in os.walk(overrides_dir):
                for f in files:
                    if f == ".gitkeep":
                        continue
                    rel_path = os.path.relpath(os.path.join(root, f), overrides_dir)
                    override_files.append(rel_path)

        # Check for custom po configurations in common.ini
        custom_dirs = []
        for section_name, section_config in po_configs.items():
            if section_name.startswith("po-"):
                # Only apply configurations that match the current po_name
                expected_po_name = section_name[3:]  # Remove "po-" prefix
                if expected_po_name == po_name:
                    po_subdir = section_config.get("PROJECT_PO_DIR", "").rstrip("/")
                    if po_subdir:
                        custom_dir = os.path.join(po_path, po_subdir)
                        custom_files = []
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
                                    "files": custom_files,
                                    "file_copy_config": section_config.get("PROJECT_PO_FILE_COPY", ""),
                                }
                            )

        po_info = {
            "name": po_name,
            "patch_files": patch_files,
            "override_files": override_files,
            "custom_dirs": custom_dirs,
        }
        po_infos.append(po_info)
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
