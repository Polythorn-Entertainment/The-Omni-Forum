"""Focused admin API handlers for settings operations."""

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


class SettingsAdminApiMixin:
    def api_admin_site_settings(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not viewer or not is_admin(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "site": serialize_site_settings(get_site_settings(conn)),
            "registration": serialize_registration_settings(get_registration_settings(conn)),
            "onboarding": get_admin_onboarding_checklist(conn),
            "backups": list_backup_archives(limit=6),
        }

    def api_update_admin_site_settings(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not viewer or not is_admin(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        ensure_can_participate(viewer)
        site = update_site_settings_from_payload(conn, self.read_json(), viewer)
        append_server_log(f"site settings updated by {viewer['username']}")
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "site": site,
            "message": "Site settings saved.",
        }
