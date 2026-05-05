"""Regression tests for testing documentation command references."""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TESTING_DOCS = (
    REPO_ROOT / "docs/en/development/testing.md",
    REPO_ROOT / "docs/zh/development/testing.md",
)
PATH_REFERENCE_PATTERN = re.compile(
    r"(?<![\w/.-])(?:\./)?(?:git-hooks|hooks|tests)/[A-Za-z0-9_./:-]+|requirements-[A-Za-z0-9_.-]+\.txt"
)
BASH_BLOCK_PATTERN = re.compile(r"```bash\n(?P<body>.*?)\n```", re.DOTALL)
HOOK_TOOL_PATTERN = re.compile(r"`(?P<path>(?:\./)?(?:git-hooks|hooks)/[A-Za-z0-9_./:-]+)`")


def _command_reference_text(markdown: str) -> str:
    command_blocks = [match.group("body") for match in BASH_BLOCK_PATTERN.finditer(markdown)]
    hook_tools = [match.group("path") for match in HOOK_TOOL_PATTERN.finditer(markdown)]
    return "\n".join(command_blocks + hook_tools)


def _referenced_repo_paths(markdown: str):
    for match in PATH_REFERENCE_PATTERN.finditer(_command_reference_text(markdown)):
        reference = match.group(0).split("::", 1)[0].rstrip("`.,;)")
        yield reference[2:] if reference.startswith("./") else reference


def test_extracts_inline_git_hooks_references():
    markdown = "**Tools**: Git hooks (`git-hooks/pre-commit`)"

    assert list(_referenced_repo_paths(markdown)) == ["git-hooks/pre-commit"]


def test_testing_docs_only_reference_existing_repo_paths():
    """Testing docs should not send contributors to removed files or directories."""
    missing = []
    for doc_path in TESTING_DOCS:
        markdown = doc_path.read_text(encoding="utf-8")
        for reference in _referenced_repo_paths(markdown):
            if not (REPO_ROOT / reference).exists():
                missing.append(f"{doc_path.relative_to(REPO_ROOT)} -> {reference}")

    assert not missing, "Missing testing doc command paths:\n" + "\n".join(missing)
