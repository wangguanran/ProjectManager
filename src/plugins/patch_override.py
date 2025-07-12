"""
Patch and override operations for project management.
"""

import os
import shutil
import subprocess
import re
import fnmatch
import xml.etree.ElementTree as ET
from src.log_manager import log
from src.profiler import auto_profile


@auto_profile
class PatchOverride:
    """
    Patch and override utility class. All methods are static and stateless.
    """

    def __init__(self):
        raise NotImplementedError(
            "PatchOverride is a utility class and cannot be instantiated."
        )

    @staticmethod
    def po_apply(env, projects_info, project_name):
        """
        Apply patch and override for the specified project.
        Args:
            env (dict): Global environment dict.
            projects_info (dict): All projects info.
            project_name (str): Project name.
        Returns:
            bool: True if success, otherwise False.
        """
        vprojects_path = env["vprojects_path"]
        log.info("start po_apply for project: '%s'", project_name)
        project_cfg = projects_info.get(project_name, {})
        board_name = project_cfg.get("board_name")
        if not board_name:
            log.error("Cannot find board name for project: '%s'", project_name)
            return False
        board_path = os.path.join(vprojects_path, board_name)
        po_dir = os.path.join(board_path, "po")
        po_config = project_cfg.get("PROJECT_PO_CONFIG", "").strip()
        if not po_config:
            log.warning("No PROJECT_PO_CONFIG found for '%s'", project_name)
            return True
        apply_pos, exclude_pos, exclude_files = PatchOverride.__parse_po_config(
            po_config
        )
        apply_pos = [po_name for po_name in apply_pos if po_name not in exclude_pos]
        log.debug("projects_info: %s", str(projects_info.get(project_name, {})))
        log.debug("po_dir: '%s'", po_dir)
        if apply_pos:
            log.debug("apply_pos: %s", str(apply_pos))
        if exclude_pos:
            log.debug("exclude_pos: %s", str(exclude_pos))
        if exclude_files:
            log.debug("exclude_files: %s", str(exclude_files))

        def __apply_patch(po_name, po_patch_dir, exclude_files):
            """Apply patches for the specified po."""
            patch_applied_dirs = set()
            log.debug("po_name: '%s', po_patch_dir: '%s'", po_name, po_patch_dir)
            if not os.path.isdir(po_patch_dir):
                log.debug("No patches dir for po: '%s'", po_name)
                return True
            log.debug("applying patches for po: '%s'", po_name)

            # Get repo path lookup function
            def find_repo_path_by_name(repo_name):
                current_dir = os.getcwd()
                if repo_name == "root":
                    if os.path.exists(os.path.join(current_dir, ".git")):
                        return current_dir
                else:
                    repo_path = os.path.join(current_dir, repo_name)
                    if os.path.exists(os.path.join(repo_path, ".git")):
                        return repo_path
                return None

            for current_dir, _, files in os.walk(po_patch_dir):
                for fname in files:
                    if fname == ".gitkeep":
                        continue
                    rel_path = os.path.relpath(
                        os.path.join(current_dir, fname), po_patch_dir
                    )
                    # rel_path: repo_name/file_path.patch
                    path_parts = rel_path.split(os.sep)
                    if len(path_parts) < 2:
                        log.error("Invalid patch file path: '%s'", rel_path)
                        continue
                    if len(path_parts) == 1:
                        repo_name = "root"
                        # For root repository, patch file contains only filename
                        # file_path variable is not used in this context
                    else:
                        repo_name = path_parts[0]
                        # For other repositories, patch file contains only filename
                        # file_path variable is not used in this context

                    # Exclude patch files configured in exclude_files
                    if po_name in exclude_files and rel_path in exclude_files[po_name]:
                        log.debug(
                            "patch file '%s' in po '%s' is excluded by config",
                            rel_path,
                            po_name,
                        )
                        continue
                    patch_target = find_repo_path_by_name(repo_name)
                    if not patch_target:
                        log.error("Cannot find repo path for '%s'", repo_name)
                        continue
                    patch_flag = os.path.join(patch_target, ".patch_applied")
                    patch_file = os.path.join(current_dir, fname)
                    log.info(
                        "applying patch: '%s' to repo: '%s'", patch_file, patch_target
                    )
                    if patch_target in patch_applied_dirs:
                        log.debug(
                            "patch flag already set for repo: '%s', skipping",
                            patch_target,
                        )
                        continue
                    if os.path.exists(patch_flag):
                        try:
                            with open(patch_flag, "r", encoding="utf-8") as f:
                                applied_pos_in_flag = f.read().strip().split("\n")
                            if po_name in applied_pos_in_flag:
                                log.info(
                                    "patch already applied for repo: '%s' by po: '%s', skipping",
                                    patch_target,
                                    po_name,
                                )
                                patch_applied_dirs.add(patch_target)
                                continue
                        except OSError:
                            pass
                    try:
                        result = subprocess.run(
                            ["git", "apply", patch_file],
                            cwd=patch_target,
                            capture_output=True,
                            text=True,
                            check=False,
                        )
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
                        with open(patch_flag, "a", encoding="utf-8") as f:
                            f.write(f"{po_name}\n")
                        patch_applied_dirs.add(patch_target)
                        log.info(
                            "patch applied and flag set for repo: '%s'", patch_target
                        )
                    except subprocess.SubprocessError as e:
                        log.error(
                            "Subprocess error applying patch '%s': '%s'", patch_file, e
                        )
                        return False
                    except OSError as e:
                        log.error("OS error applying patch '%s': '%s'", patch_file, e)
                        return False
            return True

        def __apply_override(po_name, po_override_dir, exclude_files):
            """Apply overrides for the specified po."""
            override_applied_dirs = set()
            log.debug("po_name: '%s', po_override_dir: '%s'", po_name, po_override_dir)
            if not os.path.isdir(po_override_dir):
                log.debug("No overrides dir for po: '%s'", po_name)
                return True
            log.debug("applying overrides for po: '%s'", po_name)
            for current_dir, _, files in os.walk(po_override_dir):
                for fname in files:
                    if fname == ".gitkeep":
                        # log.debug("ignore .gitkeep file in '%s'", current_dir)
                        continue
                    rel_path = os.path.relpath(
                        os.path.join(current_dir, fname), po_override_dir
                    )
                    log.debug("override rel_path: '%s'", rel_path)
                    # Exclude override files configured in exclude_files
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
                        # file_path variable is not used in this context
                    else:
                        override_target = path_parts[0]
                        # file_path variable is not used in this context

                    override_flag = os.path.join(override_target, ".override_applied")
                    log.debug(
                        "override override_target: '%s', override_flag: '%s'",
                        override_target,
                        override_flag,
                    )
                    if override_target in override_applied_dirs:
                        log.debug(
                            "override flag already set for dir: '%s', skipping",
                            override_target,
                        )
                        continue
                    if os.path.exists(override_flag):
                        try:
                            with open(override_flag, "r", encoding="utf-8") as f:
                                applied_pos_in_flag = f.read().strip().split("\n")
                            if po_name in applied_pos_in_flag:
                                log.info(
                                    "override already applied for dir: '%s' by po: '%s', skipping",
                                    override_target,
                                    po_name,
                                )
                                override_applied_dirs.add(override_target)
                                continue
                        except OSError:
                            # If file exists but can't be read, treat as not applied
                            pass
                    src_file = os.path.join(current_dir, fname)
                    dest_file = (
                        os.path.join(override_target, *rel_path.split(os.sep)[1:])
                        if len(rel_path.split(os.sep)) > 1
                        else os.path.join(override_target, fname)
                    )
                    log.debug(
                        "override src_file: '%s', dest_file: '%s'", src_file, dest_file
                    )
                    os.makedirs(os.path.dirname(dest_file), exist_ok=True)
                    try:
                        shutil.copy2(src_file, dest_file)
                        with open(override_flag, "a", encoding="utf-8") as f:
                            f.write(f"{po_name}\n")
                        override_applied_dirs.add(override_target)
                        log.info(
                            "override applied and flag set for dir: '%s', file: '%s'",
                            override_target,
                            dest_file,
                        )
                    except OSError as e:
                        log.error(
                            "Failed to copy override file '%s' to '%s': '%s'",
                            src_file,
                            dest_file,
                            e,
                        )
                        return False
            return True

        for po_name in apply_pos:
            po_patch_dir = os.path.join(po_dir, po_name, "patches")
            if not __apply_patch(po_name, po_patch_dir, exclude_files):
                log.error("po apply aborted due to patch error in po: '%s'", po_name)
                return False
            po_override_dir = os.path.join(po_dir, po_name, "overrides")
            if not __apply_override(po_name, po_override_dir, exclude_files):
                log.error("po apply aborted due to override error in po: '%s'", po_name)
                return False
            log.info("po '%s' has been processed", po_name)
        log.info("po apply finished for project: '%s'", project_name)
        return True

    @staticmethod
    def po_revert(env, projects_info, project_name):
        """
        Revert patch and override for the specified project.
        Args:
            env (dict): Global environment dict.
            projects_info (dict): All projects info.
            project_name (str): Project name.
        Returns:
            bool: True if success, otherwise False.
        """
        vprojects_path = env["vprojects_path"]
        log.info("start po_revert for project: '%s'", project_name)
        project_cfg = projects_info.get(project_name, {})
        board_name = project_cfg.get("board_name")
        if not board_name:
            log.error("Cannot find board name for project: '%s'", project_name)
            return False
        board_path = os.path.join(vprojects_path, board_name)
        po_dir = os.path.join(board_path, "po")
        po_config = project_cfg.get("PROJECT_PO_CONFIG", "").strip()
        if not po_config:
            log.warning("No PROJECT_PO_CONFIG found for '%s'", project_name)
            return True
        apply_pos, exclude_pos, exclude_files = PatchOverride.__parse_po_config(
            po_config
        )
        apply_pos = [po_name for po_name in apply_pos if po_name not in exclude_pos]
        log.debug("projects_info: %s", str(projects_info.get(project_name, {})))
        log.debug("po_dir: '%s'", po_dir)
        if apply_pos:
            log.debug("apply_pos: %s", str(apply_pos))
        if exclude_pos:
            log.debug("exclude_pos: %s", str(exclude_pos))
        if exclude_files:
            log.debug("exclude_files: %s", str(exclude_files))

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
                    rel_path = os.path.relpath(
                        os.path.join(current_dir, fname), po_patch_dir
                    )
                    log.debug("patch rel_path: '%s'", rel_path)
                    # Exclude patch files configured in exclude_files
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
                        # For root repository, patch file contains only filename
                        # file_path variable is not used in this context
                    else:
                        repo_name = path_parts[0]
                        # For other repositories, patch file contains only filename
                        # file_path variable is not used in this context

                    # 在 __revert_patch 内，patch_target = find_repo_path_by_name(repo_name) 需要提前定义 find_repo_path_by_name
                    # 直接将 patch_target 的赋值方式与 __apply_patch 保持一致
                    # 替换：
                    # patch_target = find_repo_path_by_name(repo_name)
                    # patch_flag = os.path.join(patch_target, ".patch_applied")

                    # 先定义 find_repo_path_by_name
                    def find_repo_path_by_name(repo_name):
                        current_dir = os.getcwd()
                        if repo_name == "root":
                            if os.path.exists(os.path.join(current_dir, ".git")):
                                return current_dir
                        else:
                            repo_path = os.path.join(current_dir, repo_name)
                            if os.path.exists(os.path.join(repo_path, ".git")):
                                return repo_path
                        return None

                    # 然后 patch_target = find_repo_path_by_name(repo_name)
                    patch_target = find_repo_path_by_name(repo_name)
                    if not patch_target:
                        log.error("Cannot find repo path for '%s'", repo_name)
                        continue
                    patch_flag = os.path.join(patch_target, ".patch_applied")
                    log.debug(
                        "patch patch_target: '%s', patch_flag: '%s'",
                        patch_target,
                        patch_flag,
                    )
                    if not os.path.exists(patch_flag):
                        log.debug(
                            "No patch flag found for dir: '%s', skipping", patch_target
                        )
                        continue
                    try:
                        with open(patch_flag, "r", encoding="utf-8") as f:
                            applied_pos_in_flag = f.read().strip().split("\n")
                        if po_name not in applied_pos_in_flag:
                            log.debug(
                                "patch not applied for dir: '%s' by po: '%s', skipping",
                                patch_target,
                                po_name,
                            )
                            continue
                    except OSError:
                        log.debug(
                            "Cannot read patch flag for dir: '%s', skipping",
                            patch_target,
                        )
                        continue
                    patch_file = os.path.join(current_dir, fname)
                    log.info(
                        "reverting patch: '%s' from dir: '%s'", patch_file, patch_target
                    )
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
                        # Remove po_name from flag file
                        applied_pos_in_flag.remove(po_name)
                        if applied_pos_in_flag:
                            with open(patch_flag, "w", encoding="utf-8") as f:
                                f.write("\n".join(applied_pos_in_flag) + "\n")
                        else:
                            # If no more applied pos, remove the flag file
                            os.remove(patch_flag)
                        log.info(
                            "patch reverted and flag updated for dir: '%s'",
                            patch_target,
                        )
                    except subprocess.SubprocessError as e:
                        log.error(
                            "Subprocess error reverting patch '%s': '%s'", patch_file, e
                        )
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
                    rel_path = os.path.relpath(
                        os.path.join(current_dir, fname), po_override_dir
                    )
                    log.debug("override rel_path: '%s'", rel_path)
                    # Exclude override files configured in exclude_files
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
                        # file_path variable is not used in this context
                    else:
                        override_target = path_parts[0]
                        # file_path variable is not used in this context

                    override_flag = os.path.join(override_target, ".override_applied")
                    log.debug(
                        "override override_target: '%s', override_flag: '%s'",
                        override_target,
                        override_flag,
                    )
                    if not os.path.exists(override_flag):
                        log.debug(
                            "No override flag found for dir: '%s', skipping",
                            override_target,
                        )
                        continue
                    try:
                        with open(override_flag, "r", encoding="utf-8") as f:
                            applied_pos_in_flag = f.read().strip().split("\n")
                        if po_name not in applied_pos_in_flag:
                            log.debug(
                                "override not applied for dir: '%s' by po: '%s', skipping",
                                override_target,
                                po_name,
                            )
                            continue
                    except OSError:
                        log.debug(
                            "Cannot read override flag for dir: '%s', skipping",
                            override_target,
                        )
                        continue
                    dest_file = (
                        os.path.join(override_target, *rel_path.split(os.sep)[1:])
                        if len(rel_path.split(os.sep)) > 1
                        else os.path.join(override_target, fname)
                    )
                    log.debug("override dest_file: '%s'", dest_file)
                    if os.path.exists(dest_file):
                        log.info("reverting override file: '%s'", dest_file)
                        try:
                            # First check if the file is tracked by git
                            result = subprocess.run(
                                ["git", "ls-files", "--error-unmatch", dest_file],
                                cwd=override_target,
                                capture_output=True,
                                text=True,
                                check=False,
                            )

                            if result.returncode == 0:
                                # File is tracked by git, use git checkout to restore
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
                                # File is not tracked by git, delete it directly
                                log.debug(
                                    "File '%s' is not tracked by git, deleting directly",
                                    dest_file,
                                )
                                os.remove(dest_file)

                            # Remove po_name from flag file
                            applied_pos_in_flag.remove(po_name)
                            if applied_pos_in_flag:
                                with open(override_flag, "w", encoding="utf-8") as f:
                                    f.write("\n".join(applied_pos_in_flag) + "\n")
                            else:
                                # If no more applied pos, remove the flag file
                                os.remove(override_flag)
                            log.info(
                                "override reverted and flag updated for dir: '%s', file: '%s'",
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
                        log.debug(
                            "Override file '%s' does not exist, skipping", dest_file
                        )
            return True

        for po_name in apply_pos:
            po_patch_dir = os.path.join(po_dir, po_name, "patches")
            if not __revert_patch(po_name, po_patch_dir, exclude_files):
                log.error("po revert aborted due to patch error in po: '%s'", po_name)
                return False
            po_override_dir = os.path.join(po_dir, po_name, "overrides")
            if not __revert_override(po_name, po_override_dir, exclude_files):
                log.error(
                    "po revert aborted due to override error in po: '%s'", po_name
                )
                return False
            log.info("po '%s' has been reverted", po_name)
        log.info("po revert finished for project: '%s'", project_name)
        return True

    @staticmethod
    def po_new(env, projects_info, project_name, po_name, force=False):
        """
        Create a new PO (patch and override) directory structure for the specified project.
        Args:
            env (dict): Global environment dict.
            projects_info (dict): All projects info.
            project_name (str): Project name.
            po_name (str): Name of the new PO to create.
            force (bool): If True, skip confirmation prompt.
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
        if not board_name:
            log.error("Cannot find board name for project: '%s'", project_name)
            return False

        board_path = os.path.join(env["vprojects_path"], board_name)
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

        # Check if PO directory already exists
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
            print(
                "  1. PO directory structure with patches/ and overrides/ subdirectories"
            )
            print("  2. Option to select modified files to include in the PO")

            while True:
                response = (
                    input(f"\nDo you want to create PO '{po_name}'? (yes/no): ")
                    .strip()
                    .lower()
                )
                if response in ["yes", "y"]:
                    return True
                if response in ["no", "n"]:
                    return False
                print("Please enter 'yes' or 'no'.")

        def __find_repositories():
            """Find all git repositories starting from the current working directory."""
            repositories = []
            current_dir = os.getcwd()

            # Get ignore patterns from project configuration
            ignore_patterns = __load_ignore_patterns(project_cfg)

            # First check if current directory has .repo manifest
            repo_manifest = os.path.join(current_dir, ".repo", "manifest.xml")
            if os.path.exists(repo_manifest):
                # Use manifest for repository discovery
                print("Found .repo manifest, scanning repositories...")
                try:
                    tree = ET.parse(repo_manifest)
                    root = tree.getroot()
                    for project in root.findall(".//project"):
                        path = project.get("path")
                        if path:
                            repo_path = os.path.join(current_dir, path)
                            if os.path.exists(os.path.join(repo_path, ".git")):
                                repo_name = path if path != "." else "root"

                                # Check if this repository should be ignored
                                should_ignore = False
                                for pattern in ignore_patterns:
                                    if fnmatch.fnmatch(repo_name, pattern):
                                        print(
                                            f"  Ignoring repository: {repo_name} (matches pattern: {pattern})"
                                        )
                                        should_ignore = True
                                        break

                                if not should_ignore:
                                    repositories.append((repo_path, repo_name))
                                    print(
                                        f"  Found repository: {repo_name} at {repo_path}"
                                    )
                                else:
                                    print(
                                        f"  Skipped repository: {repo_name} (ignored by config)"
                                    )
                except ET.ParseError as e:
                    log.error("Failed to parse .repo manifest: %s", e)
                    print(f"Warning: Failed to parse .repo manifest: {e}")
            elif os.path.exists(os.path.join(current_dir, ".git")):
                # Current directory is a single git repository
                repo_name = "root"

                # Check if root repository should be ignored
                should_ignore = False
                for pattern in ignore_patterns:
                    if fnmatch.fnmatch(repo_name, pattern):
                        print(
                            f"  Ignoring root repository (matches pattern: {pattern})"
                        )
                        should_ignore = True
                        break

                if not should_ignore:
                    repositories.append((current_dir, repo_name))
                    print("Found single git repository at current directory")
                else:
                    print("Skipped root repository (ignored by config)")
            else:
                # Recursively search for git repositories in subdirectories
                print("Scanning subdirectories for git repositories...")
                for root, dirs, _ in os.walk(current_dir):
                    if ".git" in dirs:
                        repo_path = root
                        repo_name = os.path.relpath(repo_path, current_dir)
                        if repo_name == ".":
                            repo_name = "root"

                        # Check if this repository should be ignored
                        should_ignore = False
                        for pattern in ignore_patterns:
                            if fnmatch.fnmatch(repo_name, pattern):
                                print(
                                    f"  Ignoring repository: {repo_name} (matches pattern: {pattern})"
                                )
                                should_ignore = True
                                break

                        if not should_ignore:
                            repositories.append((repo_path, repo_name))
                            print(f"  Found repository: {repo_name} at {repo_path}")
                        else:
                            print(
                                f"  Skipped repository: {repo_name} (ignored by config)"
                            )
                    # Don't recurse into .git directories
                    dirs[:] = [d for d in dirs if d != ".git"]

            return repositories

        def __get_modified_files(repo_path, repo_name):
            """Get modified files in a repository including staged files, with ignore support."""
            modified_files = []
            ignore_patterns = __load_ignore_patterns(project_cfg)
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

                # Process all files
                all_files = staged_files | working_files

                def is_ignored(file_path):
                    for pattern in ignore_patterns:
                        if fnmatch.fnmatch(file_path, pattern):
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
                        if file_path in staged_files and file_path in working_files:
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
                log.error(
                    "Failed to get modified files for repository %s: %s", repo_name, e
                )
                print(
                    f"Warning: Failed to get modified files for repository {repo_name}: {e}"
                )

            return modified_files

        def __find_repo_path_by_name(repo_name):
            """Find repository path by name."""
            current_dir = os.getcwd()

            if repo_name == "root":
                if os.path.exists(os.path.join(current_dir, ".git")):
                    return current_dir
            else:
                repo_path = os.path.join(current_dir, repo_name)
                if os.path.exists(os.path.join(repo_path, ".git")):
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
                custom_name = input(
                    "    Enter custom patch name (or press Enter for default): "
                ).strip()

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
                    patch_file_path = os.path.join(
                        patches_dir, repo_name, f"{filename}.patch"
                    )

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
                    print(
                        f"    Generating patch from working directory for {file_path}"
                    )

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

        def __process_single_file(file_info, po_path):
            """Process a single file and ask user to choose between patch and override."""
            repo_name, file_path, status = file_info
            patches_dir = os.path.join(po_path, "patches")
            overrides_dir = os.path.join(po_path, "overrides")

            # Create po directory when first file is selected
            os.makedirs(po_path, exist_ok=True)
            log.info("Created po directory: '%s'", po_path)

            print(f"\nFile: [{repo_name}] {file_path} ({status})")
            print("Choose action:")
            print("  1. Create patch (for tracked files with modifications)")
            print("  2. Create override (for any file)")
            print("  3. Skip this file")

            while True:
                choice = input("Choice (1/2/3): ").strip()
                if choice == "1":
                    if __create_patch_for_file(
                        repo_name, file_path, patches_dir, force=False
                    ):
                        print(f"  ✓ Created patch for {file_path}")
                        return True
                    print(f"  ✗ Failed to create patch for {file_path}")
                    return False
                if choice == "2":
                    if __create_override_for_file(repo_name, file_path, overrides_dir):
                        print(f"  ✓ Created override for {file_path}")
                        return True
                    print(f"  ✗ Failed to create override for {file_path}")
                    return False
                if choice == "3":
                    print(f"  - Skipped {file_path}")
                    return False
                print("Invalid choice. Please enter 1, 2, or 3.")

        def __interactive_file_selection(po_path):
            """Interactive file selection for PO creation."""
            print("\n=== File Selection for PO ===")
            print("Scanning for modified files in repositories...")

            # Find repositories and their modified files
            repositories = __find_repositories()
            if not repositories:
                print("No git repositories found.")
                return

            all_modified_files = []
            for repo_path, repo_name in repositories:
                modified_files = __get_modified_files(repo_path, repo_name)
                if modified_files:
                    all_modified_files.extend(modified_files)

            if not all_modified_files:
                print("No modified files found in any repository.")
                return

            # Track processed files
            processed_files = set()
            remaining_files = all_modified_files.copy()

            while True:
                print(
                    f"\n=== File Selection (Remaining: {len(remaining_files)}/{len(all_modified_files)}) ==="
                )

                # Show remaining files
                if remaining_files:
                    print("Remaining files to process:")
                    for i, (repo_name, file_path, status) in enumerate(
                        remaining_files, 1
                    ):
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
                print("  Enter 'all' to process all remaining files")
                print("  Enter 'q' to quit and finish")

                selection = input("\nSelection: ").strip()
                if selection.lower() == "q":
                    print("File selection finished.")
                    break

                if selection.lower() == "all":
                    # Process all remaining files
                    files_to_process = remaining_files.copy()
                    for file_info in files_to_process:
                        __process_single_file(file_info, po_path)
                        processed_files.add(file_info)
                        remaining_files.remove(file_info)
                    continue

                try:
                    index = int(selection) - 1
                    if 0 <= index < len(remaining_files):
                        file_info = remaining_files[index]
                        if __process_single_file(file_info, po_path):
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
            if project_cfg:
                po_ignore_config = project_cfg.get("PROJECT_PO_IGNORE", "").strip()
                if po_ignore_config:
                    config_patterns = [
                        p.strip() for p in po_ignore_config.split() if p.strip()
                    ]
                    patterns.extend(config_patterns)
                    log.debug(
                        "Loaded ignore patterns from project config: %s",
                        config_patterns,
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

            return patterns

        # Show creation information and ask for confirmation
        if not force:
            if not __confirm_creation(po_name, po_path, board_path):
                log.info("po_new cancelled by user")
                return False

        try:
            # Interactive file selection first
            if not force:
                __interactive_file_selection(po_path)

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
            log.error(
                "Failed to create po directory structure for '%s': '%s'", po_name, e
            )
            return False

    @staticmethod
    def po_del(env, projects_info, project_name, po_name, force=False):
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
        if not board_name:
            log.error("Cannot find board name for project: '%s'", project_name)
            return False

        board_path = os.path.join(env["vprojects_path"], board_name)
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
                response = (
                    input(
                        f"\nAre you sure you want to delete PO '{po_name}'? (yes/no): "
                    )
                    .strip()
                    .lower()
                )
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
                        __print_directory_tree(
                            item_path, next_prefix, max_depth, current_depth + 1
                        )
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
                    if in_project_section and stripped_line.replace(" ", "").startswith(
                        "PROJECT_PO_CONFIG="
                    ):
                        # Parse the current config and remove the PO
                        config_value = line.split("=", 1)[1].strip()
                        updated_config = __remove_po_from_config_string(
                            config_value, po_name
                        )
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
                if not board_name:
                    continue

                if board_name not in board_configs:
                    board_configs[board_name] = {}

                # Find the ini file for this board
                board_path = os.path.join(env["vprojects_path"], board_name)
                ini_file = None
                for f in os.listdir(board_path):
                    if f.endswith(".ini"):
                        ini_file = os.path.join(board_path, f)
                        break

                if not ini_file:
                    log.error("No ini file found for board: '%s'", board_name)
                    return False

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

        log.info(
            "po_del finished for project: '%s', po_name: '%s'", project_name, po_name
        )
        return True

    @staticmethod
    def po_list(env, projects_info, project_name, short=False):
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
        project_cfg = projects_info.get(project_name, {})
        board_name = project_cfg.get("board_name")
        if not board_name:
            log.error("Cannot find board name for project: '%s'", project_name)
            return []
        board_path = os.path.join(env["vprojects_path"], board_name)
        po_dir = os.path.join(board_path, "po")
        if not os.path.isdir(po_dir):
            log.warning("No po directory found for '%s'", project_name)
            return []
        # Get enabled pos from config
        po_config = project_cfg.get("PROJECT_PO_CONFIG", "").strip()
        enabled_pos = set()
        if po_config:
            apply_pos, exclude_pos, _ = PatchOverride.__parse_po_config(po_config)
            enabled_pos = {po for po in apply_pos if po not in exclude_pos}
        # Only list POs enabled in configuration
        po_list = []
        for po_name in sorted(enabled_pos):
            po_path = os.path.join(po_dir, po_name)
            if not os.path.isdir(po_path):
                continue
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
            po_info = {
                "name": po_name,
                "patch_files": patch_files,
                "override_files": override_files,
            }
            po_list.append(po_info)
        # Print summary
        print(f"\nConfigured PO list for project: {project_name} (board: {board_name})")
        if not po_list:
            print("  No configured PO found.")
        elif short:
            for po in po_list:
                print(f"  {po['name']}")
        else:
            for po in po_list:
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
        return po_list

    @staticmethod
    def __parse_po_config(po_config):
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
        return apply_pos, exclude_pos, exclude_files
