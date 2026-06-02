"""Admin health, analytics, queue, and site-stat helpers."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

from .backups import inspect_backup_archive, list_backup_archives
from .config import (
    AVATAR_IMAGE_MAX_DIMENSION,
    BACKUP_DIR,
    BACKUP_ROTATION_LIMIT,
    BACKUP_STALE_HOURS,
    BASE_DIR,
    DATA_DIR,
    DATA_FILES,
    HOST,
    MAX_REQUEST_BYTES,
    MEDIA_SCAN_COMMAND,
    MEDIA_SCAN_REQUIRED,
    MEDIA_SCAN_TIMEOUT_SECONDS,
    MEDIA_FOLDERS,
    ONLINE_WINDOW_MINUTES,
    PORT,
    POST_IMAGE_MAX_DIMENSION,
    POST_MEDIA_MAX_BYTES,
    POST_MEDIA_MAX_COUNT,
    POST_THUMBNAIL_MAX_DIMENSION,
    PUBLIC_URL,
    RESTORE_SCRIPT,
    SECURE_COOKIES,
    SERVER_STARTED_AT,
    SITE_THEME_OPTIONS,
    USER_MEDIA_LIMIT_BYTES,
    USER_MEDIA_LIMIT_FILES,
)
from .core import human_duration, human_size, utc_iso, utc_now
from .db import ensure_runtime_dirs
from .email_auth import EMAIL_AUTH_ENABLED, public_email_auth_features, smtp_configured
from .errors import APIError
from .integrations import discord_webhook_enabled
from .media import PIL_AVAILABLE
from .media_scan import media_scan_status
from .migrations import schema_migration_status
from .plugins import get_plugin_status_summary, list_plugins
from .runtime_logging import find_latest_log_entry, read_recent_logs, recent_error_logs, recent_structured_events
from .storage import get_database_storage, get_media_usage
from .validation import (
    get_registration_settings,
    pending_registration_count,
    serialize_registration_settings,
    serialize_site_settings,
    get_site_settings,
)


def get_open_contact_notice_count(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) AS count FROM contact_submissions WHERE status = 'open'").fetchone()["count"]


def get_open_report_count(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) AS count FROM reports WHERE status = 'open'").fetchone()["count"]


def get_open_appeal_count(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) AS count FROM appeals WHERE status = 'open'").fetchone()["count"]


def get_home_announcements(conn: sqlite3.Connection) -> list[str]:
    stats = get_site_stats(conn)
    items = [
        "OmniForum is live with a real persistent backend.",
        f"{stats['members']} member{'s' if stats['members'] != 1 else ''} registered so far.",
        f"{stats['threads']} thread{'s' if stats['threads'] != 1 else ''} across the forum.",
        f"{stats['posts']} post{'s' if stats['posts'] != 1 else ''} and counting.",
    ]
    latest_thread = conn.execute(
        """
        SELECT title
        FROM threads
        WHERE COALESCE(shadow_hidden, 0) = 0
          AND deleted_at IS NULL
        ORDER BY pinned DESC, updated_at DESC
        LIMIT 1
        """
    ).fetchone()
    if latest_thread:
        items.append(f"Latest conversation: {latest_thread['title']}")
    else:
        items.append("Be the first to start a thread and shape the community.")
    return items


def get_site_stats(conn: sqlite3.Connection) -> dict[str, int]:
    member_count = conn.execute("SELECT COUNT(*) AS count FROM users WHERE approval_status = 'approved'").fetchone()[
        "count"
    ]
    thread_count = conn.execute(
        "SELECT COUNT(*) AS count FROM threads WHERE COALESCE(shadow_hidden, 0) = 0 AND deleted_at IS NULL"
    ).fetchone()["count"]
    post_count = conn.execute(
        "SELECT COUNT(*) AS count FROM posts WHERE COALESCE(shadow_hidden, 0) = 0 AND deleted_at IS NULL"
    ).fetchone()["count"]
    online_since = utc_iso(utc_now() - timedelta(minutes=ONLINE_WINDOW_MINUTES))
    online_count = conn.execute(
        "SELECT COUNT(*) AS count FROM users WHERE approval_status = 'approved' AND last_seen_at >= ?",
        (online_since,),
    ).fetchone()["count"]
    return {
        "members": member_count,
        "threads": thread_count,
        "posts": post_count,
        "online": online_count,
    }


def get_backup_status(backups: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    ensure_runtime_dirs()
    backup_items = backups if backups is not None else list_backup_archives()
    all_archives = list(BACKUP_DIR.glob("omniforum-backup-*.zip"))
    total_bytes = sum(path.stat().st_size for path in all_archives if path.is_file())
    latest = backup_items[0] if backup_items else None
    now = utc_now()
    check = {
        "status": "missing",
        "checkedAt": utc_iso(now),
        "message": "No backup archive has been created yet.",
        "missingDatabases": list(DATA_FILES[path_key].name for path_key in DATA_FILES),
    }
    latest_age_seconds: int | None = None
    latest_age_label = ""
    if latest:
        try:
            created_at = datetime.fromisoformat(str(latest["createdAt"]).replace("Z", "+00:00"))
            latest_age_seconds = int((now - created_at).total_seconds())
            latest_age_label = human_duration(latest_age_seconds)
        except (KeyError, TypeError, ValueError):
            latest_age_seconds = None
        try:
            guide = inspect_backup_archive(str(latest["filename"]))
            missing = guide["contents"].get("missingDatabases", [])
            check = {
                "status": "ok" if not missing else "warning",
                "checkedAt": utc_iso(now),
                "message": "Latest backup includes all database files."
                if not missing
                else "Latest backup is missing database files.",
                "missingDatabases": missing,
            }
        except APIError as exc:
            check = {
                "status": "error",
                "checkedAt": utc_iso(now),
                "message": str(exc),
                "missingDatabases": [],
            }
    stale = bool(latest_age_seconds is not None and latest_age_seconds > BACKUP_STALE_HOURS * 3600)
    status = "healthy" if latest and check["status"] == "ok" and not stale else "warning"
    if check["status"] == "error":
        status = "error"
    if not latest:
        status_label = "No backups yet"
    elif stale:
        status_label = f"Latest backup is {latest_age_label} old"
    elif check["status"] == "ok":
        status_label = "Latest backup verified"
    else:
        status_label = check["message"]
    return {
        "count": len(all_archives),
        "listedCount": len(backup_items),
        "totalBytes": total_bytes,
        "totalSize": human_size(total_bytes),
        "latest": latest,
        "latestAgeSeconds": latest_age_seconds,
        "latestAgeLabel": latest_age_label,
        "rotationLimit": BACKUP_ROTATION_LIMIT,
        "staleAfterHours": BACKUP_STALE_HOURS,
        "status": status,
        "statusLabel": status_label,
        "check": check,
        "lastCreatedLog": find_latest_log_entry("backup created"),
    }


def get_queue_status(conn: sqlite3.Connection) -> dict[str, Any]:
    counts = {
        "reports": get_open_report_count(conn),
        "appeals": get_open_appeal_count(conn),
        "contactNotices": get_open_contact_notice_count(conn),
        "registrations": pending_registration_count(conn),
    }
    total = sum(int(value or 0) for value in counts.values())
    return {
        **counts,
        "totalOpen": total,
        "status": "attention" if total else "clear",
    }


def get_recovery_readiness(backups: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    backup_status = get_backup_status(backups)
    restore_script_exists = RESTORE_SCRIPT.exists()
    restore_script_ready = restore_script_exists and os.access(RESTORE_SCRIPT, os.X_OK)
    if backup_status["status"] == "healthy" and restore_script_ready:
        status = "healthy"
        message = "Latest backup validates and restore tooling is present."
    elif not restore_script_exists:
        status = "error"
        message = "Restore script is missing."
    elif not restore_script_ready:
        status = "warning"
        message = "Restore script exists but is not executable."
    else:
        status = "warning"
        message = backup_status["statusLabel"]
    return {
        "status": status,
        "message": message,
        "checkedAt": backup_status["check"]["checkedAt"],
        "latestBackupCheck": backup_status["check"],
        "lastBackupCreated": backup_status.get("lastCreatedLog"),
        "lastRestoreGuideCheck": find_latest_log_entry("restore guide checked"),
        "restoreScript": {
            "path": str(RESTORE_SCRIPT),
            "exists": restore_script_exists,
            "executable": restore_script_ready,
        },
    }


def admin_daily_series(
    conn: sqlite3.Connection,
    query: str,
    *,
    days: int = 7,
) -> list[dict[str, Any]]:
    series: list[dict[str, Any]] = []
    start_date = utc_now().date() - timedelta(days=days - 1)
    for offset in range(days):
        current = start_date + timedelta(days=offset)
        start = datetime.combine(current, datetime.min.time(), tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        row = conn.execute(query, (utc_iso(start), utc_iso(end))).fetchone()
        series.append({"date": current.isoformat(), "count": int(row["count"] if row else 0)})
    return series


def get_admin_analytics(conn: sqlite3.Connection) -> dict[str, Any]:
    top_sections = conn.execute(
        """
        SELECT
            s.slug,
            s.name,
            COUNT(DISTINCT t.id) AS thread_count,
            COUNT(p.id) AS post_count
        FROM sections s
        LEFT JOIN threads t ON t.section_id = s.id AND t.deleted_at IS NULL
        LEFT JOIN posts p ON p.thread_id = t.id AND p.deleted_at IS NULL
        GROUP BY s.id, s.slug, s.name
        ORDER BY post_count DESC, thread_count DESC, s.name COLLATE NOCASE ASC
        LIMIT 6
        """
    ).fetchall()
    tag_counts: dict[str, int] = {}
    tag_rows = conn.execute(
        "SELECT tags_json FROM threads WHERE deleted_at IS NULL ORDER BY updated_at DESC LIMIT 400"
    ).fetchall()
    for row in tag_rows:
        try:
            tags = json.loads(row["tags_json"] or "[]")
        except json.JSONDecodeError:
            tags = []
        for tag in tags:
            normalized = str(tag).strip().lower()
            if normalized:
                tag_counts[normalized] = tag_counts.get(normalized, 0) + 1
    top_tags = [
        {"tag": tag, "count": count}
        for tag, count in sorted(tag_counts.items(), key=lambda item: (-item[1], item[0]))[:10]
    ]
    moderator_rows = conn.execute(
        """
        SELECT actor.username, actor.role, COUNT(*) AS count
        FROM moderation_actions ma
        JOIN users actor ON actor.id = ma.actor_id
        WHERE ma.created_at >= ?
        GROUP BY ma.actor_id, actor.username, actor.role
        ORDER BY count DESC, actor.username COLLATE NOCASE ASC
        LIMIT 6
        """,
        (utc_iso(utc_now() - timedelta(days=30)),),
    ).fetchall()
    action_rows = conn.execute(
        """
        SELECT action_type, COUNT(*) AS count
        FROM moderation_actions
        WHERE created_at >= ?
        GROUP BY action_type
        ORDER BY count DESC, action_type ASC
        LIMIT 12
        """,
        (utc_iso(utc_now() - timedelta(days=30)),),
    ).fetchall()
    report_rows = conn.execute(
        """
        SELECT triage_priority, COUNT(*) AS count
        FROM reports
        WHERE status = 'open'
        GROUP BY triage_priority
        ORDER BY count DESC, triage_priority ASC
        """
    ).fetchall()
    search_rows = conn.execute(
        """
        SELECT query, COUNT(*) AS count, AVG(result_count) AS avg_results, MAX(created_at) AS latest_at
        FROM search_events
        WHERE created_at >= ? AND query != ''
        GROUP BY lower(query)
        ORDER BY count DESC, latest_at DESC
        LIMIT 8
        """,
        (utc_iso(utc_now() - timedelta(days=30)),),
    ).fetchall()
    deleted_counts = {
        "threads": conn.execute("SELECT COUNT(*) AS count FROM threads WHERE deleted_at IS NOT NULL").fetchone()[
            "count"
        ],
        "posts": conn.execute("SELECT COUNT(*) AS count FROM posts WHERE deleted_at IS NOT NULL").fetchone()["count"],
    }
    return {
        "registrations7d": admin_daily_series(
            conn,
            query="SELECT COUNT(*) AS count FROM users WHERE created_at >= ? AND created_at < ?",
        ),
        "threads7d": admin_daily_series(
            conn,
            query="SELECT COUNT(*) AS count FROM threads WHERE deleted_at IS NULL AND created_at >= ? AND created_at < ?",
        ),
        "posts7d": admin_daily_series(
            conn,
            query="SELECT COUNT(*) AS count FROM posts WHERE deleted_at IS NULL AND created_at >= ? AND created_at < ?",
        ),
        "activeUsers7d": admin_daily_series(
            conn,
            query="SELECT COUNT(DISTINCT user_id) AS count FROM sessions WHERE last_seen_at >= ? AND last_seen_at < ?",
        ),
        "searches7d": admin_daily_series(
            conn,
            query="SELECT COUNT(*) AS count FROM search_events WHERE created_at >= ? AND created_at < ?",
        ),
        "reports7d": admin_daily_series(
            conn,
            query="SELECT COUNT(*) AS count FROM reports WHERE created_at >= ? AND created_at < ?",
        ),
        "moderation7d": admin_daily_series(
            conn,
            query="SELECT COUNT(*) AS count FROM moderation_actions WHERE created_at >= ? AND created_at < ?",
        ),
        "topSections": [
            {
                "id": row["slug"],
                "name": row["name"],
                "threads": row["thread_count"],
                "posts": row["post_count"],
            }
            for row in top_sections
        ],
        "topTags": top_tags,
        "topModerators30d": [
            {
                "username": row["username"],
                "role": row["role"],
                "count": row["count"],
            }
            for row in moderator_rows
        ],
        "actionTypes30d": [
            {
                "type": row["action_type"],
                "count": row["count"],
            }
            for row in action_rows
        ],
        "activeRestrictions": {
            "banned": conn.execute("SELECT COUNT(*) AS count FROM users WHERE banned_at IS NOT NULL").fetchone()[
                "count"
            ],
            "timedOut": conn.execute(
                "SELECT COUNT(*) AS count FROM users WHERE timeout_until IS NOT NULL AND timeout_until > ?",
                (utc_iso(),),
            ).fetchone()["count"],
            "muted": conn.execute(
                "SELECT COUNT(*) AS count FROM users WHERE mute_until IS NOT NULL AND mute_until > ?",
                (utc_iso(),),
            ).fetchone()["count"],
            "shadowMuted": conn.execute("SELECT COUNT(*) AS count FROM users WHERE shadow_muted = 1").fetchone()[
                "count"
            ],
        },
        "openReportPriorities": [
            {
                "priority": row["triage_priority"] or "normal",
                "count": row["count"],
            }
            for row in report_rows
        ],
        "topSearchTerms30d": [
            {
                "query": row["query"],
                "count": row["count"],
                "averageResults": round(float(row["avg_results"] or 0), 1),
                "latestAt": row["latest_at"],
            }
            for row in search_rows
        ],
        "storageFootprint": {
            "databases": get_database_storage()["totalSize"],
            "media": get_media_usage(conn)["totalSize"],
        },
        "deletedQueue": deleted_counts,
    }


def checklist_item(key: str, label: str, ok: bool, detail: str) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "ok": bool(ok),
        "status": "ok" if ok else "attention",
        "detail": detail,
    }


def get_admin_onboarding_checklist(conn: sqlite3.Connection) -> dict[str, Any]:
    owner_count = conn.execute(
        "SELECT COUNT(*) AS count FROM users WHERE role = 'owner' AND approval_status = 'approved'"
    ).fetchone()["count"]
    section_count = conn.execute("SELECT COUNT(*) AS count FROM sections").fetchone()["count"]
    public_section_count = conn.execute(
        "SELECT COUNT(*) AS count FROM sections WHERE required_role = 'new'"
    ).fetchone()["count"]
    settings = serialize_registration_settings(get_registration_settings(conn))
    items = [
        checklist_item("owner", "Owner Account", owner_count > 0, "Create and secure the first owner account."),
        checklist_item(
            "sections", "Forum Sections", section_count >= 3, "Create enough sections for launch navigation."
        ),
        checklist_item(
            "public_sections",
            "Public Visibility",
            public_section_count > 0,
            "Keep at least one readable public section unless the forum is private.",
        ),
        checklist_item(
            "rules",
            "Rules Page",
            (BASE_DIR / "pages" / "rules.html").exists(),
            "Publish community rules and enforcement expectations.",
        ),
        checklist_item(
            "privacy",
            "Privacy Page",
            (BASE_DIR / "pages" / "privacy.html").exists(),
            "Publish privacy and data handling information.",
        ),
        checklist_item(
            "contact",
            "Contact Form",
            (BASE_DIR / "pages" / "contact.html").exists(),
            "Keep the contact form available for staff notices.",
        ),
        checklist_item(
            "registration",
            "Registration Mode",
            bool(settings.get("publicRegistrationEnabled") or settings.get("inviteRequired")),
            "Choose open, invite-only, or approval-based registration.",
        ),
        checklist_item(
            "backups", "First Backup", bool(list_backup_archives()), "Create at least one backup before public launch."
        ),
        checklist_item(
            "themes", "Theme Options", len(SITE_THEME_OPTIONS) >= 3, "Offer theme choices in user settings."
        ),
    ]
    complete = sum(1 for item in items if item["ok"])
    return {
        "complete": complete,
        "total": len(items),
        "status": "ready" if complete == len(items) else "attention",
        "items": items,
    }


def get_production_install_checks(conn: sqlite3.Connection) -> dict[str, Any]:
    data_writable = DATA_DIR.exists() and os.access(DATA_DIR, os.R_OK | os.W_OK | os.X_OK)
    media_writable = all(
        path.exists() and os.access(path, os.R_OK | os.W_OK | os.X_OK) for path in MEDIA_FOLDERS.values()
    )
    database_files_ready = all(path.exists() and os.access(path, os.R_OK | os.W_OK) for path in DATA_FILES.values())
    checks = [
        checklist_item(
            "data_dir", "Dedicated Data Folder", data_writable, f"{DATA_DIR} must be readable and writable."
        ),
        checklist_item(
            "database_files",
            "SQLite Files",
            database_files_ready,
            "All required database files should exist in the data folder.",
        ),
        checklist_item(
            "media_dirs", "Upload Folders", media_writable, "Avatar, post, and thumbnail folders must be writable."
        ),
        checklist_item(
            "docker",
            "Docker Files",
            (BASE_DIR / "Dockerfile").exists() and (BASE_DIR / "docker-compose.yml").exists(),
            "Dockerfile and docker-compose.yml are present.",
        ),
        checklist_item(
            "reverse_proxy",
            "Reverse Proxy Config",
            (BASE_DIR / "deploy" / "nginx-omniforum.conf").exists(),
            "Nginx sample config is present for public hosting.",
        ),
        checklist_item(
            "service_file",
            "Service File",
            (BASE_DIR / "deploy" / "omniforum.service").exists(),
            "Systemd service file is present for VPS installs.",
        ),
        checklist_item(
            "secure_cookies",
            "Secure Cookies",
            SECURE_COOKIES or HOST in {"127.0.0.1", "localhost"},
            "Set OMNIFORUM_SECURE_COOKIES=1 behind HTTPS.",
        ),
        checklist_item(
            "public_url",
            "Public URL",
            bool(os.getenv("OMNIFORUM_PUBLIC_URL")) or HOST in {"127.0.0.1", "localhost"},
            "Set OMNIFORUM_PUBLIC_URL for production share links.",
        ),
        checklist_item(
            "upload_limit",
            "Upload Limit",
            MAX_REQUEST_BYTES >= POST_MEDIA_MAX_BYTES * POST_MEDIA_MAX_COUNT,
            "Server request limit can handle max post uploads.",
        ),
        checklist_item(
            "backup_script",
            "Restore Script",
            RESTORE_SCRIPT.exists() and os.access(RESTORE_SCRIPT, os.X_OK),
            "Restore script should exist and be executable.",
        ),
        checklist_item(
            "image_processing",
            "Image Processing",
            PIL_AVAILABLE,
            "Pillow should be installed for resize, compression, and thumbnails.",
        ),
        checklist_item(
            "media_scanner",
            "Media Scanner",
            bool(MEDIA_SCAN_COMMAND) or not MEDIA_SCAN_REQUIRED,
            "Set OMNIFORUM_MEDIA_SCAN_COMMAND or keep scanning optional.",
        ),
        checklist_item(
            "email_auth",
            "Email Auth",
            (not EMAIL_AUTH_ENABLED) or smtp_configured(),
            "Email auth is optional; if enabled, SMTP must be configured.",
        ),
    ]
    passing = sum(1 for item in checks if item["ok"])
    return {
        "passing": passing,
        "total": len(checks),
        "status": "ready" if passing == len(checks) else "attention",
        "items": checks,
    }


def get_admin_health(conn: sqlite3.Connection) -> dict[str, Any]:
    database_storage = get_database_storage()
    media_usage = get_media_usage(conn)
    backups = list_backup_archives()
    backup_status = get_backup_status(backups)
    plugins = list_plugins()
    queues = get_queue_status(conn)
    latest_errors = recent_error_logs(limit=8)
    latest_failed_requests = recent_structured_events(event="api_request", min_status=400, limit=8)
    latest_exceptions = recent_structured_events(event="api_exception", limit=4)
    return {
        "uptimeSeconds": int((utc_now() - SERVER_STARTED_AT).total_seconds()),
        "startedAt": utc_iso(SERVER_STARTED_AT),
        "stats": get_site_stats(conn),
        "storage": {
            "databases": database_storage["labels"],
            "databaseFiles": database_storage["files"],
            "databaseTotalBytes": database_storage["totalBytes"],
            "databaseTotalSize": database_storage["totalSize"],
            "databaseMissingCount": database_storage["missingCount"],
            "mediaAssets": media_usage["totalFiles"],
            "mediaUsage": media_usage,
            "backupCount": backup_status["count"],
            "backupTotalBytes": backup_status["totalBytes"],
            "backupTotalSize": backup_status["totalSize"],
            "backupStatus": backup_status,
            "backups": backups,
            "mediaQuotaBytes": USER_MEDIA_LIMIT_BYTES,
            "mediaQuotaBytesLabel": human_size(USER_MEDIA_LIMIT_BYTES),
            "mediaQuotaFiles": USER_MEDIA_LIMIT_FILES,
        },
        "queues": queues,
        "runtime": {
            "host": HOST,
            "port": PORT,
            "maxRequestBytes": MAX_REQUEST_BYTES,
            "secureCookies": SECURE_COOKIES,
            "maxRequestSize": human_size(MAX_REQUEST_BYTES),
            "publicUrl": PUBLIC_URL,
            "discordWebhookConfigured": discord_webhook_enabled(),
            "site": serialize_site_settings(get_site_settings(conn)),
            "registration": serialize_registration_settings(get_registration_settings(conn)),
            "mediaProcessing": {
                "enabled": PIL_AVAILABLE,
                "library": "Pillow" if PIL_AVAILABLE else "Unavailable",
                "avatarMaxDimension": AVATAR_IMAGE_MAX_DIMENSION,
                "postMaxDimension": POST_IMAGE_MAX_DIMENSION,
                "thumbnailMaxDimension": POST_THUMBNAIL_MAX_DIMENSION,
            },
            "mediaScanning": {
                **media_scan_status(),
                "commandConfigured": bool(MEDIA_SCAN_COMMAND),
                "required": MEDIA_SCAN_REQUIRED,
                "timeoutSeconds": MEDIA_SCAN_TIMEOUT_SECONDS,
            },
            "emailAuth": public_email_auth_features(),
            "schemaMigrations": schema_migration_status(conn),
        },
        "analytics": get_admin_analytics(conn),
        "onboarding": get_admin_onboarding_checklist(conn),
        "installChecks": get_production_install_checks(conn),
        "plugins": plugins,
        "pluginStatus": get_plugin_status_summary(plugins),
        "logs": {
            "latestErrors": latest_errors,
            "latestFailedRequests": latest_failed_requests,
            "latestExceptions": latest_exceptions,
            "errorCount": len(latest_errors),
            "failedRequestCount": len(latest_failed_requests),
            "lastErrorAt": latest_failed_requests[0]["time"]
            if latest_failed_requests
            else (latest_errors[0]["time"] if latest_errors else ""),
        },
        "recovery": get_recovery_readiness(backups),
        "recentLogs": read_recent_logs(limit_lines=40),
    }
