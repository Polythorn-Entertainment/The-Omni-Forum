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


class ReportModerationApiMixin:
    def api_reports(
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
        if mark_notifications_read(conn, viewer["id"], target_type="report_queue"):
            conn.commit()
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "items": list_reports(conn, status=status),
            "macros": list_moderation_macros(conn),
            "counts": {
                "open": get_open_report_count(conn),
                "resolved": conn.execute(
                    "SELECT COUNT(*) AS count FROM reports WHERE status = 'resolved'"
                ).fetchone()["count"],
                "appeals": get_open_appeal_count(conn),
            },
        }

    def api_create_report(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not viewer:
            raise APIError("You must be logged in.", HTTPStatus.UNAUTHORIZED)
        self.enforce_rate_limit("report", viewer)
        enforce_recent_action_limit(
            conn,
            viewer,
            query="SELECT created_at FROM reports WHERE reporter_id = ? ORDER BY created_at DESC, id DESC LIMIT 1",
            params=(viewer["id"],),
            base_seconds=FLOOD_CONTROL_SECONDS["report"],
            verb="submit another report",
        )
        data = self.read_json()
        target_type = str(data.get("targetType") or "").strip().lower()
        try:
            target_id = int(data.get("targetId"))
        except (TypeError, ValueError) as exc:
            raise APIError("Choose something valid to report.") from exc
        target = resolve_report_target(conn, target_type, target_id, viewer=viewer)
        reason = clean_text(data.get("reason"), min_len=3, max_len=80, field="Reason")
        details = clean_text(data.get("details"), min_len=0, max_len=1500, field="Details")
        now = utc_iso()
        conn.execute(
            """
            INSERT INTO reports (
                reporter_id, target_type, target_id, target_label, target_preview,
                context_thread_id, reason, details, status, admin_note,
                handled_by, created_at, updated_at, handled_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open', '', NULL, ?, ?, NULL)
            """,
            (
                viewer["id"],
                target["type"],
                target["id"],
                target["label"],
                target["preview"],
                target.get("contextThreadId"),
                reason,
                details,
                now,
                now,
            ),
        )
        create_staff_notifications(
            conn,
            actor_id=viewer["id"],
            title=f"New report: {reason}",
            body=f"{viewer['username']} reported {target['label']}.",
            target_type="report_queue",
            metadata={"targetType": target["type"], "targetId": target["id"]},
            created_at=now,
        )
        report_lines = [
            f"Reporter: {viewer['username']}",
            f"Target: {target['label']}",
            f"Reason: {reason}",
        ]
        if details:
            report_lines.append(f"Details: {short_preview(details, max_len=240)}")
        if target.get("contextThreadId"):
            report_lines.append(f"Review: {PUBLIC_URL}/pages/thread.html?thread={target['contextThreadId']}")
        send_staff_discord_notice(
            title="New OmniForum report",
            lines=report_lines,
            color=0xFF6B6B,
        )
        conn.commit()
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "submitted": True,
            "message": "Report submitted to the moderation team.",
        }

    def api_update_report(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        report_id: int,
    ) -> dict[str, Any]:
        if not viewer or not is_staff(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        ensure_can_participate(viewer)
        row = conn.execute(
            "SELECT * FROM reports WHERE id = ?",
            (report_id,),
        ).fetchone()
        if not row:
            raise APIError("Report not found.", HTTPStatus.NOT_FOUND)
        data = self.read_json()
        status = clean_report_status(data.get("status", row["status"]))
        admin_note = clean_text(
            data.get("adminNote", row["admin_note"]),
            min_len=0,
            max_len=1200,
            field="Admin note",
        )
        priority = clean_report_priority(data.get("priority", row["triage_priority"]))
        category = clean_report_category(data.get("category", row["triage_category"]))
        resolution_code = clean_text(
            data.get("resolutionCode", row["resolution_code"]),
            min_len=0,
            max_len=80,
            field="Resolution code",
        )
        now = utc_iso()
        sla_due_at = row["sla_due_at"]
        if "slaHours" in data:
            raw_sla_hours = data.get("slaHours")
            if raw_sla_hours in {None, "", 0, "0"}:
                sla_due_at = None
            else:
                try:
                    sla_hours = int(raw_sla_hours)
                except (TypeError, ValueError) as exc:
                    raise APIError("SLA hours must be a whole number.") from exc
                if sla_hours < 1 or sla_hours > 720:
                    raise APIError("SLA hours must be between 1 and 720.")
                sla_due_at = utc_iso(utc_now() + timedelta(hours=sla_hours))
        escalated_at = row["escalated_at"]
        escalation_note = row["escalation_note"] or ""
        if "escalated" in data:
            escalated = bool(data.get("escalated"))
            escalated_at = now if escalated and not escalated_at else (escalated_at if escalated else None)
        if "escalationNote" in data:
            escalation_note = clean_text(
                data.get("escalationNote"),
                min_len=0,
                max_len=500,
                field="Escalation note",
            )
        assigned_to = row["assigned_to"]
        if "assignedTo" in data:
            if data.get("assignedTo") in {None, "", 0}:
                assigned_to = None
            else:
                try:
                    assigned_to = int(data.get("assignedTo"))
                except (TypeError, ValueError) as exc:
                    raise APIError("Assigned moderator is invalid.") from exc
                assignee = conn.execute("SELECT id, role FROM users WHERE id = ?", (assigned_to,)).fetchone()
                if not assignee or not is_staff(dict(assignee)):
                    raise APIError("Assigned moderator must be a staff account.")
        handled_at = now if status == "resolved" else None
        handled_by = viewer["id"] if status == "resolved" else None
        conn.execute(
            """
            UPDATE reports
            SET status = ?, admin_note = ?, triage_priority = ?, triage_category = ?,
                resolution_code = ?, assigned_to = ?, sla_due_at = ?, escalated_at = ?,
                escalation_note = ?, handled_by = ?, handled_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                status,
                admin_note,
                priority,
                category,
                resolution_code,
                assigned_to,
                sla_due_at,
                escalated_at,
                escalation_note,
                handled_by,
                handled_at,
                now,
                report_id,
            ),
        )
        log_audit_event(
            conn,
            actor=viewer,
            action_type="report_update",
            category="moderation",
            target_type="report",
            target_id=report_id,
            target_label=row["target_label"],
            reason=admin_note or f"Report marked {status}.",
            metadata={
                "status": status,
                "priority": priority,
                "category": category,
                "resolutionCode": resolution_code,
                "assignedTo": assigned_to,
                "slaDueAt": sla_due_at,
                "escalatedAt": escalated_at,
            },
            created_at=now,
        )
        conn.commit()
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "message": "Report updated.",
            "items": list_reports(conn, status="all"),
        }

    def api_bulk_update_reports(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not viewer or not is_staff(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        ensure_can_participate(viewer)
        data = self.read_json()
        report_ids = clean_id_list(data.get("reportIds"), field="Reports")
        if not report_ids:
            raise APIError("Choose at least one report.")
        updates: list[tuple[str, Any]] = []
        if "status" in data:
            updates.append(("status", clean_report_status(data.get("status"))))
        if "priority" in data:
            updates.append(("triage_priority", clean_report_priority(data.get("priority"))))
        if "category" in data:
            updates.append(("triage_category", clean_report_category(data.get("category"))))
        if "resolutionCode" in data:
            updates.append((
                "resolution_code",
                clean_text(data.get("resolutionCode"), min_len=0, max_len=80, field="Resolution code"),
            ))
        if "assignedTo" in data:
            assigned_to = data.get("assignedTo")
            if assigned_to in {None, "", 0}:
                updates.append(("assigned_to", None))
            else:
                try:
                    assigned_id = int(assigned_to)
                except (TypeError, ValueError) as exc:
                    raise APIError("Assigned moderator is invalid.") from exc
                assignee = conn.execute("SELECT id, role FROM users WHERE id = ?", (assigned_id,)).fetchone()
                if not assignee or not is_staff(dict(assignee)):
                    raise APIError("Assigned moderator must be a staff account.")
                updates.append(("assigned_to", assigned_id))
        if not updates:
            raise APIError("Choose at least one change to apply.")
        now = utc_iso()
        if any(field == "status" and value == "resolved" for field, value in updates):
            updates.extend([("handled_by", viewer["id"]), ("handled_at", now)])
        elif any(field == "status" and value == "open" for field, value in updates):
            updates.extend([("handled_by", None), ("handled_at", None)])
        updates.append(("updated_at", now))
        set_clause = ", ".join(f"{field} = ?" for field, _ in updates)
        placeholders = ", ".join("?" for _ in report_ids)
        conn.execute(
            f"UPDATE reports SET {set_clause} WHERE id IN ({placeholders})",
            tuple(value for _, value in updates) + tuple(report_ids),
        )
        log_audit_event(
            conn,
            actor=viewer,
            action_type="report_bulk_update",
            category="moderation",
            target_type="report",
            reason=f"Bulk-updated {len(report_ids)} reports.",
            metadata={
                "reportIds": report_ids,
                "updates": {field: value for field, value in updates},
            },
            created_at=now,
        )
        conn.commit()
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "message": "Report queue updated.",
            "items": list_reports(conn, status="all"),
        }

    def api_add_report_note(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        report_id: int,
    ) -> dict[str, Any]:
        if not viewer or not is_staff(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        ensure_can_participate(viewer)
        report = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
        if not report:
            raise APIError("Report not found.", HTTPStatus.NOT_FOUND)
        data = self.read_json()
        note = clean_text(data.get("note"), min_len=2, max_len=1200, field="Internal note")
        now = utc_iso()
        conn.execute(
            """
            INSERT INTO report_internal_notes (report_id, author_id, note, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (report_id, viewer["id"], note, now, now),
        )
        conn.execute("UPDATE reports SET updated_at = ? WHERE id = ?", (now, report_id))
        log_audit_event(
            conn,
            actor=viewer,
            action_type="report_internal_note",
            category="moderation",
            target_type="report",
            target_id=report_id,
            target_label=report["target_label"],
            reason="Internal report discussion note added.",
            metadata={"notePreview": short_preview(note, max_len=120)},
            created_at=now,
        )
        conn.commit()
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "message": "Internal note added.",
            "items": list_reports(conn, status="all"),
        }

    def api_report_macros(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not viewer or not is_staff(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "macros": list_moderation_macros(conn, include_disabled=is_admin(viewer)),
        }

    def api_create_report_macro(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not viewer or not is_staff(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        ensure_can_participate(viewer)
        data = self.read_json()
        title = clean_text(data.get("title"), min_len=2, max_len=80, field="Macro title")
        body = clean_text(data.get("body"), min_len=4, max_len=1200, field="Macro body")
        category = clean_text(data.get("category"), min_len=0, max_len=40, field="Macro category")
        enabled = bool(data.get("enabled", True))
        now = utc_iso()
        cur = conn.execute(
            """
            INSERT INTO moderation_macros (title, body, category, enabled, created_by, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (title, body, category, int(enabled), viewer["id"], now, now),
        )
        log_audit_event(
            conn,
            actor=viewer,
            action_type="moderation_macro_create",
            category="moderation",
            target_type="moderation_macro",
            target_id=cur.lastrowid,
            target_label=title,
            reason="Moderation macro created.",
            created_at=now,
        )
        conn.commit()
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "macro": serialize_moderation_macro(conn.execute(
                """
                SELECT mm.*, creator.username AS created_by_username
                FROM moderation_macros mm
                LEFT JOIN users creator ON creator.id = mm.created_by
                WHERE mm.id = ?
                """,
                (cur.lastrowid,),
            ).fetchone()),
            "macros": list_moderation_macros(conn, include_disabled=is_admin(viewer)),
            "message": "Moderation macro saved.",
        }

    def api_update_report_macro(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        macro_id: int,
    ) -> dict[str, Any]:
        if not viewer or not is_staff(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        ensure_can_participate(viewer)
        row = conn.execute("SELECT * FROM moderation_macros WHERE id = ?", (macro_id,)).fetchone()
        if not row:
            raise APIError("Macro not found.", HTTPStatus.NOT_FOUND)
        data = self.read_json()
        title = clean_text(data.get("title", row["title"]), min_len=2, max_len=80, field="Macro title")
        body = clean_text(data.get("body", row["body"]), min_len=4, max_len=1200, field="Macro body")
        category = clean_text(data.get("category", row["category"]), min_len=0, max_len=40, field="Macro category")
        enabled = bool(data.get("enabled", row["enabled"]))
        now = utc_iso()
        conn.execute(
            """
            UPDATE moderation_macros
            SET title = ?, body = ?, category = ?, enabled = ?, updated_at = ?
            WHERE id = ?
            """,
            (title, body, category, int(enabled), now, macro_id),
        )
        log_audit_event(
            conn,
            actor=viewer,
            action_type="moderation_macro_update",
            category="moderation",
            target_type="moderation_macro",
            target_id=macro_id,
            target_label=title,
            reason="Moderation macro updated.",
            metadata={"enabled": enabled},
            created_at=now,
        )
        conn.commit()
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "macros": list_moderation_macros(conn, include_disabled=is_admin(viewer)),
            "message": "Moderation macro updated.",
        }
