#!/usr/bin/env python3
"""Check public OmniForum endpoints for external monitoring."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any


def fetch_json(base_url: str, path: str, timeout: float) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}{path}"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "omniforum-healthcheck/1.0",
        },
        method="GET",
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            status = response.status
    except urllib.error.HTTPError as exc:
        with exc:
            body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{path} returned HTTP {exc.code}: {body[:240]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{path} could not be reached: {exc.reason}") from exc
    payload = json.loads(raw.decode("utf-8") or "{}")
    return {
        "path": path,
        "status": status,
        "elapsedMs": round((time.monotonic() - started) * 1000, 1),
        "payload": payload,
    }


def post_alert(webhook_url: str, message: str, timeout: float) -> None:
    body = json.dumps({"content": message[:1800]}).encode("utf-8")
    request = urllib.request.Request(
        webhook_url,
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "omniforum-healthcheck/1.0"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout):
            return
    except Exception as exc:  # noqa: BLE001 - monitoring alerts should never mask the probe result.
        print(f"warning: failed to send healthcheck alert: {exc}", file=sys.stderr)


def endpoint_ok(result: dict[str, Any]) -> tuple[bool, str]:
    path = str(result["path"])
    payload = result["payload"]
    if path == "/api/health":
        return bool(payload.get("ok")), "health endpoint reports ok"
    if path == "/api/home":
        has_site = isinstance(payload.get("site"), dict)
        has_categories = isinstance(payload.get("categories"), list)
        return has_site and has_categories, "home endpoint returned site and categories"
    return True, "endpoint responded"


def render_text(result: dict[str, Any]) -> str:
    lines = [f"OmniForum healthcheck: {'ok' if result['ok'] else 'failed'}"]
    for check in result["checks"]:
        label = "ok" if check["ok"] else "fail"
        lines.append(f"- {label}: {check['path']} in {check.get('elapsedMs', '?')} ms - {check['message']}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "base_url",
        nargs="?",
        default=os.getenv("OMNIFORUM_HEALTHCHECK_URL") or os.getenv("OMNIFORUM_PUBLIC_URL") or "",
        help="Base URL to check, for example https://forum.example.com",
    )
    parser.add_argument("--timeout", type=float, default=float(os.getenv("OMNIFORUM_HEALTHCHECK_TIMEOUT", "10")))
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    parser.add_argument(
        "--webhook-url",
        default=os.getenv("OMNIFORUM_HEALTHCHECK_WEBHOOK_URL", ""),
        help="Optional Discord-compatible webhook URL for failure alerts",
    )
    args = parser.parse_args()

    if not args.base_url:
        print("Provide a base URL or set OMNIFORUM_HEALTHCHECK_URL.", file=sys.stderr)
        return 2

    checks: list[dict[str, Any]] = []
    for path in ("/api/health", "/api/home"):
        try:
            result = fetch_json(args.base_url, path, args.timeout)
            ok, message = endpoint_ok(result)
            checks.append(
                {
                    "path": path,
                    "ok": ok,
                    "status": result["status"],
                    "elapsedMs": result["elapsedMs"],
                    "message": message,
                }
            )
        except Exception as exc:  # noqa: BLE001 - healthcheck should report all failures consistently.
            checks.append({"path": path, "ok": False, "message": str(exc)})

    result = {
        "ok": all(check["ok"] for check in checks),
        "baseUrl": args.base_url.rstrip("/"),
        "checkedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "checks": checks,
    }
    if not result["ok"] and args.webhook_url:
        post_alert(args.webhook_url, render_text(result), args.timeout)
    print(json.dumps(result, indent=2) if args.json else render_text(result))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
