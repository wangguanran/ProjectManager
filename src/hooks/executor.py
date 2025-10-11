"""Execution utilities for running registered hooks."""

from __future__ import annotations

import inspect
import logging
from typing import Any, Dict, Optional

from src.hooks.registry import HookInfo, HookSignatureSummary, HookTypeLike, get_hooks

log = logging.getLogger(__name__)


def execute_hooks(
    hook_type: HookTypeLike,
    context: Dict[str, Any],
    platform: Optional[str] = None,
    stop_on_error: bool = False,
) -> bool:
    """
    Execute all hooks of a specific type.

    Args:
        hook_type: Type of hooks to execute
        context: Context data passed to hooks
        platform: Platform name for platform-specific hooks
        stop_on_error: Whether to stop execution on first error

    Returns:
        True if all hooks executed successfully, False otherwise
    """
    hooks: list[HookInfo] = get_hooks(hook_type, platform)

    if not hooks:
        log.debug("No hooks found for type '%s'", hook_type)
        return True

    log.debug("Executing %d hooks for type '%s'", len(hooks), hook_type)

    for hook_info in hooks:
        hook_name = hook_info["name"]
        hook_priority = hook_info["priority"]

        try:
            log.debug("Executing hook '%s' with priority %d", hook_name, hook_priority.value)

            hook_result = _invoke_hook(hook_info, context)

            # Check if hook returned False (failure)
            if hook_result is False:
                log.error("Hook '%s' returned False, indicating failure", hook_name)
                return False

            log.debug("Hook '%s' executed successfully", hook_name)

        except (RuntimeError, ValueError, TypeError, OSError, AttributeError) as exc:
            log.error("Error executing hook '%s': %s", hook_name, exc)

            if stop_on_error:
                log.error("Stopping hook execution due to error in '%s'", hook_name)
                return False

    log.debug("All hooks for type '%s' executed successfully", hook_type)
    return True


def execute_single_hook(
    hook_type: HookTypeLike, hook_name: str, context: Dict[str, Any], platform: Optional[str] = None
) -> Dict[str, Any]:
    """
    Execute a specific hook by name.

    Args:
        hook_type: Type of the hook
        hook_name: Name of the specific hook to execute
        context: Context data passed to the hook
        platform: Platform name for platform-specific hooks

    Returns:
        Dictionary containing execution result
    """
    hooks = get_hooks(hook_type, platform)

    for hook_info in hooks:
        if hook_info["name"] == hook_name:
            try:
                hook_result = _invoke_hook(hook_info, context)
                return {"success": True, "hook_name": hook_name, "result": hook_result}
            except (RuntimeError, ValueError, TypeError, OSError) as exc:
                return {"success": False, "hook_name": hook_name, "error": str(exc)}

    return {
        "success": False,
        "hook_name": hook_name,
        "error": f"Hook '{hook_name}' not found for type '{hook_type}'",
    }


def validate_hooks(hook_type: HookTypeLike, platform: Optional[str] = None) -> Dict[str, Any]:
    """
    Validate that all hooks for a type can be loaded without errors.

    Args:
        hook_type: Type of hooks to validate
        platform: Platform name for platform-specific hooks

    Returns:
        Dictionary containing validation results
    """
    hooks: list[HookInfo] = get_hooks(hook_type, platform)

    validation_results: Dict[str, Any] = {
        "valid": True,
        "total_hooks": len(hooks),
        "valid_hooks": [],
        "invalid_hooks": [],
    }

    for hook_info in hooks:
        hook_name = hook_info["name"]

        try:
            invocation = hook_info.get("invocation", "positional")
            if invocation == "no_args":
                validation_results["invalid_hooks"].append(
                    {"name": hook_name, "error": "Function must accept at least one parameter"}
                )
                validation_results["valid"] = False
            else:
                entry = {"name": hook_name, "description": hook_info.get("description", "")}
                if invocation == "unknown":
                    entry["note"] = "Signature inspection unavailable"
                validation_results["valid_hooks"].append(entry)

        except (RuntimeError, ValueError, TypeError, OSError) as exc:
            validation_results["invalid_hooks"].append({"name": hook_name, "error": f"Validation error: {str(exc)}"})
            validation_results["valid"] = False

    return validation_results


def _invoke_hook(hook_info: HookInfo, context: Dict[str, Any]) -> Any:
    """Invoke a hook using the preferred calling convention captured at registration."""

    hook_func = hook_info["func"]
    summary: HookSignatureSummary | None = hook_info.get("signature_summary")

    if summary:
        return _invoke_with_signature_summary(hook_info, summary, context)

    invocation = hook_info.get("invocation", "positional")

    if invocation == "no_args":
        return hook_func()
    if invocation == "context_keyword":
        return hook_func(context=context)
    if invocation == "kwargs":
        return hook_func(**context)

    # Default behaviour matches the historical calling convention
    return hook_func(context)


def _invoke_with_signature_summary(
    hook_info: HookInfo, summary: HookSignatureSummary, context: Dict[str, Any]
) -> Any:
    """Construct arguments based on a captured signature summary and invoke the hook."""

    hook_func = hook_info["func"]
    signature = summary.signature

    if not signature.parameters:
        return hook_func()

    context_param = summary.context_parameter
    positional_arguments: list[Any] = []
    keyword_arguments: Dict[str, Any] = {}
    remaining_context: Dict[str, Any] = dict(context)

    for parameter in signature.parameters.values():
        name = parameter.name
        kind = parameter.kind

        if parameter is context_param:
            if kind in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            ):
                positional_arguments.append(context)
            elif kind == inspect.Parameter.KEYWORD_ONLY:
                keyword_arguments[name] = context
            elif kind == inspect.Parameter.VAR_POSITIONAL:
                positional_arguments.append(context)
            elif kind == inspect.Parameter.VAR_KEYWORD:
                keyword_arguments.update(remaining_context)
                remaining_context.clear()
            remaining_context.pop(name, None)
            continue

        if kind == inspect.Parameter.VAR_POSITIONAL:
            continue

        if kind == inspect.Parameter.VAR_KEYWORD:
            keyword_arguments.update(remaining_context)
            remaining_context.clear()
            continue

        if name in remaining_context:
            value = remaining_context.pop(name)
            if kind in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            ):
                positional_arguments.append(value)
            else:
                keyword_arguments[name] = value
            continue

        if parameter.default is not inspect.Signature.empty:
            if kind in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            ):
                positional_arguments.append(parameter.default)
            else:
                keyword_arguments[name] = parameter.default
            continue

        raise TypeError(
            f"Missing required context value '{name}' for hook '{hook_info['name']}'"
        )

    return hook_func(*positional_arguments, **keyword_arguments)


# Convenience functions for common operations
def execute_global_hooks(
    hook_type: HookTypeLike, context: Dict[str, Any], stop_on_error: bool = False
) -> bool:
    """Execute only global hooks for a type."""
    return execute_hooks(hook_type, context, None, stop_on_error)


def execute_platform_hooks(
    hook_type: HookTypeLike, context: Dict[str, Any], platform: str, stop_on_error: bool = False
) -> bool:
    """Execute only platform-specific hooks for a type and platform."""
    return execute_hooks(hook_type, context, platform, stop_on_error)


def execute_hooks_with_fallback(
    hook_type: HookTypeLike,
    context: Dict[str, Any],
    platform: Optional[str] = None,
    fallback_to_global: bool = True,
) -> bool:
    """
    Execute hooks with fallback to global hooks if platform hooks fail.

    Args:
        hook_type: Type of hooks to execute
        context: Context data passed to hooks
        platform: Platform name for platform-specific hooks
        fallback_to_global: Whether to fall back to global hooks if platform hooks fail

    Returns:
        True if hooks executed successfully, False otherwise
    """
    if not platform:
        return execute_hooks(hook_type, context, None)

    # Try platform-specific hooks first
    platform_result = execute_hooks(hook_type, context, platform)

    if platform_result or not fallback_to_global:
        return platform_result

    # Fall back to global hooks
    log.info("Platform hooks failed for %s, falling back to global hooks", platform)
    return execute_hooks(hook_type, context, None)
