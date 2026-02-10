"""
Internal plugin registry for PO (Patch/Override) types.

Plugins are registered by importing modules under `src/plugins/po_plugins/`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List

from .runtime import PoPluginContext, PoPluginRuntime

APPLY_PHASE_GLOBAL_PRE = "global_pre"
APPLY_PHASE_PER_PO = "per_po"

REVERT_PHASE_PER_PO = "per_po"
REVERT_PHASE_GLOBAL_POST = "global_post"


@dataclass(frozen=True)
class PoPlugin:
    name: str
    apply_phase: str
    apply_order: int
    revert_phase: str
    revert_order: int
    apply: Callable[[PoPluginContext, PoPluginRuntime], bool]
    revert: Callable[[PoPluginContext, PoPluginRuntime], bool]
    list_files: Callable[[str, PoPluginRuntime], Dict[str, Any]]
    ensure_structure: Callable[[str, bool], None]


_PLUGINS: List[PoPlugin] = []


def _noop_list_files(_po_path: str, _runtime: PoPluginRuntime) -> Dict[str, Any]:
    return {}


def _noop_ensure_structure(_po_path: str, _force: bool) -> None:
    return


def register_plugin(plugin: PoPlugin) -> None:
    if any(existing.name == plugin.name for existing in _PLUGINS):
        raise ValueError(f"PO plugin already registered: {plugin.name}")
    _PLUGINS.append(plugin)


def register_simple_plugin(
    *,
    name: str,
    apply_phase: str,
    apply_order: int,
    revert_phase: str,
    revert_order: int,
    apply: Callable[[PoPluginContext, PoPluginRuntime], bool],
    revert: Callable[[PoPluginContext, PoPluginRuntime], bool],
    list_files: Callable[[str, PoPluginRuntime], Dict[str, Any]] | None = None,
    ensure_structure: Callable[[str, bool], None] | None = None,
) -> None:
    register_plugin(
        PoPlugin(
            name=name,
            apply_phase=apply_phase,
            apply_order=apply_order,
            revert_phase=revert_phase,
            revert_order=revert_order,
            apply=apply,
            revert=revert,
            list_files=list_files or _noop_list_files,
            ensure_structure=ensure_structure or _noop_ensure_structure,
        )
    )


def get_po_plugins() -> List[PoPlugin]:
    # Lazy-load built-in plugins on first access to avoid requiring callers
    # to import the package for side effects.
    if not _PLUGINS:
        from importlib import import_module

        import_module("src.plugins.po_plugins")
    return list(_PLUGINS)
