#!/usr/bin/env python3
"""Verify a clean source archive does not contain runtime/private state."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from release_safety import scan_release_archive


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()

    leaks = scan_release_archive(args.archive)
    if leaks:
        print("Runtime/private state leaked into release archive:", file=sys.stderr)
        for leak in leaks:
            print(leak, file=sys.stderr)
        return 1
    print(f"Release archive leak scan passed: {args.archive}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
