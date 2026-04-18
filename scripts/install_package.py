#!/usr/bin/env python3
"""Install a built projman wheel into a managed runtime."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.install_utils import install_wheel_into_managed_runtime  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", required=True, help="Path to the wheel to install.")
    parser.add_argument("--install-dir", required=True, help="Directory where the launcher should be installed.")
    parser.add_argument(
        "--platform",
        choices=["linux", "macos", "windows"],
        required=True,
        help="Target platform name for launcher/runtime layout.",
    )
    parser.add_argument(
        "--launcher-name",
        default="projman",
        help="Launcher name to expose in the install directory.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    version = install_wheel_into_managed_runtime(
        wheel_path=os.path.abspath(os.path.expanduser(args.wheel)),
        install_dir=os.path.abspath(os.path.expanduser(args.install_dir)),
        platform_name=args.platform,
        launcher_name=args.launcher_name,
    )
    print(version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
