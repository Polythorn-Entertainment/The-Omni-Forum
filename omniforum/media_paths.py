"""Media storage path and URL helpers."""

from __future__ import annotations

from pathlib import Path

from .config import MEDIA_FOLDERS, MEDIA_ROUTE


def media_url_for_path(storage_path: str | None) -> str | None:
    relative = str(storage_path or "").strip().replace("\\", "/").strip("/")
    if not relative:
        return None
    return f"{MEDIA_ROUTE}/{relative}"


def resolve_media_path(storage_path: str | None) -> Path | None:
    relative = str(storage_path or "").strip().replace("\\", "/").strip("/")
    if not relative:
        return None
    parts = Path(relative).parts
    if len(parts) != 2 or parts[0] not in MEDIA_FOLDERS:
        return None
    candidate = (MEDIA_FOLDERS[parts[0]] / parts[1]).resolve()
    root = MEDIA_FOLDERS[parts[0]].resolve()
    if candidate.parent != root:
        return None
    return candidate


def delete_media_file(storage_path: str | None) -> None:
    path = resolve_media_path(storage_path)
    if path and path.exists():
        path.unlink()


def media_file_size(storage_path: str | None) -> int:
    path = resolve_media_path(storage_path)
    if not path or not path.is_file():
        return 0
    try:
        return path.stat().st_size
    except OSError:
        return 0
