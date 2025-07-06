"""
Patch and override operations for project management.
"""
import os
import shutil
import subprocess
import re
from src.log_manager import log
from src.profiler import auto_profile

@auto_profile
class PatchOverride:
    """
    Patch and override operations for po.
    """
    def __init__(self, vprojects_path, all_projects_info):
        self.vprojects_path = vprojects_path
        self.all_projects_info = all_projects_info

    def po_apply(self, project_name):
        """
        Apply patch and override for the specified project.
        Args:
            project_name (str): Project or board name.
        Returns:
            bool: True if success, otherwise False.
        """
        log.info("start po_apply for project: '%s'", project_name)
        project_cfg = self.all_projects_info.get(project_name, {})
        board_name = project_cfg.get('board_name')
        if not board_name:
            log.error("Cannot find board name for project: '%s'", project_name)
            return False
        board_path = os.path.join(self.vprojects_path, board_name)
        po_dir = os.path.join(board_path, "po")
        po_config = project_cfg.get("PROJECT_PO_CONFIG", "").strip()
        if not po_config:
            log.warning("No PROJECT_PO_CONFIG found for '%s'", project_name)
            return True
        apply_pos, exclude_pos, exclude_files = self.__parse_po_config(po_config)
        apply_pos = [po_name for po_name in apply_pos if po_name not in exclude_pos]
        log.debug("all_projects_info: %s", str(self.all_projects_info.get(project_name, {})))
        log.debug("po_dir: '%s'", po_dir)
        if apply_pos:
            log.debug("apply_pos: %s", str(apply_pos))
        if exclude_pos:
            log.debug("exclude_pos: %s", str(exclude_pos))
        if exclude_files:
            log.debug("exclude_files: %s", str(exclude_files))
        for po_name in apply_pos:
            po_patch_dir = os.path.join(po_dir, po_name, "patches")
            if not self.__apply_patch(po_name, po_patch_dir, exclude_files):
                log.error("po apply aborted due to patch error in po: '%s'", po_name)
                return False
            po_override_dir = os.path.join(po_dir, po_name, "overrides")
            if not self.__apply_override(po_name, po_override_dir, exclude_files):
                log.error("po apply aborted due to override error in po: '%s'", po_name)
                return False
            log.info("po '%s' has been processed", po_name)
        log.info("po apply finished for project: '%s'", project_name)
        return True

    def po_revert(self, project_name):
        """
        Revert patch and override for the specified project.
        Args:
            project_name (str): Project or board name.
        Returns:
            bool: True if success, otherwise False.
        """
        log.info("start po_revert for project: '%s'", project_name)
        project_cfg = self.all_projects_info.get(project_name, {})
        board_name = project_cfg.get('board_name')
        if not board_name:
            log.error("Cannot find board name for project: '%s'", project_name)
            return False
        board_path = os.path.join(self.vprojects_path, board_name)
        po_dir = os.path.join(board_path, "po")
        po_config = project_cfg.get("PROJECT_PO_CONFIG", "").strip()
        if not po_config:
            log.warning("No PROJECT_PO_CONFIG found for '%s'", project_name)
            return True
        apply_pos, exclude_pos, exclude_files = self.__parse_po_config(po_config)
        apply_pos = [po_name for po_name in apply_pos if po_name not in exclude_pos]
        log.debug("all_projects_info: %s", str(self.all_projects_info.get(project_name, {})))
        log.debug("po_dir: '%s'", po_dir)
        if apply_pos:
            log.debug("apply_pos: %s", str(apply_pos))
        if exclude_pos:
            log.debug("exclude_pos: %s", str(exclude_pos))
        if exclude_files:
            log.debug("exclude_files: %s", str(exclude_files))
        for po_name in apply_pos:
            po_patch_dir = os.path.join(po_dir, po_name, "patches")
            if not self.__revert_patch(po_name, po_patch_dir, exclude_files):
                log.error("po revert aborted due to patch error in po: '%s'", po_name)
                return False
            po_override_dir = os.path.join(po_dir, po_name, "overrides")
            if not self.__revert_override(po_name, po_override_dir, exclude_files):
                log.error("po revert aborted due to override error in po: '%s'", po_name)
                return False
            log.info("po '%s' has been reverted", po_name)
        log.info("po revert finished for project: '%s'", project_name)
        return True

    def po_new(self, project_name, po_name):
        """
        Create a new PO (patch and override) directory structure for the specified project.
        Args:
            project_name (str): Project or board name.
            po_name (str): Name of the new PO to create.
        Returns:
            bool: True if success, otherwise False.
        """
        log.info("start po_new for project: '%s', po_name: '%s'", project_name, po_name)
        if not re.match(r"^po[a-z0-9_]*$", po_name):
            log.error("po_name '%s' is invalid. It must start with 'po' and only contain lowercase letters, digits, and underscores.", po_name)
            return False
        project_cfg = self.all_projects_info.get(project_name, {})
        board_name = project_cfg.get('board_name')
        if not board_name:
            log.error("Cannot find board name for project: '%s'", project_name)
            return False

        board_path = os.path.join(self.vprojects_path, board_name)
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

        try:
            # Create po directory
            os.makedirs(po_path, exist_ok=True)
            log.info("Created po directory: '%s'", po_path)

            # Create patches directory with .gitkeep
            os.makedirs(patches_dir, exist_ok=True)
            gitkeep_file = os.path.join(patches_dir, ".gitkeep")
            if not os.path.exists(gitkeep_file):
                with open(gitkeep_file, 'w', encoding='utf-8'):
                    pass  # Create empty file
                log.info("Created .gitkeep in patches directory: '%s'", patches_dir)

            # Create overrides directory with .gitkeep
            os.makedirs(overrides_dir, exist_ok=True)
            gitkeep_file = os.path.join(overrides_dir, ".gitkeep")
            if not os.path.exists(gitkeep_file):
                with open(gitkeep_file, 'w', encoding='utf-8'):
                    pass  # Create empty file
                log.info("Created .gitkeep in overrides directory: '%s'", overrides_dir)

            log.info("po_new finished for project: '%s', po_name: '%s'", project_name, po_name)
            return True

        except OSError as e:
            log.error("Failed to create po directory structure for '%s': '%s'", po_name, e)
            return False

    def po_del(self, project_name, po_name, force=False):
        """
        Delete the specified PO directory and remove it from all project configurations.
        Args:
            project_name (str): Project or board name.
            po_name (str): Name of the PO to delete.
            force (bool): If True, skip confirmation prompt.
        Returns:
            bool: True if success, otherwise False.
        """
        log.info("start po_del for project: '%s', po_name: '%s'", project_name, po_name)

        # Validate po_name format
        if not re.match(r"^po[a-z0-9_]*$", po_name):
            log.error("po_name '%s' is invalid. It must start with 'po' and only contain lowercase letters, digits, and underscores.", po_name)
            return False

        project_cfg = self.all_projects_info.get(project_name, {})
        board_name = project_cfg.get('board_name')
        if not board_name:
            log.error("Cannot find board name for project: '%s'", project_name)
            return False

        board_path = os.path.join(self.vprojects_path, board_name)
        po_dir = os.path.join(board_path, "po")
        po_path = os.path.join(po_dir, po_name)

        # Check if PO directory exists
        if not os.path.exists(po_path):
            log.error("PO directory '%s' does not exist", po_path)
            return False

        # Show what will be deleted and ask for confirmation
        if not force:
            if not self.__confirm_deletion(po_name, po_path):
                log.info("po_del cancelled by user")
                return False

        # First, remove the PO from all project configurations
        if not self.__remove_po_from_configs(po_name):
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

    def __confirm_deletion(self, po_name, po_path):
        """
        Show deletion information and ask for user confirmation.
        Args:
            po_name (str): Name of the PO to delete.
            po_path (str): Path to the PO directory.
        Returns:
            bool: True if user confirms, False otherwise.
        """
        print("\n=== PO Deletion Confirmation ===")
        print(f"PO Name: {po_name}")
        print(f"PO Path: {po_path}")

        # Show directory contents
        if os.path.exists(po_path):
            print("\nDirectory contents:")
            self.__print_directory_tree(po_path, prefix="  ")

        # Show which projects use this PO
        using_projects = self.__find_projects_using_po(po_name)
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
            if response in ['yes', 'y']:
                return True
            if response in ['no', 'n']:
                return False
            print("Please enter 'yes' or 'no'.")

    def __print_directory_tree(self, path, prefix="", max_depth=3, current_depth=0):
        """
        Print a tree representation of directory contents.
        Args:
            path (str): Directory path to print.
            prefix (str): Prefix for indentation.
            max_depth (int): Maximum depth to print.
            current_depth (int): Current depth level.
        """
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
                    self.__print_directory_tree(item_path, next_prefix, max_depth, current_depth + 1)
                else:
                    size = os.path.getsize(item_path)
                    print(f"{current_prefix}{item} ({size} bytes)")
        except OSError as e:
            print(f"{prefix}Error reading directory: {e}")

    def __find_projects_using_po(self, po_name):
        """
        Find all projects that use the specified PO.
        Args:
            po_name (str): Name of the PO to search for.
        Returns:
            list: List of project names that use this PO.
        """
        using_projects = []
        for project_name, project_cfg in self.all_projects_info.items():
            po_config = project_cfg.get("PROJECT_PO_CONFIG", "").strip()
            if not po_config:
                continue

            # Check if this PO is used in the config
            tokens = re.findall(r'-?\w+(?:\[[^\]]+\])?', po_config)
            for token in tokens:
                base = token.lstrip('-')
                base = base.split('[', 1)[0]
                if base == po_name:
                    using_projects.append(project_name)
                    break

        return using_projects

    def __remove_po_from_configs(self, po_name):
        """
        Remove the specified PO from all project configurations.
        Args:
            po_name (str): Name of the PO to remove.
        Returns:
            bool: True if success, otherwise False.
        """
        log.debug("Removing PO '%s' from all project configurations", po_name)

        # Group projects by their board and ini file
        board_configs = {}
        for project_name, project_cfg in self.all_projects_info.items():
            board_name = project_cfg.get('board_name')
            if not board_name:
                continue

            if board_name not in board_configs:
                board_configs[board_name] = {}

            # Find the ini file for this board
            board_path = os.path.join(self.vprojects_path, board_name)
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
                if not self.__update_ini_file(ini_file, projects, po_name):
                    return False

        return True

    def __update_ini_file(self, ini_file, projects, po_name):
        """
        Update the ini file to remove the specified PO from all project configurations.
        Args:
            ini_file (str): Path to the ini file.
            projects (list): List of project names in this ini file.
            po_name (str): Name of the PO to remove.
        Returns:
            bool: True if success, otherwise False.
        """
        log.debug("Updating ini file: '%s' to remove PO '%s'", ini_file, po_name)

        try:
            # Read the current ini file
            with open(ini_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # Parse the file and update PROJECT_PO_CONFIG lines
            updated_lines = []
            current_section = None
            in_project_section = False

            for line in lines:
                stripped_line = line.strip()

                # Check if this is a section header
                if stripped_line.startswith('[') and stripped_line.endswith(']'):
                    current_section = stripped_line[1:-1].strip()
                    in_project_section = current_section in projects
                    updated_lines.append(line)
                    continue

                # If we're in a project section and this is a PROJECT_PO_CONFIG line
                if in_project_section and stripped_line.replace(' ', '').startswith('PROJECT_PO_CONFIG='):
                    # Parse the current config and remove the PO
                    config_value = line.split('=', 1)[1].strip()
                    updated_config = self.__remove_po_from_config_string(config_value, po_name)
                    # Update the line
                    updated_lines.append(f"PROJECT_PO_CONFIG={updated_config}\n")
                    log.debug("Updated PROJECT_PO_CONFIG for project '%s': '%s' -> '%s'",
                             current_section, config_value, updated_config)
                else:
                    updated_lines.append(line)

            # Write the updated file
            with open(ini_file, 'w', encoding='utf-8') as f:
                f.writelines(updated_lines)

            log.info("Updated ini file: '%s'", ini_file)
            return True

        except OSError as e:
            log.error("Failed to update ini file '%s': '%s'", ini_file, e)
            return False

    def __remove_po_from_config_string(self, config_string, po_name):
        """
        Remove the specified PO from a PROJECT_PO_CONFIG string.
        Args:
            config_string (str): The PROJECT_PO_CONFIG string.
            po_name (str): Name of the PO to remove.
        Returns:
            str: Updated config string with the PO removed.
        """
        if not config_string:
            return config_string
        tokens = re.findall(r'-?\w+(?:\[[^\]]+\])?', config_string)
        updated_tokens = []
        for token in tokens:
            # Remove leading '-' and trailing '[...]' for comparison
            base = token.lstrip('-')
            base = base.split('[', 1)[0]
            if base != po_name:
                updated_tokens.append(token)
            else:
                log.debug("Removing PO '%s' from config string token: '%s'", po_name, token)
        return ' '.join(updated_tokens)

    def __parse_po_config(self, po_config):
        apply_pos = []
        exclude_pos = set()
        exclude_files = {}
        tokens = re.findall(r'-?\w+(?:\[[^\]]+\])?', po_config)
        for token in tokens:
            if token.startswith('-'):
                if '[' in token:
                    po_name, files = re.match(r'-(\w+)\[([^\]]+)\]', token).groups()
                    file_list = set(f.strip() for f in files.split())
                    exclude_files.setdefault(po_name, set()).update(file_list)
                else:
                    po_name = token[1:]
                    exclude_pos.add(po_name)
            else:
                po_name = token
                apply_pos.append(po_name)
        return apply_pos, exclude_pos, exclude_files

    def __apply_patch(self, po_name, po_patch_dir, exclude_files):
        patch_applied_dirs = set()
        log.debug("po_name: '%s', po_patch_dir: '%s'", po_name, po_patch_dir)
        if not os.path.isdir(po_patch_dir):
            log.debug("No patches dir for po: '%s'", po_name)
            return True
        log.debug("applying patches for po: '%s'", po_name)
        for current_dir, _, files in os.walk(po_patch_dir):
            log.debug("current_dir: '%s', files: '%s'", current_dir, files)
            for fname in files:
                if fname == ".gitkeep":
                    continue
                log.debug("current_dir: '%s', fname: '%s'", current_dir, fname)
                rel_path = os.path.relpath(os.path.join(current_dir, fname), po_patch_dir)
                log.debug("patch rel_path: '%s'", rel_path)
                if po_name in exclude_files and rel_path in exclude_files[po_name]:
                    log.debug("patch file '%s' in po '%s' is excluded by config", rel_path, po_name)
                    continue
                path_parts = rel_path.split(os.sep)
                patch_target = path_parts[0] if len(path_parts) > 1 else "."
                patch_flag = os.path.join(patch_target, ".patch_applied")
                log.debug("patch patch_target: '%s', patch_flag: '%s'", patch_target, patch_flag)
                if patch_target in patch_applied_dirs:
                    log.debug("patch flag already set for dir: '%s', skipping", patch_target)
                    continue
                if os.path.exists(patch_flag):
                    try:
                        with open(patch_flag, 'r', encoding='utf-8') as f:
                            applied_pos_in_flag = f.read().strip().split('\n')
                        if po_name in applied_pos_in_flag:
                            log.info("patch already applied for dir: '%s' by po: '%s', skipping", patch_target, po_name)
                            patch_applied_dirs.add(patch_target)
                            continue
                    except OSError:
                        # If file exists but can't be read, treat as not applied
                        pass
                patch_file = os.path.join(current_dir, fname)
                log.info("applying patch: '%s' to dir: '%s'", patch_file, patch_target)
                try:
                    result = subprocess.run([
                        "git", "apply", patch_file
                    ], cwd=patch_target, capture_output=True, text=True, check=False)
                    log.debug("git apply result: returncode: '%s', stdout: '%s', stderr: '%s'", result.returncode, result.stdout, result.stderr)
                    if result.returncode != 0:
                        log.error("Failed to apply patch '%s': '%s'", patch_file, result.stderr)
                        return False
                    os.makedirs(patch_target, exist_ok=True)
                    with open(patch_flag, 'a', encoding='utf-8') as f:
                        f.write(f'{po_name}\n')
                    patch_applied_dirs.add(patch_target)
                    log.info("patch applied and flag set for dir: '%s'", patch_target)
                except subprocess.SubprocessError as e:
                    log.error("Subprocess error applying patch '%s': '%s'", patch_file, e)
                    return False
                except OSError as e:
                    log.error("OS error applying patch '%s': '%s'", patch_file, e)
                    return False
        return True

    def __apply_override(self, po_name, po_override_dir, exclude_files):
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
                rel_path = os.path.relpath(os.path.join(current_dir, fname), po_override_dir)
                log.debug("override rel_path: '%s'", rel_path)
                if po_name in exclude_files and rel_path in exclude_files[po_name]:
                    log.debug("override file '%s' in po '%s' is excluded by config", rel_path, po_name)
                    continue
                path_parts = rel_path.split(os.sep)
                override_target = path_parts[0] if len(path_parts) > 1 else "."
                override_flag = os.path.join(override_target, ".override_applied")
                log.debug("override override_target: '%s', override_flag: '%s'", override_target, override_flag)
                if override_target in override_applied_dirs:
                    log.debug("override flag already set for dir: '%s', skipping", override_target)
                    continue
                if os.path.exists(override_flag):
                    try:
                        with open(override_flag, 'r', encoding='utf-8') as f:
                            applied_pos_in_flag = f.read().strip().split('\n')
                        if po_name in applied_pos_in_flag:
                            log.info("override already applied for dir: '%s' by po: '%s', skipping", override_target, po_name)
                            override_applied_dirs.add(override_target)
                            continue
                    except OSError:
                        # If file exists but can't be read, treat as not applied
                        pass
                src_file = os.path.join(current_dir, fname)
                dest_file = os.path.join(override_target, *rel_path.split(os.sep)[1:]) if len(rel_path.split(os.sep)) > 1 else os.path.join(override_target, fname)
                log.debug("override src_file: '%s', dest_file: '%s'", src_file, dest_file)
                os.makedirs(os.path.dirname(dest_file), exist_ok=True)
                try:
                    shutil.copy2(src_file, dest_file)
                    with open(override_flag, 'a', encoding='utf-8') as f:
                        f.write(f'{po_name}\n')
                    override_applied_dirs.add(override_target)
                    log.info("override applied and flag set for dir: '%s', file: '%s'", override_target, dest_file)
                except OSError as e:
                    log.error("Failed to copy override file '%s' to '%s': '%s'", src_file, dest_file, e)
                    return False
        return True

    def __revert_patch(self, po_name, po_patch_dir, exclude_files):
        """
        Revert patches for the specified po.
        Args:
            po_name (str): PO name.
            po_patch_dir (str): Path to patches directory.
            exclude_files (dict): Files to exclude from reversion.
        Returns:
            bool: True if success, otherwise False.
        """
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
                    log.debug("patch file '%s' in po '%s' is excluded by config", rel_path, po_name)
                    continue
                path_parts = rel_path.split(os.sep)
                patch_target = path_parts[0] if len(path_parts) > 1 else "."
                patch_flag = os.path.join(patch_target, ".patch_applied")
                log.debug("patch patch_target: '%s', patch_flag: '%s'", patch_target, patch_flag)
                if not os.path.exists(patch_flag):
                    log.debug("No patch flag found for dir: '%s', skipping", patch_target)
                    continue
                try:
                    with open(patch_flag, 'r', encoding='utf-8') as f:
                        applied_pos_in_flag = f.read().strip().split('\n')
                    if po_name not in applied_pos_in_flag:
                        log.debug("patch not applied for dir: '%s' by po: '%s', skipping", patch_target, po_name)
                        continue
                except OSError:
                    log.debug("Cannot read patch flag for dir: '%s', skipping", patch_target)
                    continue
                patch_file = os.path.join(current_dir, fname)
                log.info("reverting patch: '%s' from dir: '%s'", patch_file, patch_target)
                try:
                    result = subprocess.run([
                        "git", "apply", "--reverse", patch_file
                    ], cwd=patch_target, capture_output=True, text=True, check=False)
                    log.debug("git apply --reverse result: returncode: '%s', stdout: '%s', stderr: '%s'", result.returncode, result.stdout, result.stderr)
                    if result.returncode != 0:
                        log.error("Failed to revert patch '%s': '%s'", patch_file, result.stderr)
                        return False
                    # Remove po_name from flag file
                    applied_pos_in_flag.remove(po_name)
                    if applied_pos_in_flag:
                        with open(patch_flag, 'w', encoding='utf-8') as f:
                            f.write('\n'.join(applied_pos_in_flag) + '\n')
                    else:
                        # If no more applied pos, remove the flag file
                        os.remove(patch_flag)
                    log.info("patch reverted and flag updated for dir: '%s'", patch_target)
                except subprocess.SubprocessError as e:
                    log.error("Subprocess error reverting patch '%s': '%s'", patch_file, e)
                    return False
                except OSError as e:
                    log.error("OS error reverting patch '%s': '%s'", patch_file, e)
                    return False
        return True

    def __revert_override(self, po_name, po_override_dir, exclude_files):
        """
        Revert overrides for the specified po.
        Args:
            po_name (str): PO name.
            po_override_dir (str): Path to overrides directory.
            exclude_files (dict): Files to exclude from reversion.
        Returns:
            bool: True if success, otherwise False.
        """
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
                    log.debug("override file '%s' in po '%s' is excluded by config", rel_path, po_name)
                    continue
                path_parts = rel_path.split(os.sep)
                override_target = path_parts[0] if len(path_parts) > 1 else "."
                override_flag = os.path.join(override_target, ".override_applied")
                log.debug("override override_target: '%s', override_flag: '%s'", override_target, override_flag)
                if not os.path.exists(override_flag):
                    log.debug("No override flag found for dir: '%s', skipping", override_target)
                    continue
                try:
                    with open(override_flag, 'r', encoding='utf-8') as f:
                        applied_pos_in_flag = f.read().strip().split('\n')
                    if po_name not in applied_pos_in_flag:
                        log.debug("override not applied for dir: '%s' by po: '%s', skipping", override_target, po_name)
                        continue
                except OSError:
                    log.debug("Cannot read override flag for dir: '%s', skipping", override_target)
                    continue
                dest_file = os.path.join(override_target, *rel_path.split(os.sep)[1:]) if len(rel_path.split(os.sep)) > 1 else os.path.join(override_target, fname)
                log.debug("override dest_file: '%s'", dest_file)
                if os.path.exists(dest_file):
                    log.info("reverting override file: '%s'", dest_file)
                    try:
                        # First check if the file is tracked by git
                        result = subprocess.run([
                            "git", "ls-files", "--error-unmatch", dest_file
                        ], cwd=override_target, capture_output=True, text=True, check=False)

                        if result.returncode == 0:
                            # File is tracked by git, use git checkout to restore
                            result = subprocess.run([
                                "git", "checkout", "--", dest_file
                            ], cwd=override_target, capture_output=True, text=True, check=False)
                            log.debug("git checkout result: returncode: '%s', stdout: '%s', stderr: '%s'", result.returncode, result.stdout, result.stderr)
                            if result.returncode != 0:
                                log.error("Failed to revert override file '%s': '%s'", dest_file, result.stderr)
                                return False
                        else:
                            # File is not tracked by git, delete it directly
                            log.debug("File '%s' is not tracked by git, deleting directly", dest_file)
                            os.remove(dest_file)

                        # Remove po_name from flag file
                        applied_pos_in_flag.remove(po_name)
                        if applied_pos_in_flag:
                            with open(override_flag, 'w', encoding='utf-8') as f:
                                f.write('\n'.join(applied_pos_in_flag) + '\n')
                        else:
                            # If no more applied pos, remove the flag file
                            os.remove(override_flag)
                        log.info("override reverted and flag updated for dir: '%s', file: '%s'", override_target, dest_file)
                    except subprocess.SubprocessError as e:
                        log.error("Subprocess error reverting override file '%s': '%s'", dest_file, e)
                        return False
                    except OSError as e:
                        log.error("OS error reverting override file '%s': '%s'", dest_file, e)
                        return False
                else:
                    log.debug("Override file '%s' does not exist, skipping", dest_file)
        return True
