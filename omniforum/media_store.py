"""Low-level media file writes."""

from __future__ import annotations

import secrets
from http import HTTPStatus
from typing import Any

from .config import MEDIA_FOLDERS
from .core import utc_now
from .errors import APIError
from .media_scan import scan_media_file


def store_image_upload(upload: dict[str, Any], *, bucket: str) -> str:
    return store_image_upload_paths(upload, bucket=bucket)["storage_path"]


def store_image_upload_paths(upload: dict[str, Any], *, bucket: str) -> dict[str, str]:
    if bucket not in MEDIA_FOLDERS:
        raise APIError("Upload destination is invalid.", HTTPStatus.INTERNAL_SERVER_ERROR)
    stem = f"{utc_now().strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(8)}"
    filename = f"{stem}.{upload['extension']}"
    path = MEDIA_FOLDERS[bucket] / filename
    path.write_bytes(upload["bytes"])
    result = {"storage_path": f"{bucket}/{filename}", "thumbnail_path": ""}
    written_paths = [path]
    try:
        scan_media_file(path, storage_path=result["storage_path"])
        thumbnail_bytes = upload.get("thumbnail_bytes") or b""
        thumbnail_extension = upload.get("thumbnail_extension") or ""
        if thumbnail_bytes and thumbnail_extension:
            thumb_filename = f"{stem}-thumb.{thumbnail_extension}"
            thumb_path = MEDIA_FOLDERS["thumbs"] / thumb_filename
            thumb_path.write_bytes(thumbnail_bytes)
            written_paths.append(thumb_path)
            result["thumbnail_path"] = f"thumbs/{thumb_filename}"
            scan_media_file(thumb_path, storage_path=result["thumbnail_path"])
        return result
    except Exception:
        for written_path in written_paths:
            written_path.unlink(missing_ok=True)
        raise
