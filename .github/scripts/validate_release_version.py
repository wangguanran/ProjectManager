#!/usr/bin/env python3
"""Validate PR release version requirements for main-targeted branches."""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import bump_version as version_helper  # isort: skip

AUTO_BUMP_PR_ACTIONS = frozenset({"opened", "reopened", "synchronize", "ready_for_review"})


@dataclass(frozen=True)
class ValidationResult:
    """Result for the release version gate."""

    valid: bool
    message: str
    pending_auto_bump: bool = False
    expected_version: str = ""


def bump_part_for_branch(head_branch: str) -> Optional[str]:
    """Return the semantic bump part required for a PR branch."""
    if head_branch.startswith("bug/"):
        return "patch"
    if head_branch.startswith("feature/"):
        return "minor"
    return None


def parse_version_string(version: str) -> version_helper.Version:
    """Parse an X.Y.Z version string."""
    return version_helper.parse_version(f'version = "{version}"\n')


def expected_bumped_version(base_version: str, bump_part: str) -> str:
    """Return the expected version after applying a branch bump part."""
    return version_helper.format_version(version_helper.bump_version(parse_version_string(base_version), bump_part))


def validate_release_version(
    *,
    base_version: str,
    head_version: str,
    head_branch: str,
    has_release_code_changes: bool,
    event_name: str,
    event_action: str,
) -> ValidationResult:
    """Validate the version relationship between the base and PR head."""
    bump_part = bump_part_for_branch(head_branch)
    if not bump_part:
        return ValidationResult(True, f"No release version bump required for branch: {head_branch}")

    if not has_release_code_changes:
        if head_version != base_version:
            return ValidationResult(
                False,
                (
                    f"No release code changes detected for {head_branch}, so pyproject.toml must stay at "
                    f"{base_version}; got {head_version}."
                ),
            )
        return ValidationResult(True, f"No release code changes detected; version remains {head_version}.")

    expected_version = expected_bumped_version(base_version, bump_part)
    if head_version == expected_version:
        return ValidationResult(
            True,
            f"Version bump is valid: {base_version} -> {head_version} ({bump_part})",
            expected_version=expected_version,
        )

    if event_name == "pull_request" and event_action in AUTO_BUMP_PR_ACTIONS and head_version == base_version:
        return ValidationResult(
            True,
            (
                f"Release code changes detected for {head_branch}; pyproject.toml still matches "
                f"{base_version} on this pull_request head while auto-version-bump.yml is responsible "
                f"for updating it to {expected_version}."
            ),
            pending_auto_bump=True,
            expected_version=expected_version,
        )

    return ValidationResult(
        False,
        (
            f"Expected pyproject.toml version {expected_version} for {head_branch}, got {head_version}. "
            "Wait for auto-version-bump.yml or re-run it after rebasing on the base branch."
        ),
        expected_version=expected_version,
    )


def read_ref_version(ref: str) -> str:
    """Read pyproject.toml version from a git ref."""
    return version_helper.format_version(
        version_helper.parse_version(version_helper.read_file_from_ref(ref, "pyproject.toml"))
    )


def read_worktree_version(path: Path) -> str:
    """Read pyproject.toml version from the working tree."""
    return version_helper.format_version(version_helper.parse_version(path.read_text(encoding="utf-8")))


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-ref", required=True, help="Git ref containing the target branch pyproject.toml")
    parser.add_argument("--head-ref", default="HEAD", help="Git ref to compare against --base-ref")
    parser.add_argument("--head-branch", required=True, help="Pull request source branch name")
    parser.add_argument(
        "--event-name",
        default=os.environ.get("GITHUB_EVENT_NAME", ""),
        help="GitHub event name, for example pull_request or workflow_dispatch",
    )
    parser.add_argument(
        "--event-action",
        default=os.environ.get("GITHUB_EVENT_ACTION", ""),
        help="GitHub pull_request action, for example opened, synchronize, reopened, or edited",
    )
    parser.add_argument("--file", default="pyproject.toml", help="Path to the working tree pyproject.toml")
    return parser


def main() -> int:
    """Run the release version gate."""
    args = build_parser().parse_args()
    base_version = read_ref_version(args.base_ref)
    head_version = read_worktree_version(Path(args.file))
    has_release_changes = version_helper.has_release_code_changes(args.base_ref, args.head_ref)

    result = validate_release_version(
        base_version=base_version,
        head_version=head_version,
        head_branch=args.head_branch,
        has_release_code_changes=has_release_changes,
        event_name=args.event_name,
        event_action=args.event_action,
    )
    if result.valid:
        print(result.message)
        return 0

    print(f"::error::{result.message}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
