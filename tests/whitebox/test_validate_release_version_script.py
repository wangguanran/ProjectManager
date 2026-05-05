"""Tests for the validate-main PR release version gate."""

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / ".github" / "scripts" / "validate_release_version.py"

spec = importlib.util.spec_from_file_location("validate_release_version", SCRIPT_PATH)
validate_release_version = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = validate_release_version
spec.loader.exec_module(validate_release_version)


def test_initial_bug_pr_release_code_commit_can_wait_for_auto_bump() -> None:
    result = validate_release_version.validate_release_version(
        base_version="0.2.17",
        head_version="0.2.17",
        head_branch="bug/fix-release-code",
        has_release_code_changes=True,
        event_name="pull_request",
    )

    assert result.valid
    assert result.pending_auto_bump


def test_initial_feature_pr_release_code_commit_can_wait_for_auto_bump() -> None:
    result = validate_release_version.validate_release_version(
        base_version="0.2.17",
        head_version="0.2.17",
        head_branch="feature/new-release-code",
        has_release_code_changes=True,
        event_name="pull_request",
    )

    assert result.valid
    assert result.pending_auto_bump


def test_dispatched_bug_pr_head_requires_auto_bumped_patch_version() -> None:
    result = validate_release_version.validate_release_version(
        base_version="0.2.17",
        head_version="0.2.18",
        head_branch="bug/fix-release-code",
        has_release_code_changes=True,
        event_name="workflow_dispatch",
    )

    assert result.valid
    assert not result.pending_auto_bump


def test_dispatched_feature_pr_head_requires_auto_bumped_minor_version() -> None:
    result = validate_release_version.validate_release_version(
        base_version="0.2.17",
        head_version="0.3.0",
        head_branch="feature/new-release-code",
        has_release_code_changes=True,
        event_name="workflow_dispatch",
    )

    assert result.valid
    assert not result.pending_auto_bump


def test_dispatched_release_code_head_without_bump_fails() -> None:
    result = validate_release_version.validate_release_version(
        base_version="0.2.17",
        head_version="0.2.17",
        head_branch="bug/fix-release-code",
        has_release_code_changes=True,
        event_name="workflow_dispatch",
    )

    assert not result.valid
    assert "Expected pyproject.toml version 0.2.18" in result.message


def test_release_code_head_with_wrong_bump_fails() -> None:
    result = validate_release_version.validate_release_version(
        base_version="0.2.17",
        head_version="0.2.19",
        head_branch="bug/fix-release-code",
        has_release_code_changes=True,
        event_name="workflow_dispatch",
    )

    assert not result.valid
    assert "Expected pyproject.toml version 0.2.18" in result.message
