from __future__ import annotations

import json
import sqlite3
from datetime import timedelta
from http import HTTPStatus
from typing import Any

from .config import (
    FLOOD_CONTROL_SECONDS,
    PUBLIC_URL,
)
from .core import (
    is_staff,
    utc_iso,
)
from .integrations import send_staff_discord_notice
from .validation import (
    clean_discord_username,
    clean_text,
)
from .audit import log_audit_event
from .account_state import (
    enforce_recent_action_limit,
    ensure_can_participate,
    ensure_can_send_message,
)
from .admin_health import get_open_contact_notice_count
from .domain import (
    add_dm_message,
    can_receive_direct_message,
    create_staff_notifications,
    get_current_user_payload,
    get_dm_thread_summary,
    get_notification_counts,
    get_or_create_dm_thread,
    list_contact_submissions,
    list_dm_messages,
    list_dm_threads,
    list_notifications,
    mark_dm_thread_read,
    mark_notifications_read,
    notify_dm_message,
)
from .text_utils import short_preview
from .errors import APIError


class MessagesApiMixin:
    def api_notifications(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        query: dict[str, list[str]],
    ) -> dict[str, Any]:
        if not viewer:
            raise APIError("You must be logged in.", HTTPStatus.UNAUTHORIZED)
        status = (query.get("status") or ["all"])[0]
        if status not in {"all", "unread"}:
            status = "all"
        kind = (query.get("kind") or ["all"])[0].strip().lower()
        if kind not in {"all", "replies", "mentions", "likes", "dms", "staff", "staff_actions"}:
            kind = "all"
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "items": list_notifications(conn, viewer["id"], status=status, kind=kind),
            "counts": get_notification_counts(conn, viewer["id"], viewer=viewer),
            "kind": kind,
        }

    def api_mark_notifications(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        notification_id: int | None = None,
    ) -> dict[str, Any]:
        if not viewer:
            raise APIError("You must be logged in.", HTTPStatus.UNAUTHORIZED)
        if notification_id is not None:
            updated = mark_notifications_read(
                conn,
                viewer["id"],
                notification_ids=[notification_id],
            )
        else:
            data = self.read_json()
            raw_ids = data.get("ids") or []
            ids: list[int] = []
            if isinstance(raw_ids, list):
                for value in raw_ids:
                    try:
                        ids.append(int(value))
                    except (TypeError, ValueError):
                        continue
            updated = mark_notifications_read(
                conn,
                viewer["id"],
                notification_ids=ids or None,
            )
        conn.commit()
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "updated": updated,
        }

    def api_messages(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not viewer:
            raise APIError("You must be logged in.", HTTPStatus.UNAUTHORIZED)
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "threads": list_dm_threads(conn, viewer["id"]),
        }

    def api_message_thread(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        thread_id: int,
    ) -> dict[str, Any]:
        if not viewer:
            raise APIError("You must be logged in.", HTTPStatus.UNAUTHORIZED)
        thread = get_dm_thread_summary(conn, thread_id, viewer["id"])
        if not thread:
            raise APIError("Conversation not found.", HTTPStatus.NOT_FOUND)
        updated_reads = 0
        if mark_dm_thread_read(conn, thread_id, viewer["id"]):
            updated_reads += 1
        updated_reads += mark_notifications_read(
            conn,
            viewer["id"],
            target_type="dm_thread",
            target_id=thread_id,
        )
        if updated_reads:
            conn.commit()
            thread = get_dm_thread_summary(conn, thread_id, viewer["id"])
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "thread": thread,
            "messages": list_dm_messages(conn, thread_id, viewer["id"]),
        }

    def api_send_message(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        ensure_can_send_message(viewer)
        self.enforce_rate_limit("dm_send", viewer)
        if not viewer:
            raise APIError("You must be logged in.", HTTPStatus.UNAUTHORIZED)
        data = self.read_json()
        try:
            recipient_id = int(data.get("recipientUserId"))
        except (TypeError, ValueError) as exc:
            raise APIError("Choose a valid member to message.") from exc
        if recipient_id == viewer["id"]:
            raise APIError("You cannot direct message yourself.")
        recipient = conn.execute("SELECT * FROM users WHERE id = ?", (recipient_id,)).fetchone()
        if not recipient:
            raise APIError("Member not found.", HTTPStatus.NOT_FOUND)
        if not can_receive_direct_message(conn, recipient, viewer):
            raise APIError("That user is not accepting new direct messages.", HTTPStatus.FORBIDDEN)
        enforce_recent_action_limit(
            conn,
            viewer,
            query="SELECT created_at FROM dm_messages WHERE sender_id = ? ORDER BY created_at DESC, id DESC LIMIT 1",
            params=(viewer["id"],),
            base_seconds=FLOOD_CONTROL_SECONDS["message"],
            verb="send another message",
        )
        content = clean_text(data.get("content"), min_len=1, max_len=4000, field="Message")
        thread_id = get_or_create_dm_thread(conn, viewer["id"], recipient_id)
        now = utc_iso()
        add_dm_message(
            conn,
            thread_id=thread_id,
            sender_id=viewer["id"],
            recipient_id=recipient_id,
            content=content,
            created_at=now,
        )
        notify_dm_message(
            conn,
            sender=viewer,
            recipient_id=recipient_id,
            thread_id=thread_id,
            content=content,
            created_at=now,
        )
        conn.commit()
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "thread": get_dm_thread_summary(conn, thread_id, viewer["id"]),
            "message": "Direct message sent.",
        }

    def api_reply_message(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        thread_id: int,
    ) -> dict[str, Any]:
        ensure_can_send_message(viewer)
        self.enforce_rate_limit("dm_send", viewer)
        if not viewer:
            raise APIError("You must be logged in.", HTTPStatus.UNAUTHORIZED)
        data = self.read_json()
        thread_row = conn.execute(
            """
            SELECT *
            FROM dm_threads
            WHERE id = ? AND (user_low_id = ? OR user_high_id = ?)
            """,
            (thread_id, viewer["id"], viewer["id"]),
        ).fetchone()
        if not thread_row:
            raise APIError("Conversation not found.", HTTPStatus.NOT_FOUND)
        recipient_id = (
            thread_row["user_high_id"]
            if thread_row["user_low_id"] == viewer["id"]
            else thread_row["user_low_id"]
        )
        recipient = conn.execute("SELECT * FROM users WHERE id = ?", (recipient_id,)).fetchone()
        if not recipient:
            raise APIError("Member not found.", HTTPStatus.NOT_FOUND)
        if not can_receive_direct_message(conn, recipient, viewer):
            raise APIError("That user is not accepting new direct messages.", HTTPStatus.FORBIDDEN)
        enforce_recent_action_limit(
            conn,
            viewer,
            query="SELECT created_at FROM dm_messages WHERE sender_id = ? ORDER BY created_at DESC, id DESC LIMIT 1",
            params=(viewer["id"],),
            base_seconds=FLOOD_CONTROL_SECONDS["message"],
            verb="send another message",
        )
        content = clean_text(data.get("content"), min_len=1, max_len=4000, field="Message")
        now = utc_iso()
        add_dm_message(
            conn,
            thread_id=thread_id,
            sender_id=viewer["id"],
            recipient_id=recipient_id,
            content=content,
            created_at=now,
        )
        notify_dm_message(
            conn,
            sender=viewer,
            recipient_id=recipient_id,
            thread_id=thread_id,
            content=content,
            created_at=now,
        )
        conn.commit()
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "thread": get_dm_thread_summary(conn, thread_id, viewer["id"]),
            "messages": list_dm_messages(conn, thread_id, viewer["id"]),
            "message": "Reply sent.",
        }

    def api_contact(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        self.enforce_rate_limit("contact", viewer)
        data = self.read_json()
        now = utc_iso()
        submitted_name = data.get("name") or (viewer.get("username") if viewer else "")
        name = clean_text(submitted_name, min_len=2, max_len=80, field="Name")
        discord_username = clean_discord_username(data.get("discordUsername"))
        if viewer:
            enforce_recent_action_limit(
                conn,
                viewer,
                query="SELECT created_at FROM contact_submissions WHERE user_id = ? ORDER BY created_at DESC, id DESC LIMIT 1",
                params=(viewer["id"],),
                base_seconds=FLOOD_CONTROL_SECONDS["contact"],
                verb="contact staff",
            )
        subject = clean_text(data.get("subject"), min_len=4, max_len=120, field="Subject")
        message = clean_text(data.get("message"), min_len=10, max_len=4000, field="Message")
        conn.execute(
            """
            INSERT INTO contact_submissions (
                user_id, name, email, discord_username, subject, message, status,
                admin_note, handled_by, created_at, updated_at, handled_at
            )
            VALUES (?, ?, '', ?, ?, ?, 'open', '', NULL, ?, ?, NULL)
            """,
            (
                viewer["id"] if viewer else None,
                name,
                discord_username,
                subject,
                message,
                now,
                now,
            ),
        )
        create_staff_notifications(
            conn,
            actor_id=viewer["id"] if viewer else None,
            title=f"New contact notice: {subject}",
            body=f"{name} sent a staff contact form message.",
            target_type="contact_notice",
            created_at=now,
        )
        contact_lines = [
            f"From: {name}",
            f"Subject: {subject}",
            f"Message: {short_preview(message, max_len=240)}",
        ]
        if discord_username:
            contact_lines.append(f"Discord: @{discord_username}")
        if viewer:
            contact_lines.append(f"Member: {viewer['username']}")
        contact_lines.append(f"Review: {PUBLIC_URL}/pages/settings.html")
        send_staff_discord_notice(
            title="New OmniForum contact notice",
            lines=contact_lines,
            color=0x00D4FF,
        )
        conn.commit()
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "submitted": True,
            "message": "Your message has been sent to the moderation team for review.",
        }

    def api_notices(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        query: dict[str, list[str]],
    ) -> dict[str, Any]:
        if not viewer or not is_staff(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        status = (query.get("status") or ["open"])[0]
        if status not in {"open", "resolved", "all"}:
            status = "open"
        if mark_notifications_read(conn, viewer["id"], target_type="contact_notice"):
            conn.commit()
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "items": list_contact_submissions(conn, status=status),
            "counts": {
                "open": get_open_contact_notice_count(conn),
                "resolved": conn.execute(
                    "SELECT COUNT(*) AS count FROM contact_submissions WHERE status = 'resolved'"
                ).fetchone()["count"],
            },
        }

    def api_update_contact_notice(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        submission_id: int,
    ) -> dict[str, Any]:
        if not viewer or not is_staff(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        ensure_can_participate(viewer)
        row = conn.execute(
            "SELECT * FROM contact_submissions WHERE id = ?",
            (submission_id,),
        ).fetchone()
        if not row:
            raise APIError("Contact submission not found.", HTTPStatus.NOT_FOUND)
        data = self.read_json()
        new_status = data.get("status", row["status"])
        if new_status not in {"open", "resolved"}:
            raise APIError("Invalid notice status.")
        admin_note = clean_text(
            data.get("adminNote", row["admin_note"]),
            min_len=0,
            max_len=1000,
            field="Admin note",
        )
        now = utc_iso()
        handled_at = now if new_status == "resolved" else None
        handled_by = viewer["id"] if new_status == "resolved" else None
        conn.execute(
            """
            UPDATE contact_submissions
            SET status = ?, admin_note = ?, handled_by = ?, handled_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (new_status, admin_note, handled_by, handled_at, now, submission_id),
        )
        log_audit_event(
            conn,
            actor=viewer,
            action_type="contact_notice_update",
            category="moderation",
            target_type="contact_notice",
            target_id=submission_id,
            target_label=row["subject"],
            reason=admin_note or f"Contact notice marked {new_status}.",
            metadata={
                "status": new_status,
                "name": row["name"],
                "discordUsername": row["discord_username"],
            },
            created_at=now,
        )
        conn.commit()
        updated = list_contact_submissions(conn, status="all", limit=200)
        item = next((entry for entry in updated if entry["id"] == submission_id), None)
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "item": item,
            "counts": {
                "open": get_open_contact_notice_count(conn),
                "resolved": conn.execute(
                    "SELECT COUNT(*) AS count FROM contact_submissions WHERE status = 'resolved'"
                ).fetchone()["count"],
            },
        }
