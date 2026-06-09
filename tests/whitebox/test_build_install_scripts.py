"""Static tests for build/install shell script defaults."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_build_script_defaults_to_python_package_only() -> None:
    script = (ROOT / "build.sh").read_text(encoding="utf-8")

    assert 'BUILD_STANDALONE="${BUILD_STANDALONE:-0}"' in script
    assert "--standalone" in script
    assert 'if [ "$BUILD_STANDALONE" != "1" ]; then' in script

    package_index = script.index("--- Building Python package ---")
    guard_index = script.index('if [ "$BUILD_STANDALONE" != "1" ]; then')
    standalone_index = script.index("--- Building standalone binary with pyinstaller ---")
    assert package_index < guard_index < standalone_index


def test_install_script_defaults_to_package_venv_and_keeps_standalone_mode() -> None:
    script = (ROOT / "install.sh").read_text(encoding="utf-8")

    assert "--standalone" in script
    assert 'INSTALL_STANDALONE="0"' in script
    assert 'if [ "$INSTALL_STANDALONE" = "1" ]; then' in script
    assert "-m venv" in script
    assert '-m pip install --force-reinstall "$wheel_path"' in script
    assert "Please run ./build.sh --standalone first." in script

    dispatch_index = script.index('if [ "$INSTALL_STANDALONE" = "1" ]; then')
    assert script.index("install_standalone", dispatch_index) < script.index("install_package", dispatch_index)
