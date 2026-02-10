"""Blackbox repository discovery tests."""

from __future__ import annotations

import json
from pathlib import Path

from .conftest import run_cli


def _load_repositories_json(root: Path) -> dict:
    path = root / "projects" / "repositories.json"
    assert path.exists()
    return json.loads(path.read_text(encoding="utf-8"))


def test_repo_001_single_repo_detected(workspace_a: Path) -> None:
    _ = run_cli(["project_diff", "projA"], cwd=workspace_a, check=False)
    data = _load_repositories_json(workspace_a)
    assert data["discovery_type"] == "single"
    assert any(repo["name"] == "root" for repo in data["repositories"])


def test_repo_002_manifest_repos_detected(workspace_b: Path) -> None:
    _ = run_cli(["project_diff", "projA"], cwd=workspace_b, check=False)
    data = _load_repositories_json(workspace_b)
    names = [repo["name"] for repo in data["repositories"]]
    assert data["discovery_type"] == "manifest"
    assert "repo1" in names and "repo2" in names


def test_repo_003_manifest_include_missing(workspace_b: Path) -> None:
    manifest = workspace_b / ".repo" / "manifest.xml"
    text = manifest.read_text(encoding="utf-8")
    manifest.write_text(
        text.replace("</manifest>", '  <include name="missing.xml" />\n</manifest>\n'), encoding="utf-8"
    )
    _ = run_cli(["project_diff", "projA"], cwd=workspace_b, check=False)
    log_text = (workspace_b / ".cache" / "latest.log").read_text(encoding="utf-8")
    assert "include file not found" in log_text.lower()


def test_repo_004_no_repo_no_git(empty_workspace: Path) -> None:
    _ = run_cli(["project_diff", "projA"], cwd=empty_workspace, check=False)
    data = _load_repositories_json(empty_workspace)
    assert data["repositories"] == []
    assert data.get("discovery_type") in ("", None)
