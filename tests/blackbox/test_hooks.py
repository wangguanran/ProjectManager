"""Blackbox hook registry and execution tests."""

from __future__ import annotations

from src.hooks.executor import execute_hooks, execute_hooks_with_fallback, execute_single_hook, validate_hooks
from src.hooks.registry import HookPriority, HookType, clear_hooks, get_hooks, register_hook


def setup_function() -> None:
    clear_hooks()


def test_hook_001_priority_sorting() -> None:
    register_hook(HookType.BUILD, "low", lambda ctx: True, priority=HookPriority.LOW)
    register_hook(HookType.BUILD, "high", lambda ctx: True, priority=HookPriority.HIGH)
    hooks = get_hooks(HookType.BUILD)
    assert hooks[0]["name"] == "high"
    assert hooks[1]["name"] == "low"


def test_hook_002_overwrite_same_name() -> None:
    register_hook(HookType.BUILD, "dup", lambda ctx: "a", priority=HookPriority.NORMAL)
    register_hook(HookType.BUILD, "dup", lambda ctx: "b", priority=HookPriority.NORMAL)
    hooks = get_hooks(HookType.BUILD)
    assert len(hooks) == 1
    assert hooks[0]["func"]({}) == "b"


def test_hook_003_platform_and_global_merge() -> None:
    register_hook(HookType.BUILD, "global", lambda ctx: True)
    register_hook(HookType.BUILD, "platform", lambda ctx: True, platform="platA")
    hooks = get_hooks(HookType.BUILD, platform="platA")
    names = [h["name"] for h in hooks]
    assert "global" in names and "platform" in names


def test_hook_004_execute_stop_on_false() -> None:
    register_hook(HookType.BUILD, "fail", lambda ctx: False)
    register_hook(HookType.BUILD, "later", lambda ctx: True)
    assert execute_hooks(HookType.BUILD, {}) is False


def test_hook_005_execute_error_continue() -> None:
    def broken(ctx):
        raise ValueError("boom")

    register_hook(HookType.BUILD, "broken", broken)
    register_hook(HookType.BUILD, "ok", lambda ctx: True)
    assert execute_hooks(HookType.BUILD, {}, stop_on_error=False) is True


def test_hook_006_execute_single_missing() -> None:
    result = execute_single_hook(HookType.BUILD, "missing", {}, platform=None)
    assert result["success"] is False


def test_hook_007_validate_hook_signature() -> None:
    register_hook(HookType.BUILD, "bad", lambda: True)
    validation = validate_hooks(HookType.BUILD)
    assert validation["valid"] is False
    assert validation["invalid_hooks"]


def test_hook_008_fallback_to_global() -> None:
    register_hook(HookType.BUILD, "platform_fail", lambda ctx: False, platform="platA")
    register_hook(HookType.BUILD, "global_ok", lambda ctx: True)
    assert execute_hooks_with_fallback(HookType.BUILD, {}, platform="platA") is True
