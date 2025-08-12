"""
PlatformBuilder module for platform-specific project build logic using hooks.
"""

from src.hooks import HookPriority, HookType, hook
from src.log_manager import log


# Platform-specific hooks for board01 platform
@hook(
    hook_type=HookType.PRE_BUILD,
    name="platform_pre_build",
    priority=HookPriority.HIGH,
    platform="platform",
    description="Platform-specific pre-build setup for board01",
)
def platform_pre_build(context):
    """Platform-specific pre-build setup."""
    project_name = context["project_name"]
    platform = context["platform"]

    log.info("[PlatformBuilder] Platform-specific pre-build setup for %s on %s", project_name, platform)

    # Add platform-specific logic here
    # For example: set environment variables, create platform-specific directories, etc.

    return True


@hook(
    hook_type=HookType.BUILD,
    name="platform_build",
    priority=HookPriority.NORMAL,
    platform="platform",
    description="Platform-specific build logic for board01",
)
def platform_build(context):
    """Platform-specific build logic."""
    project_name = context["project_name"]
    platform = context["platform"]

    log.info("[PlatformBuilder] Platform-specific build logic for %s on %s", project_name, platform)

    # Add platform-specific build logic here
    # For example: compile platform-specific code, run platform tests, etc.

    return True


@hook(
    hook_type=HookType.POST_BUILD,
    name="platform_post_build",
    priority=HookPriority.NORMAL,
    platform="platform",
    description="Platform-specific post-build cleanup for board01",
)
def platform_post_build(context):
    """Platform-specific post-build cleanup."""
    project_name = context["project_name"]
    platform = context["platform"]

    log.info("[PlatformBuilder] Platform-specific post-build cleanup for %s on %s", project_name, platform)

    # Add platform-specific cleanup logic here
    # For example: clean temporary files, generate platform reports, etc.

    return True


@hook(
    hook_type=HookType.VALIDATION,
    name="platform_validation",
    priority=HookPriority.HIGH,
    platform="platform",
    description="Platform-specific validation for board01",
)
def platform_validation(context):
    """Platform-specific validation."""
    project_name = context["project_name"]
    platform = context["platform"]

    log.info("[PlatformBuilder] Platform-specific validation for %s on %s", project_name, platform)

    # Add platform-specific validation logic here
    # For example: check platform dependencies, validate configuration, etc.

    return True
