"""Focused admin API handlers for registration operations."""

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


class RegistrationAdminApiMixin:
    def api_admin_registration(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not viewer or not is_admin(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        ensure_can_participate(viewer)
        mark_notifications_read(conn, viewer["id"], target_type="registration_queue")
        conn.commit()
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "controls": registration_controls_payload(conn),
        }

    def api_update_registration_settings(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not viewer or not is_admin(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        ensure_can_participate(viewer)
        current = get_registration_settings(conn)
        data = self.read_json()
        public_enabled = bool(data.get("publicRegistrationEnabled", current["public_registration_enabled"]))
        invite_required = bool(data.get("inviteRequired", current["invite_required"]))
        approval_required = bool(data.get("approvalRequired", current["approval_required"]))
        patterns = clean_text(
            data.get("blockedUsernamePatterns", current.get("blocked_username_patterns") or ""),
            min_len=0,
            max_len=4000,
            field="Blocked username patterns",
        )
        pattern_lines = blocked_username_patterns({"blocked_username_patterns": patterns})
        if len(pattern_lines) > 100:
            raise APIError("Keep the blocked username list to 100 patterns or fewer.")
        if any(len(pattern) > 80 for pattern in pattern_lines):
            raise APIError("Blocked username patterns must be 80 characters or shorter.")
        now = utc_iso()
        conn.execute(
            """
                UPDATE registration_settings
                SET public_registration_enabled = ?,
                    invite_required = ?,
                    approval_required = ?,
                    blocked_username_patterns = ?,
                    updated_by = ?,
                    updated_at = ?
                WHERE id = 1
                """,
            (
                1 if public_enabled else 0,
                1 if invite_required else 0,
                1 if approval_required else 0,
                patterns,
                viewer["id"],
                now,
            ),
        )
        log_audit_event(
            conn,
            actor=viewer,
            action_type="registration_settings_update",
            category="signup",
            target_type="settings",
            target_label="Signup controls",
            reason="Signup controls updated.",
            metadata={
                "publicRegistrationEnabled": public_enabled,
                "inviteRequired": invite_required,
                "approvalRequired": approval_required,
                "blockedPatternCount": len(pattern_lines),
            },
        )
        conn.commit()
        append_server_log(f"registration settings updated by {viewer['username']}")
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "controls": registration_controls_payload(conn),
            "message": "Signup controls updated.",
        }

    def api_create_invite(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not viewer or not is_admin(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        ensure_can_participate(viewer)
        data = self.read_json()
        note = clean_text(data.get("note"), min_len=0, max_len=160, field="Invite note")
        try:
            max_uses = int(data.get("maxUses") or 1)
        except (TypeError, ValueError) as exc:
            raise APIError("Invite uses must be a whole number.") from exc
        if max_uses < 1 or max_uses > 500:
            raise APIError("Invite uses must be between 1 and 500.")
        expires_at = None
        if data.get("expiresInDays") not in {None, ""}:
            try:
                expires_in_days = int(data.get("expiresInDays"))
            except (TypeError, ValueError) as exc:
                raise APIError("Invite expiration must be a whole number of days.") from exc
            if expires_in_days < 1 or expires_in_days > 365:
                raise APIError("Invite expiration must be between 1 and 365 days.")
            expires_at = utc_iso(utc_now() + timedelta(days=expires_in_days))
        custom_code = clean_invite_code(data.get("code"), required=False)
        now = utc_iso()
        for attempt in range(6):
            code = custom_code or generate_invite_code()
            try:
                cur = conn.execute(
                    """
                        INSERT INTO invite_codes (
                            code, note, max_uses, uses, enabled, expires_at,
                            created_by, created_at, updated_at
                        )
                        VALUES (?, ?, ?, 0, 1, ?, ?, ?, ?)
                        """,
                    (code, note, max_uses, expires_at, viewer["id"], now, now),
                )
                log_audit_event(
                    conn,
                    actor=viewer,
                    action_type="invite_create",
                    category="signup",
                    target_type="invite",
                    target_id=cur.lastrowid,
                    target_label=code,
                    reason=note,
                    metadata={
                        "maxUses": max_uses,
                        "expiresAt": expires_at,
                    },
                    created_at=now,
                )
                conn.commit()
                append_server_log(f"invite code created by {viewer['username']}: {code}")
                return {
                    "currentUser": get_current_user_payload(conn, viewer),
                    "controls": registration_controls_payload(conn),
                    "invite": next(
                        (item for item in list_invite_codes(conn) if item["code"].lower() == code.lower()),
                        None,
                    ),
                    "message": "Invite code created.",
                }
            except sqlite3.IntegrityError as exc:
                if custom_code or attempt == 5:
                    raise APIError("That invite code already exists.") from exc
        raise APIError("Could not create an invite code.")

    def api_update_invite(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        invite_id: int,
    ) -> dict[str, Any]:
        if not viewer or not is_admin(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        ensure_can_participate(viewer)
        row = conn.execute("SELECT * FROM invite_codes WHERE id = ?", (invite_id,)).fetchone()
        if not row:
            raise APIError("Invite code not found.", HTTPStatus.NOT_FOUND)
        data = self.read_json()
        note = clean_text(data.get("note", row["note"]), min_len=0, max_len=160, field="Invite note")
        enabled = bool(data.get("enabled", row["enabled"]))
        try:
            max_uses = int(data.get("maxUses", row["max_uses"]))
        except (TypeError, ValueError) as exc:
            raise APIError("Invite uses must be a whole number.") from exc
        if max_uses < max(1, int(row["uses"] or 0)) or max_uses > 500:
            raise APIError("Invite uses cannot be lower than current uses, below 1, or above 500.")
        expires_at = row["expires_at"]
        if bool(data.get("clearExpires")):
            expires_at = None
        elif data.get("expiresInDays") not in {None, ""}:
            try:
                expires_in_days = int(data.get("expiresInDays"))
            except (TypeError, ValueError) as exc:
                raise APIError("Invite expiration must be a whole number of days.") from exc
            if expires_in_days < 1 or expires_in_days > 365:
                raise APIError("Invite expiration must be between 1 and 365 days.")
            expires_at = utc_iso(utc_now() + timedelta(days=expires_in_days))
        now = utc_iso()
        conn.execute(
            """
                UPDATE invite_codes
                SET note = ?, max_uses = ?, enabled = ?, expires_at = ?, updated_at = ?
                WHERE id = ?
                """,
            (note, max_uses, 1 if enabled else 0, expires_at, now, invite_id),
        )
        log_audit_event(
            conn,
            actor=viewer,
            action_type="invite_update",
            category="signup",
            target_type="invite",
            target_id=invite_id,
            target_label=row["code"],
            reason=note,
            metadata={
                "enabled": enabled,
                "maxUses": max_uses,
                "expiresAt": expires_at,
                "previousEnabled": bool(row["enabled"]),
            },
            created_at=now,
        )
        conn.commit()
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "controls": registration_controls_payload(conn),
            "message": "Invite code updated.",
        }

    def api_review_registration(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        user_id: int,
    ) -> dict[str, Any]:
        if not viewer or not is_admin(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        ensure_can_participate(viewer)
        target = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not target or registration_status(target) != "pending":
            raise APIError("Pending registration not found.", HTTPStatus.NOT_FOUND)
        data = self.read_json()
        action = str(data.get("action") or "").strip().lower()
        if action not in {"approve", "reject"}:
            raise APIError("Choose approve or reject.")
        note = clean_text(data.get("note"), min_len=0, max_len=500, field="Review note")
        now = utc_iso()
        new_status = "approved" if action == "approve" else "rejected"
        conn.execute(
            """
                UPDATE users
                SET approval_status = ?,
                    approval_note = ?,
                    approved_by = ?,
                    approved_at = ?,
                    updated_at = ?
                WHERE id = ?
                """,
            (new_status, note, viewer["id"], now, now, user_id),
        )
        log_moderation_action(
            conn,
            user_id=user_id,
            actor_id=viewer["id"],
            action_type=f"registration_{action}",
            category="signup",
            reason=note,
            created_at=now,
        )
        if action == "approve":
            create_notification(
                conn,
                user_id=user_id,
                actor_id=viewer["id"],
                kind="staff_action",
                title="Registration approved",
                body=note or "Your account is approved. You can now log in.",
                target_type="user",
                target_id=user_id,
                created_at=now,
            )
        conn.commit()
        if action == "reject":
            delete_sessions_for_user(conn, user_id)
        append_server_log(f"registration {action} by {viewer['username']}: user {user_id}")
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "controls": registration_controls_payload(conn),
            "message": f"Registration {new_status}.",
        }
