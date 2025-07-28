"""
Project management utility class for CLI operations.
"""

import os

from configupdater import ConfigUpdater

from src.log_manager import log
from src.profiler import auto_profile


@auto_profile
class ProjectManager:
    """
    Project management utility class. All methods are static and stateless.
    """

    OPERATION_META: dict[str, dict] = {
        # Example: set to True if the operation needs repositories
        # "some_operation": {"needs_repositories": True},
        # Other operations...
    }

    def __init__(self):
        raise NotImplementedError(
            "ProjectManager is a utility class and cannot be instantiated."
        )

    @staticmethod
    def project_new(env, projects_info, project_name):
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

        def strip_empty_lines(lines):
            while lines and lines[0].strip() == "":
                lines = lines[1:]
            while lines and lines[-1].strip() == "":
                lines = lines[:-1]
            return lines

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
            print(
                f"Error: Board directory '{board_name}' does not exist for project '{project_name}'."
            )
            return False
        if not ini_file:
            log.error("No ini file found for board: '%s'", board_name)
            print(f"No ini file found for board: '{board_name}'")
            return False

        # project_name cannot be the same as board_name (board section is not a project)
        if project_name == board_name:
            log.error(
                "Project name '%s' cannot be the same as board name.", project_name
            )
            print(
                f"Error: Project name '{project_name}' cannot be the same as board name."
            )
            return False

        # Check for duplicate project
        config = ConfigUpdater()
        config.optionxform = str
        config.read(ini_file, encoding="utf-8")
        if project_name in config.sections():
            log.error(
                "Project '%s' already exists in board '%s'.", project_name, board_name
            )
            print(f"Project '{project_name}' already exists in board '{board_name}'.")
            return False

        # Recursively inherit configuration
        inherited_config = get_inherited_config(projects_info, project_name)
        parent_config = (
            inherited_config.get("config", {})
            if isinstance(inherited_config.get("config", {}), dict)
            else {}
        )
        chip_name = parent_config.get("PROJECT_CHIP_NAME")
        project_customer = parent_config.get("PROJECT_CUSTOMER")
        project_name_parts = []
        if chip_name:
            project_name_parts.append(chip_name)
        project_name_parts.append(project_name)
        if project_customer:
            project_name_parts.append(project_customer)
        project_name_value = "_".join(project_name_parts)

        # Only write new project-specific fields
        new_section_lines = [f"[{project_name}]\n"]
        new_section_lines.append(f"PROJECT_NAME={project_name_value}\n")
        # Do not write PROJECT_PO_CONFIG by default, let it inherit from parent
        new_section_lines.append("\n")

        # Read the original ini file content to preserve comments and formatting
        with open(ini_file, "r", encoding="utf-8") as f:
            original_lines = f.readlines()

        # --- Parse all section contents ---
        section_blocks = []  # [(section_name, [lines])]
        current_section = None
        current_lines = []
        for line in original_lines:
            line_strip = line.strip()
            if line_strip.startswith("[") and line_strip.endswith("]"):
                if current_section is not None:
                    section_blocks.append(
                        (current_section, strip_empty_lines(current_lines))
                    )
                current_section = line_strip[1:-1]
                current_lines = [line]
            else:
                if current_section is not None:
                    current_lines.append(line)
        if current_section is not None:
            section_blocks.append((current_section, strip_empty_lines(current_lines)))

        # --- Add new project section to section_blocks ---
        new_section = (project_name, new_section_lines)
        section_blocks.append(new_section)

        section_objs = {name: config[name] for name in config.sections()}
        for name in config.sections():
            config.remove_section(name)
        for idx, name in enumerate(section_objs.keys()):
            config.add_section(name)
            for opt_key, opt_val in section_objs[name].items():
                val = opt_val.value if hasattr(opt_val, "value") else opt_val
                config[name][opt_key] = val
                if hasattr(opt_val, "comment"):
                    config[name][opt_key].comment = opt_val.comment
            if hasattr(section_objs[name], "comment") and section_objs[name].comment:
                config[name].set_comment(section_objs[name].comment)
            # Only insert one blank line between every two sections
            if idx < len(section_objs) - 1:
                config[name].add_after.space()
        # Before adding the new project, ensure there is one blank line after the last section
        if project_name not in config:
            if config.sections():
                last_section = list(config.sections())[-1]
                last_section_obj = config[last_section]
                last_section_obj.add_after.space()
            config.add_section(project_name)
        config[project_name]["PROJECT_NAME"] = project_name_value
        # Do not write PROJECT_PO_CONFIG by default
        config.update_file()
        log.debug("Created new project '%s' in board '%s'.", project_name, board_name)
        print(f"Created new project '{project_name}' in board '{board_name}'.")
        # Print all config for the new project (merged: ini section + inherited config['config'])
        parent_config = (
            inherited_config.get("config", {})
            if isinstance(inherited_config.get("config", {}), dict)
            else {}
        )
        merged_config = dict(parent_config)
        if project_name in config:
            for key, value in config[project_name].items():
                merged_config[key] = value.value if hasattr(value, "value") else value
        print(f"All config for project '{project_name}':")
        for key, value in merged_config.items():
            print(f"  {key} = {value}")
        return True

    @staticmethod
    def project_del(env, projects_info, project_name):
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
            print(
                f"Error: Board directory '{board_name}' does not exist for project '{project_name}'."
            )
            return False
        if not ini_file:
            log.error("No ini file found for board: '%s'", board_name)
            print(f"No ini file found for board: '{board_name}'")
            return False

        # project_name cannot be the same as board_name
        if project_name == board_name:
            log.error(
                "Project name '%s' cannot be the same as board name.", project_name
            )
            print(
                f"Error: Project name '{project_name}' cannot be the same as board name."
            )
            return False

        config = ConfigUpdater()
        config.optionxform = str
        config.read(ini_file, encoding="utf-8")
        # Recursively delete all subprojects
        to_delete = [project_name] + find_all_subprojects(projects_info, project_name)
        for del_name in to_delete:
            if del_name not in config.sections():
                log.info(
                    "Project '%s' does not exist in board '%s'.", del_name, board_name
                )
                print(f"Project '{del_name}' does not exist in board '{board_name}'.")
            else:
                config.remove_section(del_name)
                log.debug("Removed project '%s' from board '%s'.", del_name, board_name)
                print(f"Removed project '{del_name}' from board '{board_name}'.")
        config.update_file()
        return True

    @staticmethod
    def board_new(env, projects_info, board_name):
        """
        Create a new board.
        Args:
            env (dict): Global environment dict.
            projects_info (dict): All projects info.
            board_name (str): Board name.
        """
        # TODO: implement board_new

    @staticmethod
    def board_del(env, projects_info, board_name):
        """
        Delete the specified board.
        Args:
            env (dict): Global environment dict.
            projects_info (dict): All projects info.
            board_name (str): Board name.
        """
        # TODO: implement board_del
