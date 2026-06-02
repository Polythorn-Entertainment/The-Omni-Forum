from __future__ import annotations

import json
import sqlite3
from datetime import timedelta
from http import HTTPStatus
from typing import Any

from .config import (
    FLOOD_CONTROL_SECONDS,
    PUBLIC_URL,
    ROLES,
)
from .core import (
    can_manage_user,
    can_moderate_user,
    is_admin,
    is_staff,
    make_password_hash,
    role_level,
    utc_iso,
    utc_now,
)
from .integrations import send_staff_discord_notice
from .validation import (
    clean_id_list,
    clean_password,
    clean_report_category,
    clean_report_priority,
    clean_report_status,
    clean_text,
)
from .audit import log_audit_event
from .account_state import (
    active_mute_until,
    active_timeout_until,
    award_xp,
    enforce_recent_action_limit,
    ensure_can_participate,
    is_banned_user,
    sync_user_restrictions,
)
from .sessions import delete_sessions_for_user
from .admin_health import (
    get_open_appeal_count,
    get_open_report_count,
)
from .domain import (
    create_staff_notifications,
    get_current_user_payload,
    get_user_profile,
    list_appeals_for_viewer,
    list_moderation_macros,
    list_reports,
    log_moderation_action,
    mark_notifications_read,
    notify_staff_action,
    resolve_report_target,
    serialize_moderation_macro,
)
from .text_utils import short_preview
from .errors import APIError


class UserModerationApiMixin:
    def api_update_role(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        user_id: int,
    ) -> dict[str, Any]:
        if not viewer or not can_manage_user(viewer, "new"):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        ensure_can_participate(viewer)
        target = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not target:
            raise APIError("User not found.", HTTPStatus.NOT_FOUND)
        data = self.read_json()
        new_role = data.get("role")
        if new_role not in ROLES:
            raise APIError("Invalid role.")
        if target["role"] == "owner" and viewer["role"] != "owner":
            raise APIError("Only the owner can modify the owner role.", HTTPStatus.FORBIDDEN)
        if viewer["role"] == "admin" and role_level(new_role) > role_level("mod"):
            raise APIError("Admins can only assign up to mod.", HTTPStatus.FORBIDDEN)
        if viewer["role"] == "admin" and role_level(target["role"]) >= role_level("admin"):
            raise APIError("Admins cannot change admin or owner accounts.", HTTPStatus.FORBIDDEN)
        now = utc_iso()
        conn.execute(
            "UPDATE users SET role = ?, updated_at = ? WHERE id = ?",
            (new_role, now, user_id),
        )
        log_moderation_action(
            conn,
            user_id=user_id,
            actor_id=viewer["id"],
            action_type="role_change",
            reason=f"Role updated from {target['role']} to {new_role}.",
            metadata={"fromRole": target["role"], "toRole": new_role},
            created_at=now,
        )
        notify_staff_action(
            conn,
            target_user_id=user_id,
            actor=viewer,
            action="role_change",
            reason=f"Role updated from {target['role']} to {new_role}.",
            metadata={"fromRole": target["role"], "toRole": new_role},
            created_at=now,
        )
        conn.commit()
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "user": get_user_profile(conn, user_id, viewer=viewer),
        }

    def api_moderate_user(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        user_id: int,
    ) -> dict[str, Any]:
        if not viewer or not is_staff(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        ensure_can_participate(viewer)
        target_row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not target_row:
            raise APIError("User not found.", HTTPStatus.NOT_FOUND)
        target = sync_user_restrictions(conn, target_row)
        if not target or not can_moderate_user(viewer, target):
            raise APIError("You cannot moderate that user.", HTTPStatus.FORBIDDEN)

        data = self.read_json()
        action = str(data.get("action") or "").strip().lower()
        now = utc_iso()
        message = "Moderation action saved."

        if action == "note":
            note = clean_text(data.get("note") or data.get("reason"), min_len=2, max_len=1000, field="Note")
            log_moderation_action(
                conn,
                user_id=user_id,
                actor_id=viewer["id"],
                action_type="note",
                note=note,
                created_at=now,
            )
            conn.commit()
            message = "Staff note saved."
        elif action == "warn":
            reason = clean_text(data.get("reason"), min_len=4, max_len=500, field="Warning reason")
            log_moderation_action(
                conn,
                user_id=user_id,
                actor_id=viewer["id"],
                action_type="warn",
                reason=reason,
                created_at=now,
            )
            notify_staff_action(
                conn,
                target_user_id=user_id,
                actor=viewer,
                action="warn",
                reason=reason,
                created_at=now,
            )
            conn.commit()
            message = "Warning logged."
        elif action == "timeout":
            if is_banned_user(target):
                raise APIError("Banned users cannot also receive a timeout.")
            try:
                minutes = int(data.get("minutes"))
            except (TypeError, ValueError) as exc:
                raise APIError("Timeout duration must be a whole number of minutes.") from exc
            if minutes < 1 or minutes > 43_200:
                raise APIError("Timeout duration must be between 1 minute and 30 days.")
            reason = clean_text(data.get("reason"), min_len=4, max_len=500, field="Timeout reason")
            expires_at = utc_iso(utc_now() + timedelta(minutes=minutes))
            conn.execute(
                """
                UPDATE users
                SET timeout_until = ?, timeout_reason = ?, timeout_set_by = ?, updated_at = ?
                WHERE id = ?
                """,
                (expires_at, reason, viewer["id"], now, user_id),
            )
            log_moderation_action(
                conn,
                user_id=user_id,
                actor_id=viewer["id"],
                action_type="timeout",
                reason=reason,
                expires_at=expires_at,
                metadata={"minutes": minutes},
                created_at=now,
            )
            notify_staff_action(
                conn,
                target_user_id=user_id,
                actor=viewer,
                action="timeout",
                reason=reason,
                metadata={"minutes": minutes},
                created_at=now,
            )
            conn.commit()
            message = "User timed out."
        elif action == "clear_timeout":
            if not active_timeout_until(target):
                raise APIError("This user is not currently timed out.")
            reason = clean_text(data.get("reason"), min_len=0, max_len=500, field="Reason")
            conn.execute(
                """
                UPDATE users
                SET timeout_until = NULL, timeout_reason = '', timeout_set_by = NULL, updated_at = ?
                WHERE id = ?
                """,
                (now, user_id),
            )
            log_moderation_action(
                conn,
                user_id=user_id,
                actor_id=viewer["id"],
                action_type="clear_timeout",
                reason=reason,
                created_at=now,
            )
            notify_staff_action(
                conn,
                target_user_id=user_id,
                actor=viewer,
                action="clear_timeout",
                reason=reason,
                created_at=now,
            )
            conn.commit()
            message = "Timeout cleared."
        elif action == "mute":
            try:
                minutes = int(data.get("minutes"))
            except (TypeError, ValueError) as exc:
                raise APIError("Mute duration must be a whole number of minutes.") from exc
            if minutes < 1 or minutes > 43_200:
                raise APIError("Mute duration must be between 1 minute and 30 days.")
            reason = clean_text(data.get("reason"), min_len=4, max_len=500, field="Mute reason")
            expires_at = utc_iso(utc_now() + timedelta(minutes=minutes))
            conn.execute(
                """
                UPDATE users
                SET mute_until = ?, mute_reason = ?, mute_set_by = ?, updated_at = ?
                WHERE id = ?
                """,
                (expires_at, reason, viewer["id"], now, user_id),
            )
            log_moderation_action(
                conn,
                user_id=user_id,
                actor_id=viewer["id"],
                action_type="mute",
                reason=reason,
                expires_at=expires_at,
                metadata={"minutes": minutes},
                created_at=now,
            )
            notify_staff_action(
                conn,
                target_user_id=user_id,
                actor=viewer,
                action="mute",
                reason=reason,
                metadata={"minutes": minutes},
                created_at=now,
            )
            conn.commit()
            message = "User muted."
        elif action == "clear_mute":
            if not active_mute_until(target):
                raise APIError("This user is not currently muted.")
            reason = clean_text(data.get("reason"), min_len=0, max_len=500, field="Reason")
            conn.execute(
                """
                UPDATE users
                SET mute_until = NULL, mute_reason = '', mute_set_by = NULL, updated_at = ?
                WHERE id = ?
                """,
                (now, user_id),
            )
            log_moderation_action(
                conn,
                user_id=user_id,
                actor_id=viewer["id"],
                action_type="clear_mute",
                reason=reason,
                created_at=now,
            )
            notify_staff_action(
                conn,
                target_user_id=user_id,
                actor=viewer,
                action="clear_mute",
                reason=reason,
                created_at=now,
            )
            conn.commit()
            message = "Mute cleared."
        elif action == "shadow_mute":
            reason = clean_text(data.get("reason"), min_len=4, max_len=500, field="Shadow mute reason")
            conn.execute(
                """
                UPDATE users
                SET shadow_muted = 1, updated_at = ?
                WHERE id = ?
                """,
                (now, user_id),
            )
            log_moderation_action(
                conn,
                user_id=user_id,
                actor_id=viewer["id"],
                action_type="shadow_mute",
                reason=reason,
                created_at=now,
            )
            conn.commit()
            message = "User shadow-muted."
        elif action == "clear_shadow_mute":
            if not bool(target.get("shadow_muted")):
                raise APIError("This user is not currently shadow-muted.")
            reason = clean_text(data.get("reason"), min_len=0, max_len=500, field="Reason")
            conn.execute(
                """
                UPDATE users
                SET shadow_muted = 0, updated_at = ?
                WHERE id = ?
                """,
                (now, user_id),
            )
            log_moderation_action(
                conn,
                user_id=user_id,
                actor_id=viewer["id"],
                action_type="clear_shadow_mute",
                reason=reason,
                created_at=now,
            )
            conn.commit()
            message = "Shadow mute cleared."
        elif action == "ban":
            if is_banned_user(target):
                raise APIError("This user is already banned.")
            reason = clean_text(data.get("reason"), min_len=4, max_len=500, field="Ban reason")
            conn.execute(
                """
                UPDATE users
                SET banned_at = ?, ban_reason = ?, banned_by = ?,
                    timeout_until = NULL, timeout_reason = '', timeout_set_by = NULL,
                    mute_until = NULL, mute_reason = '', mute_set_by = NULL,
                    updated_at = ?
                WHERE id = ?
                """,
                (now, reason, viewer["id"], now, user_id),
            )
            log_moderation_action(
                conn,
                user_id=user_id,
                actor_id=viewer["id"],
                action_type="ban",
                reason=reason,
                created_at=now,
            )
            notify_staff_action(
                conn,
                target_user_id=user_id,
                actor=viewer,
                action="ban",
                reason=reason,
                created_at=now,
            )
            conn.commit()
            delete_sessions_for_user(conn, user_id)
            message = "User banned."
        elif action == "unban":
            if not is_banned_user(target):
                raise APIError("This user is not currently banned.")
            reason = clean_text(data.get("reason"), min_len=0, max_len=500, field="Reason")
            conn.execute(
                """
                UPDATE users
                SET banned_at = NULL, ban_reason = '', banned_by = NULL, updated_at = ?
                WHERE id = ?
                """,
                (now, user_id),
            )
            log_moderation_action(
                conn,
                user_id=user_id,
                actor_id=viewer["id"],
                action_type="unban",
                reason=reason,
                created_at=now,
            )
            notify_staff_action(
                conn,
                target_user_id=user_id,
                actor=viewer,
                action="unban",
                reason=reason,
                created_at=now,
            )
            conn.commit()
            message = "User unbanned."
        elif action == "xp_adjust":
            try:
                delta_xp = int(data.get("deltaXp"))
            except (TypeError, ValueError) as exc:
                raise APIError("XP adjustment must be a whole number.") from exc
            if delta_xp == 0 or delta_xp < -5000 or delta_xp > 5000:
                raise APIError("XP adjustment must be between -5000 and 5000 and cannot be zero.")
            reason = clean_text(data.get("reason"), min_len=4, max_len=500, field="XP reason")
            before_xp = int(target["xp"])
            before_role = target["role"]
            award_xp(conn, user_id, delta_xp)
            updated_target = conn.execute("SELECT xp, role FROM users WHERE id = ?", (user_id,)).fetchone()
            after_xp = int(updated_target["xp"]) if updated_target else before_xp
            after_role = updated_target["role"] if updated_target else before_role
            log_moderation_action(
                conn,
                user_id=user_id,
                actor_id=viewer["id"],
                action_type="xp_adjust",
                reason=reason,
                delta_xp=delta_xp,
                metadata={
                    "beforeXp": before_xp,
                    "afterXp": after_xp,
                    "beforeRole": before_role,
                    "afterRole": after_role,
                },
                created_at=now,
            )
            notify_staff_action(
                conn,
                target_user_id=user_id,
                actor=viewer,
                action="xp_adjust",
                reason=reason,
                delta_xp=delta_xp,
                metadata={
                    "beforeXp": before_xp,
                    "afterXp": after_xp,
                    "beforeRole": before_role,
                    "afterRole": after_role,
                },
                created_at=now,
            )
            conn.commit()
            message = "XP updated."
        elif action == "set_temp_password":
            if not is_admin(viewer):
                raise APIError(
                    "Only admins and the owner can set temporary passwords.",
                    HTTPStatus.FORBIDDEN,
                )
            if is_banned_user(target):
                raise APIError("Unban the user before issuing a recovery password.")
            temp_password = clean_password(data.get("tempPassword"))
            note = clean_text(data.get("note"), min_len=0, max_len=500, field="Recovery note")
            try:
                expires_in_hours = int(data.get("expiresInHours") or 48)
            except (TypeError, ValueError) as exc:
                raise APIError("Temporary password expiry must be a whole number of hours.") from exc
            if expires_in_hours < 1 or expires_in_hours > 168:
                raise APIError("Temporary passwords must expire between 1 and 168 hours.")
            reset_expires_at = utc_iso(utc_now() + timedelta(hours=expires_in_hours))
            conn.execute(
                """
                UPDATE users
                SET password_hash = ?, password_reset_required = 1,
                    password_reset_set_by = ?, password_reset_set_at = ?,
                    password_reset_expires_at = ?, recovery_note = ?, updated_at = ?
                WHERE id = ?
                """,
                (make_password_hash(temp_password), viewer["id"], now, reset_expires_at, note, now, user_id),
            )
            log_moderation_action(
                conn,
                user_id=user_id,
                actor_id=viewer["id"],
                action_type="temp_password",
                note=note,
                expires_at=reset_expires_at,
                metadata={
                    "expiresInHours": expires_in_hours,
                    "recoveryDiscordUsername": target.get("recovery_discord_username") or "",
                    "checklist": [
                        "Verify the request through the user's saved Discord username or known forum context.",
                        "Record why the account owner is believed to be legitimate.",
                        "Tell the user the temporary password expires and must be changed immediately after login.",
                    ],
                },
                created_at=now,
            )
            notify_staff_action(
                conn,
                target_user_id=user_id,
                actor=viewer,
                action="temp_password",
                note=note,
                metadata={"expiresAt": reset_expires_at},
                created_at=now,
            )
            conn.commit()
            delete_sessions_for_user(conn, user_id)
            message = "Temporary password set. The user will be forced to reset it after login."
        else:
            raise APIError("Unknown moderation action.")

        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "user": get_user_profile(conn, user_id, viewer=viewer),
            "message": message,
        }
