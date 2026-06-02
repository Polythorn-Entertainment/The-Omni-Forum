"""Storage and media maintenance helpers."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any

from .config import DATA_FILES, MEDIA_DIR, MEDIA_FOLDERS
from .core import human_size, utc_iso
from .db import ensure_runtime_dirs
from .media import cleanup_orphan_post_artifacts


def referenced_media_paths(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        """
        SELECT storage_path FROM post_media WHERE storage_path != ''
        UNION
        SELECT thumbnail_path AS storage_path FROM post_media WHERE thumbnail_path != ''
        UNION
        SELECT avatar_path AS storage_path FROM users WHERE avatar_path != ''
        """
    ).fetchall()
    return {row["storage_path"] for row in rows if row["storage_path"]}


def cleanup_missing_avatar_paths(conn: sqlite3.Connection) -> int:
    stale_ids: list[int] = []
    rows = conn.execute("SELECT id, avatar_path FROM users WHERE avatar_path != ''").fetchall()
    for row in rows:
        storage_path = row["avatar_path"]
        parts = storage_path.split("/", 1)
        if len(parts) != 2 or parts[0] not in MEDIA_FOLDERS:
            stale_ids.append(int(row["id"]))
            continue
        if not (MEDIA_FOLDERS[parts[0]] / parts[1]).exists():
            stale_ids.append(int(row["id"]))
    if stale_ids:
        conn.execute(
            f"UPDATE users SET avatar_path = '' WHERE id IN ({', '.join('?' for _ in stale_ids)})",
            tuple(stale_ids),
        )
        conn.commit()
    return len(stale_ids)


def cleanup_orphan_media(conn: sqlite3.Connection) -> dict[str, Any]:
    broken_avatar_refs = cleanup_missing_avatar_paths(conn)
    orphaned_rows = cleanup_orphan_post_artifacts(conn)
    referenced = referenced_media_paths(conn)
    deleted_files: list[str] = []
    total_bytes = 0
    for file_path in MEDIA_DIR.iterdir():
        if not file_path.is_file():
            continue
        total_bytes += file_path.stat().st_size
        file_path.unlink(missing_ok=True)
        deleted_files.append(f"uploads/{file_path.name}")
    for bucket, directory in MEDIA_FOLDERS.items():
        for file_path in directory.glob("*"):
            if not file_path.is_file():
                continue
            storage_path = f"{bucket}/{file_path.name}"
            if storage_path in referenced:
                continue
            total_bytes += file_path.stat().st_size
            file_path.unlink(missing_ok=True)
            deleted_files.append(storage_path)
    return {
        "deletedCount": len(deleted_files),
        "deletedBytes": total_bytes,
        "deletedSize": human_size(total_bytes),
        "deletedFiles": deleted_files[:50],
        "brokenAvatarRefsCleared": broken_avatar_refs,
        "orphanRowsRemoved": orphaned_rows,
    }


def get_database_storage() -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    total_bytes = 0
    for key, path in DATA_FILES.items():
        exists = path.exists()
        stat = path.stat() if exists else None
        size = stat.st_size if stat else 0
        total_bytes += size
        files.append(
            {
                "key": key,
                "name": path.name,
                "exists": exists,
                "size": size,
                "sizeLabel": human_size(size),
                "updatedAt": utc_iso(datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)) if stat else "",
            }
        )
    return {
        "totalBytes": total_bytes,
        "totalSize": human_size(total_bytes),
        "fileCount": len(files),
        "missingCount": sum(1 for item in files if not item["exists"]),
        "files": files,
        "labels": {item["name"]: item["sizeLabel"] for item in files},
    }


def get_storage_sizes() -> dict[str, str]:
    return get_database_storage()["labels"]


def get_media_usage(conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    ensure_runtime_dirs()
    referenced = referenced_media_paths(conn) if conn is not None else set()
    buckets: list[dict[str, Any]] = []
    total_files = 0
    total_bytes = 0
    orphaned_files = 0
    orphaned_bytes = 0

    loose_files = [path for path in MEDIA_DIR.glob("*") if path.is_file()]
    for file_path in loose_files:
        size = file_path.stat().st_size
        total_files += 1
        total_bytes += size
        orphaned_files += 1
        orphaned_bytes += size

    if loose_files:
        buckets.append(
            {
                "bucket": "loose",
                "label": "Loose uploads",
                "files": len(loose_files),
                "bytes": sum(path.stat().st_size for path in loose_files),
                "sizeLabel": human_size(sum(path.stat().st_size for path in loose_files)),
                "orphanedFiles": len(loose_files),
                "orphanedBytes": sum(path.stat().st_size for path in loose_files),
                "orphanedSize": human_size(sum(path.stat().st_size for path in loose_files)),
            }
        )

    for bucket, directory in MEDIA_FOLDERS.items():
        files = [path for path in directory.glob("*") if path.is_file()]
        bucket_bytes = 0
        bucket_orphaned_files = 0
        bucket_orphaned_bytes = 0
        for file_path in files:
            size = file_path.stat().st_size
            storage_path = f"{bucket}/{file_path.name}"
            bucket_bytes += size
            total_files += 1
            total_bytes += size
            if conn is not None and storage_path not in referenced:
                bucket_orphaned_files += 1
                bucket_orphaned_bytes += size
                orphaned_files += 1
                orphaned_bytes += size
        buckets.append(
            {
                "bucket": bucket,
                "label": bucket.replace("_", " ").title(),
                "files": len(files),
                "bytes": bucket_bytes,
                "sizeLabel": human_size(bucket_bytes),
                "orphanedFiles": bucket_orphaned_files,
                "orphanedBytes": bucket_orphaned_bytes,
                "orphanedSize": human_size(bucket_orphaned_bytes),
            }
        )

    return {
        "totalFiles": total_files,
        "totalBytes": total_bytes,
        "totalSize": human_size(total_bytes),
        "orphanedFiles": orphaned_files,
        "orphanedBytes": orphaned_bytes,
        "orphanedSize": human_size(orphaned_bytes),
        "buckets": buckets,
    }


def count_media_assets() -> int:
    return get_media_usage()["totalFiles"]
