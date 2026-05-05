"""
Hook execution engine for extensible project building operations.
"""

import logging
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from src.hooks.registry import HookType, get_hooks

log = logging.getLogger(__name__)


def _hook_key(hook_info: Dict[str, Any]) -> Tuple[Optional[str], str]:
    """Return a stable key for a registered hook within one execution pass."""
    return (hook_info.get("platform"), str(hook_info["name"]))


def _execute_hook_list(
    hook_type: Union[str, "HookType"],
    hooks: List[Dict[str, Any]],
    context: Dict[str, Any],
    stop_on_error: bool = False,
    executed_hooks: Optional[Set[Tuple[Optional[str], str]]] = None,
) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """Execute hook info dictionaries and return the first failing hook."""
    if not hooks:
        log.debug("No hooks found for type '%s'", hook_type)
        return True, None

    log.debug("Executing %d hooks for type '%s'", len(hooks), hook_type)

    for hook_info in hooks:
        hook_name = hook_info["name"]
        hook_func = hook_info["func"]
        hook_priority = hook_info["priority"]

        if executed_hooks is not None:
            executed_hooks.add(_hook_key(hook_info))

        try:
            log.debug("Executing hook '%s' with priority %d", hook_name, hook_priority.value)

            # Execute the hook function
            hook_result = hook_func(context)

            # Check if hook returned False (failure)
            if hook_result is False:
                log.error("Hook '%s' returned False, indicating failure", hook_name)
                return False, hook_info

            log.debug("Hook '%s' executed successfully", hook_name)

        except Exception as e:  # pylint: disable=broad-exception-caught
            error_msg = f"Error executing hook '{hook_name}': {str(e)}"
            log.error(error_msg)

            if stop_on_error:
                log.error("Stopping hook execution due to error in '%s'", hook_name)
                return False, hook_info

    log.debug("All hooks for type '%s' executed successfully", hook_type)
    return True, None


def execute_hooks(
    hook_type: Union[str, "HookType"],
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
    hooks = get_hooks(hook_type, platform)
    result, _failed_hook = _execute_hook_list(hook_type, hooks, context, stop_on_error)
    return result


def execute_single_hook(
    hook_type: Union[str, "HookType"], hook_name: str, context: Dict[str, Any], platform: Optional[str] = None
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
                hook_result = hook_info["func"](context)
                return {"success": True, "hook_name": hook_name, "result": hook_result}
            except Exception as e:  # pylint: disable=broad-exception-caught
                return {"success": False, "hook_name": hook_name, "error": str(e)}

    return {
        "success": False,
        "hook_name": hook_name,
        "error": f"Hook '{hook_name}' not found for type '{hook_type}'",
    }


def validate_hooks(hook_type: Union[str, "HookType"], platform: Optional[str] = None) -> Dict[str, Any]:
    """
    Validate that all hooks for a type can be loaded without errors.

    Args:
        hook_type: Type of hooks to validate
        platform: Platform name for platform-specific hooks

    Returns:
        Dictionary containing validation results
    """
    hooks = get_hooks(hook_type, platform)

    validation_results: Dict[str, Any] = {
        "valid": True,
        "total_hooks": len(hooks),
        "valid_hooks": [],
        "invalid_hooks": [],
    }

    for hook_info in hooks:
        hook_name = hook_info["name"]
        hook_func = hook_info["func"]

        try:
            # Try to get function signature to validate it can be called
            import inspect

            sig = inspect.signature(hook_func)

            # execute_hooks calls hook_func(context), so validate the same call shape.
            sig.bind(object())
            validation_results["valid_hooks"].append(
                {"name": hook_name, "description": hook_info.get("description", "")}
            )

        except TypeError as e:
            validation_results["invalid_hooks"].append(
                {"name": hook_name, "error": f"Function must be callable with one context argument: {str(e)}"}
            )
            validation_results["valid"] = False

        except (RuntimeError, ValueError, OSError) as e:
            validation_results["invalid_hooks"].append({"name": hook_name, "error": f"Validation error: {str(e)}"})
            validation_results["valid"] = False

    return validation_results


# Convenience functions for common operations
def execute_global_hooks(
    hook_type: Union[str, "HookType"], context: Dict[str, Any], stop_on_error: bool = False
) -> bool:
    """Execute only global hooks for a type."""
    return execute_hooks(hook_type, context, None, stop_on_error)


def execute_platform_hooks(
    hook_type: Union[str, "HookType"], context: Dict[str, Any], platform: str, stop_on_error: bool = False
) -> bool:
    """Execute only platform-specific hooks for a type and platform."""
    return execute_hooks(hook_type, context, platform, stop_on_error)


def execute_hooks_with_fallback(
    hook_type: Union[str, "HookType"],
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

    # Try merged global/platform hooks first
    executed_hooks: Set[Tuple[Optional[str], str]] = set()
    platform_hooks = get_hooks(hook_type, platform)
    platform_result, failed_hook = _execute_hook_list(hook_type, platform_hooks, context, executed_hooks=executed_hooks)

    if platform_result or not fallback_to_global:
        return platform_result

    if failed_hook is not None and failed_hook.get("platform") is None:
        return False

    # Fall back to global hooks
    log.info("Platform hooks failed for %s, falling back to global hooks", platform)
    fallback_hooks = [hook for hook in get_hooks(hook_type, None) if _hook_key(hook) not in executed_hooks]
    fallback_result, _failed_hook = _execute_hook_list(
        hook_type, fallback_hooks, context, executed_hooks=executed_hooks
    )
    return fallback_result
