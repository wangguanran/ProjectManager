"""Guardrails for the PyInstaller build script."""

from pathlib import Path


def test_build_script_avoids_broad_collect_all_hooks() -> None:
    build_script = (Path(__file__).resolve().parents[2] / "build.sh").read_text(encoding="utf-8")

    assert "--collect-all=git" not in build_script
    assert "--collect-all=rich" not in build_script
    assert "--collect-all=textual" not in build_script
    assert "--collect-all=importlib_metadata" not in build_script
