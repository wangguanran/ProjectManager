"""Documentation consistency tests for command reference guides."""

from __future__ import annotations

import re
from importlib import import_module
from pathlib import Path

from src.operations.registry import get_registered_operations

REPO_ROOT = Path(__file__).resolve().parents[2]
EN_COMMAND_REFERENCE = REPO_ROOT / "docs" / "en" / "user-guide" / "command-reference.md"
ZH_COMMAND_REFERENCE = REPO_ROOT / "docs" / "zh" / "user-guide" / "command-reference.md"
PLUGIN_MODULES = (
    "src.plugins.project_manager",
    "src.plugins.project_builder",
    "src.plugins.patch_override",
    "src.plugins.doctor",
    "src.plugins.snapshot",
    "src.plugins.upgrader",
)


def _registered_operations() -> set[str]:
    for module_name in PLUGIN_MODULES:
        import_module(module_name)
    return set(get_registered_operations())


def _documented_commands(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    return set(re.findall(r"^### `([^`]+)`", text, re.MULTILINE))


def _heading_section(text: str, heading: str) -> str:
    pattern = rf"^### `{re.escape(heading)}`.*?(?=^### `|\Z)"
    match = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    assert match, f"Heading `{heading}` not found"
    return match.group(0)


def _syntax_block(text: str, heading: str) -> str:
    section = _heading_section(text, heading)
    match = re.search(r"```bash\n(.*?)\n```", section, re.DOTALL)
    assert match, f"Syntax block missing under `{heading}`"
    return match.group(1)


def test_command_reference_docs_cover_all_registered_commands() -> None:
    expected = _registered_operations()
    for path in (EN_COMMAND_REFERENCE, ZH_COMMAND_REFERENCE):
        assert _documented_commands(path) == expected


def test_command_reference_docs_list_key_global_safety_flags() -> None:
    expected_flags = ("--load-scripts", "--no-fuzzy", "--safe-mode", "--allow-network", "--yes")
    for path in (EN_COMMAND_REFERENCE, ZH_COMMAND_REFERENCE):
        text = path.read_text(encoding="utf-8")
        for flag in expected_flags:
            assert flag in text


def test_update_command_reference_syntax_includes_token_and_dry_run() -> None:
    for path in (EN_COMMAND_REFERENCE, ZH_COMMAND_REFERENCE):
        syntax = _syntax_block(path.read_text(encoding="utf-8"), "update")
        assert "--token <token>" in syntax
        assert "--dry-run" in syntax
