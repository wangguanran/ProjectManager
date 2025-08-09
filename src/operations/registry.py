"""
Simple registry for function-based operations.
"""

from __future__ import annotations

from typing import Any, Callable, Dict

REGISTRY: Dict[str, Callable[..., Any]] = {}


def register(
    name: str | None = None,
    *,
    needs_repositories: bool = False,
    desc: str | None = None,
):
    """
    Decorator to register a function as a CLI operation.

    - name: operation name to expose; defaults to function.__name__
    - needs_repositories: mark if operation requires repositories discovery
    - desc: one-line description for help text
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        op_name = name or func.__name__
        # attach light metadata to function object
        setattr(
            func,
            "_operation_meta",
            {
                "needs_repositories": bool(needs_repositories),
                "desc": desc or (func.__doc__.strip().splitlines()[0] if func.__doc__ else "plugin operation"),
            },
        )
        REGISTRY[op_name] = func
        return func

    return decorator


def get_registered_operations() -> Dict[str, Dict[str, Any]]:
    """
    Return a mapping op_name -> info dict compatible with __main__ expectations.
    """
    ops: Dict[str, Dict[str, Any]] = {}
    for name, func in REGISTRY.items():
        # Build signature-like info lazily in __main__ to avoid import cycles
        ops[name] = {"func": func}
    return ops
