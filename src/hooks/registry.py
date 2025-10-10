"""Registry primitives for registering and querying lifecycle hooks."""

from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple, TypedDict, Union

log = logging.getLogger(__name__)

class HookInfoBase(TypedDict):
    """Typed representation of the metadata stored for each hook."""

    name: str
    func: Callable[..., object]
    priority: "HookPriority"
    description: str
    platform: Optional[str]


@dataclass(frozen=True)
class HookSignatureSummary:
    """Pre-computed information about how to invoke a hook."""

    signature: inspect.Signature
    context_parameter: Optional[inspect.Parameter]


class HookInfo(HookInfoBase, total=False):
    """Extended metadata captured at registration time."""

    invocation: str
    parameters: Tuple[str, ...]
    signature_summary: HookSignatureSummary


HookTypeLike = Union[str, "HookType"]

_hooks: Dict[str, List[HookInfo]] = {}
_platform_hooks: Dict[str, Dict[str, List[HookInfo]]] = {}


class HookPriority(Enum):
    """Hook execution priority levels."""

    CRITICAL = 1
    HIGH = 10
    NORMAL = 50
    LOW = 100


class HookType(Enum):
    """Types of hooks that can be registered."""

    PRE_BUILD = "pre_build"
    BUILD = "build"
    POST_BUILD = "post_build"
    PRE_DIFF = "pre_diff"
    POST_DIFF = "post_diff"
    VALIDATION = "validation"
    CUSTOM = "custom"


def register_hook(
    hook_type: HookTypeLike,
    name: str,
    func: Callable[..., object],
    priority: HookPriority = HookPriority.NORMAL,
    platform: Optional[str] = None,
    description: str = "",
) -> None:
    """
    Register a hook function.

    Args:
        hook_type: Type of the hook
        name: Unique name for the hook
        func: Function to execute
        priority: Execution priority
        platform: Platform name if platform-specific
        description: Description of the hook
    """
    hook_type_str = hook_type.value if isinstance(hook_type, HookType) else str(hook_type)

    if platform:
        # Handle platform-specific hooks
        if platform not in _platform_hooks:
            _platform_hooks[platform] = {}
        if hook_type_str not in _platform_hooks[platform]:
            _platform_hooks[platform][hook_type_str] = []
        hook_list = _platform_hooks[platform][hook_type_str]
    else:
        # Handle global hooks
        if hook_type_str not in _hooks:
            _hooks[hook_type_str] = []
        hook_list = _hooks[hook_type_str]

    # Check if hook with same name already exists
    for existing_hook in hook_list:
        if existing_hook["name"] == name:
            log.warning("Hook '%s' already registered for type '%s', overwriting", name, hook_type_str)
            hook_list.remove(existing_hook)
            break

    invocation, parameters, summary = _summarise_hook_signature(func)

    hook_info: HookInfo = {
        "name": name,
        "func": func,
        "priority": priority,
        "description": description,
        "platform": platform,
    }

    if invocation:
        hook_info["invocation"] = invocation
    if parameters:
        hook_info["parameters"] = parameters
    if summary:
        hook_info["signature_summary"] = summary

    hook_list.append(hook_info)
    # Sort by priority (lower number = higher priority)
    hook_list.sort(key=lambda x: x["priority"].value)

    log.debug("Registered hook '%s' for type '%s' with priority %d", name, hook_type_str, priority.value)


def get_hooks(hook_type: HookTypeLike, platform: Optional[str] = None) -> List[HookInfo]:
    """
    Get all hooks for a specific type and optionally platform.

    Args:
        hook_type: Type of hooks to retrieve
        platform: Platform name if platform-specific hooks are needed

    Returns:
        List of hook information dictionaries
    """
    hook_type_str = hook_type.value if isinstance(hook_type, HookType) else str(hook_type)

    hooks: List[HookInfo] = []

    # Get global hooks
    if hook_type_str in _hooks:
        hooks.extend(_hooks[hook_type_str])

    # Get platform-specific hooks
    if platform and platform in _platform_hooks:
        if hook_type_str in _platform_hooks[platform]:
            hooks.extend(_platform_hooks[platform][hook_type_str])

    # Sort by priority
    hooks.sort(key=lambda x: x["priority"].value)

    return hooks


def unregister_hook(hook_type: HookTypeLike, name: str, platform: Optional[str] = None) -> bool:
    """
    Unregister a hook by name.

    Args:
        hook_type: Type of the hook
        name: Name of the hook to unregister
        platform: Platform name if platform-specific

    Returns:
        True if hook was unregistered, False if not found
    """
    hook_type_str = hook_type.value if isinstance(hook_type, HookType) else str(hook_type)

    if platform:
        if platform not in _platform_hooks or hook_type_str not in _platform_hooks[platform]:
            return False
        hook_list = _platform_hooks[platform][hook_type_str]
    else:
        if hook_type_str not in _hooks:
            return False
        hook_list = _hooks[hook_type_str]

    for i, hook_item in enumerate(hook_list):
        if hook_item["name"] == name:
            hook_list.pop(i)
            log.debug("Unregistered hook '%s' for type '%s'", name, hook_type_str)
            return True

    return False


def list_hooks(hook_type: Optional[HookTypeLike] = None) -> Dict[str, Dict[str, List[HookInfo]]]:
    """
    List all registered hooks.

    Args:
        hook_type: Optional hook type to filter by

    Returns:
        Dictionary containing hook information
    """
    result: Dict[str, Dict[str, List[HookInfo]]] = {"global_hooks": {}, "platform_hooks": {}}

    if hook_type:
        hook_type_str = hook_type.value if isinstance(hook_type, HookType) else str(hook_type)
        if hook_type_str in _hooks:
            result["global_hooks"][hook_type_str] = _hooks[hook_type_str]

        for platform, platform_hooks in _platform_hooks.items():
            if hook_type_str in platform_hooks:
                if platform not in result["platform_hooks"]:
                    result["platform_hooks"][platform] = {}
                result["platform_hooks"][platform][hook_type_str] = platform_hooks[hook_type_str]
    else:
        result["global_hooks"] = {k: v.copy() for k, v in _hooks.items()}
        result["platform_hooks"] = {
            platform: {k: v.copy() for k, v in hooks.items()} for platform, hooks in _platform_hooks.items()
        }

    return result


def clear_hooks(hook_type: Optional[HookTypeLike] = None, platform: Optional[str] = None) -> None:
    """
    Clear all hooks or hooks of a specific type/platform.

    Args:
        hook_type: Optional hook type to clear
        platform: Optional platform to clear
    """
    if platform:
        if platform in _platform_hooks:
            if hook_type:
                hook_type_str = hook_type.value if isinstance(hook_type, HookType) else str(hook_type)
                if hook_type_str in _platform_hooks[platform]:
                    del _platform_hooks[platform][hook_type_str]
            else:
                del _platform_hooks[platform]
    else:
        if hook_type:
            hook_type_str = hook_type.value if isinstance(hook_type, HookType) else str(hook_type)
            if hook_type_str in _hooks:
                del _hooks[hook_type_str]
        else:
            _hooks.clear()
            _platform_hooks.clear()


def hook(
    hook_type: HookTypeLike,
    name: str,
    priority: HookPriority = HookPriority.NORMAL,
    platform: Optional[str] = None,
    description: str = "",
):
    """
    Decorator for registering hooks.

    Args:
        hook_type: Type of the hook
        name: Unique name for the hook
        priority: Execution priority
        platform: Platform name if platform-specific
        description: Description of the hook
    """

    def decorator(func: Callable[..., object]):
        register_hook(
            hook_type=hook_type,
            name=name,
            func=func,
            priority=priority,
            platform=platform,
            description=description,
        )
        return func

    return decorator


def _summarise_hook_signature(
    func: Callable[..., object],
) -> Tuple[str, Tuple[str, ...], Optional[HookSignatureSummary]]:
    """Return how a hook function prefers to receive the execution context."""

    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):
        return ("unknown", (), None)

    parameters = tuple(signature.parameters.values())
    if not parameters:
        return ("no_args", (), HookSignatureSummary(signature=signature, context_parameter=None))

    context_parameter: Optional[inspect.Parameter] = None

    for parameter in parameters:
        if parameter.name == "context":
            context_parameter = parameter
            break

    if context_parameter is None:
        for parameter in parameters:
            if parameter.kind in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.VAR_POSITIONAL,
            ):
                context_parameter = parameter
                break

    if context_parameter and context_parameter.kind == inspect.Parameter.KEYWORD_ONLY:
        invocation = "context_keyword"
    elif context_parameter is None and any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in parameters
    ):
        invocation = "kwargs"
    else:
        invocation = "positional"

    return (
        invocation,
        tuple(parameter.name for parameter in parameters),
        HookSignatureSummary(signature=signature, context_parameter=context_parameter),
    )


# Convenience functions for common operations
def register_global_hook(
    hook_type: HookTypeLike,
    name: str,
    func: Callable[..., object],
    priority: HookPriority = HookPriority.NORMAL,
    description: str = "",
) -> None:
    """
    Register a global hook function.

    Args:
        hook_type: Type of the hook
        name: Unique name for the hook
        func: Function to execute
        priority: Execution priority
        description: Description of the hook
    """
    register_hook(hook_type, name, func, priority, None, description)


def register_platform_hook(
    hook_type: HookTypeLike,
    name: str,
    func: Callable[..., object],
    platform: str,
    priority: HookPriority = HookPriority.NORMAL,
    description: str = "",
) -> None:
    """
    Register a platform-specific hook function.

    Args:
        hook_type: Type of the hook
        name: Unique name for the hook
        func: Function to execute
        platform: Platform name
        priority: Execution priority
        description: Description of the hook
    """
    register_hook(hook_type, name, func, priority, platform, description)


def get_global_hooks(hook_type: HookTypeLike) -> List[HookInfo]:
    """Get only global hooks for a type."""
    return get_hooks(hook_type, None)


def get_platform_hooks(hook_type: HookTypeLike, platform: str) -> List[HookInfo]:
    """Get only platform-specific hooks for a type and platform."""
    hook_type_str = hook_type.value if isinstance(hook_type, HookType) else str(hook_type)

    if platform in _platform_hooks and hook_type_str in _platform_hooks[platform]:
        return _platform_hooks[platform][hook_type_str].copy()
    return []
