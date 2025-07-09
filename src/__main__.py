"""
Main entry point for running the src package as a module.
"""

import importlib.util
import inspect
import argparse
import builtins
import os
import re
import sys
import configparser
import json
from src.utils import get_version
from src.log_manager import log
from src.plugins.project_manager import ProjectManager
from src.plugins.patch_override import PatchOverride


# ===== 迁移的工具函数 =====
def _load_all_projects(vprojects_path):
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
        ini_file = None
        for f in os.listdir(item_path):
            if f.endswith(".ini"):
                ini_file = os.path.join(item_path, f)
                break
        if not ini_file:
            log.warning("No ini file found in board directory: '%s'", item_path)
            continue
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
        config = configparser.ConfigParser()
        config.optionxform = str
        config.read(ini_file, encoding="utf-8")
        for project in config.sections():
            project_dict = dict(config.items(project))
            project_dict = {k.upper(): v for k, v in project_dict.items()}
            project_dict["board_name"] = item
            all_projects[project] = project_dict

    def find_parent(project):
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
            for k, v in parent_cfg.items():
                merged[k] = v
        for k, v in all_projects[project].items():
            if k == "PROJECT_PO_CONFIG" and k in merged:
                merged[k] = merged[k].strip() + " " + v.strip()
            else:
                merged[k] = v
        merged_projects[project] = merged
        return merged

    projects_info = {}
    for project in all_projects:
        if project in invalid_projects:
            continue
        merged_cfg = merge_config(project)
        projects_info[project] = merged_cfg
    return projects_info


def _load_plugin_operations(plugin_classes):
    """
    通用插件加载函数，仅支持类插件（只收集静态方法和类方法）。
    plugin_classes: list of plugin classes
    返回: dict，key为操作名，value为操作描述和方法等
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
            required_params = [
                pname
                for pname in params
                if sig.parameters[pname].default == inspect.Parameter.empty
            ]
            operations[method_name] = {
                "func": func,
                "desc": desc,
                "params": params,
                "param_count": len(params),
                "required_params": required_params,
                "required_count": len(required_params),
            }
    return operations


def _load_builtin_plugin_operations():
    plugin_classes = [ProjectManager, PatchOverride]
    return _load_plugin_operations(plugin_classes)


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
            class_name = os.path.splitext(file_name)[0].capitalize()
            if hasattr(mod, class_name):
                cls = getattr(mod, class_name)
                if inspect.isclass(cls):
                    plugin_classes.append(cls)
        except (ImportError, AttributeError) as e:
            log.error("Failed to load platform plugin from %s: %s", script_path, e)
    return _load_plugin_operations(plugin_classes)


def _parse_args_and_plugin_args(builtin_operations):
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

    builtin_help_lines = []
    for op, info in builtin_operations.items():
        func = info["func"]
        sig = inspect.signature(func)
        desc = info["desc"]
        flags = get_supported_flags(sig)
        if flags:
            flag_str = " ".join([f"--{f.replace('_','-')}" for f in flags])
            builtin_help_lines.append(f"  {op:<15} {desc} {flag_str}")
        else:
            builtin_help_lines.append(f"  {op:<15} {desc}")

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

    # 只通过插件注册的 operation 生成 help/choices
    help_text = "supported operations :\n" + "\n".join(builtin_help_lines)
    choices = list(builtin_operations.keys())
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=plugin_options if plugin_options else None,
    )
    parser.add_argument("--version", action="version", version=get_version())
    parser.add_argument(
        "operate", choices=choices, help=help_text, metavar="operations"
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
    """Main entry point for the CLI project manager."""
    log.debug("sys.argv: %s", sys.argv)

    root_path = os.path.dirname(os.path.dirname(__file__))
    env = {
        "root_path": root_path,
        "vprojects_path": os.path.join(root_path, "vprojects"),
    }
    log.debug("env: %s", env)

    projects_info = _load_all_projects(env["vprojects_path"])
    log.debug("Loaded %d projects.", len(projects_info))
    log.debug(
        "Loaded projects info:\n'%s'",
        json.dumps(projects_info, indent=4, ensure_ascii=False),
    )
    platform_operations = _load_platform_plugin_operations(env["vprojects_path"])
    log.debug("Loaded %d platform operations.", len(platform_operations))
    builtin_operations = _load_builtin_plugin_operations()
    log.debug("Loaded %d builtin operations.", len(builtin_operations))

    # 合并所有操作
    all_operations = {**builtin_operations, **platform_operations}

    operate, name, parsed_args, parsed_kwargs, args_dict = _parse_args_and_plugin_args(
        all_operations
    )
    builtins.ENABLE_CPROFILE = args_dict.get("perf_analyze", False)

    # 只通过插件注册的 operation 执行
    if operate in all_operations:
        op_info = all_operations[operate]
        func = op_info["func"]
        params = op_info["params"]
        sig = inspect.signature(func)
        # 只统计 CLI 用户需要输入的参数（去掉 env, projects_info）
        cli_params = [p for p in params if p not in ("env", "projects_info")]
        required_cli_params = [
            p
            for p in cli_params
            if sig.parameters[p].default == inspect.Parameter.empty
        ]
        # name + parsed_args 是用户实际输入的参数
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
