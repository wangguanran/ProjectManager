"""Project management utility class for CLI operations."""

import json
import os
import shutil
from datetime import datetime
from typing import Dict, List

from configupdater import ConfigUpdater

from src.log_manager import log
from src.operations.registry import register


@register("project_new", needs_repositories=False, desc="Create a new project.")
def project_new(env: Dict, projects_info: Dict, project_name: str) -> bool:
    """
    Create a new project.
    Args:
        env (dict): Global environment dict.
        projects_info (dict): All projects info.
        project_name (str): Project name. Must be provided.
    """

    _ = env

    def find_parent_project(name):
        if "-" in name:
            return name.rsplit("-", 1)[0]
        return None

    def get_inherited_config(projects_info, name):
        config = {}
        parent = find_parent_project(name)
        if parent and parent in projects_info:
            config.update(get_inherited_config(projects_info, parent))
        if name in projects_info:
            config.update(projects_info[name])
        return config

    def find_board_for_project(project_name, projects_info):
        """
        Find the appropriate board for a new project based on parent project or project name pattern.
        """
        # First, try to find parent project to determine board
        parent = find_parent_project(project_name)
        if parent:
            # If project name suggests a parent (contains "-"),
            # the parent MUST exist in projects_info
            if parent in projects_info:
                parent_cfg = projects_info[parent]
                return (
                    parent_cfg.get("board_name"),
                    parent_cfg.get("board_path"),
                    parent_cfg.get("ini_file"),
                )
            return None, None, None

        # If no parent found, try to infer board from project name pattern
        # Look for existing projects with similar naming patterns
        for existing_project, project_info in projects_info.items():
            if project_name.startswith(existing_project + "-"):
                return (
                    project_info.get("board_name"),
                    project_info.get("board_path"),
                    project_info.get("ini_file"),
                )
        # No fallback strategy - if we can't determine board, return None
        return None, None, None

    # Find board information for the new project
    board_name, board_path, ini_file = find_board_for_project(project_name, projects_info)
    if not project_name:
        log.error("Project name must be provided.")
        print("Error: Project name must be provided.")
        return False
    if not board_name or not board_path:
        log.error("Cannot determine board for project '%s'. Please ensure:", project_name)
        print(f"Error: Cannot determine board for project '{project_name}'. Please ensure:")
        if "-" in project_name:
            parent = find_parent_project(project_name)
            print(f"  1. Parent project '{parent}' exists in projects_info")
            print("  2. The parent project is properly configured with board information")
        else:
            print("  1. The project has a parent project that exists in projects_info")
            print("  2. The project name follows the pattern 'parent-project'")
            print("  3. There are available board directories in projects")
        return False
    if not os.path.isdir(board_path):
        log.error(
            "Board directory '%s' does not exist for project '%s'.",
            board_name,
            project_name,
        )
        print(f"Error: Board directory '{board_name}' does not exist for project '{project_name}'.")
        return False
    if not ini_file:
        log.error("No ini file found for board: '%s'", board_name)
        print(f"No ini file found for board: '{board_name}'")
        return False

    # project_name cannot be the same as board_name (board section is not a project)
    if project_name == board_name:
        log.error("Project name '%s' cannot be the same as board name.", project_name)
        print(f"Error: Project name '{project_name}' cannot be the same as board name.")
        return False

    # Check for duplicate project
    config = ConfigUpdater()
    config.optionxform = str
    try:
        # Ensure ini file is readable
        if not os.access(ini_file, os.R_OK):
            log.error("INI file is not readable: '%s'", ini_file)
            print(f"Error: INI file is not readable: '{ini_file}'")
            return False
        config.read(ini_file, encoding="utf-8")
    except (PermissionError, OSError, UnicodeError) as err:
        log.error("Failed to read INI file '%s': %s", ini_file, err)
        print(f"Error: Failed to read INI file '{ini_file}': {err}")
        return False
    if project_name in config.sections():
        log.error("Project '%s' already exists in board '%s'.", project_name, board_name)
        print(f"Project '{project_name}' already exists in board '{board_name}'.")
        return False

    # Recursively inherit configuration
    inherited_config = get_inherited_config(projects_info, project_name)
    parent_config = inherited_config.get("config", {}) if isinstance(inherited_config.get("config", {}), dict) else {}
    platform_name = parent_config.get("PROJECT_PLATFORM")
    project_customer = parent_config.get("PROJECT_CUSTOMER")
    project_name_parts = []
    if platform_name:
        project_name_parts.append(platform_name)
    project_name_parts.append(project_name)
    if project_customer:
        project_name_parts.append(project_customer)
    project_name_value = "_".join(project_name_parts)

    # Read the original ini file content to preserve comments and formatting
    try:
        if not os.access(ini_file, os.R_OK):
            log.error("INI file is not readable: '%s'", ini_file)
            print(f"Error: INI file is not readable: '{ini_file}'")
            return False
        with open(ini_file, "r", encoding="utf-8") as f:
            original_lines = f.readlines()
    except (PermissionError, OSError, UnicodeError) as err:
        log.error("Failed to read INI file '%s': %s", ini_file, err)
        print(f"Error: Failed to read INI file '{ini_file}': {err}")
        return False

    # Rewrite only the board's PROJECT_NAME assignment to have spaces around '=' and keep comments intact
    new_lines = []
    current_section = None
    for line in original_lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            current_section = stripped[1:-1]
            new_lines.append(line)
            continue
        if current_section == board_name:
            lstrip = line.lstrip()
            if lstrip.upper().startswith("PROJECT_NAME") and "=" in line:
                # Preserve leading indentation and any trailing inline comment
                prefix_len = len(line) - len(lstrip)
                prefix = line[:prefix_len]
                _after = line.split("=", 1)[1]
                # Keep everything after '=' including inline comments/spaces
                new_lines.append(f"{prefix}PROJECT_NAME = {_after.lstrip()}")
                continue
        new_lines.append(line)

    # Ensure a single blank line before appending the new section
    if new_lines and new_lines[-1].strip() != "":
        new_lines.append("\n")
    elif len(new_lines) >= 2 and new_lines[-1].strip() == "" and new_lines[-2].strip() == "":
        # Reduce multiple trailing blanks to a single one
        while len(new_lines) >= 2 and new_lines[-1].strip() == "" and new_lines[-2].strip() == "":
            new_lines.pop()

    # Append the new project section
    new_lines.append(f"[{project_name}]\n")
    new_lines.append(f"PROJECT_NAME = {project_name_value}\n")

    # Write back preserving all original comments and formatting elsewhere
    try:
        # Ensure board directory and file are writable
        board_dirname = os.path.dirname(ini_file)
        if board_dirname and not os.access(board_dirname, os.W_OK):
            log.error("Board directory is not writable: '%s'", board_dirname)
            print(f"Error: Board directory is not writable: '{board_dirname}'")
            return False
        if not os.access(ini_file, os.W_OK):
            log.error("INI file is not writable: '%s'", ini_file)
            print(f"Error: INI file is not writable: '{ini_file}'")
            return False
        with open(ini_file, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
    except (PermissionError, OSError, UnicodeError) as err:
        log.error("Failed to write INI file '%s': %s", ini_file, err)
        print(f"Error: Failed to write INI file '{ini_file}': {err}")
        return False

    log.debug("Created new project '%s' in board '%s'.", project_name, board_name)
    print(f"Created new project '{project_name}' in board '{board_name}'.")

    # Print all config for the new project (merged: ini section + inherited config['config'])
    # Re-read using ConfigUpdater to fetch the new section values
    config_after = ConfigUpdater()
    config_after.optionxform = str
    try:
        config_after.read(ini_file, encoding="utf-8")
    except (PermissionError, OSError, UnicodeError) as err:
        log.error("Failed to re-read INI file '%s': %s", ini_file, err)
        print(f"Error: Failed to re-read INI file '{ini_file}': {err}")
        return False
    parent_config = inherited_config.get("config", {}) if isinstance(inherited_config.get("config", {}), dict) else {}
    merged_config = dict(parent_config)
    if project_name in config_after:
        for key, value in config_after[project_name].items():
            merged_config[key] = value.value if hasattr(value, "value") else value
    print(f"All config for project '{project_name}':")
    for key, value in merged_config.items():
        print(f"  {key} = {value}")
    return True


@register("project_del", needs_repositories=False, desc="Delete the specified project.")
def project_del(env: Dict, projects_info: Dict, project_name: str) -> bool:
    """
    Delete the specified project directory and update its status in the config file.
    Args:
        env (dict): Global environment dict.
        projects_info (dict): All projects info.
        project_name (str): Project name.
    """

    _ = env

    def find_all_subprojects(projects_info, project_name):
        """Find all subprojects recursively whose names start with project_name-"""
        subprojects = []
        for name in projects_info:
            if name != project_name and name.startswith(project_name + "-"):
                subprojects.append(name)
        all_subs = []
        for sub in subprojects:
            all_subs.append(sub)
            all_subs.extend(find_all_subprojects(projects_info, sub))
        return all_subs

    project_cfg = projects_info.get(project_name, {})
    board_name = project_cfg.get("board_name")
    board_path = project_cfg.get("board_path")
    ini_file = project_cfg.get("ini_file")
    if not project_name:
        log.error("Project name must be provided.")
        print("Error: Project name must be provided.")
        return False
    if not board_name or not board_path:
        log.error("Board info missing for project '%s'", project_name)
        print(f"Error: Board info missing for project '{project_name}'.")
        return False
    if not os.path.isdir(board_path):
        log.error(
            "Board directory '%s' does not exist for project '%s'.",
            board_name,
            project_name,
        )
        print(f"Error: Board directory '{board_name}' does not exist for project '{project_name}'.")
        return False
    if not ini_file:
        log.error("No ini file found for board: '%s'", board_name)
        print(f"No ini file found for board: '{board_name}'")
        return False

    # project_name cannot be the same as board_name
    if project_name == board_name:
        log.error("Project name '%s' cannot be the same as board name.", project_name)
        print(f"Error: Project name '{project_name}' cannot be the same as board name.")
        return False

    config = ConfigUpdater()
    config.optionxform = str
    config.read(ini_file, encoding="utf-8")
    # Recursively delete all subprojects
    to_delete = [project_name] + find_all_subprojects(projects_info, project_name)
    for del_name in to_delete:
        if del_name not in config.sections():
            log.info("Project '%s' does not exist in board '%s'.", del_name, board_name)
            print(f"Project '{del_name}' does not exist in board '{board_name}'.")
        else:
            config.remove_section(del_name)
            log.debug("Removed project '%s' from board '%s'.", del_name, board_name)
            print(f"Removed project '{del_name}' from board '{board_name}'.")
    config.update_file()
    return True


@register("board_new", needs_repositories=False, desc="Create a new board.")
def board_new(env: Dict, projects_info: Dict, board_name: str) -> bool:
    """
    Create a new board.
    Args:
        env (dict): Global environment dict.
        projects_info (dict): All projects info.
        board_name (str): Board name.
    """

    _ = projects_info

    if not isinstance(board_name, str) or not board_name.strip():
        log.error("Board name must be a non-empty string.")
        print("Error: Board name must be a non-empty string.")
        return False

    board_name = board_name.strip()
    if board_name in {".", ".."}:
        log.error("Board name '%s' is not allowed.", board_name)
        print(f"Error: Board name '{board_name}' is not allowed.")
        return False

    normalised_board_name = os.path.normpath(board_name)
    if normalised_board_name in {".", ".."}:
        log.error("Board name '%s' resolves to an invalid path.", board_name)
        print(f"Error: Board name '{board_name}' resolves to an invalid path.")
        return False

    if os.path.isabs(normalised_board_name):
        log.error("Board name '%s' must not resolve to an absolute path.", board_name)
        print(f"Error: Board name '{board_name}' must not resolve to an absolute path.")
        return False

    if any(sep in board_name for sep in (os.sep, os.altsep) if sep):
        log.error("Board name '%s' contains invalid path characters.", board_name)
        print(f"Error: Board name '{board_name}' contains invalid path characters.")
        return False

    board_name = normalised_board_name

    reserved_names = {"common", "template", "scripts", ".cache", ".git"}
    if board_name in reserved_names:
        log.error("Board name '%s' is reserved and cannot be used.", board_name)
        print(f"Error: Board name '{board_name}' is reserved and cannot be used.")
        return False

    if not isinstance(env, dict):
        log.error("Environment must be a dictionary containing 'projects_path'.")
        print("Error: Environment must contain 'projects_path'.")
        return False

    projects_path = env.get("projects_path")
    if not isinstance(projects_path, str) or not projects_path.strip():
        log.error("Invalid 'projects_path' in environment: %s", projects_path)
        print("Error: Invalid 'projects_path' in environment.")
        return False

    projects_path = os.path.abspath(projects_path)
    try:
        os.makedirs(projects_path, exist_ok=True)
    except OSError as err:
        log.error("Failed to ensure projects path '%s': %s", projects_path, err)
        print(f"Error: Failed to ensure projects path '{projects_path}': {err}")
        return False

    board_path = os.path.abspath(os.path.join(projects_path, board_name))
    if os.path.commonpath([projects_path, board_path]) != projects_path:
        log.error(
            "Board name '%s' resolves outside of projects path '%s'.",
            board_name,
            projects_path,
        )
        print(
            f"Error: Board name '{board_name}' resolves outside of projects path '{projects_path}'."
        )
        return False
    if os.path.exists(board_path):
        log.error("Board '%s' already exists at '%s'.", board_name, board_path)
        print(f"Error: Board '{board_name}' already exists.")
        return False

    po_path = os.path.join(board_path, "po")
    ini_path = os.path.join(board_path, f"{board_name}.ini")
    projects_json_path = os.path.join(board_path, "projects.json")

    template_dir = os.path.join(projects_path, "template")
    template_ini_path = os.path.join(template_dir, "template.ini")
    template_po_path = os.path.join(template_dir, "po")

    def _generate_ini_lines() -> List[str]:
        default_lines = [
            f"[{board_name}]\n",
            "PROJECT_NAME = \n",
            "PROJECT_VERSION = \n",
            "PROJECT_PO_CONFIG = \n",
            "PROJECT_PO_IGNORE = \n",
        ]
        if not os.path.isfile(template_ini_path):
            return default_lines
        try:
            with open(template_ini_path, "r", encoding="utf-8") as template_file:
                lines = template_file.readlines()
        except (OSError, UnicodeError) as err:
            log.warning(
                "Failed to read template ini '%s': %s. Using default template.",
                template_ini_path,
                err,
            )
            return default_lines

        replaced = False
        ini_lines = []
        for line in lines:
            stripped = line.strip()
            if not replaced and stripped.startswith("[") and stripped.endswith("]"):
                ini_lines.append(f"[{board_name}]\n")
                replaced = True
            else:
                ini_lines.append(line)
        if not ini_lines:
            return default_lines
        if not replaced:
            ini_lines.insert(0, f"[{board_name}]\n")
        return ini_lines

    def _initialise_po_directory() -> None:
        if os.path.isdir(template_po_path):
            try:
                shutil.copytree(template_po_path, po_path)
            except FileExistsError:
                # Destination should be empty for new boards, but fall back to
                # copying contents to support environments that may create the
                # directory earlier (e.g. via concurrent setup steps).
                for root, _dirs, files in os.walk(template_po_path):
                    rel_root = os.path.relpath(root, template_po_path)
                    dest_root = po_path if rel_root == "." else os.path.join(po_path, rel_root)
                    os.makedirs(dest_root, exist_ok=True)
                    for file_name in files:
                        shutil.copy2(
                            os.path.join(root, file_name),
                            os.path.join(dest_root, file_name),
                        )
            return

        os.makedirs(po_path, exist_ok=False)
        default_po_root = os.path.join(po_path, "po_template")
        for subdir in ("patches", "overrides"):
            os.makedirs(os.path.join(default_po_root, subdir), exist_ok=True)

    try:
        os.makedirs(board_path, exist_ok=False)
        _initialise_po_directory()
        ini_lines = _generate_ini_lines()
        with open(ini_path, "w", encoding="utf-8") as ini_file:
            ini_file.writelines(ini_lines)

        board_metadata = {
            "board_name": board_name,
            "board_path": board_path,
            "last_updated": datetime.now().isoformat(),
            "projects": [],
        }
        with open(projects_json_path, "w", encoding="utf-8") as json_file:
            json.dump(board_metadata, json_file, indent=2, ensure_ascii=False)
    except FileExistsError:
        log.error("Board directory structure for '%s' already exists.", board_name)
        print(f"Error: Board '{board_name}' already exists.")
        return False
    except (OSError, UnicodeError, ValueError) as err:
        log.error("Failed to create board '%s': %s", board_name, err)
        print(f"Error: Failed to create board '{board_name}': {err}")
        if os.path.isdir(board_path):
            shutil.rmtree(board_path, ignore_errors=True)
        return False

    log.debug("Created new board '%s' at '%s'.", board_name, board_path)
    print(f"Created new board '{board_name}' at '{board_path}'.")
    print(f"Board ini file: {ini_path}")
    print(f"PO directory: {po_path}")
    return True


@register("board_del", needs_repositories=False, desc="Delete the specified board.")
def board_del(env: Dict, projects_info: Dict, board_name: str) -> bool:
    """
    Delete the specified board.
    Args:
        env (dict): Global environment dict.
        projects_info (dict): All projects info.
        board_name (str): Board name.
    """
    if not isinstance(board_name, str) or not board_name.strip():
        log.error("Board name must be a non-empty string.")
        print("Error: Board name must be a non-empty string.")
        return False

    board_name = board_name.strip()
    if board_name in {".", ".."}:
        log.error("Board name '%s' is not allowed.", board_name)
        print(f"Error: Board name '{board_name}' is not allowed.")
        return False

    normalised_board_name = os.path.normpath(board_name)
    if normalised_board_name in {".", ".."}:
        log.error("Board name '%s' resolves to an invalid path.", board_name)
        print(f"Error: Board name '{board_name}' resolves to an invalid path.")
        return False

    if os.path.isabs(normalised_board_name):
        log.error("Board name '%s' must not resolve to an absolute path.", board_name)
        print(f"Error: Board name '{board_name}' must not resolve to an absolute path.")
        return False

    if any(sep in board_name for sep in (os.sep, os.altsep) if sep):
        log.error("Board name '%s' contains invalid path characters.", board_name)
        print(f"Error: Board name '{board_name}' contains invalid path characters.")
        return False

    board_name = normalised_board_name

    reserved_names = {"common", "template", "scripts", ".cache", ".git"}
    if board_name in reserved_names:
        log.error("Board '%s' is reserved and cannot be deleted.", board_name)
        print(f"Error: Board '{board_name}' is reserved and cannot be deleted.")
        return False

    if not isinstance(env, dict):
        log.error("Environment must be a dictionary containing 'projects_path'.")
        print("Error: Environment must contain 'projects_path'.")
        return False

    projects_path = env.get("projects_path")
    if not isinstance(projects_path, str) or not projects_path.strip():
        log.error("Invalid 'projects_path' in environment: %s", projects_path)
        print("Error: Invalid 'projects_path' in environment.")
        return False

    protected_boards = env.get("protected_boards", [])
    if isinstance(protected_boards, (set, list, tuple)) and board_name in set(protected_boards):
        log.error("Board '%s' is protected and cannot be deleted.", board_name)
        print(f"Error: Board '{board_name}' is protected and cannot be deleted.")
        return False

    projects_path = os.path.abspath(projects_path)
    board_path = os.path.abspath(os.path.join(projects_path, board_name))
    if os.path.commonpath([projects_path, board_path]) != projects_path:
        log.error(
            "Board name '%s' resolves outside of projects path '%s'.",
            board_name,
            projects_path,
        )
        print(
            f"Error: Board name '{board_name}' resolves outside of projects path '{projects_path}'."
        )
        return False
    if not os.path.isdir(board_path):
        log.error("Board '%s' does not exist at '%s'.", board_name, board_path)
        print(f"Error: Board '{board_name}' does not exist.")
        return False

    log.debug("Deleting board '%s' at '%s'.", board_name, board_path)

    try:
        shutil.rmtree(board_path)
    except OSError as err:
        log.error("Failed to delete board '%s': %s", board_name, err)
        print(f"Error: Failed to delete board '{board_name}': {err}")
        return False

    root_path = env.get("root_path")
    if not isinstance(root_path, str) or not root_path:
        root_path = os.path.abspath(os.path.join(projects_path, os.pardir))

    cache_paths = [
        os.path.join(root_path, ".cache", "projects", board_name),
        os.path.join(root_path, ".cache", "boards", board_name),
        os.path.join(root_path, ".cache", "build", board_name),
    ]
    for cache_path in cache_paths:
        if os.path.exists(cache_path):
            try:
                shutil.rmtree(cache_path)
                log.debug("Removed cache directory '%s'.", cache_path)
            except OSError as err:
                log.warning("Failed to remove cache path '%s': %s", cache_path, err)

    def _update_projects_index(projects_path: str, board: str) -> None:
        index_path = os.path.join(projects_path, "projects.json")
        if not os.path.isfile(index_path):
            return

        try:
            with open(index_path, "r", encoding="utf-8") as index_file:
                data = json.load(index_file)
        except (OSError, UnicodeError, json.JSONDecodeError) as err:
            log.warning("Failed to read projects index '%s': %s", index_path, err)
            return

        changed = False
        payload = data
        if isinstance(data, dict):
            if board in data:
                data.pop(board, None)
                changed = True
            elif "boards" in data and isinstance(data["boards"], dict):
                if board in data["boards"]:
                    data["boards"].pop(board, None)
                    changed = True
            elif "boards" in data and isinstance(data["boards"], list):
                filtered_boards = [item for item in data["boards"] if item != board]
                if len(filtered_boards) != len(data["boards"]):
                    data["boards"] = filtered_boards
                    changed = True
        elif isinstance(data, list):
            filtered_data = [item for item in data if item != board]
            if len(filtered_data) != len(data):
                payload = filtered_data
                changed = True
        else:
            log.debug(
                "Projects index '%s' has unsupported format (%s). Skipping update.",
                index_path,
                type(data),
            )
            return

        if changed:
            try:
                with open(index_path, "w", encoding="utf-8") as index_file:
                    json.dump(payload, index_file, indent=2, ensure_ascii=False)
                log.debug(
                    "Updated projects index '%s' after deleting board '%s'.",
                    index_path,
                    board,
                )
            except (OSError, UnicodeError, ValueError) as err:
                log.warning("Failed to update projects index '%s': %s", index_path, err)

    _update_projects_index(projects_path, board_name)

    if isinstance(projects_info, dict):
        removed_projects = [
            name
            for name, info in list(projects_info.items())
            if isinstance(info, dict) and info.get("board_name") == board_name
        ]
        for name in removed_projects:
            projects_info.pop(name, None)
        if board_name in projects_info:
            projects_info.pop(board_name, None)
        if removed_projects:
            log.debug(
                "Removed %d project(s) associated with board '%s' from in-memory index.",
                len(removed_projects),
                board_name,
            )

    print(f"Deleted board '{board_name}'.")
    return True
