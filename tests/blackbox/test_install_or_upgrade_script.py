"""Tests for the one-shot install-or-upgrade shell script."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "install-or-upgrade.sh"


def _write_executable(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


def test_install_or_upgrade_installs_when_projman_missing(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    calls_file = tmp_path / "calls.txt"
    fake_installer = tmp_path / "fake-installer.sh"
    _write_executable(
        fake_installer,
        f"""#!/usr/bin/env bash
set -euo pipefail
printf 'installer %s\\n' "$*" > "{calls_file}"
""",
    )

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}/usr/bin:/bin"
    env["PROJECTMANAGER_BOOTSTRAP_INSTALLER"] = str(fake_installer)

    result = subprocess.run(
        ["/bin/bash", str(SCRIPT), "--user", "--no-verify"],
        cwd=str(REPO_ROOT),
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert calls_file.read_text(encoding="utf-8") == "installer --user --no-verify\n"


def test_install_or_upgrade_updates_when_projman_exists(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    calls_file = tmp_path / "calls.txt"
    _write_executable(
        fake_bin / "projman",
        f"""#!/usr/bin/env bash
set -euo pipefail
printf 'projman %s\\n' "$*" > "{calls_file}"
""",
    )
    fake_installer = tmp_path / "fake-installer.sh"
    _write_executable(
        fake_installer,
        f"""#!/usr/bin/env bash
set -euo pipefail
printf 'installer %s\\n' "$*" >> "{calls_file}"
""",
    )

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}/usr/bin:/bin"
    env["PROJECTMANAGER_BOOTSTRAP_INSTALLER"] = str(fake_installer)

    result = subprocess.run(
        ["/bin/bash", str(SCRIPT), "--user", "--stable"],
        cwd=str(REPO_ROOT),
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert calls_file.read_text(encoding="utf-8") == "projman update --user --stable\n"
