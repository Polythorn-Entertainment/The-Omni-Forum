"""Focused admin API handlers for data operations."""

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


class DataAdminApiMixin:
    def api_admin_trash(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        query: dict[str, list[str]],
    ) -> dict[str, Any]:
        if not viewer or not is_admin(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        try:
            limit = int((query.get("limit") or ["60"])[0])
        except (TypeError, ValueError):
            limit = 60
        limit = max(1, min(120, limit))
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "items": list_deleted_content(conn, limit=limit),
        }

    def api_admin_media_cleanup(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not viewer or not is_admin(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        ensure_can_participate(viewer)
        result = cleanup_orphan_media(conn)
        log_audit_event(
            conn,
            actor=viewer,
            action_type="media_cleanup",
            category="operations",
            target_type="media",
            reason=f"Removed {result['deletedCount']} files ({result['deletedSize']}).",
            metadata=result,
        )
        conn.commit()
        append_server_log(
            f"media cleanup by {viewer['username']}: {result['deletedCount']} files, {result['deletedSize']}"
        )
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "cleanup": result,
            "message": "Media cleanup complete.",
        }

    def api_restore_trash(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not viewer or not is_admin(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        ensure_can_participate(viewer)
        data = self.read_json()
        item_type = str(data.get("type") or "").strip().lower()
        try:
            item_id = int(data.get("id"))
        except (TypeError, ValueError) as exc:
            raise APIError("Choose a valid item to restore.") from exc
        if item_type == "thread":
            row = conn.execute(
                "SELECT id, title FROM threads WHERE id = ? AND deleted_at IS NOT NULL",
                (item_id,),
            ).fetchone()
            if not row:
                raise APIError("That deleted thread could not be found.", HTTPStatus.NOT_FOUND)
            restore_deleted_thread(conn, item_id)
            label = row["title"]
        elif item_type == "post":
            row = conn.execute(
                """
                    SELECT p.id, p.thread_id, t.deleted_at AS thread_deleted_at
                    FROM posts p
                    JOIN threads t ON t.id = p.thread_id
                    WHERE p.id = ? AND p.deleted_at IS NOT NULL
                    """,
                (item_id,),
            ).fetchone()
            if not row:
                raise APIError("That deleted post could not be found.", HTTPStatus.NOT_FOUND)
            if row["thread_deleted_at"]:
                raise APIError("Restore the parent thread before restoring this reply.")
            restore_deleted_post(conn, item_id)
            label = f"post #{item_id}"
        else:
            raise APIError("Unsupported restore type.")
        log_audit_event(
            conn,
            actor=viewer,
            action_type="trash_restore",
            category="content",
            target_type=item_type,
            target_id=item_id,
            target_label=label,
            reason=f"Restored {label}.",
        )
        conn.commit()
        append_server_log(f"trash restore by {viewer['username']}: {item_type} {item_id}")
        send_staff_discord_notice(
            title="OmniForum trash restore",
            lines=[
                f"Admin: {viewer['username']}",
                f"Restored: {label}",
                f"Type: {item_type}",
            ],
            color=0x7B5EA7,
        )
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "items": list_deleted_content(conn, limit=60),
            "message": f"Restored {label}.",
        }
