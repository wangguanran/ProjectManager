"""Behavioural tests for the hook registration and execution helpers."""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List

import pytest

# Ensure the project source directory is importable when tests run in isolation.
# pylint: disable=wrong-import-position
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.hooks import (
    HookPriority,
    HookType,
    clear_hooks,
    execute_hooks,
    register_hook,
    validate_hooks,
)


@pytest.fixture(autouse=True)
def _clear_hooks_between_tests() -> None:
    """Ensure each test runs with an empty registry."""

    clear_hooks()


def test_execute_hook_binds_context_and_named_arguments() -> None:
    """Positional parameters beyond the context are populated from the context dict."""

    calls: List[Dict[str, Any]] = []

    def sample_hook(ctx: Dict[str, Any], board_name: str) -> bool:
        calls.append({"board": board_name, "value": ctx["value"]})
        return True

    register_hook(HookType.CUSTOM, "sample", sample_hook, priority=HookPriority.NORMAL)

    context = {"value": 7, "board_name": "demo"}
    assert execute_hooks(HookType.CUSTOM, context)
    assert calls == [{"board": "demo", "value": 7}]


def test_execute_hook_supports_keyword_only_context() -> None:
    """Hooks declaring a keyword-only context parameter receive it correctly."""

    captured: List[int] = []

    def keyword_only_hook(*, context: Dict[str, int]) -> None:
        captured.append(context["value"])

    register_hook(HookType.CUSTOM, "keyword_only", keyword_only_hook)

    assert execute_hooks(HookType.CUSTOM, {"value": 3})
    assert captured == [3]


def test_execute_hook_supports_kwargs_only_function() -> None:
    """Hooks with only ``**kwargs`` receive the full context mapping."""

    captured: List[Dict[str, Any]] = []

    def kwargs_only_hook(**kwargs: Any) -> None:
        captured.append(kwargs)

    register_hook(HookType.CUSTOM, "kwargs_only", kwargs_only_hook)

    context = {"value": 5, "extra": "info"}
    assert execute_hooks(HookType.CUSTOM, context)
    assert captured == [context]


def test_execute_hook_supports_varargs_context() -> None:
    """Hooks that rely on ``*args`` still receive the context dictionary."""

    captured: List[int] = []

    def varargs_hook(*args: Any) -> None:
        assert args
        captured.append(args[0]["value"])

    register_hook(HookType.CUSTOM, "varargs", varargs_hook)

    assert execute_hooks(HookType.CUSTOM, {"value": 11})
    assert captured == [11]


def test_execute_hook_missing_required_argument_reports_failure() -> None:
    """A missing required parameter surfaces as an execution failure."""

    def requires_missing(context: Dict[str, Any], required: int) -> None:  # pragma: no cover - exercised via hooks
        raise AssertionError("Should not be reached")

    register_hook(HookType.CUSTOM, "requires_missing", requires_missing)

    assert not execute_hooks(HookType.CUSTOM, {"value": 9}, stop_on_error=True)


def test_validate_hooks_flags_no_argument_hook() -> None:
    """Hooks without parameters are highlighted by validation."""

    def no_args_hook() -> None:  # pragma: no cover - invoked through validation metadata
        raise AssertionError("Should not be invoked")

    register_hook(HookType.CUSTOM, "no_args", no_args_hook)

    validation = validate_hooks(HookType.CUSTOM)
    assert not validation["valid"]
    assert validation["invalid_hooks"] == [
        {"name": "no_args", "error": "Function must accept at least one parameter"}
    ]
