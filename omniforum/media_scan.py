"""Optional media scanning hooks for production upload pipelines."""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path
from typing import Any

from .config import MEDIA_SCAN_COMMAND, MEDIA_SCAN_REQUIRED, MEDIA_SCAN_TIMEOUT_SECONDS
from .errors import APIError
from .runtime_logging import append_structured_log


def media_scan_status() -> dict[str, Any]:
    return {
        "configured": bool(MEDIA_SCAN_COMMAND),
        "required": bool(MEDIA_SCAN_REQUIRED),
        "timeoutSeconds": MEDIA_SCAN_TIMEOUT_SECONDS,
        "status": "enabled" if MEDIA_SCAN_COMMAND else ("missing" if MEDIA_SCAN_REQUIRED else "optional"),
    }


def media_scan_command_args(path: Path, storage_path: str) -> list[str]:
    if "{path}" in MEDIA_SCAN_COMMAND or "{storage_path}" in MEDIA_SCAN_COMMAND:
        command = MEDIA_SCAN_COMMAND.replace("{path}", str(path)).replace("{storage_path}", storage_path)
        return shlex.split(command)
    return [*shlex.split(MEDIA_SCAN_COMMAND), str(path)]


def scan_media_file(path: Path, *, storage_path: str) -> dict[str, Any]:
    if not MEDIA_SCAN_COMMAND:
        if MEDIA_SCAN_REQUIRED:
            raise APIError("Media scanning is required but no scanner is configured.")
        return {"status": "skipped", "configured": False}
    args = media_scan_command_args(path, storage_path)
    try:
        result = subprocess.run(
            args,
            cwd=str(path.parent),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=MEDIA_SCAN_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        append_structured_log(
            "media_scan",
            storagePath=storage_path,
            status="error",
            error=str(exc),
        )
        raise APIError("That upload could not be scanned. Please try a different file.") from exc
    payload = {
        "status": "clean" if result.returncode == 0 else "rejected",
        "configured": True,
        "returnCode": result.returncode,
    }
    append_structured_log(
        "media_scan",
        storagePath=storage_path,
        status=payload["status"],
        returnCode=result.returncode,
    )
    if result.returncode != 0:
        raise APIError("That upload was rejected by the media safety scanner.")
    return payload
