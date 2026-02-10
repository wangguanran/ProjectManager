"""
Built-in PO plugin bundle.

Importing this package registers the default PO plugins.
"""

from __future__ import annotations

# Import built-in plugins for side-effect registration.
from . import commits as _commits  # noqa: F401
from . import custom as _custom  # noqa: F401
from . import overrides as _overrides  # noqa: F401
from . import patches as _patches  # noqa: F401
