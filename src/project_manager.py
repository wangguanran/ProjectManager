"""
Main module for project management.
"""

import argparse
import builtins
import configparser
import importlib
import importlib.util
import inspect
import json
import os
import re
import sys
from src.log_manager import log
from src.profiler import auto_profile
from src.utils import path_from_root, get_version
from src.plugins.patch_override import PatchOverride

PM_CONFIG_PATH = path_from_root("pm_config.json")
DEFAULT_KEYWORD = "demo"


@auto_profile
class ProjectManager:
    """
    Project utility class. Provides project management and plugin operation features.
    """

    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self.vprojects_path = path_from_root("vprojects")
        log.debug("vprojects path: '%s'", self.vprojects_path)

        self.all_projects_info = self.__load_all_projects(self.vprojects_path)
        log.debug("Loaded %d projects.", len(self.all_projects_info))
        log.debug(
            "Loaded projects info:\n'%s'",
            json.dumps(self.all_projects_info, indent=2, ensure_ascii=False),
        )

        self.platform_operations = self.__load_platform_plugin_operations(
            self.vprojects_path
        )
        log.debug("Loaded %d platform operations.", len(self.platform_operations))

        self.builtin_operations = self.__load_builtin_plugin_operations(
            self.vprojects_path, self.all_projects_info
        )
        log.debug("Loaded %d builtin  operations.", len(self.builtin_operations))

    def __load_all_projects(self, vprojects_path):
        """
        Scan all board projects under vprojects, parse ini files, and save all project info.
        Build parent-child inheritance: child inherits all parent configs, child overrides same keys except PROJECT_PO_CONFIG, which is concatenated (parent first, then child).
        Board info is saved in each project's dict as key 'board_name'.
        """
        exclude_dirs = {"scripts", "common", "template", ".cache", ".git"}
        if not os.path.exists(vprojects_path):
            log.warning("vprojects directory does not exist: '%s'", vprojects_path)
            return {}
        all_projects = {}
        invalid_projects = set()
        for item in os.listdir(vprojects_path):
            item_path = os.path.join(vprojects_path, item)
            if not os.path.isdir(item_path) or item in exclude_dirs:
                continue
            # Find ini file in this board directory
            ini_file = None
            for f in os.listdir(item_path):
                if f.endswith(".ini"):
                    ini_file = os.path.join(item_path, f)
                    break
            if not ini_file:
                log.warning("No ini file found in board directory: '%s'", item_path)
                continue
            # First pass: check for duplicate keys in the whole ini file
            has_duplicate = False
            with open(ini_file, "r", encoding="utf-8") as f:
                current_project = None
                keys_in_project = set()
                for line in f:
                    line = line.strip()
                    if not line or line.startswith(";") or line.startswith("#"):
                        continue
                    if line.startswith("[") and line.endswith("]"):
                        current_project = line[1:-1].strip()
                        keys_in_project = set()
                        continue
                    if "=" in line and current_project:
                        key = line.split("=", 1)[0].strip()
                        if key in keys_in_project:
                            log.error(
                                "Duplicate key '%s' found in project '%s' of file '%s'",
                                key,
                                current_project,
                                ini_file,
                            )
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
                project_dict = {
                    k.upper(): v for k, v in project_dict.items()
                }  # 统一 key 大写
                project_dict["board_name"] = item  # Save board info in project dict
                all_projects[project] = project_dict

        # Build parent-child relationship and merge configs
        def find_parent(project):
            # The parent project name is the project name with the last '-' and following part removed
            if "-" in project:
                return project.rsplit("-", 1)[0]
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
                    merged[k] = v
            # Then add/override with child's own config
            for k, v in all_projects[project].items():
                if k == "PROJECT_PO_CONFIG" and k in merged:
                    # Concatenate parent and child, parent first, child after
                    merged[k] = merged[k].strip() + " " + v.strip()
                else:
                    merged[k] = v
            merged_projects[project] = merged
            return merged

        all_projects_info = {}
        for project in all_projects:
            if project in invalid_projects:
                continue
            merged_cfg = merge_config(project)
            all_projects_info[project] = merged_cfg
        return all_projects_info

    def __load_platform_plugin_operations(self, vprojects_path):
        """
        Load all platform-related script plugins under the scripts directory of each board in vprojects (excluding scripts, common, template, .cache).
        Collect all callable function names from each script into a list and return it.
        """
        exclude_dirs = {"scripts", "common", "template", ".cache"}
        platform_operations = set()
        if not os.path.exists(vprojects_path):
            log.warning("vprojects directory does not exist: '%s'", vprojects_path)
            return list(platform_operations)
        for item in os.listdir(vprojects_path):
            item_path = os.path.join(vprojects_path, item)
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
                    spec = importlib.util.spec_from_file_location(
                        module_name, script_path
                    )
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
                        "Failed to load script: '%s', error: '%s'", script_path, e
                    )
                    continue
        return list(platform_operations)

    def __load_builtin_plugin_operations(self, vprojects_path, all_projects_info):
        """
        Load builtin plugin operations by explicit import and registration.
        """
        builtin_operations = {}
        # Explicitly register all builtin plugin classes here
        builtin_plugin_classes = [PatchOverride]
        for plugin_cls in builtin_plugin_classes:
            try:
                instance = plugin_cls(vprojects_path, all_projects_info)
                for method in dir(instance):
                    if method.startswith("_"):
                        continue
                    m = getattr(instance, method)
                    if callable(m):
                        desc = getattr(m, "__doc__", None)
                        if desc:
                            desc = desc.strip().splitlines()[0]
                        else:
                            desc = "plugin operation"

                        # Get function signature information
                        sig = inspect.signature(m)
                        params = list(sig.parameters.keys())
                        # Remove 'self' parameter for instance methods
                        if params and params[0] == "self":
                            params = params[1:]

                        # Count required parameters (those without default values)
                        required_params = []
                        for param_name in params:
                            param = sig.parameters[param_name]
                            if param.default == inspect.Parameter.empty:
                                required_params.append(param_name)

                        builtin_operations[method] = {
                            "func": m,
                            "desc": desc,
                            "params": params,
                            "param_count": len(params),
                            "required_params": required_params,
                            "required_count": len(required_params),
                        }
            except (OSError, ImportError, AttributeError) as e:
                log.error(
                    "Failed to load builtin plugin '%s': '%s'", plugin_cls.__name__, e
                )
        return builtin_operations

    def new_project(self, project_name):
        """
        Create a new project.
        TODO: implement new_project
        """
        # TODO: implement new_project

    def del_project(self, project_name):
        """
        Delete the specified project directory and update its status in the config file.
        TODO: implement del_project
        """
        # TODO: implement del_project

    def build(self, project_name):
        """
        Build the specified project.
        TODO: implement build
        """
        # TODO: implement build

    def new_board(self, board_name):
        """
        Create a new board.
        TODO: implement new_board
        """
        # TODO: implement new_board

    def del_board(self, board_name):
        """
        Delete the specified board.
        TODO: implement del_board
        """
        # TODO: implement del_board


def parse_args_and_plugin_args(manager):
    # All imports should be at the top of the file
    # import argparse, inspect, re, sys

    def get_supported_flags(sig):
        return [
            name
            for name, param in sig.parameters.items()
            if name not in ("self", "project_name")
            and param.default is not inspect.Parameter.empty
        ]

    def get_flag_description(docstring, flag):
        if not docstring:
            return "(no description)"
        pattern = rf"{flag} \(([^)]+)\): ([^\n]+)"
        m = re.search(pattern, docstring)
        if m:
            return m.group(2).strip()
        return "(no description)"

    # Collect all plugin flags, their supported operations, and descriptions
    flag_info = {}
    for op, info in manager.builtin_operations.items():
        func = info["func"]
        sig = inspect.signature(func)
        doc = func.__doc__
        flags = get_supported_flags(sig)
        for flag in flags:
            if flag not in flag_info:
                flag_info[flag] = {"ops": [], "desc": None}
            flag_info[flag]["ops"].append(op)
            if not flag_info[flag]["desc"]:
                flag_info[flag]["desc"] = get_flag_description(doc, flag)

    # Build builtin operations help lines
    builtin_help_lines = []
    for op, info in manager.builtin_operations.items():
        func = info["func"]
        sig = inspect.signature(func)
        desc = info["desc"]
        flags = get_supported_flags(sig)
        if flags:
            flag_str = " ".join([f"--{f.replace('_','-')}" for f in flags])
            builtin_help_lines.append(f"  {op:<15} {desc} {flag_str}")
        else:
            builtin_help_lines.append(f"  {op:<15} {desc}")

    # Build plugin options section for epilog
    if flag_info:
        plugin_options_lines = []
        for flag, meta in sorted(flag_info.items()):
            flag_display = f"--{flag.replace('_','-')}"
            ops_display = f"Supported by: {', '.join(meta['ops'])}"
            desc = meta["desc"]
            flag_ops = f"  {flag_display:<10} {ops_display:<22}"
            plugin_options_lines.append(f"{flag_ops}{desc}")
        plugin_options = "\n".join(plugin_options_lines)
    else:
        plugin_options = ""

    help_text = (
        "supported operations:\n"
        "  build         build the specified project\n"
        "  new_project   create a new project\n"
        "  del_project   delete a project\n"
        "  new_board     create a new board\n"
        "  del_board     delete a board\n"
        "builtin operations:\n" + "\n".join(builtin_help_lines)
    )
    choices = ["build", "new_project", "del_project", "new_board", "del_board"] + list(
        manager.builtin_operations.keys()
    )
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=plugin_options if plugin_options else None,
    )
    parser.add_argument("--version", action="version", version=get_version())
    parser.add_argument(
        "operate",
        choices=choices,
        help=help_text,
    )
    parser.add_argument("name", help="project or board name")
    parser.add_argument(
        "args", nargs="*", help="additional arguments for plugin operations"
    )
    parser.add_argument(
        "--perf-analyze",
        action="store_true",
        help="Enable cProfile performance analysis",
    )

    # Only add plugin flags as argparse arguments when showing help
    if "--help" in sys.argv or "-h" in sys.argv:
        for flag, meta in sorted(flag_info.items()):
            flag_display = f"--{flag.replace('_','-')}"
            ops_display = f"Supported by: {', '.join(meta['ops'])}."
            desc = meta["desc"]
            parser.add_argument(
                flag_display,
                action="store_true",
                help=f"{ops_display} {desc}",
            )
        parser.epilog = None
    else:
        parser.epilog = plugin_options if plugin_options else None

    args, unknown = parser.parse_known_args()
    args_dict = vars(args)
    additional_args = args_dict.get("args", []) + unknown
    # Merge parse_plugin_args logic here
    parsed_args = []
    parsed_kwargs = {}
    i = 0
    while i < len(additional_args):
        arg = additional_args[i]
        if arg.startswith("--"):
            key = arg[2:].replace("-", "_")
            if i + 1 < len(additional_args) and not additional_args[i + 1].startswith(
                "--"
            ):
                value = additional_args[i + 1]
                parsed_kwargs[key] = value
                i += 2
            else:
                parsed_kwargs[key] = True
                i += 1
        else:
            parsed_args.append(arg)
            i += 1
    operate = args_dict["operate"]
    name = args_dict.get("name")
    return operate, name, parsed_args, parsed_kwargs, args_dict


def main():
    manager = ProjectManager()
    operate, name, parsed_args, parsed_kwargs, args_dict = parse_args_and_plugin_args(
        manager
    )
    builtins.ENABLE_CPROFILE = args_dict.get("perf_analyze", False)

    if operate == "build":
        manager.build(project_name=name)
    elif operate == "new_project":
        manager.new_project(project_name=name)
    elif operate == "del_project":
        manager.del_project(project_name=name)
    elif operate == "new_board":
        manager.new_board(board_name=name)
    elif operate == "del_board":
        manager.del_board(board_name=name)
    elif operate in manager.builtin_operations:
        op_info = manager.builtin_operations[operate]
        func = op_info["func"]
        params = op_info["params"]
        required_count = op_info["required_count"]
        if len(parsed_args) < max(0, required_count - 1):
            log.error(
                "Operation '%s' requires %d arguments, but only %d provided",
                operate,
                required_count - 1,
                len(parsed_args),
            )
            log.error("Required parameters: %s", ", ".join(params[1:required_count]))
            return
        func_args = [name] + parsed_args
        func_kwargs = parsed_kwargs
        try:
            func(*func_args, **func_kwargs)
        except TypeError as e:
            log.error("Failed to call operation '%s': %s", operate, e)
    else:
        log.error("Operation '%s' is not supported.", operate)


if __name__ == "__main__":
    main()
