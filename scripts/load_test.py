#!/usr/bin/env python3
"""Run a lightweight read-only load probe against public OmniForum endpoints."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import statistics
import time
import urllib.error
import urllib.request
from typing import Any


def fetch(base_url: str, path: str, timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        headers={"Accept": "application/json", "User-Agent": "omniforum-load-test/1.0"},
        method="GET",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            status = response.status
        payload = json.loads(raw.decode("utf-8") or "{}")
        ok = status == 200 and (payload.get("ok") is True or isinstance(payload.get("site"), dict))
        error = ""
    except urllib.error.HTTPError as exc:
        with exc:
            status = exc.code
            error = exc.read().decode("utf-8", errors="replace")[:240]
        ok = False
    except Exception as exc:  # noqa: BLE001 - load probe should collect all request failures.
        status = 0
        ok = False
        error = str(exc)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
    return {"path": path, "status": status, "ok": ok, "elapsedMs": elapsed_ms, "error": error}


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((pct / 100) * (len(ordered) - 1))))
    return round(ordered[index], 1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url")
    parser.add_argument("--requests", type=int, default=40)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--timeout", type=float, default=10)
    parser.add_argument("--max-p95-ms", type=float, default=1500)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    paths = ["/api/health", "/api/home"]
    jobs = [paths[index % len(paths)] for index in range(args.requests)]
    started = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as pool:
        results = list(pool.map(lambda path: fetch(args.base_url, path, args.timeout), jobs))
    total_elapsed = round((time.perf_counter() - started) * 1000, 1)

    latencies = [float(result["elapsedMs"]) for result in results]
    errors = [result for result in results if not result["ok"]]
    summary = {
        "ok": not errors and percentile(latencies, 95) <= args.max_p95_ms,
        "baseUrl": args.base_url.rstrip("/"),
        "requests": len(results),
        "concurrency": args.concurrency,
        "totalElapsedMs": total_elapsed,
        "meanMs": round(statistics.mean(latencies), 1) if latencies else 0.0,
        "p50Ms": percentile(latencies, 50),
        "p95Ms": percentile(latencies, 95),
        "maxMs": max(latencies) if latencies else 0.0,
        "errorCount": len(errors),
        "errors": errors[:5],
    }
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(
            "OmniForum load probe: "
            f"{'ok' if summary['ok'] else 'failed'} "
            f"requests={summary['requests']} concurrency={summary['concurrency']} "
            f"p50={summary['p50Ms']}ms p95={summary['p95Ms']}ms errors={summary['errorCount']}"
        )
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
