"""
Main entry point for running the src package as a module.
"""

import argparse
import builtins
import importlib.util
import inspect
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from difflib import SequenceMatcher
from importlib import import_module
from typing import Any, List, Optional, Tuple

import configupdater

import src.plugins.upgrader  # pylint: disable=unused-import
from src.log_manager import log
from src.operations.registry import get_registered_operations
from src.profiler import func_cprofile, func_time
from src.utils import get_version

# Ensure function-based operations are registered by importing modules that use @register
import_module("src.plugins.project_manager")
import_module("src.plugins.project_builder")
import_module("src.plugins.patch_override")
import_module("src.plugins.doctor")


# ===== Migration utility functions =====
def _strip_comment(val):
    """Remove inline comments after `#` or `;`.

    Notes:
    - Preserve literal `#` / `;` characters inside single/double quotes.
    - Treat `#` / `;` as a comment delimiter only when it appears at the start
      of the value or is preceded by whitespace.
    """

    text = "" if val is None else str(val)
    in_single = False
    in_double = False
    for idx, ch in enumerate(text):
        if ch == "'" and not in_double:
            in_single = not in_single
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            continue
        if in_single or in_double:
            continue
        if ch not in {"#", ";"}:
            continue
        if idx == 0 or text[idx - 1].isspace():
            return text[:idx].strip()
    return text.strip()


@func_time
@func_cprofile
def _load_common_config(projects_path):
    """
    Load common.ini configuration file.

    Args:
        projects_path (str): Path to projects directory

    Returns:
        tuple: (common_configs, po_configs)
            - common_configs: dict containing [common] section config
            - po_configs: dict containing all po-* sections config
    """
    common_config_path = os.path.join(projects_path, "common", "common.ini")
    common_configs = {}
    po_configs = {}

    if os.path.exists(common_config_path):
        common_updater = configupdater.ConfigUpdater()
        common_updater.read(common_config_path, encoding="utf-8")

        # Load all sections from common.ini
        for section_name in common_updater.sections():
            section = common_updater[section_name]
            section_dict = {k.upper(): _strip_comment(section[k].value) for k in section}

            if section_name == "common":
                common_configs[section_name] = section_dict
            elif section_name.startswith("po-"):
                po_configs[section_name] = section_dict
            else:
                # Other sections are also stored in common_configs for backward compatibility
                common_configs[section_name] = section_dict

        if "common" not in common_configs:
            log.warning("[common] section not found in: '%s'", common_config_path)
    else:
        log.warning("common config not found: '%s'", common_config_path)

    return common_configs, po_configs


@func_time
@func_cprofile
def _load_all_projects(projects_path, common_configs):
    exclude_dirs = {"scripts", "common", "template", ".cache", ".git"}
    if not os.path.exists(projects_path):
        log.warning("projects directory does not exist: '%s'", projects_path)
        return {}
    projects_info = {}
    raw_configs = {}
    invalid_projects = set()

    # Use the passed common_configs parameter

    for item in os.listdir(projects_path):
        board_name = item
        board_path = os.path.join(projects_path, board_name)
        if not os.path.isdir(board_path) or board_name in exclude_dirs:
            continue
        ini_files = [f for f in os.listdir(board_path) if f.endswith(".ini")]
        if not ini_files:
            log.warning("No ini file found in board directory: '%s'", board_path)
            continue
        if len(ini_files) > 1:
            ini_files = sorted(ini_files)
            msg = f"Multiple ini files found in {board_path}: {ini_files}"
            log.error(msg)
            raise ValueError(msg)
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
            config_dict = {k.upper(): _strip_comment(v.value) for k, v in config[project_name].items()}
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
        # Merge common configuration first (only [common] section)
        if "common" in common_configs:
            for k, v in common_configs["common"].items():
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

    # Write project information to board directories
    def __write_projects_info_to_boards(projects_info, projects_path):
        """
        Write project information to board directories.

        Args:
            projects_info (dict): Dictionary containing project information
            projects_path (str): Path to projects directory
        """
        try:
            root_path = os.path.abspath(os.path.join(projects_path, os.pardir))

            def _to_relpath(path_value: Optional[str]) -> Optional[str]:
                if not path_value:
                    return path_value
                try:
                    rel = os.path.relpath(path_value, root_path)
                except ValueError:
                    rel = os.path.basename(path_value)
                # Fail closed: never persist absolute paths in caches.
                if os.path.isabs(rel):
                    rel = os.path.basename(rel)
                return rel

            # Group projects by board_name
            board_projects = {}
            for project_name, project_info in projects_info.items():
                board_name = project_info.get("board_name")
                if not board_name:
                    continue
                if board_name not in board_projects:
                    board_projects[board_name] = []
                board_projects[board_name].append(
                    {
                        "project_name": project_name,
                        "config": project_info.get("config", {}),
                        "parent": project_info.get("parent"),
                        "children": project_info.get("children", []),
                        "ini_file": project_info.get("ini_file"),
                    }
                )

            # Write project information to each board directory
            for board_name, projects in board_projects.items():
                board_path = os.path.join(projects_path, board_name)
                if not os.path.exists(board_path):
                    log.warning("Board directory does not exist: %s", board_path)
                    continue

                # Prepare project data for JSON output (store relative paths only).
                board_projects_out = []
                for project in projects:
                    item = dict(project)
                    item["ini_file"] = _to_relpath(item.get("ini_file"))
                    board_projects_out.append(item)

                project_data = {
                    "board_name": board_name,
                    "board_path": _to_relpath(board_path),
                    "last_updated": datetime.now().isoformat(),
                    "projects": board_projects_out,
                }

                # Write to projects.json in board directory
                projects_json_path = os.path.join(board_path, "projects.json")
                with open(projects_json_path, "w", encoding="utf-8") as f:
                    json.dump(project_data, f, indent=2, ensure_ascii=False)

                log.debug("Project information written to: %s", projects_json_path)

        except (OSError, IOError, ValueError) as e:
            log.error("Failed to write project information to board directories: %s", e)

    __write_projects_info_to_boards(projects_info, projects_path)

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
def _import_platform_scripts(projects_path):
    scripts_dir = os.path.join(projects_path, "scripts")
    if not os.path.exists(scripts_dir):
        log.debug("Scripts directory not found: %s", scripts_dir)
        return

    # Import all script modules
    imported_count = 0
    for file_name in os.listdir(scripts_dir):
        if not file_name.endswith(".py") or file_name.startswith("_"):
            continue
        script_path = os.path.join(scripts_dir, file_name)
        module_name = f"scripts_{os.path.splitext(file_name)[0]}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, script_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            # Module is imported successfully
            imported_count += 1
        except (ImportError, AttributeError) as e:
            log.error("Failed to import platform script from %s: %s", script_path, e)

    log.debug("Imported %d platform scripts from %s", imported_count, scripts_dir)


def _env_truthy(value: str) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _arg_truthy(value: Any) -> bool:
    if value is True:
        return True
    if value in (False, None):
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _should_load_platform_scripts(argv: List[str]) -> bool:
    """
    Decide whether to import projects/scripts/*.py.

    Safety:
    - Never auto-import by default.
    - Never import for early-exit flags like --help / --version.
    - In --safe-mode, ignore env-based opt-in (PROJMAN_LOAD_SCRIPTS) and only allow explicit CLI opt-in.
    """

    if "-h" in argv or "--help" in argv or "--version" in argv:
        return False
    safe_mode = "--safe-mode" in argv or _env_truthy(os.environ.get("PROJMAN_SAFE_MODE", ""))
    if safe_mode:
        if _env_truthy(os.environ.get("PROJMAN_LOAD_SCRIPTS", "")) and "--load-scripts" not in argv:
            log.warning("Safe mode enabled; ignoring PROJMAN_LOAD_SCRIPTS (use --load-scripts explicitly).")
        return "--load-scripts" in argv
    if "--load-scripts" in argv:
        return True
    return _env_truthy(os.environ.get("PROJMAN_LOAD_SCRIPTS", ""))


@func_time
def _parse_args_and_plugin_args(builtin_operations):
    def _extract_plugin_tokens(argv: List[str], parsed_name: Optional[str]) -> List[str]:
        """
        Extract plugin tokens in original argv order.

        Rationale:
        - `argparse.parse_known_args()` may split unknown option values into the
          positional `args` bucket, which breaks our later `args + unknown`
          reconstruction (order is lost).
        - Plugin flags/args are defined as "everything after <operate> [name]".
        """

        # Skip global options before <operate>. Today we only have boolean flags
        # (`--perf-analyze`) plus early-exit flags (`--help/--version`).
        operate_idx = None
        for idx, token in enumerate(argv):
            if token in {"-h", "--help", "--version", "--perf-analyze"}:
                continue
            if token.startswith("-"):
                # Unknown option before <operate>; treat as global and ignore.
                continue
            if operate_idx is None:
                operate_idx = idx
                continue

        if operate_idx is None:
            return []

        start_idx = operate_idx + 1
        if parsed_name is not None:
            for idx in range(start_idx, len(argv)):
                token = argv[idx]
                if token.startswith("-"):
                    continue
                start_idx = idx + 1
                break

        return argv[start_idx:]

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

    argv = sys.argv[1:]

    # Only generate help/choices through plugin-registered operations
    help_text = "supported operations :\n" + "\n".join(builtin_help_lines)
    choices = list(builtin_operations)
    # Do not add plugin-related parameters to parser, only describe in epilog or help_text
    parser = FuzzyOperationParser(
        available_operations=choices,
        enable_fuzzy="--no-fuzzy" not in argv,
        usage="__main__.py [options] operations [name] [args ...]",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=plugin_options if plugin_options else None,
        add_help=True,
    )
    parser.add_argument("--version", action="version", version=get_version())
    parser.add_argument("operate", help=help_text, metavar="operations")
    parser.add_argument("name", nargs="?", help="project or board name (if operation requires)")
    parser.add_argument("args", nargs="*", help="additional arguments for plugin operations")
    parser.add_argument(
        "--perf-analyze",
        action="store_true",
        help="Enable cProfile performance analysis",
    )
    parser.add_argument(
        "--load-scripts",
        action="store_true",
        help="Opt-in: import workspace scripts under projects/scripts/*.py (unsafe in untrusted workspaces).",
    )
    parser.add_argument(
        "--no-fuzzy",
        action="store_true",
        help="Require exact operation match (disable fuzzy matching and fail on ambiguity).",
    )
    parser.add_argument(
        "--safe-mode",
        action="store_true",
        help="Enable safe mode for untrusted workspaces (blocks env-based script loading; requires confirmation for destructive ops; blocks network upgrade unless allowed).",
    )
    parser.add_argument(
        "--allow-network",
        action="store_true",
        help="Safe mode: allow network operations such as 'upgrade'.",
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Safe mode: explicitly confirm running destructive operations (non-interactive).",
    )

    # Do not add plugin-related parameters to parser, only describe in epilog or help_text
    parser.epilog = plugin_options if plugin_options else None

    args, _unknown = parser.parse_known_args(argv)
    args_dict = vars(args)
    # Preserve original order; do NOT concatenate `args` + `unknown`.
    additional_args = _extract_plugin_tokens(argv, args_dict.get("name"))
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
    Also writes repository information to projects/repositories.json file.
    """
    current_dir = os.getcwd()
    manifest = os.path.join(current_dir, ".repo", "manifest.xml")
    log.debug("manifest: %s", manifest)
    repositories = []
    repo_type = None

    def add_repo_if_exists(path_attr):
        if not path_attr:
            return
        repo_path = os.path.join(current_dir, path_attr)
        if os.path.exists(os.path.join(repo_path, ".git")):
            repo_name = path_attr if path_attr != "." else "root"
            repositories.append((repo_path, repo_name))

    def parse_manifest_file(manifest_file, include_base_dir=None, visited=None):
        if visited is None:
            visited = set()
        try:
            real_path = os.path.realpath(manifest_file)
            if real_path in visited:
                return
            visited.add(real_path)
            tree = ET.parse(manifest_file)
            root = tree.getroot()
            for project in root.findall(".//project"):
                add_repo_if_exists(project.get("path"))
            for inc in root.findall(".//include"):
                name = inc.get("name")
                if not name:
                    continue
                candidates = []
                if include_base_dir:
                    candidates.append(os.path.join(include_base_dir, name))
                candidates.append(os.path.join(os.path.dirname(manifest_file), name))
                include_path = next((c for c in candidates if os.path.exists(c)), None)
                if include_path is None:
                    log.warning("Include file not found: %s (searched: %s)", name, ", ".join(candidates))
                    continue
                parse_manifest_file(include_path, include_base_dir=os.path.dirname(include_path), visited=visited)
        except ET.ParseError as e:
            log.error("Failed to parse manifest '%s': %s", manifest_file, e)
        except FileNotFoundError:
            log.error("Manifest file not found: %s", manifest_file)

    if os.path.exists(manifest):
        include_base = os.path.join(current_dir, ".repo", "manifests")
        parse_manifest_file(manifest, include_base_dir=include_base, visited=set())
        repo_type = "manifest"
    elif os.path.exists(os.path.join(current_dir, ".git")):
        repositories.append((current_dir, "root"))
        repo_type = "single"

    log.debug("repositories found: %s", json.dumps(repositories, indent=2, ensure_ascii=False))

    # Write repository information to projects/repositories.json
    _write_repositories_to_file(repositories, repo_type, current_dir)

    return repositories


def _write_repositories_to_file(repositories, repo_type, current_dir):
    """
    Write repository information to projects/repositories.json file.

    Args:
        repositories: List of (repo_path, repo_name) tuples
        repo_type: Type of repository discovery ("manifest" or "single")
        current_dir: Current working directory
    """
    try:
        # Create projects directory if it doesn't exist
        projects_dir = os.path.join(current_dir, "projects")
        os.makedirs(projects_dir, exist_ok=True)

        # Prepare repository data
        repo_data = {
            "discovery_time": datetime.now().isoformat(),
            "discovery_type": repo_type,
            # Store relative paths only (safe to share).
            "current_directory": ".",
            "repositories": [],
        }

        for repo_path, repo_name in repositories:
            rel_path = os.path.relpath(repo_path, current_dir) if repo_path != current_dir else "."
            if os.path.isabs(rel_path):
                rel_path = os.path.basename(rel_path)
            repo_info = {
                "name": repo_name,
                "path": rel_path,
                "relative_path": rel_path,
                "is_git_repo": os.path.exists(os.path.join(repo_path, ".git")),
            }
            repo_data["repositories"].append(repo_info)

        # Write to repositories.json file
        repos_file = os.path.join(projects_dir, "repositories.json")
        with open(repos_file, "w", encoding="utf-8") as f:
            json.dump(repo_data, f, indent=2, ensure_ascii=False)

        log.debug("Repository information written to: %s", repos_file)

    except (OSError, IOError, ValueError) as e:
        log.error("Failed to write repository information to file: %s", e)


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


def _find_best_operation_match(
    user_input: str, available_operations: List[str], threshold: float = 0.6
) -> Optional[str]:
    """
    Find the best matching operation name using fuzzy string matching.

    Args:
        user_input: The user-provided operation name
        available_operations: List of available operation names
        threshold: Minimum similarity score to consider a match (0.0 to 1.0)

    Returns:
        The best matching operation name, or None if no match above threshold
    """
    # Handle empty input
    if not user_input:
        return None

    if user_input in available_operations:
        return user_input

    best_match = None
    best_score = 0.0

    for operation in available_operations:
        # Calculate similarity using SequenceMatcher
        similarity = SequenceMatcher(None, user_input.lower(), operation.lower()).ratio()

        # Check if user_input is a substring of operation (e.g., "build" in "project_build")
        if user_input.lower() in operation.lower():
            # Boost substring matches, but prefer shorter operations for same substring
            substring_boost = 0.8
            # If multiple operations contain the substring, prefer the one that starts with it
            if operation.lower().startswith(user_input.lower()):
                substring_boost = 0.9
            similarity = max(similarity, substring_boost)

        # Check if operation starts with user_input (e.g., "proj" matches "project_build")
        if operation.lower().startswith(user_input.lower()):
            similarity = max(similarity, 0.7)

        # Special handling for common prefixes
        if user_input.lower() == "build" and "build" in operation.lower():
            # For "build", prefer operations that end with "build" over those that contain "build" in the middle
            if operation.lower().endswith("build"):
                similarity = max(similarity, 0.95)
            elif "build" in operation.lower():
                similarity = max(similarity, 0.85)

        # Special handling for exact word matches
        if user_input.lower() == "build" and operation.lower() == "project_build":
            # For "build", strongly prefer "project_build" over other build operations
            similarity = max(similarity, 0.98)

        # Special handling for build-related prefixes
        if user_input.lower() in ["bui", "buil"] and operation.lower() == "project_build":
            # For build prefixes, strongly prefer "project_build" over other build operations
            similarity = max(similarity, 0.97)

        if user_input.lower() == "po" and operation.lower().startswith("po_"):
            # For "po", prefer po_* operations over project_post_*
            similarity = max(similarity, 0.9)

        if similarity > best_score:
            best_score = similarity
            best_match = operation

    if best_score >= threshold:
        log.debug("Fuzzy match: '%s' -> '%s' (score: %.2f)", user_input, best_match, best_score)
        return best_match

    return None


def _find_all_operation_matches(
    user_input: str, available_operations: List[str], threshold: float = 0.6
) -> Tuple[Optional[str], List[str]]:
    """
    Find all possible matching operation names using fuzzy string matching.

    Args:
        user_input: The user-provided operation name
        available_operations: List of available operation names
        threshold: Minimum similarity score to consider a match (0.0 to 1.0)

    Returns:
        Tuple of (best_match, all_matches) where:
        - best_match: The single best matching operation name, or None if no match above threshold
        - all_matches: List of all operations that match above threshold
    """
    # Handle empty input
    if not user_input:
        return None, []

    if user_input in available_operations:
        return user_input, [user_input]

    matches = []
    best_match = None
    best_score = 0.0

    for operation in available_operations:
        # Calculate similarity using SequenceMatcher
        similarity = SequenceMatcher(None, user_input.lower(), operation.lower()).ratio()

        # Check if user_input is a substring of operation (e.g., "build" in "project_build")
        if user_input.lower() in operation.lower():
            # Boost substring matches, but prefer shorter operations for same substring
            substring_boost = 0.8
            # If multiple operations contain the substring, prefer the one that starts with it
            if operation.lower().startswith(user_input.lower()):
                substring_boost = 0.9
            similarity = max(similarity, substring_boost)

        # Check if operation starts with user_input (e.g., "proj" matches "project_build")
        if operation.lower().startswith(user_input.lower()):
            similarity = max(similarity, 0.7)

        # Special handling for common prefixes
        if user_input.lower() == "build" and "build" in operation.lower():
            # For "build", prefer operations that end with "build" over those that contain "build" in the middle
            if operation.lower().endswith("build"):
                similarity = max(similarity, 0.95)
            elif "build" in operation.lower():
                similarity = max(similarity, 0.85)

        # Special handling for exact word matches
        if user_input.lower() == "build" and operation.lower() == "project_build":
            # For "build", strongly prefer "project_build" over other build operations
            similarity = max(similarity, 0.98)

        # Special handling for build-related prefixes
        if user_input.lower() in ["bui", "buil"] and operation.lower() == "project_build":
            # For build prefixes, strongly prefer "project_build" over other build operations
            similarity = max(similarity, 0.97)

        if user_input.lower() == "po" and operation.lower().startswith("po_"):
            # For "po", prefer po_* operations over project_post_*
            similarity = max(similarity, 0.9)

        if similarity >= threshold:
            matches.append((operation, similarity))
            if similarity > best_score:
                best_score = similarity
                best_match = operation

    # Sort matches by similarity score (highest first)
    matches.sort(key=lambda x: x[1], reverse=True)
    all_matches = [op for op, _ in matches]

    if best_match:
        log.debug("Fuzzy match: '%s' -> '%s' (score: %.2f)", user_input, best_match, best_score)
        return best_match, all_matches

    return None, []


class FuzzyOperationParser(argparse.ArgumentParser):
    """
    Custom ArgumentParser that supports fuzzy matching for operation names.
    """

    def __init__(self, available_operations: List[str], *args, enable_fuzzy: bool = True, **kwargs):
        self.available_operations = available_operations
        self.enable_fuzzy = bool(enable_fuzzy)
        super().__init__(*args, **kwargs)

    def _get_value(self, action, arg_string):
        """
        Override to implement fuzzy matching for operation argument.
        """
        if action.dest == "operate":
            # Try exact match first
            if arg_string in self.available_operations:
                return arg_string

            if not self.enable_fuzzy:
                suggestions = []
                for op in self.available_operations:
                    if arg_string.lower() in op.lower() or op.lower().startswith(arg_string.lower()):
                        suggestions.append(op)
                suffix = f" Did you mean: {', '.join(suggestions[:5])}?" if suggestions else ""
                raise argparse.ArgumentTypeError(
                    f"Unknown operation '{arg_string}' (fuzzy matching disabled by --no-fuzzy).{suffix}"
                )

            # Try fuzzy match
            best_match, all_matches = _find_all_operation_matches(arg_string, self.available_operations)

            if best_match:
                if len(all_matches) == 1:
                    # Single match - print hint and return
                    log.info("Fuzzy match: '%s' -> '%s'", arg_string, best_match)
                    return best_match
                # Multiple matches - show all options and use the best one
                matches_str = ", ".join(all_matches)
                log.warning("Ambiguous operation '%s'. Possible matches: %s", arg_string, matches_str)
                log.info("Using best match: '%s' -> '%s'", arg_string, best_match)
                return best_match

            # If no match found, raise error with suggestions
            suggestions = []
            for op in self.available_operations:
                if arg_string.lower() in op.lower() or op.lower().startswith(arg_string.lower()):
                    suggestions.append(op)

            if suggestions:
                suggestions_str = ", ".join(suggestions[:5])  # Limit to 5 suggestions
                raise argparse.ArgumentTypeError(f"Unknown operation '{arg_string}'. Did you mean: {suggestions_str}?")
            raise argparse.ArgumentTypeError(
                f"Unknown operation '{arg_string}'. Available operations: {', '.join(self.available_operations)}"
            )

        return super()._get_value(action, arg_string)


@func_time
@func_cprofile
def main():
    """Main entry point for the CLI project manager."""
    log.debug("sys.argv: %s", sys.argv)

    # Define root_path as current working directory
    root_path = os.getcwd()
    # Use projects path from current working directory
    projects_path = os.path.join(root_path, "projects")

    env = {
        "root_path": root_path,
        "projects_path": projects_path,
        # "repositories": _find_repositories(),  # lazy loading
    }

    # Opt-in: import platform scripts (workspace code execution).
    if _should_load_platform_scripts(sys.argv[1:]):
        _import_platform_scripts(env["projects_path"])

    builtin_operations = _load_builtin_plugin_operations()
    log.debug("Loaded %d builtin operations.", len(builtin_operations))
    log.debug("Builtin operations: %s", list(builtin_operations.keys()))

    # Use only builtin operations since platform scripts are just imported
    all_operations = builtin_operations

    operate, name, parsed_args, parsed_kwargs, args_dict = _parse_args_and_plugin_args(all_operations)
    builtins.ENABLE_CPROFILE = args_dict.get("perf_analyze", False)

    safe_mode = bool(args_dict.get("safe_mode"))
    allow_network = bool(args_dict.get("allow_network"))
    confirmed = bool(args_dict.get("yes"))
    env["safe_mode"] = safe_mode
    env["allow_network"] = allow_network
    env["confirmed"] = confirmed

    # Only execute operations registered through plugins
    if operate in all_operations:
        if safe_mode:
            destructive_ops = {
                "upgrade",
                "po_apply",
                "po_revert",
                "po_new",
                "po_update",
                "po_del",
                "project_build",
                "project_new",
                "project_del",
                "board_new",
                "board_del",
            }
            is_dry_run = _arg_truthy(parsed_kwargs.get("dry_run"))
            if operate == "upgrade" and not is_dry_run and not allow_network:
                log.error("Safe mode blocks networked upgrade without --allow-network.")
                print("Error: --safe-mode blocks 'upgrade' without --allow-network (use --dry-run to preview).")
                sys.exit(1)
            if operate in destructive_ops and not is_dry_run and not confirmed:
                log.error("Safe mode blocks destructive operation '%s' without --dry-run or --yes.", operate)
                print(f"Error: --safe-mode requires --dry-run or --yes for '{operate}'.")
                sys.exit(1)

        op_info = all_operations[operate]
        func = op_info["func"]
        needs_projects = get_operation_meta_flag(func, operate, "needs_projects")
        if needs_projects:
            # Load common configurations after CLI args are parsed.
            # This avoids printing workspace warnings for early-exit flags like --version / --help.
            common_configs, po_configs = _load_common_config(env["projects_path"])
            env["po_configs"] = po_configs
            log.debug("env: \n%s", json.dumps(env, indent=4, ensure_ascii=False))
            log.debug("Loaded %d po configurations.", len(po_configs))
            log.debug("Po configurations: %s", list(po_configs.keys()))

            try:
                projects_info = _load_all_projects(env["projects_path"], common_configs)
            except ValueError as err:
                log.error("Failed to scan projects: %s", err)
                sys.exit(1)
            log.debug("Loaded %d projects.", len(projects_info))
            log.debug(
                "Loaded projects info:\n%s",
                json.dumps(projects_info, indent=4, ensure_ascii=False),
            )
        else:
            env["po_configs"] = {}
            projects_info = {}

        params = op_info["params"]
        sig = inspect.signature(func)
        # Only count CLI parameters that users need to input (remove env, projects_info)
        cli_params = [p for p in params if p not in ("env", "projects_info")]
        required_cli_params = [p for p in cli_params if sig.parameters[p].default == inspect.Parameter.empty]
        # name + parsed_args are the actual parameters input by the user
        user_args = ([name] if name is not None else []) + parsed_args
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
            result = func(*func_args, **func_kwargs)
            if result is False:
                log.error("Operation '%s' failed", operate)
                sys.exit(1)
        except TypeError as e:
            log.error("Failed to call operation '%s': %s", operate, e)
            sys.exit(1)
    else:
        log.error("Operation '%s' is not supported.", operate)
        sys.exit(1)


if __name__ == "__main__":
    main()
