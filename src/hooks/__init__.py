"""
Hook system for extensible project building operations.
"""

from src.hooks.executor import (
    execute_global_hooks,
    execute_hooks,
    execute_hooks_with_fallback,
    execute_platform_hooks,
    execute_single_hook,
    validate_hooks,
)
from src.hooks.registry import (
    HookPriority,
    HookType,
    clear_hooks,
    get_global_hooks,
    get_hooks,
    get_platform_hooks,
    hook,
    list_hooks,
    register_global_hook,
    register_hook,
    register_platform_hook,
    unregister_hook,
)

__all__ = [
    # Enums
    "HookType",
    "HookPriority",
    # Decorators
    "hook",
    # Registration functions
    "register_hook",
    "register_global_hook",
    "register_platform_hook",
    # Query functions
    "get_hooks",
    "get_global_hooks",
    "get_platform_hooks",
    "list_hooks",
    # Management functions
    "unregister_hook",
    "clear_hooks",
    # Execution functions
    "execute_hooks",
    "execute_single_hook",
    "validate_hooks",
    "execute_global_hooks",
    "execute_platform_hooks",
    "execute_hooks_with_fallback",
]
