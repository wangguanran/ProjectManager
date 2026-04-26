"""Tests for GitHub Actions version bump helper."""

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / ".github" / "scripts" / "bump_version.py"

spec = importlib.util.spec_from_file_location("bump_version", SCRIPT_PATH)
bump_version = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bump_version)


def test_parse_version_reads_pyproject_version() -> None:
    text = '[project]\nname = "demo"\nversion = "0.1.1"\n'

    assert bump_version.parse_version(text) == (0, 1, 1)


def test_bump_version_patch_increments_only_patch() -> None:
    assert bump_version.bump_version((0, 1, 1), "patch") == (0, 1, 2)


def test_bump_version_minor_increments_minor_and_resets_patch() -> None:
    assert bump_version.bump_version((0, 1, 9), "minor") == (0, 2, 0)


def test_bump_version_major_increments_major_and_resets_lower_parts() -> None:
    assert bump_version.bump_version((0, 9, 9), "major") == (1, 0, 0)


def test_replace_version_updates_only_project_version() -> None:
    text = '[project]\nname = "demo"\nversion = "0.1.1"\n'

    assert 'version = "0.2.0"' in bump_version.replace_version(text, (0, 2, 0))
