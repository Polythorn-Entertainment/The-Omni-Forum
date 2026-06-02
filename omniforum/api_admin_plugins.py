"""Focused admin API handlers for plugin operations."""

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


class PluginAdminApiMixin:
    def api_update_plugin(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        plugin_id: str,
    ) -> dict[str, Any]:
        if not viewer or not is_admin(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        ensure_can_participate(viewer)
        data = self.read_json()
        if "enabled" not in data:
            raise APIError("Choose whether that plugin should be enabled.")
        plugin = set_plugin_enabled(plugin_id, bool(data.get("enabled")))
        state = "enabled" if plugin["enabled"] else "disabled"
        log_audit_event(
            conn,
            actor=viewer,
            action_type="plugin_update",
            category="plugins",
            target_type="plugin",
            target_label=plugin["id"],
            reason=f"Plugin {state}.",
            metadata={
                "pluginName": plugin["name"],
                "enabled": plugin["enabled"],
            },
        )
        conn.commit()
        append_server_log(f"plugin {state} by {viewer['username']}: {plugin['id']}")
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "plugin": plugin,
            "plugins": list_plugins(include_disabled=True),
            "message": f"{plugin['name']} is now {state}.",
        }
