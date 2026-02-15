"""
Utilities for emitting machine-readable execution plans.

This is intentionally lightweight and has no side effects beyond writing the
requested plan JSON to stdout or a file.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, Optional, Tuple

from src.log_manager import redact_secrets

_TRUTHY = {"1", "true", "yes", "y", "on"}
_FALSY = {"0", "false", "no", "n", "off"}


def parse_emit_plan(value: Any) -> Tuple[bool, Optional[str]]:
    """Return (enabled, path). When enabled and path is None, emit to stdout."""
    if value in (None, False):
        return False, None
    if value is True:
        return True, None

    text = str(value).strip()
    if not text:
        return False, None
    lowered = text.lower()
    if lowered in _TRUTHY:
        return True, None
    if lowered in _FALSY:
        return False, None
    return True, text


def _redact_payload(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        return redact_secrets(value)
    if isinstance(value, list):
        return [_redact_payload(v) for v in value]
    if isinstance(value, dict):
        return {k: _redact_payload(v) for k, v in value.items()}
    return value


def emit_plan_json(payload: Dict[str, Any], emit_plan: Any) -> bool:
    """Emit a redacted JSON payload to stdout or to the provided path."""
    enabled, out_path = parse_emit_plan(emit_plan)
    if not enabled:
        return False

    redacted = _redact_payload(payload)
    text = json.dumps(redacted, indent=2, ensure_ascii=False) + "\n"

    if out_path:
        out_path = os.path.expanduser(out_path)
        out_dir = os.path.dirname(out_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        tmp_path = f"{out_path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp_path, out_path)
        return True

    sys.stdout.write(text)
    return True
