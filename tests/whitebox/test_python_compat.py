"""Python version compatibility checks for declared support versions."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_operation_registry_source_parses_as_python39() -> None:
    source_path = REPO_ROOT / "src" / "operations" / "registry.py"
    source = source_path.read_text(encoding="utf-8")

    ast.parse(source, filename=str(source_path), feature_version=(3, 9))


def test_operation_registry_avoids_python310_union_type_syntax() -> None:
    source_path = REPO_ROOT / "src" / "operations" / "registry.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))

    union_type_annotations = []
    for node in ast.walk(tree):
        annotation = getattr(node, "annotation", None)
        if isinstance(annotation, ast.BinOp) and isinstance(annotation.op, ast.BitOr):
            union_type_annotations.append((annotation.lineno, annotation.col_offset))

    assert union_type_annotations == []
