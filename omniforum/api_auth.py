from __future__ import annotations

import json
import sqlite3
from datetime import timedelta
from http import HTTPStatus
from typing import Any

from .config import AVATAR_MAX_BYTES
from .core import (
    consume_recovery_code,
    create_recovery_codes,
    make_password_hash,
    normalize_recovery_code,
    parse_iso,
    recovery_code_summary,
    utc_iso,
    utc_now,
    verify_password,
)
from .email_auth import (
    EMAIL_AUTH_ENABLED,
    consume_email_auth_token,
    create_email_auth_token,
    public_email_auth_features,
    send_password_reset_email,
)
from .media import (
    decode_image_upload,
    delete_media_file,
    ensure_user_media_quota,
    store_image_upload,
)
from .runtime_logging import append_server_log
from .validation import (
    clean_discord_username,
    clean_dm_privacy,
    clean_email,
    clean_invite_code,
    clean_password,
    clean_profile_accent,
    clean_profile_badge,
    clean_signature,
    clean_site_theme,
    clean_status_text,
    clean_text,
    clean_username,
    ensure_username_allowed_for_registration,
    find_valid_invite_code,
    get_registration_settings,
    registration_status,
)
from .audit import log_audit_event
from .account_state import (
    ensure_can_participate,
    sync_user_restrictions,
)
from .sessions import (
    create_session,
    delete_session,
    revoke_other_sessions,
)
from .domain import (
    build_user_export,
    create_staff_notifications,
    get_current_user_payload,
    get_user_profile,
)
from .errors import APIError


class AuthApiMixin:
    def api_auth_features(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        return {
            "authFeatures": {"email": public_email_auth_features()},
            "currentUser": get_current_user_payload(conn, viewer),
        }

    def api_current_user(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        return {
            "authFeatures": {"email": public_email_auth_features()},
            "currentUser": get_current_user_payload(conn, viewer),
        }

    def api_register(self, conn: sqlite3.Connection) -> dict[str, Any]:
        self.enforce_rate_limit("register")
        self.enforce_rate_limit("register_burst")
        data = self.read_json()
        username = clean_username(data.get("username"))
        password = clean_password(data.get("password"))
        raw_email = str(data.get("email") or "").strip()
        if raw_email and not EMAIL_AUTH_ENABLED:
            raise APIError("Email account features are not enabled on this forum.")
        email = clean_email(raw_email) if raw_email else ""
        now = utc_iso()
        current_count = conn.execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"]
        first_account = current_count == 0
        role = "owner" if first_account else "new"
        settings = get_registration_settings(conn)
        invite_code = ""
        invite_row = None
        approval_status = "approved"
        if not first_account:
            ensure_username_allowed_for_registration(username, settings)
            public_enabled = bool(settings.get("public_registration_enabled", 1))
            invite_required = bool(settings.get("invite_required", 0))
            if not public_enabled and not invite_required:
                raise APIError("Registration is currently closed.", HTTPStatus.FORBIDDEN)
            if invite_required:
                invite_code = clean_invite_code(data.get("inviteCode"))
                invite_row = find_valid_invite_code(conn, invite_code)
                if not invite_row:
                    raise APIError("That invite code is invalid, expired, or already used.", HTTPStatus.FORBIDDEN)
            approval_status = "pending" if bool(settings.get("approval_required", 0)) else "approved"
        bio = "New to OmniForum. Say hello and start the first thread."
        approved_at = now if approval_status == "approved" else None
        last_seen_at = now if approval_status == "approved" else None
        try:
            cur = conn.execute(
                """
                INSERT INTO users (
                    username, password_hash, email, role, bio, xp, created_at, updated_at, last_seen_at,
                    approval_status, approved_at, registration_ip, invite_code_used
                )
                VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    username,
                    make_password_hash(password),
                    email,
                    role,
                    bio,
                    now,
                    now,
                    last_seen_at,
                    approval_status,
                    approved_at,
                    self.request_ip(),
                    invite_code,
                ),
            )
            if invite_row:
                conn.execute(
                    "UPDATE invite_codes SET uses = uses + 1, updated_at = ? WHERE id = ?",
                    (now, invite_row["id"]),
                )
            if approval_status == "pending":
                create_staff_notifications(
                    conn,
                    actor_id=None,
                    title="Registration pending approval",
                    body=f"{username} is waiting for admin review.",
                    target_type="registration_queue",
                    target_id=cur.lastrowid,
                    created_at=now,
                )
            conn.commit()
        except sqlite3.IntegrityError as exc:
            raise APIError("Username already taken.") from exc

        if approval_status == "pending":
            append_server_log(f"registration pending approval: {username}")
            return {
                "currentUser": None,
                "pendingApproval": True,
                "message": "Account created and pending admin approval.",
                "__status__": HTTPStatus.ACCEPTED,
            }

        token, expires_at, csrf_token = create_session(
            conn,
            cur.lastrowid,
            ip_address=self.request_ip(),
            user_agent=self.request_user_agent(),
        )
        user = get_user_profile(
            conn,
            cur.lastrowid,
            viewer={"id": cur.lastrowid, "role": role},
        )
        if user is not None:
            user["csrfToken"] = csrf_token
        return {
            "currentUser": user,
            "__status__": HTTPStatus.CREATED,
            "__cookie_header__": self.make_session_cookie(token, expires_at),
        }

    def api_login(self, conn: sqlite3.Connection) -> dict[str, Any]:
        self.enforce_rate_limit("login")
        data = self.read_json()
        username = clean_username(data.get("username"))
        password = clean_text(data.get("password"), min_len=0, max_len=128, field="Password")
        recovery_code = normalize_recovery_code(data.get("recoveryCode"))
        if not password and not recovery_code:
            raise APIError("Enter a password or recovery code.", HTTPStatus.UNAUTHORIZED)
        row = conn.execute(
            "SELECT * FROM users WHERE lower(username) = lower(?)",
            (username,),
        ).fetchone()
        if not row:
            raise APIError("Invalid username or password.", HTTPStatus.UNAUTHORIZED)
        status = registration_status(row)
        if status == "pending":
            raise APIError("This account is still pending admin approval.", HTTPStatus.FORBIDDEN)
        if status == "rejected":
            raise APIError("This account registration was rejected.", HTTPStatus.FORBIDDEN)
        password_valid = verify_password(password, row["password_hash"])
        recovery_code_used = False
        now = utc_iso()
        if not password_valid:
            if recovery_code and consume_recovery_code(conn, row["id"], recovery_code):
                recovery_code_used = True
                conn.execute(
                    """
                    UPDATE users
                    SET password_reset_required = 1,
                        password_reset_set_by = NULL,
                        password_reset_set_at = ?,
                        password_reset_expires_at = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        now,
                        utc_iso(utc_now() + timedelta(minutes=30)),
                        now,
                        row["id"],
                    ),
                )
                log_audit_event(
                    conn,
                    actor_id=row["id"],
                    action_type="recovery_code_login",
                    category="settings",
                    target_type="user",
                    target_id=row["id"],
                    target_label=row["username"],
                    reason="Recovery code used to start a forced password reset session.",
                    created_at=now,
                )
                conn.commit()
                row = conn.execute("SELECT * FROM users WHERE id = ?", (row["id"],)).fetchone()
            else:
                raise APIError("Invalid username or password.", HTTPStatus.UNAUTHORIZED)
        reset_expires_at = parse_iso(row["password_reset_expires_at"] if row else None)
        if bool(row["password_reset_required"]) and reset_expires_at and reset_expires_at <= utc_now():
            raise APIError(
                "That temporary password has expired. Ask an admin to issue a new recovery password.",
                HTTPStatus.FORBIDDEN,
            )
        user_row = sync_user_restrictions(conn, row)
        if not user_row:
            raise APIError("Invalid username or password.", HTTPStatus.UNAUTHORIZED)
        token, expires_at, csrf_token = create_session(
            conn,
            user_row["id"],
            ip_address=self.request_ip(),
            user_agent=self.request_user_agent(),
        )
        conn.execute(
            "UPDATE users SET last_seen_at = ?, updated_at = ? WHERE id = ?",
            (now, now, user_row["id"]),
        )
        conn.commit()
        user = get_user_profile(conn, user_row["id"], viewer=user_row)
        if user is not None:
            user["csrfToken"] = csrf_token
        return {
            "currentUser": user,
            "recoveryCodeUsed": recovery_code_used,
            "__cookie_header__": self.make_session_cookie(token, expires_at),
        }

    def api_logout(self, conn: sqlite3.Connection) -> dict[str, Any]:
        token = self.current_session_token()
        delete_session(conn, token)
        return {
            "currentUser": None,
            "__cookie_header__": self.clear_session_cookie_header(),
        }

    def api_update_me(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        ensure_can_participate(viewer)
        self.enforce_rate_limit("profile_update", viewer)
        data = self.read_json()
        username = clean_username(
            data.get("username", viewer.get("username", "")),
        )
        bio = clean_text(
            data.get("bio", viewer.get("bio", "")),
            min_len=0,
            max_len=280,
            field="Bio",
        )
        status_text = clean_status_text(data.get("statusText", viewer.get("status_text", "")))
        avatar_upload = data.get("avatarUpload")
        remove_avatar = bool(data.get("removeAvatar"))
        site_theme = clean_site_theme(data.get("siteTheme", viewer.get("site_theme", "midnight")))
        dm_privacy = clean_dm_privacy(data.get("dmPrivacy", viewer.get("dm_privacy", "everyone")))
        blur_sensitive_media = bool(data.get("blurSensitiveMedia", viewer.get("blur_sensitive_media", 1)))
        compact_post_layout = bool(data.get("compactPostLayout", viewer.get("compact_post_layout", 0)))
        hide_ignored_content = bool(data.get("hideIgnoredContent", viewer.get("hide_ignored_content", 1)))
        notify_replies = bool(data.get("notifyReplies", viewer.get("notify_replies", 1)))
        notify_likes = bool(data.get("notifyLikes", viewer.get("notify_likes", 1)))
        notify_mentions = bool(data.get("notifyMentions", viewer.get("notify_mentions", 1)))
        notify_dms = bool(data.get("notifyDms", viewer.get("notify_dms", 1)))
        signature = clean_signature(data.get("signature", viewer.get("signature", "")))
        profile_badge = clean_profile_badge(data.get("profileBadge", viewer.get("profile_badge", "")))
        profile_accent = clean_profile_accent(data.get("profileAccent", viewer.get("profile_accent", "")))
        recovery_discord_username = clean_discord_username(
            data.get("recoveryDiscordUsername", viewer.get("recovery_discord_username", ""))
        )
        email = str(viewer.get("email") or "")
        if "email" in data:
            raw_email = str(data.get("email") or "").strip()
            if raw_email and not EMAIL_AUTH_ENABLED:
                raise APIError("Email account features are not enabled on this forum.")
            email = clean_email(raw_email) if raw_email else ""
        current_avatar_path = str(viewer.get("avatar_path") or "")
        next_avatar_path = current_avatar_path
        decoded_avatar_upload = None
        if avatar_upload:
            decoded_avatar_upload = decode_image_upload(
                avatar_upload,
                field="Avatar",
                max_bytes=AVATAR_MAX_BYTES,
                kind="avatar",
            )
            ensure_user_media_quota(
                conn,
                viewer["id"],
                [decoded_avatar_upload],
                replacing_paths=[current_avatar_path] if current_avatar_path else [],
            )
            next_avatar_path = store_image_upload(
                decoded_avatar_upload,
                bucket="avatars",
            )
        elif remove_avatar:
            next_avatar_path = ""
        now = utc_iso()
        try:
            conn.execute(
                """
                UPDATE users
                SET username = ?, bio = ?, status_text = ?, avatar_path = ?, site_theme = ?, dm_privacy = ?,
                    blur_sensitive_media = ?, compact_post_layout = ?, hide_ignored_content = ?,
                    notify_replies = ?, notify_likes = ?, notify_mentions = ?, notify_dms = ?,
                    signature = ?, profile_badge = ?, profile_accent = ?,
                    recovery_discord_username = ?, email = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    username,
                    bio,
                    status_text,
                    next_avatar_path,
                    site_theme,
                    dm_privacy,
                    int(blur_sensitive_media),
                    int(compact_post_layout),
                    int(hide_ignored_content),
                    int(notify_replies),
                    int(notify_likes),
                    int(notify_mentions),
                    int(notify_dms),
                    signature,
                    profile_badge,
                    profile_accent,
                    recovery_discord_username,
                    email,
                    now,
                    viewer["id"],
                ),
            )
        except sqlite3.IntegrityError as exc:
            if next_avatar_path != current_avatar_path:
                delete_media_file(next_avatar_path)
            raise APIError("Username already taken.") from exc
        conn.commit()
        if next_avatar_path != current_avatar_path:
            delete_media_file(current_avatar_path)
        refreshed = sync_user_restrictions(
            conn,
            conn.execute("SELECT * FROM users WHERE id = ?", (viewer["id"],)).fetchone(),
        )
        if refreshed is not None and viewer.get("session_csrf_token"):
            refreshed["session_csrf_token"] = viewer.get("session_csrf_token")
        return {
            "currentUser": get_user_profile(conn, viewer["id"], viewer=refreshed),
            "message": "Profile updated.",
        }

    def api_update_password(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not viewer:
            raise APIError("You must be logged in.", HTTPStatus.UNAUTHORIZED)
        row = conn.execute("SELECT * FROM users WHERE id = ?", (viewer["id"],)).fetchone()
        if not row:
            raise APIError("User not found.", HTTPStatus.NOT_FOUND)
        user_row = sync_user_restrictions(conn, row)
        if not user_row:
            raise APIError("User not found.", HTTPStatus.NOT_FOUND)

        data = self.read_json()
        new_password = clean_password(data.get("newPassword"))
        current_password = str(data.get("currentPassword") or "")

        if not bool(user_row.get("password_reset_required")):
            if not verify_password(current_password, user_row["password_hash"]):
                raise APIError("Current password is incorrect.", HTTPStatus.FORBIDDEN)

        if verify_password(new_password, user_row["password_hash"]):
            raise APIError("Choose a password different from the current one.")

        now = utc_iso()
        conn.execute(
            """
            UPDATE users
            SET password_hash = ?, password_reset_required = 0,
                password_reset_set_by = NULL, password_reset_set_at = NULL,
                password_reset_expires_at = NULL,
                updated_at = ?
            WHERE id = ?
            """,
            (make_password_hash(new_password), now, viewer["id"]),
        )
        conn.commit()
        refreshed = sync_user_restrictions(
            conn,
            conn.execute("SELECT * FROM users WHERE id = ?", (viewer["id"],)).fetchone(),
        )
        if refreshed is not None and viewer.get("session_csrf_token"):
            refreshed["session_csrf_token"] = viewer.get("session_csrf_token")
        return {
            "currentUser": get_user_profile(conn, viewer["id"], viewer=refreshed),
            "message": "Password updated.",
        }

    def api_revoke_other_sessions(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        ensure_can_participate(viewer)
        if not viewer:
            raise APIError("You must be logged in.", HTTPStatus.UNAUTHORIZED)
        revoked = revoke_other_sessions(conn, viewer["id"], self.current_session_token())
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "revoked": revoked,
            "message": "Other active sessions were signed out." if revoked else "No other active sessions were found.",
        }

    def api_recovery_codes(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        ensure_can_participate(viewer)
        if not viewer:
            raise APIError("You must be logged in.", HTTPStatus.UNAUTHORIZED)
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "summary": recovery_code_summary(conn, viewer["id"]),
            "discordUsername": viewer.get("recovery_discord_username") or "",
            "message": "Recovery codes can be used once if you forget your password.",
        }

    def api_create_recovery_codes(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        ensure_can_participate(viewer)
        if not viewer:
            raise APIError("You must be logged in.", HTTPStatus.UNAUTHORIZED)
        data = self.read_json()
        if not bool(viewer.get("password_reset_required")):
            current_password = str(data.get("currentPassword") or "")
            if not verify_password(current_password, viewer["password_hash"]):
                raise APIError("Current password is required to regenerate recovery codes.", HTTPStatus.FORBIDDEN)
        codes = create_recovery_codes(conn, viewer["id"])
        log_audit_event(
            conn,
            actor=viewer,
            action_type="recovery_codes_regenerate",
            category="settings",
            target_type="user",
            target_id=viewer["id"],
            target_label=viewer["username"],
            reason="Account recovery codes regenerated.",
        )
        conn.commit()
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "codes": codes,
            "summary": recovery_code_summary(conn, viewer["id"]),
            "message": "Recovery codes regenerated. Store them somewhere safe; they are shown once.",
        }

    def api_request_email_password_reset(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        self.enforce_rate_limit("email_auth", viewer)
        data = self.read_json()
        identifier = clean_text(data.get("identifier"), min_len=3, max_len=200, field="Account")
        generic = {
            "authFeatures": {"email": public_email_auth_features()},
            "message": "If that account has email recovery enabled, a reset link has been sent.",
        }
        if not EMAIL_AUTH_ENABLED:
            raise APIError("Email account features are not enabled on this forum.")
        row = conn.execute(
            """
            SELECT id, username, email
            FROM users
            WHERE username = ? COLLATE NOCASE OR email = ? COLLATE NOCASE
            """,
            (identifier, identifier),
        ).fetchone()
        if not row or not row["email"]:
            return generic
        token = create_email_auth_token(
            conn,
            int(row["id"]),
            email=str(row["email"]),
            purpose="password_reset",
        )
        send_password_reset_email(str(row["username"]), str(row["email"]), token)
        conn.commit()
        log_audit_event(
            conn,
            actor=None,
            action_type="email_password_reset_request",
            category="settings",
            target_type="user",
            target_id=int(row["id"]),
            target_label=str(row["username"]),
            reason="Email password reset link requested.",
        )
        conn.commit()
        return generic

    def api_complete_email_password_reset(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        self.enforce_rate_limit("email_auth", viewer)
        if not EMAIL_AUTH_ENABLED:
            raise APIError("Email account features are not enabled on this forum.")
        data = self.read_json()
        token_value = clean_text(data.get("token"), min_len=20, max_len=160, field="Reset token")
        new_password = clean_password(data.get("newPassword"))
        token_row = consume_email_auth_token(conn, token_value, purpose="password_reset")
        if not token_row:
            raise APIError("That reset link is invalid or expired.", HTTPStatus.FORBIDDEN)
        user_row = conn.execute("SELECT * FROM users WHERE id = ?", (int(token_row["user_id"]),)).fetchone()
        if not user_row:
            raise APIError("User not found.", HTTPStatus.NOT_FOUND)
        if verify_password(new_password, user_row["password_hash"]):
            raise APIError("Choose a password different from the current one.")
        now = utc_iso()
        conn.execute(
            """
            UPDATE users
            SET password_hash = ?, password_reset_required = 0,
                password_reset_set_by = NULL, password_reset_set_at = NULL,
                password_reset_expires_at = NULL,
                email_verified_at = COALESCE(email_verified_at, ?),
                updated_at = ?
            WHERE id = ?
            """,
            (make_password_hash(new_password), now, now, int(user_row["id"])),
        )
        log_audit_event(
            conn,
            actor=None,
            action_type="email_password_reset_complete",
            category="settings",
            target_type="user",
            target_id=int(user_row["id"]),
            target_label=str(user_row["username"]),
            reason="Password reset completed through an email link.",
        )
        conn.commit()
        return {
            "authFeatures": {"email": public_email_auth_features()},
            "message": "Password updated. You can now log in with the new password.",
        }

    def api_export_me(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        ensure_can_participate(viewer)
        if not viewer:
            raise APIError("You must be logged in.", HTTPStatus.UNAUTHORIZED)
        export_payload = build_user_export(conn, viewer["id"])
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "filename": f"omniforum-export-{viewer['username']}-{utc_now().strftime('%Y%m%d-%H%M%S')}.json",
            "export": export_payload,
        }
