"""Blackbox --no-fuzzy operation resolution tests."""

from __future__ import annotations

from pathlib import Path

from .conftest import run_cli


def test_no_fuzzy_rejects_build_prefix(workspace_a: Path) -> None:
    result = run_cli(["--no-fuzzy", "buil", "projA"], cwd=workspace_a, check=False)
    assert result.returncode != 0
    combined = ((result.stdout or "") + (result.stderr or "")).lower()
    assert "fuzzy matching disabled" in combined


def test_no_fuzzy_rejects_ambiguous_po_prefix(workspace_a: Path) -> None:
    result = run_cli(["--no-fuzzy", "po", "projA"], cwd=workspace_a, check=False)
    assert result.returncode != 0
    combined = ((result.stdout or "") + (result.stderr or "")).lower()
    assert "fuzzy matching disabled" in combined


def test_no_fuzzy_exact_operation_still_works(workspace_a: Path) -> None:
    result = run_cli(["--no-fuzzy", "po_list", "projA", "--short"], cwd=workspace_a, check=False)
    assert result.returncode == 0
