#!/usr/bin/env python3
"""Container healthcheck for OmniForum."""

from __future__ import annotations

import json
import os
import sys
import urllib.request


def main() -> int:
    port = os.getenv("OMNIFORUM_PORT", "8000")
    url = f"http://127.0.0.1:{port}/api/health"
    with urllib.request.urlopen(url, timeout=3) as response:
        payload = json.loads(response.read().decode("utf-8") or "{}")
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
