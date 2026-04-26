#!/usr/bin/env python3
"""Bump the project version in pyproject.toml for release automation."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
from pathlib import Path
from typing import Tuple

VERSION_PATTERN = re.compile(r'(?m)^(version\s*=\s*")(\d+)\.(\d+)\.(\d+)(")')
Version = Tuple[int, int, int]


def parse_version(text: str) -> Version:
    """Return the project version tuple from pyproject.toml content."""
    match = VERSION_PATTERN.search(text)
    if not match:
        raise ValueError("Unable to find project.version in pyproject.toml")
    return tuple(int(part) for part in match.group(2, 3, 4))


def bump_version(version: Version, part: str) -> Version:
    """Bump a semantic version part and reset lower-order parts."""
    major, minor, patch = version
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


def write_github_output(version: str) -> None:
    """Expose the computed version to GitHub Actions when available."""
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    with open(output_path, "a", encoding="utf-8") as output:
        output.write(f"version={version}\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", default="pyproject.toml", help="Path to pyproject.toml")
    parser.add_argument(
        "--base-ref",
        help="Git ref to read the base version from; defaults to the working tree file",
    )
    parser.add_argument(
        "--part",
        choices=("major", "minor", "patch"),
        required=True,
        help="Semantic version part to bump",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Update the working tree file with the computed version",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    version_file = Path(args.file)
    base_text = (
        read_file_from_ref(args.base_ref, args.file) if args.base_ref else version_file.read_text(encoding="utf-8")
    )
    next_version = bump_version(parse_version(base_text), args.part)
    next_version_text = format_version(next_version)

    if args.write:
        current_text = version_file.read_text(encoding="utf-8")
        version_file.write_text(replace_version(current_text, next_version), encoding="utf-8")

    write_github_output(next_version_text)
    print(next_version_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
