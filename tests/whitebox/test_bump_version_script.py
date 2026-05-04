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


def test_bump_version_none_keeps_version() -> None:
    assert bump_version.bump_version((0, 1, 1), "none") == (0, 1, 1)


def test_bump_version_minor_increments_minor_and_resets_patch() -> None:
    assert bump_version.bump_version((0, 1, 9), "minor") == (0, 2, 0)


def test_bump_version_major_increments_major_and_resets_lower_parts() -> None:
    assert bump_version.bump_version((0, 9, 9), "major") == (1, 0, 0)


def test_replace_version_updates_only_project_version() -> None:
    text = '[project]\nname = "demo"\nversion = "0.1.1"\n'

    assert 'version = "0.2.0"' in bump_version.replace_version(text, (0, 2, 0))


def test_release_code_path_detection() -> None:
    assert bump_version.has_release_code_paths(["src/utils.py"])
    assert bump_version.has_release_code_paths(["scripts/write_build_info.py"])
    assert bump_version.has_release_code_paths(["build.sh"])
    assert bump_version.has_release_code_paths(["requirements.txt"])


def test_non_code_path_detection() -> None:
    assert not bump_version.has_release_code_paths(["docs/test_cases_en.md"])
    assert not bump_version.has_release_code_paths(["AGENTS.md"])
    assert not bump_version.has_release_code_paths([".github/workflows/python-app.yml"])
    assert not bump_version.has_release_code_paths(["tests/whitebox/test_bump_version_script.py"])


def test_pyproject_version_only_change_is_not_code(monkeypatch) -> None:
    def fake_read_file_from_ref(ref: str, _filename: str) -> str:
        version = "0.1.1" if ref == "base" else "0.1.2"
        return f'[project]\nname = "demo"\nversion = "{version}"\n'

    monkeypatch.setattr(bump_version, "read_file_from_ref", fake_read_file_from_ref)

    assert not bump_version.has_pyproject_code_changes("base", "head")


def test_pyproject_dependency_change_is_code(monkeypatch) -> None:
    def fake_read_file_from_ref(ref: str, _filename: str) -> str:
        dependencies = 'dependencies = ["a"]' if ref == "base" else 'dependencies = ["a", "b"]'
        return f'[project]\nname = "demo"\nversion = "0.1.1"\n{dependencies}\n'

    monkeypatch.setattr(bump_version, "read_file_from_ref", fake_read_file_from_ref)

    assert bump_version.has_pyproject_code_changes("base", "head")
