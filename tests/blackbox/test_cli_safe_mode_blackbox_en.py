"""Blackbox safe-mode tests."""

from __future__ import annotations

from pathlib import Path

from .conftest import run_cli


def test_safe_mode_help_works(workspace_a: Path) -> None:
    result = run_cli(["--safe-mode", "--help"], cwd=workspace_a, check=False)
    assert result.returncode == 0
    assert "--safe-mode" in (result.stdout or "")


def test_safe_mode_version_works(workspace_a: Path) -> None:
    result = run_cli(["--safe-mode", "--version"], cwd=workspace_a, check=False)
    assert result.returncode == 0
    assert (result.stdout or "").strip().startswith("0.0.13")


def test_safe_mode_blocks_update_without_allow_network(workspace_a: Path) -> None:
    result = run_cli(["--safe-mode", "update"], cwd=workspace_a, check=False)
    assert result.returncode != 0
    combined = (result.stdout or "") + (result.stderr or "")
    assert "--allow-network" in combined


def test_safe_mode_blocks_po_apply_without_dry_run_or_yes(workspace_a: Path) -> None:
    result = run_cli(["--safe-mode", "po_apply", "projA"], cwd=workspace_a, check=False)
    assert result.returncode != 0
    combined = (result.stdout or "") + (result.stderr or "")
    assert "--dry-run or --yes" in combined


def test_safe_mode_allows_po_apply_with_dry_run(workspace_a: Path) -> None:
    result = run_cli(["--safe-mode", "po_apply", "projA", "--dry-run"], cwd=workspace_a, check=False)
    assert result.returncode == 0


def test_safe_mode_blocks_project_build_without_dry_run_or_yes(workspace_a: Path) -> None:
    result = run_cli(["--safe-mode", "project_build", "projA"], cwd=workspace_a, check=False)
    assert result.returncode != 0
    combined = (result.stdout or "") + (result.stderr or "")
    assert "--dry-run or --yes" in combined


def test_safe_mode_allows_project_build_with_dry_run(workspace_a: Path) -> None:
    result = run_cli(["--safe-mode", "project_build", "projA", "--dry-run"], cwd=workspace_a, check=False)
    assert result.returncode == 0


def test_safe_mode_ignores_env_based_script_loading(workspace_a: Path) -> None:
    scripts_dir = workspace_a / "projects" / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    marker_py = scripts_dir / "marker.py"
    marker_txt = workspace_a / "marker_safe_mode.txt"
    marker_txt.unlink(missing_ok=True)

    marker_py.write_text(
        "import os\n"
        "with open(os.path.join(os.getcwd(), 'marker_safe_mode.txt'), 'w', encoding='utf-8') as f:\n"
        "    f.write('hit')\n",
        encoding="utf-8",
    )

    result = run_cli(
        ["--safe-mode", "update", "--dry-run"],
        cwd=workspace_a,
        env={"PROJMAN_LOAD_SCRIPTS": "1"},
        check=False,
    )
    assert result.returncode == 0
    assert not marker_txt.exists()
