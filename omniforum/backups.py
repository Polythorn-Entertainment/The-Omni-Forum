"""Backup archive creation and inspection helpers."""

from __future__ import annotations

import re
import zipfile
from datetime import datetime, timezone
from http import HTTPStatus
from pathlib import Path
from typing import Any

from .config import (
    BACKUP_DIR,
    BACKUP_ROTATION_LIMIT,
    BASE_DIR,
    DATA_FILES,
    EXPORT_ROUTE,
    LOG_FILE,
    MEDIA_FOLDERS,
    RESTORE_SCRIPT,
)
from .core import human_size, utc_iso, utc_now
from .db import ensure_runtime_dirs
from .errors import APIError


def rotate_backup_archives() -> None:
    backups = sorted(BACKUP_DIR.glob("omniforum-backup-*.zip"), key=lambda path: path.stat().st_mtime, reverse=True)
    for path in backups[BACKUP_ROTATION_LIMIT:]:
        path.unlink(missing_ok=True)


def create_backup_archive() -> Path:
    ensure_runtime_dirs()
    filename = f"omniforum-backup-{utc_now().strftime('%Y%m%d-%H%M%S')}.zip"
    target = BACKUP_DIR / filename
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for db_path in DATA_FILES.values():
            if db_path.exists():
                archive.write(db_path, arcname=f"data/{db_path.name}")
        if LOG_FILE.exists():
            archive.write(LOG_FILE, arcname="data/logs/server.log")
        for bucket, directory in MEDIA_FOLDERS.items():
            for file_path in sorted(directory.glob("*")):
                if file_path.is_file():
                    archive.write(file_path, arcname=f"data/uploads/{bucket}/{file_path.name}")
    rotate_backup_archives()
    return target


def list_backup_archives(*, limit: int = 12) -> list[dict[str, Any]]:
    ensure_runtime_dirs()
    archives = sorted(
        BACKUP_DIR.glob("omniforum-backup-*.zip"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    items: list[dict[str, Any]] = []
    for path in archives[:limit]:
        stat = path.stat()
        items.append(
            {
                "filename": path.name,
                "size": stat.st_size,
                "sizeLabel": human_size(stat.st_size),
                "createdAt": utc_iso(datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)),
                "downloadUrl": f"{EXPORT_ROUTE}/backups/{path.name}",
            }
        )
    return items


def resolve_backup_archive(filename: str) -> Path:
    candidate = str(filename or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9._-]+\.zip", candidate):
        raise APIError("Choose a valid backup archive.", HTTPStatus.BAD_REQUEST)
    path = (BACKUP_DIR / candidate).resolve()
    if path.parent != BACKUP_DIR.resolve() or not path.is_file():
        raise APIError("Backup archive not found.", HTTPStatus.NOT_FOUND)
    return path


def inspect_backup_archive(filename: str) -> dict[str, Any]:
    archive_path = resolve_backup_archive(filename)
    try:
        with zipfile.ZipFile(archive_path) as archive:
            names = sorted(name for name in archive.namelist() if not name.endswith("/"))
    except zipfile.BadZipFile as exc:
        raise APIError("That backup archive could not be opened.", HTTPStatus.BAD_REQUEST) from exc
    databases = [name for name in names if name.startswith("data/") and name.endswith(".db")]
    media_files = [name for name in names if name.startswith("data/uploads/")]
    log_files = [name for name in names if name.startswith("data/logs/")]
    missing = [
        path.name
        for path in DATA_FILES.values()
        if f"data/{path.name}" not in names
    ]
    return {
        "filename": archive_path.name,
        "downloadUrl": f"{EXPORT_ROUTE}/backups/{archive_path.name}",
        "size": archive_path.stat().st_size,
        "sizeLabel": human_size(archive_path.stat().st_size),
        "createdAt": utc_iso(datetime.fromtimestamp(archive_path.stat().st_mtime, tz=timezone.utc)),
        "contents": {
            "databaseCount": len(databases),
            "mediaCount": len(media_files),
            "logCount": len(log_files),
            "entriesPreview": names[:12],
            "hasAllDatabases": not missing,
            "missingDatabases": missing,
        },
        "restore": {
            "scriptPath": str(RESTORE_SCRIPT),
            "command": f"{RESTORE_SCRIPT} {archive_path} {BASE_DIR}",
            "steps": [
                "Create a fresh backup before restoring over live data.",
                "Stop OmniForum or your reverse-proxy-managed service first.",
                "Run the restore script with the backup archive path and project directory.",
                "Start OmniForum again and confirm /api/health, the homepage, and an admin login work.",
            ],
            "checks": [
                "Confirm the archive date and filename match the snapshot you want.",
                "Confirm the archive includes the expected database files and upload assets.",
                "Verify your current data/ directory was copied to a pre-restore safety snapshot.",
            ],
        },
    }
