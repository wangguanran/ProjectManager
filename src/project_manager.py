"""
Main module for project management.
"""
import os
import shutil
import sys
import json
import argparse
import fnmatch
import importlib.util
import configparser
from src.log_manager import log
from src.profiler import auto_profile
from src.utils import path_from_root, get_version, list_file_path

PM_CONFIG_PATH = path_from_root("pm_config.json")
DEFAULT_KEYWORD = "demo"

@auto_profile
class ProjectManager:
    """
    Project utility class. Provides project management and plugin operation features.
    """
    def __init__(self):
        self.vprojects_path = path_from_root("vprojects")
        self.all_projects_info = {}
        self.platform_operations = []
        self.project_to_board = {}
        self.__load_all_projects()
        self.__load_script_plugins()
        # Print all loaded project info
        log.debug("Loaded projects info:\n%s", json.dumps(self.all_projects_info, indent=2, ensure_ascii=False))
        log.debug("Platform operations: %s", self.platform_operations)
        log.info("Loaded %d projects.", len(self.all_projects_info))
        log.info("Loaded %d script plugins.", len(self.platform_operations))

    def __load_all_projects(self):
        """
        Scan all board projects under vprojects, parse ini files, and save all project info.
        Build parent-child inheritance: child inherits all parent configs, child overrides same keys except PROJECT_PO_CONFIG, which is concatenated (parent first, then child).
        """
        exclude_dirs = {"scripts", "common", "template", ".cache"}
        if not os.path.exists(self.vprojects_path):
            log.warning("vprojects directory does not exist: %s", self.vprojects_path)
            return
        all_projects = {}
        project_to_board = {}
        invalid_projects = set()
        for item in os.listdir(self.vprojects_path):
            item_path = os.path.join(self.vprojects_path, item)
            if not os.path.isdir(item_path) or item in exclude_dirs:
                continue
            # Find ini file in this board directory
            ini_file = None
            for f in os.listdir(item_path):
                if f.endswith(".ini"):
                    ini_file = os.path.join(item_path, f)
                    break
            if not ini_file:
                log.warning("No ini file found in board directory: %s", item_path)
                continue
            # First pass: check for duplicate keys in the whole ini file
            has_duplicate = False
            with open(ini_file, 'r', encoding='utf-8') as f:
                current_project = None
                keys_in_project = set()
                for line in f:
                    line = line.strip()
                    if not line or line.startswith(';') or line.startswith('#'):
                        continue
                    if line.startswith('[') and line.endswith(']'):
                        current_project = line[1:-1].strip()
                        keys_in_project = set()
                        continue
                    if '=' in line and current_project:
                        key = line.split('=', 1)[0].strip()
                        if key in keys_in_project:
                            log.error("Duplicate key '%s' found in project '%s' of file '%s'", key, current_project, ini_file)
                            has_duplicate = True
                        else:
                            keys_in_project.add(key)
            if has_duplicate:
                continue  # skip this ini file entirely
            # No duplicate, safe to parse
            config = configparser.ConfigParser()
            config.optionxform = str  # preserve case
            config.read(ini_file, encoding="utf-8")
            for project in config.sections():
                project_dict = dict(config.items(project))
                all_projects[project] = project_dict
                project_to_board[project] = item  # record which board this project belongs to
        # Build parent-child relationship and merge configs
        def find_parent(project):
            # The parent project name is the project name with the last '-' and following part removed
            if '-' in project:
                return project.rsplit('-', 1)[0]
            return None
        merged_projects = {}
        def merge_config(project):
            if project in merged_projects:
                return merged_projects[project]
            if project in invalid_projects:
                return {}
            parent = find_parent(project)
            merged = {}
            if parent and parent in all_projects:
                parent_cfg = merge_config(parent)
                # Copy parent config first
                for k, v in parent_cfg.items():
                    if k == 'PROJECT_PO_CONFIG':
                        merged[k] = v  # Use parent's first, will handle concatenation later
                    else:
                        merged[k] = v
            # Then add/override with child's own config
            for k, v in all_projects[project].items():
                if k == 'PROJECT_PO_CONFIG' and k in merged:
                    # Concatenate parent and child, parent first, child after
                    merged[k] = merged[k].strip() + ' ' + v.strip()
                else:
                    merged[k] = v
            merged_projects[project] = merged
            return merged
        for project in all_projects:
            if project in invalid_projects:
                continue
            merged_cfg = merge_config(project)
            self.all_projects_info[project] = merged_cfg
        self.project_to_board = project_to_board  # Save project to board mapping

    def __load_script_plugins(self):
        """
        Load all script plugins under the scripts directory of each board in vprojects (excluding scripts, common, template, .cache).
        Collect all callable function names from each script into self.platform_operations.
        """
        exclude_dirs = {"scripts", "common", "template", ".cache"}
        platform_operations = set()
        if not os.path.exists(self.vprojects_path):
            log.warning("vprojects directory does not exist: %s", self.vprojects_path)
            self.platform_operations = list(platform_operations)
            return
        for item in os.listdir(self.vprojects_path):
            item_path = os.path.join(self.vprojects_path, item)
            if not os.path.isdir(item_path) or item in exclude_dirs:
                continue
            scripts_dir = os.path.join(item_path, "scripts")
            if not os.path.exists(scripts_dir):
                continue
            for file_name in os.listdir(scripts_dir):
                if not file_name.endswith(".py") or file_name.startswith("_"):
                    continue
                script_path = os.path.join(scripts_dir, file_name)
                module_name = f"{item}_scripts_{os.path.splitext(file_name)[0]}"
                try:
                    spec = importlib.util.spec_from_file_location(module_name, script_path)
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    for attr in dir(mod):
                        if attr.startswith("_"):
                            continue
                        func = getattr(mod, attr)
                        if callable(func):
                            platform_operations.add(attr)
                except OSError as e:
                    log.error(
                        "Failed to load script: %s, error: %s",
                        script_path, e
                    )
                    continue
        self.platform_operations = list(platform_operations)

    def new_project(self, project_name, type_, base=None):
        """
        Create a new project.
        Args:
            project_name (str): New project name.
            type_ (str): Type, 'board' or 'projects'.
            base (str): Base project name.
        Returns:
            bool: True if success, otherwise False.
        """
        log.info("Creating new project: name='%s', type='%s', base='%s'", project_name, type_, base)
        keyword = DEFAULT_KEYWORD
        base = base or project_name
        basedir = path_from_root(base)
        destdir = path_from_root(project_name)
        log.debug("basedir = '%s' destdir = '%s'", basedir, destdir)

        if type_ not in ["board", "projects"]:
            log.error("--type must be 'board' or 'projects'")
            return False

        if os.path.exists(basedir):
            if os.path.exists(destdir):
                log.error("Project already exists, cannot create repeatedly.")
            else:
                with open(PM_CONFIG_PATH, "r", encoding="utf-8") as f_read:
                    platform_json_info = json.load(f_read)
                    if hasattr(platform_json_info[base], "keyword"):
                        keyword = platform_json_info[base]["keyword"]
                    else:
                        keyword = DEFAULT_KEYWORD if base == project_name else base
                log.debug("keyword='%s'", keyword)
                shutil.copytree(basedir, destdir, symlinks=True)
                for file_path in list_file_path(destdir, list_dir=True):
                    if (fnmatch.fnmatch(os.path.basename(file_path), "env*.ini")
                            or file_path.endswith(".patch")):
                        try:
                            log.debug("Modifying file content '%s'", file_path)
                            with open(file_path, "r+", encoding="utf-8") as f_rw:
                                content = f_rw.readlines()
                                f_rw.seek(0)
                                f_rw.truncate()
                                for line in content:
                                    line = line.replace(keyword, project_name)
                                    f_rw.write(line)
                        except OSError as e:
                            log.error("Cannot read file '%s': %s", file_path, e)
                            return False
                    if keyword in os.path.basename(file_path):
                        p_dest = os.path.join(
                            os.path.dirname(file_path),
                            os.path.basename(file_path).replace(keyword, project_name))
                        log.debug(
                            "Renaming src file = '%s' dest file = '%s'",
                            file_path, p_dest
                        )
                        os.rename(file_path, p_dest)
                return True
        else:
            log.error("Base project directory does not exist, unable to create new project.")
        return False

    def del_project(self, project_name, info_path=None):
        """
        Delete the specified project directory and update its status in the config file.
        Args:
            project_name (str): Project name.
            info_path (str): Config file path.
        Returns:
            bool: True if success, otherwise False.
        """
        log.info("Start to delete project: %s", project_name)
        json_info = {}
        project_path = path_from_root(project_name)
        log.debug("project path = %s", project_path)

        if os.path.exists(project_path):
            shutil.rmtree(project_path)
        else:
            log.warning("'%s' path already deleted.", project_name)
        if not info_path:
            info_path = getattr(self, 'info_path', None)
        try:
            with open(info_path, "r", encoding="utf-8") as f_read:
                json_info = json.load(f_read)
                json_info[project_name]["status"] = "deleted"
            with open(info_path, "w+", encoding="utf-8") as f_write:
                json.dump(json_info, f_write, indent=4)
        except OSError as e:
            log.error("Cannot find info file: %s", e)
            return False
        return True

    def po_apply(self, project_name):
        """
        Apply PO operation for the specified project.
        Args:
            project_name (str): Project or board name.
        Returns:
            bool: True if success, otherwise False.
        """
        log.info("start po_apply for project: %s", project_name)
        # 1. Get board name and path
        board = self.project_to_board.get(project_name)
        if not board:
            log.error("Cannot find board for project: %s", project_name)
            return False
        board_path = os.path.join(self.vprojects_path, board)
        po_dir = os.path.join(board_path, "po")
        # 2. Get project config
        project_cfg = self.all_projects_info.get(project_name, {})
        po_config = project_cfg.get("PROJECT_PO_CONFIG", "").strip()
        if not po_config:
            log.warning("No PROJECT_PO_CONFIG found for %s", project_name)
            return True
        # 3. Parse po config
        import re
        apply_pos = []  # po packages to apply
        exclude_pos = set()  # po packages to exclude
        exclude_files = {}  # po package -> set(files)
        tokens = re.findall(r'-?\w+(?:\[[^\]]+\])?', po_config)
        for token in tokens:
            if token.startswith('-'):
                if '[' in token:
                    # -po_test04[testfile.c src/testfile.c]
                    po, files = re.match(r'-(\w+)\[([^\]]+)\]', token).groups()
                    file_list = set(f.strip() for f in files.split())
                    exclude_files.setdefault(po, set()).update(file_list)
                else:
                    po = token[1:]
                    exclude_pos.add(po)
            else:
                po = token
                apply_pos.append(po)
        # Remove duplicates and exclude po packages that should be excluded
        apply_pos = [po for po in apply_pos if po not in exclude_pos]

        log.debug("project_to_board: %s", str(self.project_to_board))
        log.debug("all_projects_info: %s", str(self.all_projects_info.get(project_name, {})))
        log.debug("po_dir: %s", po_dir)
        if apply_pos:
            log.debug("apply_pos: %s", str(apply_pos))
        if exclude_pos:
            log.debug("exclude_pos: %s", str(exclude_pos))
        if exclude_files:
            log.debug("exclude_files: %s", str(exclude_files))
        def _apply_patch(po, po_patch_dir, exclude_files):
            patch_applied_dirs = set()
            log.debug("_apply_patch: po=%s, po_patch_dir=%s", po, po_patch_dir)
            if not os.path.isdir(po_patch_dir):
                log.debug("No patches dir for PO: %s", po)
                return True
            log.debug("applying patches for po: %s", po)
            for root, _, files in os.walk(po_patch_dir):
                for fname in files:
                    if fname == ".gitkeep":
                        log.debug("ignore .gitkeep file in %s", root)
                        continue
                    rel_path = os.path.relpath(os.path.join(root, fname), po_patch_dir)
                    log.debug("patch rel_path: %s", rel_path)
                    if po in exclude_files and rel_path in exclude_files[po]:
                        log.debug("patch file %s in po %s is excluded by config", rel_path, po)
                        continue
                    top_dir = rel_path.split(os.sep)[0]
                    patch_flag = os.path.join(top_dir, ".patch_applied")
                    log.debug("patch top_dir: %s, patch_flag: %s", top_dir, patch_flag)
                    if top_dir in patch_applied_dirs:
                        log.debug("patch flag already set for dir: %s, skipping", top_dir)
                        continue
                    if os.path.exists(patch_flag):
                        log.info("patch already applied for dir: %s, skipping", top_dir)
                        patch_applied_dirs.add(top_dir)
                        continue
                    patch_file = os.path.join(root, fname)
                    log.info("applying patch: %s to dir: %s", patch_file, top_dir)
                    import subprocess
                    try:
                        result = subprocess.run([
                            "git", "apply", patch_file
                        ], cwd=".", capture_output=True, text=True)
                        log.debug("git apply result: returncode=%s, stdout=%s, stderr=%s", result.returncode, result.stdout, result.stderr)
                        if result.returncode != 0:
                            log.error("Failed to apply patch %s: %s", patch_file, result.stderr)
                            return False
                        else:
                            with open(patch_flag, 'w') as f:
                                f.write('patch applied')
                            patch_applied_dirs.add(top_dir)
                            log.info("patch applied and flag set for dir: %s", top_dir)
                    except Exception as e:
                        log.error("Exception applying patch %s: %s", patch_file, e)
                        return False
            return True

        def _apply_override(po, po_override_dir, exclude_files):
            override_applied_dirs = set()
            log.debug("_apply_override: po=%s, po_override_dir=%s", po, po_override_dir)
            if not os.path.isdir(po_override_dir):
                log.debug("No overrides dir for PO: %s", po)
                return True
            log.debug("applying overrides for po: %s", po)
            for root, _, files in os.walk(po_override_dir):
                for fname in files:
                    if fname == ".gitkeep":
                        log.debug("ignore .gitkeep file in %s", root)
                        continue
                    rel_path = os.path.relpath(os.path.join(root, fname), po_override_dir)
                    log.debug("override rel_path: %s", rel_path)
                    if po in exclude_files and rel_path in exclude_files[po]:
                        log.debug("override file %s in po %s is excluded by config", rel_path, po)
                        continue
                    top_dir = rel_path.split(os.sep)[0]
                    override_flag = os.path.join(top_dir, ".override_applied")
                    log.debug("override top_dir: %s, override_flag: %s", top_dir, override_flag)
                    if top_dir in override_applied_dirs:
                        log.debug("override flag already set for dir: %s, skipping", top_dir)
                        continue
                    if os.path.exists(override_flag):
                        log.info("override already applied for dir: %s, skipping", top_dir)
                        override_applied_dirs.add(top_dir)
                        continue
                    src_file = os.path.join(root, fname)
                    dest_file = os.path.join(top_dir, *rel_path.split(os.sep)[1:]) if len(rel_path.split(os.sep)) > 1 else os.path.join(top_dir, fname)
                    log.debug("override src_file: %s, dest_file: %s", src_file, dest_file)
                    os.makedirs(os.path.dirname(dest_file), exist_ok=True)
                    try:
                        shutil.copy2(src_file, dest_file)
                        with open(override_flag, 'w') as f:
                            f.write('override applied')
                        override_applied_dirs.add(top_dir)
                        log.info("override applied and flag set for dir: %s, file: %s", top_dir, dest_file)
                    except Exception as e:
                        log.error("Failed to copy override file %s to %s: %s", src_file, dest_file, e)
                        return False
            return True

        # 4. Process patch and override in po order
        for po in apply_pos:
            po_patch_dir = os.path.join(po_dir, po, "patches")
            if not _apply_patch(po, po_patch_dir, exclude_files):
                log.error("PO apply aborted due to patch error in PO: %s", po)
                return False
            po_override_dir = os.path.join(po_dir, po, "overrides")
            if not _apply_override(po, po_override_dir, exclude_files):
                log.error("PO apply aborted due to override error in PO: %s", po)
                return False
            log.info("po %s has been processed", po)
        log.info("po apply finished for project: %s", project_name)
        return True

def parse_cmd():
    """
    Parse command line arguments for the project manager.
    Returns:
        dict: Parsed arguments as a dictionary.
    """
    log.debug("argv = %s", sys.argv)
    parser = argparse.ArgumentParser()
    parser.add_argument('--version', action="version", version=get_version())
    help_text = (
        "supported operations: build/new_project/del_project/po_apply"
    )
    parser.add_argument(
        "operate",
        choices=["build", "new_project", "del_project", "po_apply"],
        help=help_text,
    )
    parser.add_argument("name", help="project or board name")
    parser.add_argument("--type", help="type for new operation: board or projects",
                        choices=["board", "projects"], default=None)
    parser.add_argument("--base", help="base project name for new operation")
    parser.add_argument('--perf-analyze', action='store_true', help='Enable cProfile performance analysis')
    args = parser.parse_args()
    return args.__dict__


def main():
    """
    Main entry point for the project manager CLI.
    """
    args_dict = parse_cmd()
    import builtins
    builtins.ENABLE_CPROFILE = args_dict.get('perf_analyze', False)
    manager = ProjectManager()

    operate = args_dict["operate"]
    name = args_dict["name"]
    type_ = args_dict.get("type")
    base = args_dict.get("base")

    if operate == "new_project":
        manager.new_project(project_name=name, type_=type_, base=base)
    elif operate == "del_project":
        manager.del_project(project_name=name)
    elif operate == "po_apply":
        manager.po_apply(project_name=name)
    else:
        log.error("Operation '%s' is not supported.", operate)


if __name__ == '__main__':
    main()
