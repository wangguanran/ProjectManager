"""
Black-box CLI security tests derived from docs/test_cases_en.md.

Focus: ensure workspace scripts under projects/scripts are NOT auto-imported
by default (opt-in only).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _run_cli(workdir: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    # Ensure default behavior is tested deterministically.
    env.pop("PROJMAN_LOAD_SCRIPTS", None)
    return subprocess.run(
        [sys.executable, "-m", "src", *args],
        cwd=str(workdir),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_platform_scripts_not_auto_imported_by_default(tmp_path: Path) -> None:
    """CLI-013: platform scripts are not auto-imported by default."""
    scripts_dir = tmp_path / "projects" / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    (scripts_dir / "marker.py").write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "Path('scripts_imported.txt').write_text('1', encoding='utf-8')",
                "",
            ]
        ),
        encoding="utf-8",
    )

    marker = tmp_path / "scripts_imported.txt"
    assert not marker.exists()
    cp = _run_cli(tmp_path, "update", "--dry-run")
    assert cp.returncode == 0
    assert not marker.exists()


def test_cli_platform_scripts_imported_when_opted_in(tmp_path: Path) -> None:
    """CLI-014: `--load-scripts` opts into platform script import."""
    scripts_dir = tmp_path / "projects" / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    (scripts_dir / "marker.py").write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "Path('scripts_imported.txt').write_text('1', encoding='utf-8')",
                "",
            ]
        ),
        encoding="utf-8",
    )

    marker = tmp_path / "scripts_imported.txt"
    assert not marker.exists()
    cp = _run_cli(tmp_path, "--load-scripts", "update", "--dry-run")
    assert cp.returncode == 0
    assert marker.exists()
