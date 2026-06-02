"""Focused admin API handlers for backup operations."""

from __future__ import annotations

import json
import sqlite3
from datetime import timedelta
from http import HTTPStatus
from typing import Any

from .account_state import ensure_can_participate
from .admin_export import build_admin_export, build_import_preview
from .admin_health import get_admin_health, get_admin_onboarding_checklist
from .audit import list_audit_events, log_audit_event
from .backups import create_backup_archive, inspect_backup_archive, list_backup_archives
from .config import EXPORT_ROUTE, PUBLIC_URL
from .content_state import list_deleted_content, restore_deleted_post, restore_deleted_thread
from .core import is_admin, utc_iso, utc_now
from .domain import (
    create_notification,
    get_current_user_payload,
    log_moderation_action,
    mark_notifications_read,
)
from .errors import APIError
from .integrations import send_staff_discord_notice
from .plugins import list_plugins, set_plugin_enabled
from .runtime_logging import append_server_log, read_recent_logs
from .sessions import delete_sessions_for_user
from .site_settings import update_site_settings_from_payload
from .storage import cleanup_orphan_media
from .validation import (
    blocked_username_patterns,
    clean_invite_code,
    clean_text,
    generate_invite_code,
    get_registration_settings,
    get_site_settings,
    list_invite_codes,
    registration_controls_payload,
    registration_status,
    serialize_registration_settings,
    serialize_site_settings,
)


class BackupAdminApiMixin:
    def api_admin_backup(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not viewer or not is_admin(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        ensure_can_participate(viewer)
        archive = create_backup_archive()
        log_audit_event(
            conn,
            actor=viewer,
            action_type="backup_create",
            category="operations",
            target_type="backup",
            target_label=archive.name,
            reason="Backup archive created.",
            metadata={
                "filename": archive.name,
                "size": archive.stat().st_size if archive.exists() else 0,
            },
        )
        conn.commit()
        append_server_log(f"backup created by {viewer['username']}: {archive.name}")
        send_staff_discord_notice(
            title="OmniForum backup created",
            lines=[
                f"Admin: {viewer['username']}",
                f"Archive: {archive.name}",
                f"Download: {PUBLIC_URL}{EXPORT_ROUTE}/backups/{archive.name}",
            ],
            color=0x06D6A0,
        )
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "downloadUrl": f"{EXPORT_ROUTE}/backups/{archive.name}",
            "filename": archive.name,
            "message": "Backup archive created.",
        }

    def api_admin_backup_guide(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        query: dict[str, list[str]],
    ) -> dict[str, Any]:
        if not viewer or not is_admin(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        filename = (query.get("file") or [""])[0].strip()
        guide = inspect_backup_archive(filename)
        log_audit_event(
            conn,
            actor=viewer,
            action_type="restore_guide_view",
            category="operations",
            target_type="backup",
            target_label=guide["filename"],
            reason="Restore guide opened.",
            metadata={
                "hasAllDatabases": guide["contents"].get("hasAllDatabases"),
                "databaseCount": guide["contents"].get("databaseCount"),
                "mediaCount": guide["contents"].get("mediaCount"),
            },
        )
        conn.commit()
        append_server_log(f"restore guide checked by {viewer['username']}: {guide['filename']}")
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "guide": guide,
        }
