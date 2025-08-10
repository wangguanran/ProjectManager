"""
Hook registry system for extensible project building operations.
"""

import logging
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

log = logging.getLogger(__name__)

# Global hook registry instance
_hooks: Dict[str, List[Dict[str, Any]]] = {}
_platform_hooks: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}


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
    hook_type: Union[str, HookType],
    name: str,
    func: Callable,
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

    hook_info = {
        "name": name,
        "func": func,
        "priority": priority,
        "description": description,
        "platform": platform,
    }

    hook_list.append(hook_info)
    # Sort by priority (lower number = higher priority)
    hook_list.sort(key=lambda x: x["priority"].value)

    log.debug("Registered hook '%s' for type '%s' with priority %d", name, hook_type_str, priority.value)


def get_hooks(hook_type: Union[str, HookType], platform: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get all hooks for a specific type and optionally platform.

    Args:
        hook_type: Type of hooks to retrieve
        platform: Platform name if platform-specific hooks are needed

    Returns:
        List of hook information dictionaries
    """
    hook_type_str = hook_type.value if isinstance(hook_type, HookType) else str(hook_type)

    hooks = []

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


def unregister_hook(hook_type: Union[str, HookType], name: str, platform: Optional[str] = None) -> bool:
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


def list_hooks(hook_type: Optional[Union[str, HookType]] = None) -> Dict[str, Any]:
    """
    List all registered hooks.

    Args:
        hook_type: Optional hook type to filter by

    Returns:
        Dictionary containing hook information
    """
    result: Dict[str, Any] = {"global_hooks": {}, "platform_hooks": {}}

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
        result["global_hooks"] = _hooks.copy()
        result["platform_hooks"] = _platform_hooks.copy()

    return result


def clear_hooks(hook_type: Optional[Union[str, HookType]] = None, platform: Optional[str] = None) -> None:
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
    hook_type: Union[str, HookType],
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

    def decorator(func):
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


# Convenience functions for common operations
def register_global_hook(
    hook_type: Union[str, HookType],
    name: str,
    func: Callable,
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
    hook_type: Union[str, HookType],
    name: str,
    func: Callable,
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


def get_global_hooks(hook_type: Union[str, HookType]) -> List[Dict[str, Any]]:
    """Get only global hooks for a type."""
    return get_hooks(hook_type, None)


def get_platform_hooks(hook_type: Union[str, HookType], platform: str) -> List[Dict[str, Any]]:
    """Get only platform-specific hooks for a type and platform."""
    hook_type_str = hook_type.value if isinstance(hook_type, HookType) else str(hook_type)

    if platform in _platform_hooks and hook_type_str in _platform_hooks[platform]:
        return _platform_hooks[platform][hook_type_str].copy()
    return []
