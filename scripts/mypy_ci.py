#!/usr/bin/env python3
"""
CI helper for incremental mypy adoption.

Runs mypy and enforces that the total error count does not exceed the baseline
stored in `mypy_baseline.json`.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple


ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = ROOT / "mypy_baseline.json"


def _run_mypy(targets: List[str]) -> Tuple[int, str]:
    cmd = [
        sys.executable,
        "-m",
        "mypy",
        *targets,
        "--no-color-output",
    ]
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, check=False)
    output = (proc.stdout or "") + (proc.stderr or "")

    if proc.returncode == 0:
        return 0, output

    match = re.search(r"Found\s+(\d+)\s+errors?\s+in\s+", output)
    if match:
        return int(match.group(1)), output

    # Fallback: count error lines if summary is missing (e.g., crash/interrupt).
    error_lines = [line for line in output.splitlines() if ": error:" in line]
    if error_lines:
        return len(error_lines), output

    raise RuntimeError(f"mypy failed without a parsable summary (exit={proc.returncode}).\n{output}")


def _load_baseline() -> Dict[str, Any]:
    if not BASELINE_PATH.exists():
        raise FileNotFoundError(f"Missing baseline file: {BASELINE_PATH}")
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


def _write_baseline(*, error_count: int, targets: List[str], command: str) -> None:
    payload: Dict[str, Any] = {
        "baseline_error_count": error_count,
        "targets": targets,
        "command": command,
    }
    BASELINE_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run mypy and enforce baseline error count.")
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Update mypy_baseline.json with the current error count.",
    )
    parser.add_argument(
        "--targets",
        nargs="*",
        default=["src", "crewai_agents"],
        help="Directories/packages passed to mypy.",
    )
    args = parser.parse_args()

    targets = list(args.targets)
    # Avoid embedding machine-specific absolute paths in the committed baseline.
    command = f"python -m mypy {' '.join(targets)} --no-color-output"

    errors, output = _run_mypy(targets)

    if args.update_baseline:
        _write_baseline(error_count=errors, targets=targets, command=command)
        print(f"Updated baseline: {errors} errors")
        return 0

    baseline = _load_baseline()
    baseline_errors = int(baseline.get("baseline_error_count", 0))

    if errors > baseline_errors:
        print(f"mypy errors increased: {errors} > baseline {baseline_errors}", file=sys.stderr)
        print("", file=sys.stderr)
        print("To accept a new baseline (not recommended unless intentional):", file=sys.stderr)
        print(f"  {sys.executable} scripts/mypy_ci.py --update-baseline", file=sys.stderr)
        print("", file=sys.stderr)
        print("mypy output (tail):", file=sys.stderr)
        tail = "\n".join(output.splitlines()[-60:])
        print(tail, file=sys.stderr)
        return 1

    print(f"mypy ok: {errors} errors (baseline {baseline_errors})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
