"""Per-user media usage and quota helpers."""

from __future__ import annotations

import sqlite3
from typing import Any

from .config import USER_MEDIA_LIMIT_BYTES, USER_MEDIA_LIMIT_FILES
from .core import human_size
from .errors import APIError
from .media_paths import media_file_size


def get_user_media_usage(conn: sqlite3.Connection, user_id: int) -> dict[str, Any]:
    user_row = conn.execute(
        "SELECT avatar_path FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    avatar_path = str(user_row["avatar_path"] or "") if user_row else ""
    media_rows = conn.execute(
        """
        SELECT pm.storage_path, pm.thumbnail_path
        FROM post_media pm
        JOIN posts p ON p.id = pm.post_id
        WHERE p.author_id = ?
        """,
        (user_id,),
    ).fetchall()
    user_file_paths = [avatar_path] if avatar_path else []
    user_file_paths.extend(str(row["storage_path"] or "") for row in media_rows if row["storage_path"])
    byte_paths = list(user_file_paths)
    byte_paths.extend(str(row["thumbnail_path"] or "") for row in media_rows if row["thumbnail_path"])
    unique_user_files = sorted({path for path in user_file_paths if path})
    unique_byte_paths = sorted({path for path in byte_paths if path})
    bytes_used = sum(media_file_size(path) for path in unique_byte_paths)
    avatar_count = 1 if avatar_path else 0
    return {
        "files": len(unique_user_files),
        "bytes": bytes_used,
        "bytesLabel": human_size(bytes_used),
        "avatarCount": avatar_count,
        "postMediaCount": max(0, len(unique_user_files) - avatar_count),
        "limitFiles": USER_MEDIA_LIMIT_FILES,
        "limitBytes": USER_MEDIA_LIMIT_BYTES,
        "limitBytesLabel": human_size(USER_MEDIA_LIMIT_BYTES),
        "remainingFiles": max(0, USER_MEDIA_LIMIT_FILES - len(unique_user_files)),
        "remainingBytes": max(0, USER_MEDIA_LIMIT_BYTES - bytes_used),
        "remainingBytesLabel": human_size(max(0, USER_MEDIA_LIMIT_BYTES - bytes_used)),
    }


def ensure_user_media_quota(
    conn: sqlite3.Connection,
    user_id: int,
    uploads: list[dict[str, Any]],
    *,
    replacing_paths: list[str] | None = None,
) -> dict[str, Any]:
    if not uploads:
        return get_user_media_usage(conn, user_id)
    usage = get_user_media_usage(conn, user_id)
    replacing = sorted({path for path in (replacing_paths or []) if path})
    replaced_bytes = sum(media_file_size(path) for path in replacing)
    replaced_files = len([path for path in replacing if not path.startswith("thumbs/")])
    pending_bytes = sum(
        len(upload.get("bytes") or b"") + len(upload.get("thumbnail_bytes") or b"") for upload in uploads
    )
    next_file_total = max(0, int(usage["files"]) - replaced_files) + len(uploads)
    next_byte_total = max(0, int(usage["bytes"]) - replaced_bytes) + pending_bytes
    if next_file_total > USER_MEDIA_LIMIT_FILES:
        raise APIError(
            f"You have reached the media library limit of {USER_MEDIA_LIMIT_FILES} files. "
            "Remove older uploads before adding more.",
        )
    if next_byte_total > USER_MEDIA_LIMIT_BYTES:
        raise APIError(
            f"Your media library is over the {human_size(USER_MEDIA_LIMIT_BYTES)} quota. "
            "Remove older uploads or use smaller files before uploading more.",
        )
    return {
        **usage,
        "nextFiles": next_file_total,
        "nextBytes": next_byte_total,
        "nextBytesLabel": human_size(next_byte_total),
    }
