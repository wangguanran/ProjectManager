"""Project management utility class for CLI operations."""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from configupdater import ConfigUpdater

from src.log_manager import log
from src.operations.registry import register


@dataclass(frozen=True)
class BoardContext:
    """Resolved context for an existing board."""

    board_name: str
    board_path: Path
    ini_path: Path


def _existing_board_context(project_name: str, projects_info: Dict[str, Dict]) -> Optional[BoardContext]:
    info = projects_info.get(project_name)
    if not isinstance(info, dict):
        return None
    board_name = info.get("board_name")
    board_path = info.get("board_path")
    ini_file = info.get("ini_file")
    if not (board_name and board_path and ini_file):
        return None
    return BoardContext(board_name=str(board_name), board_path=Path(board_path), ini_path=Path(ini_file))


def _safe_access(path: Path, mode: int) -> bool:
    try:
        return os.access(path, mode)
    except OSError:
        return False


def _normalise_board_name(board_name: str) -> Optional[str]:
    if not isinstance(board_name, str) or not board_name.strip():
        return None
    name = board_name.strip()
    if name in {".", ".."}:
        return None
    normalised = os.path.normpath(name)
    if normalised in {".", ".."} or os.path.isabs(normalised):
        return None
    if any(sep in name for sep in (os.sep, os.altsep) if sep):
        return None
    return normalised


def _reserved_board_name(board_name: str) -> bool:
    return board_name in {"common", "template", "scripts", ".cache", ".git"}


@register("project_new", needs_repositories=False, desc="Create a new project.")
def project_new(env: Dict, projects_info: Dict, project_name: str) -> bool:
    """Create a new project entry inside an existing board."""

    if not isinstance(projects_info, dict):
        log.error("projects_info must be a dictionary for project_new.")
        print("Error: projects_info must be a dictionary.")
        return False

    _ = env

    def find_parent(name: str) -> Optional[str]:
        return name.rsplit("-", 1)[0] if "-" in name else None

    def inherited_config(name: str) -> Dict:
        config: Dict = {}
        parent = find_parent(name)
        if parent:
            config.update(inherited_config(parent))
        if name in projects_info:
            config.update(projects_info[name])
        return config

    def candidate_contexts() -> Iterable[BoardContext]:
        parent = find_parent(project_name)
        if parent:
            context = _existing_board_context(parent, projects_info)
            if context:
                yield context
            return
        for existing_project in projects_info:
            if project_name.startswith(f"{existing_project}-"):
                context = _existing_board_context(existing_project, projects_info)
                if context:
                    yield context

    if not project_name:
        log.error("Project name must be provided.")
        print("Error: Project name must be provided.")
        return False

    context = next(candidate_contexts(), None)
    if context is None:
        log.error("Cannot determine board for project '%s'. Please ensure:", project_name)
        print(f"Error: Cannot determine board for project '{project_name}'. Please ensure:")
        if "-" in project_name:
            parent = find_parent(project_name)
            print(f"  1. Parent project '{parent}' exists in projects_info")
            print("  2. The parent project is properly configured with board information")
        else:
            print("  1. The project has a parent project that exists in projects_info")
            print("  2. The project name follows the pattern 'parent-project'")
            print("  3. There are available board directories in projects")
        return False

    board_name = context.board_name
    board_path = context.board_path
    ini_file = context.ini_path

    if not board_path.is_dir():
        log.error("Board directory '%s' does not exist for project '%s'.", board_name, project_name)
        print(f"Error: Board directory '{board_name}' does not exist for project '{project_name}'.")
        return False
    if not ini_file.exists():
        log.error("No ini file found for board: '%s'", board_name)
        print(f"No ini file found for board: '{board_name}'")
        return False
    if project_name == board_name:
        log.error("Project name '%s' cannot be the same as board name.", project_name)
        print(f"Error: Project name '{project_name}' cannot be the same as board name.")
        return False

    config = ConfigUpdater()
    config.optionxform = str
    try:
        if not _safe_access(ini_file, os.R_OK):
            log.error("INI file is not readable: '%s'", ini_file)
            print(f"Error: INI file is not readable: '{ini_file}'")
            return False
        config.read(str(ini_file), encoding="utf-8")
    except (PermissionError, OSError, UnicodeError) as err:
        log.error("Failed to read INI file '%s': %s", ini_file, err)
        print(f"Error: Failed to read INI file '{ini_file}': {err}")
        return False

    if project_name in config.sections():
        log.error("Project '%s' already exists in board '%s'.", project_name, board_name)
        print(f"Project '{project_name}' already exists in board '{board_name}'.")
        return False

    inherited = inherited_config(project_name)
    parent_config = inherited.get("config", {}) if isinstance(inherited.get("config", {}), dict) else {}
    platform_name = parent_config.get("PROJECT_PLATFORM")
    project_customer = parent_config.get("PROJECT_CUSTOMER")
    project_name_parts: List[str] = []
    if platform_name:
        project_name_parts.append(platform_name)
    project_name_parts.append(project_name)
    if project_customer:
        project_name_parts.append(project_customer)
    project_name_value = "_".join(project_name_parts)

    try:
        if not _safe_access(ini_file, os.R_OK):
            log.error("INI file is not readable: '%s'", ini_file)
            print(f"Error: INI file is not readable: '{ini_file}'")
            return False
        original_lines = ini_file.read_text(encoding="utf-8").splitlines(keepends=True)
    except (PermissionError, OSError, UnicodeError) as err:
        log.error("Failed to read INI file '%s': %s", ini_file, err)
        print(f"Error: Failed to read INI file '{ini_file}': {err}")
        return False

    new_lines: List[str] = []
    current_section: Optional[str] = None
    for line in original_lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            current_section = stripped[1:-1]
            new_lines.append(line)
            continue
        if current_section == board_name:
            lstrip = line.lstrip()
            if lstrip.upper().startswith("PROJECT_NAME") and "=" in line:
                prefix_len = len(line) - len(lstrip)
                prefix = line[:prefix_len]
                _after = line.split("=", 1)[1]
                new_lines.append(f"{prefix}PROJECT_NAME = {_after.lstrip()}")
                continue
        new_lines.append(line)

    if new_lines and new_lines[-1].strip():
        new_lines.append("\n")
    while len(new_lines) >= 2 and not new_lines[-1].strip() and not new_lines[-2].strip():
        new_lines.pop()

    new_lines.append(f"[{project_name}]\n")
    new_lines.append(f"PROJECT_NAME = {project_name_value}\n")

    board_dir = ini_file.parent
    try:
        if board_dir and not _safe_access(board_dir, os.W_OK):
            log.error("Board directory is not writable: '%s'", board_dir)
            print(f"Error: Board directory is not writable: '{board_dir}'")
            return False
        if not _safe_access(ini_file, os.W_OK):
            log.error("INI file is not writable: '%s'", ini_file)
            print(f"Error: INI file is not writable: '{ini_file}'")
            return False
        ini_file.write_text("".join(new_lines), encoding="utf-8")
    except (PermissionError, OSError, UnicodeError) as err:
        log.error("Failed to write INI file '%s': %s", ini_file, err)
        print(f"Error: Failed to write INI file '{ini_file}': {err}")
        return False

    log.debug("Created new project '%s' in board '%s'.", project_name, board_name)
    print(f"Created new project '{project_name}' in board '{board_name}'.")

    config_after = ConfigUpdater()
    config_after.optionxform = str
    try:
        config_after.read(str(ini_file), encoding="utf-8")
    except (PermissionError, OSError, UnicodeError) as err:
        log.error("Failed to re-read INI file '%s': %s", ini_file, err)
        print(f"Error: Failed to re-read INI file '{ini_file}': {err}")
        return False

    merged_config = dict(parent_config)
    if project_name in config_after:
        for key, value in config_after[project_name].items():
            merged_config[key] = value.value if hasattr(value, "value") else value

    print(f"All config for project '{project_name}':")
    for key, value in merged_config.items():
        print(f"  {key} = {value}")

    project_dir = board_path / project_name
    project_dir.mkdir(parents=True, exist_ok=True)
    log.info("Project '%s' created in board '%s'.", project_name, board_name)
    print(f"Project '{project_name}' created in board '{board_name}'.")
    return True


@register("project_del", needs_repositories=False, desc="Delete the specified project.")
def project_del(env: Dict, projects_info: Dict, project_name: str) -> bool:
    """Delete the specified project and any nested subprojects."""

    _ = env

    def find_all_subprojects(name: str) -> List[str]:
        direct = [candidate for candidate in projects_info if candidate != name and candidate.startswith(f"{name}-")]
        descendants: List[str] = []
        for child in direct:
            descendants.append(child)
            descendants.extend(find_all_subprojects(child))
        return descendants

    project_cfg = projects_info.get(project_name, {})
    board_name = project_cfg.get("board_name")
    board_path = Path(project_cfg.get("board_path", "")) if project_cfg.get("board_path") else None
    ini_file = Path(project_cfg.get("ini_file", "")) if project_cfg.get("ini_file") else None

    if not project_name:
        log.error("Project name must be provided.")
        print("Error: Project name must be provided.")
        return False
    if not board_name or not board_path:
        log.error("Board info missing for project '%s'", project_name)
        print(f"Error: Board info missing for project '{project_name}'.")
        return False
    if not board_path.is_dir():
        log.error("Board directory '%s' does not exist for project '%s'.", board_name, project_name)
        print(f"Error: Board directory '{board_name}' does not exist for project '{project_name}'.")
        return False
    if not ini_file or not ini_file.exists():
        log.error("No ini file found for board: '%s'", board_name)
        print(f"No ini file found for board: '{board_name}'")
        return False
    if project_name == board_name:
        log.error("Project name '%s' cannot be the same as board name.", project_name)
        print(f"Error: Project name '{project_name}' cannot be the same as board name.")
        return False

    config = ConfigUpdater()
    config.optionxform = str
    config.read(str(ini_file), encoding="utf-8")
    to_delete = [project_name] + find_all_subprojects(project_name)
    for name in to_delete:
        if name not in config.sections():
            log.info("Project '%s' does not exist in board '%s'.", name, board_name)
            print(f"Project '{name}' does not exist in board '{board_name}'.")
        else:
            config.remove_section(name)
            log.debug("Removed project '%s' from board '%s'.", name, board_name)
            print(f"Removed project '{name}' from board '{board_name}'.")
    config.update_file()
    return True


@register("board_new", needs_repositories=False, desc="Create a new board.")
def board_new(env: Dict, projects_info: Dict, board_name: str) -> bool:
    """Create a new board and scaffold its directory structure."""

    _ = projects_info

    normalised = _normalise_board_name(board_name)
    if not normalised:
        log.error("Board name must be a non-empty relative path without special components.")
        print("Error: Board name must be a non-empty relative path without special components.")
        return False
    if _reserved_board_name(normalised):
        log.error("Board name '%s' is reserved and cannot be used.", normalised)
        print(f"Error: Board name '{normalised}' is reserved and cannot be used.")
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

    projects_root = Path(projects_path).resolve()
    try:
        projects_root.mkdir(parents=True, exist_ok=True)
    except OSError as err:
        log.error("Failed to ensure projects path '%s': %s", projects_root, err)
        print(f"Error: Failed to ensure projects path '{projects_root}': {err}")
        return False

    board_path = (projects_root / normalised).resolve()
    try:
        board_path.relative_to(projects_root)
    except ValueError:
        log.error("Board name '%s' resolves outside of projects path '%s'.", normalised, projects_root)
        print(f"Error: Board name '{normalised}' resolves outside of projects path '{projects_root}'.")
        return False
    if board_path.exists():
        log.error("Board '%s' already exists at '%s'.", normalised, board_path)
        print(f"Error: Board '{normalised}' already exists.")
        return False

    po_path = board_path / "po"
    ini_path = board_path / f"{normalised}.ini"
    projects_json_path = board_path / "projects.json"

    template_dir = projects_root / "template"
    template_ini_path = template_dir / "template.ini"
    template_po_path = template_dir / "po"

    def _generate_ini_lines() -> List[str]:
        default_lines = [
            f"[{normalised}]\n",
            "PROJECT_NAME = \n",
            "PROJECT_VERSION = \n",
            "PROJECT_PO_CONFIG = \n",
            "PROJECT_PO_IGNORE = \n",
        ]
        if not template_ini_path.is_file():
            return default_lines
        try:
            lines = template_ini_path.read_text(encoding="utf-8").splitlines(keepends=True)
        except (OSError, UnicodeError) as err:
            log.warning("Failed to read template ini '%s': %s. Using default template.", template_ini_path, err)
            return default_lines
        replaced = False
        ini_lines: List[str] = []
        for line in lines:
            stripped = line.strip()
            if not replaced and stripped.startswith("[") and stripped.endswith("]"):
                ini_lines.append(f"[{normalised}]\n")
                replaced = True
            else:
                ini_lines.append(line)
        if not ini_lines:
            return default_lines
        if not replaced:
            ini_lines.insert(0, f"[{normalised}]\n")
        return ini_lines

    def _initialise_po_directory() -> None:
        if template_po_path.is_dir():
            try:
                shutil.copytree(template_po_path, po_path)
                return
            except FileExistsError:
                pass
            for root, _dirs, files in os.walk(template_po_path):
                rel_root = Path(root).relative_to(template_po_path)
                dest_root = po_path if rel_root == Path(".") else po_path / rel_root
                dest_root.mkdir(parents=True, exist_ok=True)
                for file_name in files:
                    shutil.copy2(Path(root) / file_name, dest_root / file_name)
            return
        default_po_root = po_path / "po_template"
        for subdir in ("patches", "overrides"):
            (default_po_root / subdir).mkdir(parents=True, exist_ok=True)

    try:
        board_path.mkdir(parents=False, exist_ok=False)
        _initialise_po_directory()
        ini_path.write_text("".join(_generate_ini_lines()), encoding="utf-8")
        board_metadata = {
            "board_name": normalised,
            "board_path": str(board_path),
            "last_updated": datetime.now().isoformat(),
            "projects": [],
        }
        projects_json_path.write_text(json.dumps(board_metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    except FileExistsError:
        log.error("Board directory structure for '%s' already exists.", normalised)
        print(f"Error: Board '{normalised}' already exists.")
        return False
    except (OSError, UnicodeError, ValueError) as err:
        log.error("Failed to create board '%s': %s", normalised, err)
        print(f"Error: Failed to create board '{normalised}': {err}")
        if board_path.is_dir():
            shutil.rmtree(board_path, ignore_errors=True)
        return False

    log.debug("Created new board '%s' at '%s'.", normalised, board_path)
    print(f"Created new board '{normalised}' at '{board_path}'.")
    print(f"Board ini file: {ini_path}")
    print(f"PO directory: {po_path}")
    return True


@register("board_del", needs_repositories=False, desc="Delete the specified board.")
def board_del(env: Dict, projects_info: Dict, board_name: str) -> bool:
    """Delete a board and clean up associated cache entries."""

    normalised = _normalise_board_name(board_name)
    if not normalised:
        log.error("Board name must be a non-empty relative path without special components.")
        print("Error: Board name must be a non-empty relative path without special components.")
        return False
    if _reserved_board_name(normalised):
        log.error("Board name '%s' is reserved and cannot be used.", normalised)
        print(f"Error: Board name '{normalised}' is reserved and cannot be used.")
        return False

    projects_path = env.get("projects_path") if isinstance(env, dict) else None
    if not isinstance(projects_path, str) or not projects_path.strip():
        log.error("Invalid 'projects_path' in environment: %s", projects_path)
        print("Error: Invalid 'projects_path' in environment.")
        return False

    protected_boards = env.get("protected_boards", []) if isinstance(env, dict) else []
    if isinstance(protected_boards, (set, list, tuple)) and normalised in set(protected_boards):
        log.error("Board '%s' is protected and cannot be deleted.", normalised)
        print(f"Error: Board '{normalised}' is protected and cannot be deleted.")
        return False

    projects_root = Path(projects_path).resolve()
    board_path = (projects_root / normalised).resolve()
    try:
        board_path.relative_to(projects_root)
    except ValueError:
        log.error("Board name '%s' resolves outside of projects path '%s'.", normalised, projects_root)
        print(f"Error: Board name '{normalised}' resolves outside of projects path '{projects_root}'.")
        return False
    if not board_path.is_dir():
        log.error("Board '%s' does not exist at '%s'.", normalised, board_path)
        print(f"Error: Board '{normalised}' does not exist.")
        return False

    log.debug("Deleting board '%s' at '%s'.", normalised, board_path)
    try:
        shutil.rmtree(board_path)
    except OSError as err:
        log.error("Failed to delete board '%s': %s", normalised, err)
        print(f"Error: Failed to delete board '{normalised}': {err}")
        return False

    root_path = env.get("root_path") if isinstance(env, dict) else None
    if not isinstance(root_path, str) or not root_path:
        root_path = projects_root.parent

    cache_paths = [
        Path(root_path) / ".cache" / "projects" / normalised,
        Path(root_path) / ".cache" / "boards" / normalised,
        Path(root_path) / ".cache" / "build" / normalised,
    ]
    for cache_path in cache_paths:
        if cache_path.exists():
            try:
                shutil.rmtree(cache_path)
                log.debug("Removed cache directory '%s'.", cache_path)
            except OSError as err:
                log.warning("Failed to remove cache path '%s': %s", cache_path, err)

    def _update_projects_index(projects_dir: Path, board: str) -> None:
        index_path = projects_dir / "projects.json"
        if not index_path.is_file():
            return
        try:
            payload = json.loads(index_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as err:
            log.warning("Failed to read projects index '%s': %s", index_path, err)
            return
        changed = False
        updated = payload
        if isinstance(payload, dict):
            if board in payload:
                payload.pop(board, None)
                changed = True
            elif isinstance(payload.get("boards"), dict) and board in payload["boards"]:
                payload["boards"].pop(board, None)
                changed = True
            elif isinstance(payload.get("boards"), list):
                filtered = [item for item in payload["boards"] if item != board]
                if len(filtered) != len(payload["boards"]):
                    payload["boards"] = filtered
                    changed = True
        elif isinstance(payload, list):
            filtered = [item for item in payload if item != board]
            if len(filtered) != len(payload):
                updated = filtered
                changed = True
        else:
            log.debug("Projects index '%s' has unsupported format (%s). Skipping update.", index_path, type(payload))
            return
        if changed:
            try:
                index_path.write_text(json.dumps(updated, indent=2, ensure_ascii=False), encoding="utf-8")
                log.debug("Updated projects index '%s' after deleting board '%s'.", index_path, board)
            except (OSError, UnicodeError, ValueError) as err:
                log.warning("Failed to update projects index '%s': %s", index_path, err)

    _update_projects_index(projects_root, normalised)

    if isinstance(projects_info, dict):
        removed = [
            name
            for name, info in list(projects_info.items())
            if isinstance(info, dict) and info.get("board_name") == normalised
        ]
        for name in removed:
            projects_info.pop(name, None)
        if normalised in projects_info:
            projects_info.pop(normalised, None)
        if removed:
            log.debug(
                "Removed %d project(s) associated with board '%s' from in-memory index.",
                len(removed),
                normalised,
            )

    print(f"Deleted board '{normalised}'.")
    return True
