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
