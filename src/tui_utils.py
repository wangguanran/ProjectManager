"""Optional TUI helpers.

This module intentionally imports optional dependencies lazily, so that the
default CLI remains usable without extra packages.
"""

from __future__ import annotations

import sys
from typing import Any, Tuple

INSTALL_HINT = 'pip install -e ".[tui]"'


class TuiUnavailable(RuntimeError):
    """Raised when TUI mode cannot be used (missing deps or no TTY)."""


def _is_tty() -> bool:
    try:
        return bool(sys.stdin.isatty() and sys.stdout.isatty())
    except (AttributeError, OSError, ValueError):  # pragma: no cover
        return False


def get_questionary(*, require_tty: bool = True) -> Any:
    """Import and return `questionary`, raising a user-friendly error if unavailable."""
    if require_tty and not _is_tty():
        raise TuiUnavailable("TUI requires an interactive TTY (stdin/stdout).")

    try:
        import questionary  # type: ignore
    except ModuleNotFoundError as exc:
        raise TuiUnavailable(f"TUI dependency is not installed. Install it with: {INSTALL_HINT}") from exc

    return questionary


def tui_available(*, require_tty: bool = True) -> Tuple[bool, str]:
    """Return (ok, message) for whether TUI mode can be used in this environment."""
    try:
        get_questionary(require_tty=require_tty)
    except TuiUnavailable as exc:
        return False, str(exc)
    return True, ""
