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


class AppealModerationApiMixin:
    def api_appeals(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        query: dict[str, list[str]],
    ) -> dict[str, Any]:
        if not viewer:
            raise APIError("You must be logged in.", HTTPStatus.UNAUTHORIZED)
        status = (query.get("status") or ["open"])[0].strip().lower()
        if status not in {"open", "resolved", "all"}:
            status = "open"
        target_user_id = None
        if is_staff(viewer):
            raw_user_id = (query.get("userId") or [""])[0].strip()
            if raw_user_id:
                try:
                    target_user_id = int(raw_user_id)
                except (TypeError, ValueError):
                    target_user_id = None
            if mark_notifications_read(conn, viewer["id"], target_type="appeal_queue"):
                conn.commit()
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "items": list_appeals_for_viewer(
                conn,
                viewer,
                status=status,
                target_user_id=target_user_id,
            ),
            "counts": {
                "open": get_open_appeal_count(conn),
                "resolved": conn.execute(
                    "SELECT COUNT(*) AS count FROM appeals WHERE status = 'resolved'"
                ).fetchone()["count"],
            },
        }

    def api_create_appeal(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not viewer:
            raise APIError("You must be logged in.", HTTPStatus.UNAUTHORIZED)
        if not (is_banned_user(viewer) or active_timeout_until(viewer) or active_mute_until(viewer)):
            raise APIError("There is no active restriction on this account to appeal.")
        existing = conn.execute(
            "SELECT id FROM appeals WHERE user_id = ? AND status = 'open' ORDER BY created_at DESC LIMIT 1",
            (viewer["id"],),
        ).fetchone()
        if existing:
            raise APIError("You already have an open appeal under review.")
        data = self.read_json()
        message = clean_text(data.get("message"), min_len=12, max_len=2000, field="Appeal")
        now = utc_iso()
        cur = conn.execute(
            """
            INSERT INTO appeals (
                user_id, target_user_id, action_id, message, status,
                staff_note, handled_by, created_at, updated_at, handled_at
            )
            VALUES (?, ?, NULL, ?, 'open', '', NULL, ?, ?, NULL)
            """,
            (viewer["id"], viewer["id"], message, now, now),
        )
        create_staff_notifications(
            conn,
            actor_id=viewer["id"],
            title=f"New appeal from {viewer['username']}",
            body=short_preview(message, max_len=140),
            target_type="appeal_queue",
            target_id=cur.lastrowid,
            created_at=now,
        )
        send_staff_discord_notice(
            title="New OmniForum appeal",
            lines=[
                f"User: {viewer['username']}",
                f"Appeal: {short_preview(message, max_len=240)}",
                f"Review: {PUBLIC_URL}/pages/settings.html",
            ],
            color=0xF4B860,
        )
        conn.commit()
        return {
            "currentUser": get_user_profile(conn, viewer["id"], viewer=viewer),
            "message": "Appeal submitted for staff review.",
            "items": list_appeals_for_viewer(conn, viewer, status="all"),
        }

    def api_update_appeal(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        appeal_id: int,
    ) -> dict[str, Any]:
        if not viewer or not is_staff(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        ensure_can_participate(viewer)
        row = conn.execute("SELECT * FROM appeals WHERE id = ?", (appeal_id,)).fetchone()
        if not row:
            raise APIError("Appeal not found.", HTTPStatus.NOT_FOUND)
        data = self.read_json()
        status = clean_report_status(data.get("status", row["status"]))
        staff_note = clean_text(
            data.get("staffNote", row["staff_note"]),
            min_len=0,
            max_len=1200,
            field="Staff note",
        )
        now = utc_iso()
        handled_at = now if status == "resolved" else None
        handled_by = viewer["id"] if status == "resolved" else None
        conn.execute(
            """
            UPDATE appeals
            SET status = ?, staff_note = ?, handled_by = ?, handled_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (status, staff_note, handled_by, handled_at, now, appeal_id),
        )
        log_audit_event(
            conn,
            actor=viewer,
            action_type="appeal_update",
            category="moderation",
            target_type="appeal",
            target_id=appeal_id,
            target_label=f"appeal #{appeal_id}",
            reason=staff_note or f"Appeal marked {status}.",
            metadata={
                "status": status,
                "userId": row["user_id"],
            },
            created_at=now,
        )
        conn.commit()
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "message": "Appeal updated.",
            "items": list_appeals_for_viewer(conn, viewer, status="all"),
        }
