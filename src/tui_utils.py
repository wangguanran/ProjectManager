"""Optional terminal UI helpers."""

from __future__ import annotations

import sys
from typing import Tuple

INSTALL_HINT = 'pip install -e ".[tui]"'


class TuiUnavailable(RuntimeError):
    """Raised when TUI mode cannot be used (missing deps or no TTY)."""


def _is_tty() -> bool:
    try:
        return bool(sys.stdin.isatty() and sys.stdout.isatty())
    except (AttributeError, OSError, ValueError):  # pragma: no cover
        return False


def ensure_tui_available(*, require_tty: bool = True) -> None:
    """Validate that the Textual-based TUI can run in this environment."""
    if require_tty and not _is_tty():
        raise TuiUnavailable("TUI requires an interactive TTY (stdin/stdout).")

    try:
        __import__("textual")
    except ModuleNotFoundError as exc:
        raise TuiUnavailable(f"TUI dependency is not installed. Install it with: {INSTALL_HINT}") from exc


def tui_available(*, require_tty: bool = True) -> Tuple[bool, str]:
    """Return (ok, message) for whether TUI mode can be used in this environment."""
    try:
        ensure_tui_available(require_tty=require_tty)
    except TuiUnavailable as exc:
        return False, str(exc)
    return True, ""
