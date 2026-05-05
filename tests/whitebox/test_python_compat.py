"""Python version compatibility checks for declared support versions."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

STARTUP_IMPORT_PATHS = [
    REPO_ROOT / "src" / "__main__.py",
    REPO_ROOT / "src" / "operations" / "registry.py",
    REPO_ROOT / "src" / "plugins" / "po_plugins" / "runtime.py",
    REPO_ROOT / "src" / "plugins" / "po_plugins" / "registry.py",
]


def _relative_path(source_path: Path) -> str:
    return str(source_path.relative_to(REPO_ROOT))


def _has_bit_or_union(annotation: ast.AST) -> bool:
    return any(isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr) for node in ast.walk(annotation))


def test_startup_import_sources_parse_as_python38() -> None:
    for source_path in STARTUP_IMPORT_PATHS:
        source = source_path.read_text(encoding="utf-8")

        ast.parse(source, filename=str(source_path), feature_version=(3, 8))


def test_startup_import_sources_avoid_python310_union_type_syntax() -> None:
    union_type_annotations = []
    for source_path in STARTUP_IMPORT_PATHS:
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))

        for node in ast.walk(tree):
            annotation = getattr(node, "annotation", None)
            if isinstance(annotation, ast.AST) and _has_bit_or_union(annotation):
                union_type_annotations.append((_relative_path(source_path), annotation.lineno, annotation.col_offset))

            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                returns = node.returns
                if returns is not None and _has_bit_or_union(returns):
                    union_type_annotations.append((_relative_path(source_path), returns.lineno, returns.col_offset))

    assert union_type_annotations == []
