"""
Patch and override operations for project management.
"""

import fnmatch
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Dict, List, Tuple

from src.log_manager import log
from src.operations.registry import register

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
        if token.startswith("-"):
            if "[" in token:
                match = re.match(r"-(\w+)\[([^\]]+)\]", token)
                if match:
                    po_name, files = match.groups()
                    file_list = set(f.strip() for f in files.split())
                    exclude_files.setdefault(po_name, set()).update(file_list)
            else:
                po_name = token[1:]
                exclude_pos.add(po_name)
        else:
            po_name = token
            apply_pos.append(po_name)

    # Filter apply_pos to exclude items in exclude_pos
    apply_pos = [po_name for po_name in apply_pos if po_name not in exclude_pos]

    return apply_pos, exclude_pos, exclude_files


@register("po_apply", needs_repositories=True, desc="Apply patch and override for a project")
def po_apply(env: Dict, projects_info: Dict, project_name: str) -> bool:
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

    def __execute_command(ctx, command, cwd=None, description="", shell=False):
        """Execute command and log it to po_applied file.

        Args:
            ctx: PoApplyContext object containing po_applied_flag_path
            command: Command to execute (list of strings or string)
            cwd: Working directory for command execution
            description: Optional description for the command
            shell: Whether to use shell for command execution

        Returns:
            subprocess.CompletedProcess: Result of command execution
        """

        # Format command for logging
        if isinstance(command, list):
            cmd_str = " ".join(f'"{arg}"' if " " in arg else arg for arg in command)
        else:
            cmd_str = str(command)

        # Add working directory info if specified
        if cwd:
            cmd_str = f"cd {cwd} && {cmd_str}"

        # Add description if provided
        if description:
            cmd_str = f"# {description}\n{cmd_str}"

        # Execute command
        try:
            result = subprocess.run(
                command,
                cwd=cwd,
                capture_output=True,
                text=True,
                check=False,
                shell=shell,
            )

            # Log command to po_applied file
            if ctx.po_applied_flag_path:
                with open(ctx.po_applied_flag_path, "a", encoding="utf-8") as f:
                    f.write(f"{cmd_str}\n")

            return result

        except Exception as e:
            log.error("Command execution failed: %s", e)
            raise

    @dataclass
    class PoApplyContext:
        """Context container for po_apply execution.

        Holds frequently used paths and configuration for a single PO during apply:
        - po_name: current PO name
        - po_patch_dir: directory containing patch files (po/<po_name>/patches)
        - po_override_dir: directory containing override files (po/<po_name>/overrides)
        - po_custom_dir: unified custom root directory (po/<po_name>/custom)
        - po_applied_flag_path: path to the applied-flag file for this PO
        - exclude_files: mapping of PO name to a set of excluded relative file paths
        - po_configs: custom configuration sections from env used to drive custom apply
        """

        po_name: str
        po_patch_dir: str
        po_override_dir: str
        po_custom_dir: str
        po_applied_flag_path: str
        exclude_files: Dict[str, set]
        po_configs: Dict

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
                try:
                    result = __execute_command(
                        ctx,
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

        def find_repo_path_by_name(repo_name):
            """Find repository path by name."""
            for repo_path, rname in repositories:
                if rname == repo_name:
                    return repo_path
            return None

        def find_actual_repo_root(rel_path):
            """Find the actual repository root for the given relative path."""
            path_parts = rel_path.split(os.sep)
            if len(path_parts) == 1:
                return "."
            if len(path_parts) >= 2:
                for i in range(len(path_parts), 0, -1):
                    potential_repo_name = os.path.join(*path_parts[:i])
                    repo_path = find_repo_path_by_name(potential_repo_name)
                    if repo_path:
                        return repo_path
                return path_parts[0]
            log.error("Invalid override file path: '%s'", rel_path)
            return None

        # 1) Group files by repo_root before copying/deleting
        repo_to_files: Dict[str, List[Tuple[str, str, bool]]] = {}  # (src_file, dest_file, is_remove)
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
                repo_root = find_actual_repo_root(rel_path)
                if repo_root is None:
                    continue
                src_file = os.path.join(current_dir, fname)

                # Check if this is a remove operation
                is_remove = fname.endswith(".remove")
                if is_remove:
                    # For remove operations, the target file is the same path without .remove suffix
                    dest_file = rel_path[:-7]  # Remove '.remove' suffix
                    log.debug("remove operation detected for file: '%s'", dest_file)
                else:
                    dest_file = rel_path

                repo_to_files.setdefault(repo_root, []).append((src_file, dest_file, is_remove))

        # 2) Perform copies/deletes per repo_root (no applied flags)
        for repo_root, file_list in repo_to_files.items():
            log.debug(
                "override repo_root: '%s'",
                repo_root,
            )
            for src_file, dest_file, is_remove in file_list:
                log.debug("override src_file: '%s', dest_file: '%s', is_remove: %s", src_file, dest_file, is_remove)

                if is_remove:
                    # Perform delete operation
                    try:
                        # Check if target file exists
                        if os.path.exists(dest_file):
                            # Use __execute_command for delete operation
                            result = __execute_command(
                                ctx, ["rm", "-rf", dest_file], description=f"Remove file {dest_file}"
                            )

                            if result.returncode != 0:
                                log.error("Failed to remove file '%s': %s", dest_file, result.stderr)
                                return False

                            log.info("Removed file '%s'", dest_file)
                        else:
                            log.debug("File '%s' does not exist, skipping removal", dest_file)
                    except OSError as e:
                        log.error(
                            "Failed to remove file '%s': '%s'",
                            dest_file,
                            e,
                        )
                        return False
                else:
                    # Perform copy operation
                    dest_dir = os.path.dirname(dest_file)
                    if dest_dir:
                        os.makedirs(dest_dir, exist_ok=True)
                    try:
                        # Use __execute_command for copy operation
                        result = __execute_command(
                            ctx, ["cp", "-rf", src_file, dest_file], description="Copy override file"
                        )

                        if result.returncode != 0:
                            log.error(
                                "Failed to copy override file '%s' to '%s': %s", src_file, dest_file, result.stderr
                            )
                            return False

                        log.info("Copied override file '%s' to '%s'", src_file, dest_file)
                    except OSError as e:
                        log.error(
                            "Failed to copy override file '%s' to '%s': '%s'",
                            src_file,
                            dest_file,
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

        def __execute_file_copy(ctx, section_custom_dir, source_pattern, target_path):
            """Execute a single file copy operation with wildcard and directory support.

            - Supports *, ?, [], and ** patterns via cp command
            - cp -rf handles both files and directories automatically
            """
            log.debug("Executing file copy: source='%s', target='%s'", source_pattern, target_path)

            abs_pattern = os.path.join(section_custom_dir, source_pattern)

            try:
                # Create target directory if it doesn't exist
                target_dir = os.path.dirname(target_path)
                if target_dir:
                    os.makedirs(target_dir, exist_ok=True)

                # Use cp -rf for copy operation (handles wildcards, files and directories)
                # Use shell=True to allow wildcard expansion
                result = __execute_command(
                    ctx, f"cp -rf {abs_pattern} {target_path}", description="Copy custom file", shell=True
                )

                if result.returncode != 0:
                    log.error("Failed to copy '%s' to '%s': %s", abs_pattern, target_path, result.stderr)
                    return False

                return True
            except OSError as e:
                log.error("Failed to copy '%s' to '%s': %s", abs_pattern, target_path, e)
                return False

        for section_name, section_config in ctx.po_configs.items():
            po_config_dict = section_config
            po_subdir = po_config_dict.get("PROJECT_PO_DIR", "").rstrip("/")

            # Without normalization: use custom root when empty; otherwise join relative to custom root
            section_custom_dir = os.path.join(ctx.po_custom_dir, po_subdir) if po_subdir else ctx.po_custom_dir
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
                if not __execute_file_copy(ctx, section_custom_dir, source_pattern, target_path):
                    log.error(
                        "Failed to execute file copy for po: '%s', source: '%s', target: '%s'",
                        ctx.po_name,
                        source_pattern,
                        target_path,
                    )
                    return False

        return True

    for po_name in apply_pos:
        # Check applied flag per PO and skip if already applied
        po_path = os.path.join(po_dir, po_name)
        po_applied_flag_path = os.path.join(po_path, "po_applied")
        if os.path.isfile(po_applied_flag_path):
            log.info("po '%s' already applied, skipping", po_name)
            continue

        log.info("po '%s' starting to apply patch and override", po_name)

        # Create po_applied file header first
        try:
            os.makedirs(po_path, exist_ok=True)
            with open(po_applied_flag_path, "w", encoding="utf-8") as f:
                f.write(f"# Applied for project {project_name}\n")
                f.write("# Operation log - commands executed during po_apply:\n")
                f.write("# Commands can be re-executed manually for debugging\n\n")
        except OSError as e:
            log.error("Failed to create applied flag for po '%s': '%s'", po_name, e)
            return False

        ctx = PoApplyContext(
            po_name=po_name,
            po_patch_dir=os.path.join(po_dir, po_name, "patches"),
            po_override_dir=os.path.join(po_dir, po_name, "overrides"),
            po_custom_dir=os.path.join(po_dir, po_name, "custom"),
            po_applied_flag_path=po_applied_flag_path,
            exclude_files=exclude_files,
            po_configs=env.get("po_configs", {}),
        )

        if not __apply_patch(ctx):
            log.error("po apply aborted due to patch error in po: '%s'", po_name)
            return False
        if not __apply_override(ctx):
            log.error("po apply aborted due to override error in po: '%s'", po_name)
            return False
        # Apply custom from unified custom directory via ctx
        if not __apply_custom(ctx):
            log.error("po apply aborted due to custom po error in po: '%s'", po_name)
            return False

        log.info("po '%s' has been processed", po_name)
    log.info("po apply finished for project: '%s'", project_name)
    return True


@register(
    "po_revert",
    needs_repositories=True,
    desc="Revert patch and override for a project",
)
def po_revert(env: Dict, projects_info: Dict, project_name: str) -> bool:
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
                path_parts = rel_path.split(os.sep)
                if len(path_parts) == 1:
                    override_target = "."
                elif len(path_parts) >= 2:
                    override_target = os.path.join(*path_parts[:-1])
                else:
                    log.error("Invalid override file path: '%s'", rel_path)
                    return False

                dest_file = (
                    os.path.join(override_target, *rel_path.split(os.sep)[1:])
                    if len(rel_path.split(os.sep)) > 1
                    else os.path.join(override_target, fname)
                )
                log.debug("override dest_file: '%s'", dest_file)
                if os.path.exists(dest_file):
                    log.info("reverting override file: '%s'", dest_file)
                    try:
                        result = subprocess.run(
                            ["git", "ls-files", "--error-unmatch", dest_file],
                            cwd=override_target,
                            capture_output=True,
                            text=True,
                            check=False,
                        )

                        if result.returncode == 0:
                            result = subprocess.run(
                                ["git", "checkout", "--", dest_file],
                                cwd=override_target,
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
                                    dest_file,
                                    result.stderr,
                                )
                                return False
                        else:
                            log.debug(
                                "File '%s' is not tracked by git, deleting directly",
                                dest_file,
                            )
                            os.remove(dest_file)

                        log.info(
                            "override reverted for dir: '%s', file: '%s'",
                            override_target,
                            dest_file,
                        )
                    except subprocess.SubprocessError as e:
                        log.error(
                            "Subprocess error reverting override file '%s': '%s'",
                            dest_file,
                            e,
                        )
                        return False
                    except OSError as e:
                        log.error(
                            "OS error reverting override file '%s': '%s'",
                            dest_file,
                            e,
                        )
                        return False
                else:
                    log.debug("Override file '%s' does not exist, skipping", dest_file)
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
                return False
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


@register("po_del", needs_repositories=False, desc="Delete a PO for a project")
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
