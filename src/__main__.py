"""
Main entry point for running the src package as a module.
"""

import argparse
import builtins
import importlib.util
import inspect
import json
import os
import pathlib
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from importlib import import_module

import configupdater

from src.log_manager import log
from src.operations.registry import get_registered_operations
from src.profiler import func_cprofile, func_time
from src.utils import get_version

# Ensure function-based operations are registered by importing modules that use @register
import_module("src.plugins.project_manager")
import_module("src.plugins.project_builder")
import_module("src.plugins.patch_override")


# ===== Migration utility functions =====
@func_time
@func_cprofile
def _load_all_projects(vprojects_path):
    exclude_dirs = {"scripts", "common", "template", ".cache", ".git"}
    if not os.path.exists(vprojects_path):
        log.warning("vprojects directory does not exist: '%s'", vprojects_path)
        return {}
    projects_info = {}
    raw_configs = {}
    invalid_projects = set()

    # Load common config first
    common_config_path = os.path.join(vprojects_path, "common", "common.ini")
    common_configs = {}

    def strip_comment(val):
        # Remove inline comments after # or ;
        return val.split("#", 1)[0].split(";", 1)[0].strip()

    if os.path.exists(common_config_path):
        common_updater = configupdater.ConfigUpdater()
        common_updater.read(common_config_path, encoding="utf-8")
        # Only load [common] section
        if common_updater.has_section("common"):
            section = common_updater["common"]
            section_dict = {k.upper(): strip_comment(section[k].value) for k in section}
            common_configs["common"] = section_dict
        else:
            log.warning("[common] section not found in: '%s'", common_config_path)
    else:
        log.warning("common config not found: '%s'", common_config_path)

    for item in os.listdir(vprojects_path):
        board_name = item
        board_path = os.path.join(vprojects_path, board_name)
        if not os.path.isdir(board_path) or board_name in exclude_dirs:
            continue
        ini_files = [f for f in os.listdir(board_path) if f.endswith(".ini")]
        if not ini_files:
            log.warning("No ini file found in board directory: '%s'", board_path)
            continue
        assert len(ini_files) == 1, f"Multiple ini files found in {board_path}: {ini_files}"
        ini_file = os.path.join(board_path, ini_files[0])
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
            continue
        config = configupdater.ConfigUpdater()
        config.read(ini_file, encoding="utf-8")
        for project_name in config.sections():
            config_dict = {k.upper(): strip_comment(v.value) for k, v in config[project_name].items()}
            raw_configs[project_name] = config_dict
            projects_info[project_name] = {
                "config": None,  # placeholder, will be merged later
                "board_name": board_name,
                "board_path": board_path,
                "ini_file": ini_file,
                "parent": None,  # parent project name
                "children": [],  # list of children project names
            }

    # Build parent-child relationships
    def find_parent(project_name):
        if "-" in project_name:
            return project_name.rsplit("-", 1)[0]
        return None

    # First, assign parent for each project
    for project_name, project_info in projects_info.items():
        parent_name = find_parent(project_name)
        project_info["parent"] = parent_name

    # Then, assign children for each project
    for project_name, project_info in projects_info.items():
        parent_name = project_info["parent"]
        if parent_name and parent_name in projects_info:
            parent_project_info = projects_info[parent_name]
            parent_project_info["children"].append(project_name)

    merged_configs = {}

    def merge_config(project):
        if project in merged_configs:
            return merged_configs[project]
        if project in invalid_projects:
            return {}
        parent = find_parent(project)
        merged = {}
        # Merge common configuration first
        for section_dict in common_configs.values():
            for k, v in section_dict.items():
                merged[k] = v
        # Then merge parent project configuration
        if parent and parent in raw_configs:
            parent_cfg = merge_config(parent)
            for k, v in parent_cfg.items():
                merged[k] = v
        # Finally merge current project configuration
        for k, v in raw_configs[project].items():
            if k == "PROJECT_PO_CONFIG" and k in merged:
                merged[k] = merged[k].strip() + " " + v.strip()
            else:
                merged[k] = v
        merged_configs[project] = merged
        return merged

    for project, project_info in projects_info.items():
        if project in invalid_projects:
            continue
        project_info["config"] = merge_config(project)
    return projects_info


@func_time
@func_cprofile
def _load_plugin_operations(plugin_classes):
    """
    Generic plugin loading function, only supports class plugins (only collects static methods and class methods).
    plugin_classes: list of plugin classes
    Returns: dict, key is operation name, value is operation description and method etc.
    """
    operations = {}
    for plugin_cls in plugin_classes:
        for method_name, raw_attr in plugin_cls.__dict__.items():
            if method_name.startswith("_"):
                continue
            if isinstance(raw_attr, staticmethod):
                func = raw_attr.__func__
            elif isinstance(raw_attr, classmethod):
                func = raw_attr.__func__
            else:
                continue
            desc = getattr(func, "__doc__", None)
            if desc:
                desc = desc.strip().splitlines()[0]
            else:
                desc = "plugin operation"
            sig = inspect.signature(func)
            params = list(sig.parameters.keys())
            required_params = [pname for pname in params if sig.parameters[pname].default == inspect.Parameter.empty]
            # Check if @needs_repositories is in docstring
            docstring = getattr(func, "__doc__", "")
            needs_repositories = "@needs_repositories" in docstring if docstring else False
            # Attach plugin class to function for metadata access
            setattr(func, "_plugin_class", plugin_cls)
            operations[method_name] = {
                "func": func,
                "desc": desc,
                "params": params,
                "param_count": len(params),
                "required_params": required_params,
                "required_count": len(required_params),
                "needs_repositories": needs_repositories,
                "plugin_class": plugin_cls,  # Store the original plugin class for metadata access
            }
    return operations


@func_time
def _load_builtin_plugin_operations():
    # Merge with function-registered operations (function-first precedence)
    func_ops_min = get_registered_operations()
    func_ops = {}
    for name, info in func_ops_min.items():
        func = info["func"]
        desc = getattr(func, "_operation_meta", {}).get("desc") or (
            func.__doc__.strip().splitlines()[0] if func.__doc__ else "plugin operation"
        )
        sig = inspect.signature(func)
        params = list(sig.parameters.keys())
        required_params = [pname for pname in params if sig.parameters[pname].default == inspect.Parameter.empty]
        func_ops[name] = {
            "func": func,
            "desc": desc,
            "params": params,
            "param_count": len(params),
            "required_params": required_params,
            "required_count": len(required_params),
            "needs_repositories": bool(getattr(func, "_operation_meta", {}).get("needs_repositories", False)),
            "plugin_class": None,
        }
    # function ops override class ops if name clashes
    return {**func_ops}


@func_time
@func_cprofile
def _load_platform_plugin_operations(vprojects_path):
    scripts_dir = os.path.join(vprojects_path, "scripts")
    plugin_classes = []
    if not os.path.exists(scripts_dir):
        return {}
    for file_name in os.listdir(scripts_dir):
        if not file_name.endswith(".py") or file_name.startswith("_"):
            continue
        script_path = os.path.join(scripts_dir, file_name)
        module_name = f"scripts_{os.path.splitext(file_name)[0]}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, script_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            # Load all classes that do not start with an underscore
            for attr_name in dir(mod):
                if attr_name.startswith("_"):
                    continue
                attr = getattr(mod, attr_name)
                if inspect.isclass(attr) and attr.__module__ == mod.__name__:
                    plugin_classes.append(attr)
        except (ImportError, AttributeError) as e:
            log.error("Failed to load platform plugin from %s: %s", script_path, e)
    return _load_plugin_operations(plugin_classes)


@func_time
def _parse_args_and_plugin_args(builtin_operations):
    def get_supported_flags(sig):
        return [
            name
            for name, param in sig.parameters.items()
            if name not in ("self", "project_name") and param.default is not inspect.Parameter.empty
        ]

    def get_flag_description(docstring, flag):
        if not docstring:
            return "(no description)"
        pattern = rf"{flag} \(([^)]+)\): ([^\n]+)"
        m = re.search(pattern, docstring)
        if m:
            return m.group(2).strip()
        return "(no description)"

    flag_info = {}
    for op, info in builtin_operations.items():
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

    # Calculate the maximum length of operation names
    op_max_len = max((len(op) for op in builtin_operations.keys()), default=0) + 2  # extra space

    builtin_help_lines = []
    for op, info in builtin_operations.items():
        func = info["func"]
        sig = inspect.signature(func)
        desc = info["desc"]
        flags = get_supported_flags(sig)
        if flags:
            flag_str = " ".join([f"--{f.replace('_','-')}" for f in flags])
            builtin_help_lines.append(f"  {op:<{op_max_len}}{desc} {flag_str}")
        else:
            builtin_help_lines.append(f"  {op:<{op_max_len}}{desc}")

    if flag_info:
        plugin_options_lines = []
        # Calculate the maximum length of all flag_display and ops_display
        flag_max_len = (
            max(
                (len(f"--{flag.replace('_','-')}") for flag in flag_info),
                default=0,
            )
            + 4
        )
        ops_max_len = (
            max(
                (len(f"Supported by: {', '.join(meta['ops'])}") for meta in flag_info.values()),
                default=0,
            )
            + 4
        )
        for flag, meta in sorted(flag_info.items()):
            flag_display = f"--{flag.replace('_','-')}"
            ops_display = f"Supported by: {', '.join(meta['ops'])}"
            desc = meta["desc"]
            plugin_options_lines.append(f"  {flag_display:<{flag_max_len}}{ops_display:<{ops_max_len}}{desc}")
        plugin_options = "\n".join(plugin_options_lines)
    else:
        plugin_options = ""

    # Only generate help/choices through plugin-registered operations
    help_text = "supported operations :\n" + "\n".join(builtin_help_lines)
    choices = list(builtin_operations)
    # Do not add plugin-related parameters to parser, only describe in epilog or help_text
    parser = argparse.ArgumentParser(
        usage="__main__.py [options] operations name [args ...]",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=plugin_options if plugin_options else None,
        add_help=True,
    )
    parser.add_argument("--version", action="version", version=get_version())
    parser.add_argument("operate", choices=choices, help=help_text, metavar="operations")
    parser.add_argument("name", help="project or board name")
    parser.add_argument("args", nargs="*", help="additional arguments for plugin operations")
    parser.add_argument(
        "--perf-analyze",
        action="store_true",
        help="Enable cProfile performance analysis",
    )

    # Do not add plugin-related parameters to parser, only describe in epilog or help_text
    parser.epilog = plugin_options if plugin_options else None

    args, unknown = parser.parse_known_args()
    args_dict = vars(args)
    additional_args = args_dict.get("args", []) + unknown
    parsed_args = []
    parsed_kwargs = {}
    i = 0
    while i < len(additional_args):
        arg = additional_args[i]
        if arg.startswith("--"):
            key = arg[2:].replace("-", "_")
            if i + 1 < len(additional_args) and not additional_args[i + 1].startswith("--"):
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


@func_time
@func_cprofile
def _find_repositories():
    """
    Return a list of (repo_path, repo_name) for all git repositories in current dir or .repo manifest.
    repo_name: relative path, root repo is 'root'.
    """
    current_dir = os.getcwd()
    manifest = os.path.join(current_dir, ".repo", "manifest.xml")
    repositories = []
    if os.path.exists(manifest):
        # manifest mode
        try:
            tree = ET.parse(manifest)
            root = tree.getroot()
            for project in root.findall(".//project"):
                path = project.get("path")
                if path:
                    repo_path = os.path.join(current_dir, path)
                    if os.path.exists(os.path.join(repo_path, ".git")):
                        repo_name = path if path != "." else "root"
                        repositories.append((repo_path, repo_name))
        except ET.ParseError as e:
            log.error("Failed to parse .repo manifest: %s", e)
    elif os.path.exists(os.path.join(current_dir, ".git")):
        # single repo mode
        repositories.append((current_dir, "root"))
    # Print repositories for debug
    log.debug("repositories found: %s", json.dumps(repositories, indent=2, ensure_ascii=False))
    return repositories


@func_time
def check_and_create_vprojects(vprojects_path):
    """Check if vprojects directory exists, prompt user and create if needed."""
    if not os.path.exists(vprojects_path):
        answer = input("vprojects directory does not exist, create standard structure? [y/N]: ").strip().lower()
        if answer in ("y", "yes"):

            def touch(path):
                pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
                pathlib.Path(path).touch(exist_ok=True)

            structure = {
                "common/common.ini": None,
                "common/po/.gitkeep": None,
                "template/template.ini": None,
                "template/po/po_template/overrides/.gitkeep": None,
                "template/po/po_template/patches/.gitkeep": None,
                "scripts/.gitkeep": None,
            }
            for rel_path in structure:
                abs_path = os.path.join(vprojects_path, rel_path)
                if abs_path.endswith(".ini"):
                    touch(abs_path)
                else:
                    # .gitkeep placeholder
                    pathlib.Path(abs_path).parent.mkdir(parents=True, exist_ok=True)
                    with open(abs_path, "w", encoding="utf-8") as f:
                        f.write("")
            print(f"vprojects directory and basic structure created at: {vprojects_path}")
            # Initialize git repository in vprojects

            try:
                subprocess.run(["git", "init"], cwd=vprojects_path, check=True)
                subprocess.run(["git", "add", "-A"], cwd=vprojects_path, check=True)
                subprocess.run(
                    ["git", "commit", "-m", "Initial vprojects structure"],
                    cwd=vprojects_path,
                    check=True,
                )
                print("Initialized empty Git repository in vprojects directory and committed initial structure.")
                # TODO: Install git hooks here for file checking in the future
            except subprocess.CalledProcessError as e:
                print(f"Failed to initialize git repository: {e}. Output: {e.output if hasattr(e, 'output') else ''}")
        else:
            print("vprojects directory not created, exiting.")
            sys.exit(0)


@func_time
def get_operation_meta_flag(func, operate, key):
    """
    Retrieve a boolean flag from operation metadata for a given function, operation name, and config key.
    Checks class and parent classes' OPERATION_META only.
    """
    # Try to get the plugin class from the function's metadata first
    # Prefer function-based metadata first
    meta = getattr(func, "_operation_meta", None)
    if meta is not None and key in meta:
        return bool(meta[key])
    log.error("Failed to get operation meta flag for '%s' with key '%s'", operate, key)
    return False


@func_time
@func_cprofile
def main():
    """Main entry point for the CLI project manager."""
    log.debug("sys.argv: %s", sys.argv)

    # Define root_path as current working directory
    root_path = os.getcwd()
    # Use vprojects path from current working directory
    vprojects_path = os.path.join(root_path, "vprojects")

    check_and_create_vprojects(vprojects_path)

    env = {
        "root_path": root_path,
        "vprojects_path": vprojects_path,
        # "repositories": _find_repositories(),  # lazy loading
    }
    log.debug("env: \n%s", json.dumps(env, indent=4, ensure_ascii=False))

    projects_info = _load_all_projects(env["vprojects_path"])
    log.debug("Loaded %d projects.", len(projects_info))
    log.debug(
        "Loaded projects info:\n%s",
        json.dumps(projects_info, indent=4, ensure_ascii=False),
    )
    platform_operations = _load_platform_plugin_operations(env["vprojects_path"])
    log.debug("Loaded %d platform operations.", len(platform_operations))
    log.debug("Platform operations: %s", list(platform_operations.keys()))
    builtin_operations = _load_builtin_plugin_operations()
    log.debug("Loaded %d builtin operations.", len(builtin_operations))
    log.debug("Builtin operations: %s", list(builtin_operations.keys()))

    # Merge all operations
    all_operations = {**builtin_operations, **platform_operations}

    operate, name, parsed_args, parsed_kwargs, args_dict = _parse_args_and_plugin_args(all_operations)
    builtins.ENABLE_CPROFILE = args_dict.get("perf_analyze", False)

    # Only execute operations registered through plugins
    if operate in all_operations:
        op_info = all_operations[operate]
        func = op_info["func"]
        params = op_info["params"]
        sig = inspect.signature(func)
        # Only count CLI parameters that users need to input (remove env, projects_info)
        cli_params = [p for p in params if p not in ("env", "projects_info")]
        required_cli_params = [p for p in cli_params if sig.parameters[p].default == inspect.Parameter.empty]
        # name + parsed_args are the actual parameters input by the user
        user_args = [name] + parsed_args
        if len(user_args) < len(required_cli_params):
            log.error(
                "Operation '%s' requires %d arguments, but only %d provided",
                operate,
                len(required_cli_params),
                len(user_args),
            )
            log.error("Required parameters: %s", ", ".join(required_cli_params))
            sys.exit(1)
        if get_operation_meta_flag(func, operate, "needs_repositories"):
            log.info("Operation '%s' requires repositories, loading repositories...", operate)
            env["repositories"] = _find_repositories()
        func_args = [env, projects_info] + user_args
        func_kwargs = parsed_kwargs
        try:
            func(*func_args, **func_kwargs)
        except TypeError as e:
            log.error("Failed to call operation '%s': %s", operate, e)
    else:
        log.error("Operation '%s' is not supported.", operate)


if __name__ == "__main__":
    main()
