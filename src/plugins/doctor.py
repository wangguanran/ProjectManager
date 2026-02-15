"""Workspace diagnostics command (`doctor`)."""

from __future__ import annotations

import json as jsonlib
import os
from typing import Any, Dict, List, Optional

from src.log_manager import log
from src.operations.registry import register


def _add_check(
    checks: List[Dict[str, Any]],
    *,
    check_id: str,
    severity: str,
    title: str,
    message: str,
    hint: Optional[str] = None,
    path: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
) -> None:
    entry: Dict[str, Any] = {
        "id": check_id,
        "severity": severity,
        "title": title,
        "message": message,
    }
    if hint:
        entry["hint"] = hint
    if path:
        entry["path"] = path
    if data:
        entry["data"] = data
    checks.append(entry)


@register(
    "doctor",
    needs_projects=False,
    needs_repositories=False,
    desc="Workspace diagnostics and fix suggestions.",
)
def doctor(env: Dict[str, Any], projects_info: Dict[str, Any], json: bool = False, strict: bool = False) -> bool:
    """
    Validate the current workspace and print actionable suggestions.

    json (bool): Output machine-readable JSON to stdout.
    strict (bool): Treat warnings as errors (non-zero exit).
    """

    _ = projects_info

    root_path = env.get("root_path") or os.getcwd()
    projects_path = env.get("projects_path") or os.path.join(root_path, "projects")

    checks: List[Dict[str, Any]] = []

    # 1) projects/ directory existence
    if os.path.isdir(projects_path):
        _add_check(
            checks,
            check_id="projects_dir_exists",
            severity="ok",
            title="projects/ directory exists",
            message="Found projects directory.",
            path=projects_path,
        )
    else:
        _add_check(
            checks,
            check_id="projects_dir_exists",
            severity="error",
            title="projects/ directory exists",
            message="projects directory is missing.",
            hint="Run projman from a workspace root that contains projects/, or create projects/ and required configs.",
            path=projects_path,
        )

    # 2) common.ini existence and [common] section
    common_ini_path = os.path.join(projects_path, "common", "common.ini")
    if os.path.isdir(projects_path):
        if os.path.exists(common_ini_path):
            try:
                common_ini_text = ""
                with open(common_ini_path, "r", encoding="utf-8") as f:
                    common_ini_text = f.read()
                if "[common]" in common_ini_text:
                    _add_check(
                        checks,
                        check_id="common_ini_exists",
                        severity="ok",
                        title="common.ini is present",
                        message="Found projects/common/common.ini with [common] section.",
                        path=common_ini_path,
                    )
                else:
                    _add_check(
                        checks,
                        check_id="common_ini_exists",
                        severity="warn",
                        title="common.ini is present",
                        message="Found common.ini, but [common] section is missing.",
                        hint="Add a [common] section to projects/common/common.ini (see docs/test_cases_en.md Dataset A).",
                        path=common_ini_path,
                    )
            except (OSError, UnicodeError) as err:
                _add_check(
                    checks,
                    check_id="common_ini_exists",
                    severity="error",
                    title="common.ini is readable",
                    message=f"Failed to read common.ini: {err}",
                    hint="Check file permissions/encoding for projects/common/common.ini.",
                    path=common_ini_path,
                )
        else:
            _add_check(
                checks,
                check_id="common_ini_exists",
                severity="warn",
                title="common.ini is present",
                message="projects/common/common.ini is missing.",
                hint="Create projects/common/common.ini (see docs/test_cases_en.md Dataset A).",
                path=common_ini_path,
            )
    else:
        _add_check(
            checks,
            check_id="common_ini_exists",
            severity="skip",
            title="common.ini is present",
            message="Skipped: projects/ directory is missing.",
            path=common_ini_path,
        )

    # 3) Board directories: exactly one ini file per board
    exclude_dirs = {"scripts", "common", "template", ".cache", ".git"}
    boards_no_ini: List[str] = []
    boards_multi_ini: Dict[str, List[str]] = {}
    dup_keys: List[Dict[str, str]] = []

    if os.path.isdir(projects_path):
        try:
            for entry in sorted(os.listdir(projects_path)):
                board_path = os.path.join(projects_path, entry)
                if not os.path.isdir(board_path) or entry in exclude_dirs:
                    continue

                ini_files = sorted([f for f in os.listdir(board_path) if f.endswith(".ini")])
                if not ini_files:
                    boards_no_ini.append(entry)
                    continue
                if len(ini_files) > 1:
                    boards_multi_ini[entry] = ini_files
                    continue

                ini_path = os.path.join(board_path, ini_files[0])
                try:
                    with open(ini_path, "r", encoding="utf-8") as f:
                        current_section = None
                        keys_in_section = set()
                        for raw_line in f:
                            line = raw_line.strip()
                            if not line or line.startswith(";") or line.startswith("#"):
                                continue
                            if line.startswith("[") and line.endswith("]"):
                                current_section = line[1:-1].strip()
                                keys_in_section = set()
                                continue
                            if "=" in line and current_section:
                                key = line.split("=", 1)[0].strip()
                                if key in keys_in_section:
                                    dup_keys.append(
                                        {
                                            "board": entry,
                                            "ini": ini_files[0],
                                            "section": current_section,
                                            "key": key,
                                        }
                                    )
                                else:
                                    keys_in_section.add(key)
                except (OSError, UnicodeError) as err:
                    boards_multi_ini.setdefault(entry, []).append(f"{ini_files[0]} (unreadable: {err})")
        except OSError as err:
            _add_check(
                checks,
                check_id="boards_ini_files",
                severity="error",
                title="Board ini file layout",
                message=f"Failed to scan projects directory: {err}",
                hint="Check permissions for projects/ directory.",
                path=projects_path,
            )

    if os.path.isdir(projects_path):
        if boards_multi_ini:
            _add_check(
                checks,
                check_id="boards_ini_files",
                severity="error",
                title="Board ini file layout",
                message="Some board directories have multiple ini files (this will crash config scan).",
                hint="Keep exactly one *.ini per board directory under projects/<board>/.",
                path=projects_path,
                data={"boards_multi_ini": boards_multi_ini},
            )
        elif boards_no_ini:
            _add_check(
                checks,
                check_id="boards_ini_files",
                severity="warn",
                title="Board ini file layout",
                message="Some board directories have no ini file (they will be skipped).",
                hint="Add a single *.ini file per board directory.",
                path=projects_path,
                data={"boards_no_ini": boards_no_ini},
            )
        else:
            _add_check(
                checks,
                check_id="boards_ini_files",
                severity="ok",
                title="Board ini file layout",
                message="Each board directory has exactly one ini file.",
                path=projects_path,
            )
    else:
        _add_check(
            checks,
            check_id="boards_ini_files",
            severity="skip",
            title="Board ini file layout",
            message="Skipped: projects/ directory is missing.",
            path=projects_path,
        )

    # 4) Duplicate keys inside ini sections
    if os.path.isdir(projects_path):
        if dup_keys:
            _add_check(
                checks,
                check_id="ini_duplicate_keys",
                severity="error",
                title="Duplicate keys in ini sections",
                message="Duplicate keys detected (these boards will be skipped during config scan).",
                hint="Remove duplicate keys in the affected ini sections.",
                path=projects_path,
                data={"duplicates": dup_keys[:50], "duplicates_truncated": len(dup_keys) > 50},
            )
        else:
            _add_check(
                checks,
                check_id="ini_duplicate_keys",
                severity="ok",
                title="Duplicate keys in ini sections",
                message="No duplicate keys detected in ini sections.",
                path=projects_path,
            )
    else:
        _add_check(
            checks,
            check_id="ini_duplicate_keys",
            severity="skip",
            title="Duplicate keys in ini sections",
            message="Skipped: projects/ directory is missing.",
            path=projects_path,
        )

    # 5) Git workspace presence (best-effort)
    manifest_path = os.path.join(root_path, ".repo", "manifest.xml")
    git_dir = os.path.join(root_path, ".git")
    if os.path.exists(manifest_path) or os.path.exists(git_dir):
        _add_check(
            checks,
            check_id="git_or_manifest_present",
            severity="ok",
            title="Git repo / manifest detected",
            message="Workspace appears to contain git repositories.",
            path=root_path,
            data={"has_git": os.path.exists(git_dir), "has_manifest": os.path.exists(manifest_path)},
        )
    else:
        _add_check(
            checks,
            check_id="git_or_manifest_present",
            severity="warn",
            title="Git repo / manifest detected",
            message="No .git or .repo/manifest.xml detected; git-based operations may fail.",
            hint="Initialize a git repo in the workspace root or run doctor from the correct repo root.",
            path=root_path,
        )

    errors = sum(1 for c in checks if c["severity"] == "error")
    warns = sum(1 for c in checks if c["severity"] == "warn")

    status = "ok"
    if errors:
        status = "error"
    elif warns:
        status = "warn"

    failed = errors > 0 or (strict and warns > 0)

    report = {
        "schema_version": 1,
        "status": status,
        "strict": bool(strict),
        "workspace": {"root_path": root_path, "projects_path": projects_path},
        "summary": {"errors": errors, "warnings": warns, "checks": len(checks)},
        "checks": checks,
    }

    if json:
        print(jsonlib.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("projman doctor")
        print(f"workspace: {root_path}")
        print(f"projects:  {projects_path}")
        print(f"status:    {status} (errors={errors}, warnings={warns})")
        for c in checks:
            if c["severity"] in {"ok", "skip"}:
                continue
            line = f"- {c['severity'].upper():5s} {c['id']}: {c['title']} - {c['message']}"
            if "path" in c:
                line += f" ({c['path']})"
            print(line)
            if "hint" in c:
                print(f"  hint: {c['hint']}")

    if failed:
        log.error("doctor found issues: errors=%d warnings=%d strict=%s", errors, warns, strict)
        return False
    return True
