"""Runtime log writing and inspection helpers."""

from __future__ import annotations

import json
import re
from typing import Any

from .config import APP_LOG_FILE, LOG_FILE
from .core import utc_iso
from .db import ensure_runtime_dirs


def append_server_log(message: str) -> None:
    ensure_runtime_dirs()
    with LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(f"[{utc_iso()}] {message}\n")


def append_structured_log(event: str, **fields: Any) -> None:
    ensure_runtime_dirs()
    payload = {
        "event": event,
        "time": utc_iso(),
        **fields,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    append_server_log(f"json {encoded}")
    with APP_LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(f"{encoded}\n")


def read_recent_logs(*, limit_lines: int = 120) -> list[str]:
    if not LOG_FILE.exists():
        return []
    lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
    return lines[-limit_lines:]


def parse_log_timestamp(line: str) -> str:
    match = re.match(r"\[([^\]]+)\]", line or "")
    return match.group(1) if match else ""


def parse_log_status(line: str) -> int | None:
    match = re.search(r'"\s+(\d{3})\s+', line or "")
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def find_latest_log_entry(*needles: str) -> dict[str, str] | None:
    lowered_needles = [needle.lower() for needle in needles if needle]
    if not lowered_needles:
        return None
    for line in reversed(read_recent_logs(limit_lines=600)):
        lowered = line.lower()
        if any(needle in lowered for needle in lowered_needles):
            return {
                "time": parse_log_timestamp(line),
                "line": line,
            }
    return None


def recent_error_logs(*, limit: int = 8) -> list[dict[str, Any]]:
    error_terms = (" error", "failed", "exception", "traceback", "bad request")
    entries: list[dict[str, Any]] = []
    for line in reversed(read_recent_logs(limit_lines=500)):
        status = parse_log_status(line)
        lowered = f" {line.lower()}"
        if (status is not None and status >= 400) or any(term in lowered for term in error_terms):
            entries.append(
                {
                    "time": parse_log_timestamp(line),
                    "status": status,
                    "line": line,
                }
            )
        if len(entries) >= limit:
            break
    return entries


def parse_structured_log(line: str) -> dict[str, Any] | None:
    marker = "] json "
    if marker not in line:
        return None
    try:
        payload = json.loads(line.split(marker, 1)[1])
    except (json.JSONDecodeError, IndexError):
        return None
    return payload if isinstance(payload, dict) else None


def recent_structured_events(*, event: str | None = None, min_status: int | None = None, limit: int = 12) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for line in reversed(read_recent_logs(limit_lines=800)):
        payload = parse_structured_log(line)
        if not payload:
            continue
        if event and payload.get("event") != event:
            continue
        if min_status is not None and int(payload.get("status") or 0) < min_status:
            continue
        entries.append(payload)
        if len(entries) >= limit:
            break
    return entries
