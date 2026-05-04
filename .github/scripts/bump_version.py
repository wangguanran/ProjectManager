#!/usr/bin/env python3
"""Bump the project version in pyproject.toml for release automation."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
from pathlib import Path
from typing import Iterable, Tuple

VERSION_PATTERN = re.compile(r'(?m)^(version\s*=\s*")(\d+)\.(\d+)\.(\d+)(")')
Version = Tuple[int, int, int]

RELEASE_CODE_PREFIXES = (
    "src/",
    "projects/",
    "scripts/",
)
RELEASE_CODE_FILES = {
    "build.sh",
    "install.sh",
    "get_latest_release.sh",
    "install.ps1",
    "Dockerfile",
    "requirements.txt",
}


def parse_version(text: str) -> Version:
    """Return the project version tuple from pyproject.toml content."""
    match = VERSION_PATTERN.search(text)
    if not match:
        raise ValueError("Unable to find project.version in pyproject.toml")
    return tuple(int(part) for part in match.group(2, 3, 4))


def bump_version(version: Version, part: str) -> Version:
    """Bump a semantic version part and reset lower-order parts."""
    major, minor, patch = version
    if part == "none":
        return version
    if part == "major":
        return major + 1, 0, 0
    if part == "minor":
        return major, minor + 1, 0
    if part == "patch":
        return major, minor, patch + 1
    raise ValueError(f"Unsupported bump part: {part}")


def format_version(version: Version) -> str:
    """Render a version tuple as X.Y.Z."""
    return ".".join(str(part) for part in version)


def replace_version(text: str, version: Version) -> str:
    """Replace the first project.version assignment in pyproject.toml content."""
    replacement = rf"\g<1>{format_version(version)}\g<5>"
    updated, count = VERSION_PATTERN.subn(replacement, text, count=1)
    if count != 1:
        raise ValueError("Unable to replace project.version in pyproject.toml")
    return updated


def read_file_from_ref(ref: str, filename: str) -> str:
    """Read a file from a git ref."""
    return subprocess.check_output(
        ["git", "show", f"{ref}:{filename}"],
        text=True,
        stderr=subprocess.STDOUT,
    )


def git_output(*args: str) -> str:
    """Return stdout from a git command."""
    return subprocess.check_output(["git", *args], text=True, stderr=subprocess.STDOUT)


def strip_project_version(text: str) -> str:
    """Remove project.version assignments before comparing pyproject changes."""
    return VERSION_PATTERN.sub(r"\g<1><version>\g<5>", text)


def is_release_code_path(path: str) -> bool:
    """Return whether a path affects release code behavior."""
    return path in RELEASE_CODE_FILES or path.startswith(RELEASE_CODE_PREFIXES)


def has_pyproject_code_changes(base_ref: str, head_ref: str) -> bool:
    """Return whether pyproject changed beyond the release version line."""
    try:
        base_text = read_file_from_ref(base_ref, "pyproject.toml")
        head_text = read_file_from_ref(head_ref, "pyproject.toml")
    except subprocess.CalledProcessError:
        return True
    return strip_project_version(base_text) != strip_project_version(head_text)


def has_release_code_changes(base_ref: str, head_ref: str) -> bool:
    """Return whether git changes include release-relevant code."""
    changed_files = git_output("diff", "--name-only", f"{base_ref}...{head_ref}").splitlines()
    return has_release_code_paths(changed_files, base_ref=base_ref, head_ref=head_ref)


def has_release_code_paths(paths: Iterable[str], base_ref: str = "", head_ref: str = "") -> bool:
    """Return whether changed paths include release-relevant code."""
    for path in paths:
        if path == "pyproject.toml":
            if not base_ref or not head_ref or has_pyproject_code_changes(base_ref, head_ref):
                return True
            continue
        if is_release_code_path(path):
            return True
    return False


def write_github_output(**values: str) -> None:
    """Expose computed values to GitHub Actions when available."""
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    with open(output_path, "a", encoding="utf-8") as output:
        for key, value in values.items():
            output.write(f"{key}={value}\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", default="pyproject.toml", help="Path to pyproject.toml")
    parser.add_argument(
        "--base-ref",
        help="Git ref to read the base version from; defaults to the working tree file",
    )
    parser.add_argument("--head-ref", default="HEAD", help="Git ref to compare against --base-ref")
    parser.add_argument(
        "--part",
        choices=("major", "minor", "patch", "none"),
        help="Semantic version part to bump",
    )
    parser.add_argument(
        "--check-release-code-changes",
        action="store_true",
        help="Print whether changes include release-relevant code and write has_release_code_changes",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Update the working tree file with the computed version",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.check_release_code_changes:
        if not args.base_ref:
            raise ValueError("--base-ref is required with --check-release-code-changes")
        has_code_changes = has_release_code_changes(args.base_ref, args.head_ref)
        value = "true" if has_code_changes else "false"
        write_github_output(has_release_code_changes=value)
        print(value)
        return 0

    if not args.part:
        raise ValueError("--part is required unless --check-release-code-changes is used")

    version_file = Path(args.file)
    base_text = (
        read_file_from_ref(args.base_ref, args.file) if args.base_ref else version_file.read_text(encoding="utf-8")
    )
    next_version = bump_version(parse_version(base_text), args.part)
    next_version_text = format_version(next_version)

    if args.write:
        current_text = version_file.read_text(encoding="utf-8")
        version_file.write_text(replace_version(current_text, next_version), encoding="utf-8")

    write_github_output(version=next_version_text)
    print(next_version_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
