"""
Hook system tests derived from docs/test_cases_en.md (HOOK-001..HOOK-008).
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List

import pytest

# Ensure repo root is importable (some tests modify sys.path to point at ./src).
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.hooks import (
    HookPriority,
    HookType,
    clear_hooks,
    execute_hooks,
    execute_hooks_with_fallback,
    execute_single_hook,
    get_hooks,
    register_hook,
    validate_hooks,
)


@pytest.fixture(autouse=True)
def _clean_hooks() -> None:
    clear_hooks()
    yield
    clear_hooks()


def test_hooks_sorted_by_priority() -> None:
    """HOOK-001: Global hooks sorted by priority."""
    calls: List[str] = []

    def hi(ctx: Dict[str, Any]) -> bool:
        calls.append("hi")
        return True

    def lo(ctx: Dict[str, Any]) -> bool:
        calls.append("lo")
        return True

    register_hook(HookType.BUILD, "lo", lo, priority=HookPriority.LOW)
    register_hook(HookType.BUILD, "hi", hi, priority=HookPriority.HIGH)

    hooks = get_hooks(HookType.BUILD)
    assert [h["name"] for h in hooks] == ["hi", "lo"]


def test_hook_overwrite_by_name() -> None:
    """HOOK-002: Same-name hook overwrites."""

    def f1(ctx: Dict[str, Any]) -> bool:
        _ = ctx
        return True

    def f2(ctx: Dict[str, Any]) -> bool:
        _ = ctx
        return True

    register_hook(HookType.CUSTOM, "dup", f1)
    register_hook(HookType.CUSTOM, "dup", f2)

    hooks = get_hooks(HookType.CUSTOM)
    assert len(hooks) == 1
    assert hooks[0]["func"] is f2


def test_platform_hooks_merged_with_global() -> None:
    """HOOK-003: Platform hooks merged with global."""

    def g(ctx: Dict[str, Any]) -> bool:
        _ = ctx
        return True

    def p(ctx: Dict[str, Any]) -> bool:
        _ = ctx
        return True

    register_hook(HookType.BUILD, "global", g, priority=HookPriority.NORMAL)
    register_hook(HookType.BUILD, "plat", p, priority=HookPriority.NORMAL, platform="platA")

    hooks = get_hooks(HookType.BUILD, platform="platA")
    names = {h["name"] for h in hooks}
    assert names == {"global", "plat"}


def test_hook_return_false_stops_execution() -> None:
    """HOOK-004: Hook returning False stops execution."""
    calls: List[str] = []

    def bad(ctx: Dict[str, Any]) -> bool:
        _ = ctx
        calls.append("bad")
        return False

    def good(ctx: Dict[str, Any]) -> bool:
        _ = ctx
        calls.append("good")
        return True

    register_hook(HookType.VALIDATION, "bad", bad, priority=HookPriority.HIGH)
    register_hook(HookType.VALIDATION, "good", good, priority=HookPriority.LOW)

    ok = execute_hooks(HookType.VALIDATION, context={})
    assert ok is False
    assert calls == ["bad"]


def test_hook_exception_continues_when_stop_on_error_false() -> None:
    """HOOK-005: Exception with stop_on_error=False continues."""
    calls: List[str] = []

    def boom(ctx: Dict[str, Any]) -> bool:
        _ = ctx
        calls.append("boom")
        raise ValueError("x")

    def good(ctx: Dict[str, Any]) -> bool:
        _ = ctx
        calls.append("good")
        return True

    register_hook(HookType.PRE_BUILD, "boom", boom, priority=HookPriority.HIGH)
    register_hook(HookType.PRE_BUILD, "good", good, priority=HookPriority.LOW)

    ok = execute_hooks(HookType.PRE_BUILD, context={}, stop_on_error=False)
    assert ok is True
    assert calls == ["boom", "good"]


def test_execute_single_hook_not_found() -> None:
    """HOOK-006: execute_single_hook not found."""
    res = execute_single_hook(HookType.CUSTOM, "missing", context={})
    assert res["success"] is False
    assert "not found" in str(res.get("error", "")).lower()


def test_validate_hooks_no_arg_invalid() -> None:
    """HOOK-007: No-arg hook is invalid."""

    def noargs() -> bool:
        return True

    register_hook(HookType.CUSTOM, "noargs", noargs)
    res = validate_hooks(HookType.CUSTOM)
    assert res["valid"] is False
    assert any(item["name"] == "noargs" for item in res["invalid_hooks"])


def test_execute_hooks_with_fallback_platform_failure_falls_back_to_global() -> None:
    """HOOK-008: Platform failure falls back to global."""

    def plat(ctx: Dict[str, Any]) -> bool:
        _ = ctx
        return False

    def glob(ctx: Dict[str, Any]) -> bool:
        _ = ctx
        return True

    register_hook(HookType.BUILD, "plat", plat, platform="platA")
    register_hook(HookType.BUILD, "glob", glob)

    ok = execute_hooks_with_fallback(HookType.BUILD, context={}, platform="platA")
    assert ok is True
