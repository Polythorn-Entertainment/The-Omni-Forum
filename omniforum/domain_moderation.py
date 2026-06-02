"""Focused forum domain helpers for moderation."""

from __future__ import annotations

import json
import sqlite3
from http import HTTPStatus
from typing import Any
from .config import ROLES
from .core import (
    has_required_role,
    is_staff,
    parse_iso,
    utc_iso,
    utc_now,
)
from .errors import APIError
from .audit import log_audit_event
from .account_state import (
    active_mute_until,
    active_timeout_until,
    sync_user_restrictions,
)
from .text_utils import short_preview

def log_moderation_action(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    actor_id: int,
    action_type: str,
    category: str = "moderation",
    reason: str = "",
    note: str = "",
    delta_xp: int = 0,
    expires_at: str | None = None,
    metadata: dict[str, Any] | None = None,
    created_at: str | None = None,
) -> None:
    timestamp = created_at or utc_iso()
    conn.execute(
        """
        INSERT INTO moderation_actions (
            user_id, actor_id, action_type, reason, note, delta_xp,
            expires_at, created_at, metadata_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            actor_id,
            action_type,
            reason,
            note,
            delta_xp,
            expires_at,
            timestamp,
            json.dumps(metadata or {}),
        ),
    )
    target = conn.execute("SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()
    audit_metadata = {
        **(metadata or {}),
        "note": note,
        "deltaXp": delta_xp,
        "expiresAt": expires_at,
        "moderationTargetUserId": user_id,
    }
    log_audit_event(
        conn,
        actor_id=actor_id,
        action_type=action_type,
        category=category,
        target_type="user",
        target_id=user_id,
        target_label=target["username"] if target else f"user {user_id}",
        reason=reason or note,
        metadata={
            key: value
            for key, value in audit_metadata.items()
            if value is not None and value != "" and value != 0
        },
        created_at=timestamp,
    )


def serialize_moderation_action(row: sqlite3.Row) -> dict[str, Any]:
    try:
        metadata = json.loads(row["metadata_json"] or "{}")
    except json.JSONDecodeError:
        metadata = {}
    return {
        "id": row["id"],
        "type": row["action_type"],
        "reason": row["reason"] or "",
        "note": row["note"] or "",
        "deltaXp": row["delta_xp"] or 0,
        "expiresAt": row["expires_at"],
        "createdAt": row["created_at"],
        "metadata": metadata,
        "actor": {
            "id": row["actor_id"],
            "username": row["actor_username"],
            "role": row["actor_role"],
        },
    }


def list_user_moderation_actions(
    conn: sqlite3.Connection,
    user_id: int,
    *,
    limit: int = 16,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            ma.*,
            actor.username AS actor_username,
            actor.role AS actor_role
        FROM moderation_actions ma
        JOIN users actor ON actor.id = ma.actor_id
        WHERE ma.user_id = ?
        ORDER BY ma.created_at DESC, ma.id DESC
        LIMIT ?
        """,
        (user_id, limit),
    ).fetchall()
    return [serialize_moderation_action(row) for row in rows]


def serialize_user_moderation(row: dict[str, Any]) -> dict[str, Any]:
    timeout_until = active_timeout_until(row)
    mute_until = active_mute_until(row)
    return {
        "isBanned": bool(row.get("banned_at")),
        "bannedAt": row.get("banned_at"),
        "banReason": row.get("ban_reason") or "",
        "bannedBy": (
            {
                "id": row.get("banned_by"),
                "username": row.get("banned_by_username"),
            }
            if row.get("banned_by") and row.get("banned_by_username")
            else None
        ),
        "isTimedOut": bool(timeout_until),
        "timeoutUntil": utc_iso(timeout_until) if timeout_until else None,
        "timeoutReason": row.get("timeout_reason") or "",
        "timeoutBy": (
            {
                "id": row.get("timeout_set_by"),
                "username": row.get("timeout_by_username"),
            }
            if row.get("timeout_set_by") and row.get("timeout_by_username")
            else None
        ),
        "isMuted": bool(mute_until),
        "muteUntil": utc_iso(mute_until) if mute_until else None,
        "muteReason": row.get("mute_reason") or "",
        "muteBy": (
            {
                "id": row.get("mute_set_by"),
                "username": row.get("mute_by_username"),
            }
            if row.get("mute_set_by") and row.get("mute_by_username")
            else None
        ),
        "isShadowMuted": bool(row.get("shadow_muted")),
        "passwordResetRequired": bool(row.get("password_reset_required")),
        "passwordResetSetAt": row.get("password_reset_set_at"),
        "passwordResetExpiresAt": row.get("password_reset_expires_at"),
        "passwordResetBy": (
            {
                "id": row.get("password_reset_set_by"),
                "username": row.get("password_reset_by_username"),
            }
            if row.get("password_reset_set_by") and row.get("password_reset_by_username")
            else None
        ),
    }


def resolve_report_target(
    conn: sqlite3.Connection,
    target_type: str,
    target_id: int,
    *,
    viewer: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from .domain_threads import get_thread_by_id

    if target_type == "thread":
        thread = get_thread_by_id(conn, target_id)
        if not thread:
            raise APIError("Thread not found.", HTTPStatus.NOT_FOUND)
        if not has_required_role(viewer, thread["section_required_role"]):
            raise APIError("You do not have access to that thread.", HTTPStatus.FORBIDDEN)
        return {
            "type": "thread",
            "id": target_id,
            "label": thread["title"],
            "preview": f"In {thread['section_name']} · started by {thread['author_name']}",
            "contextThreadId": target_id,
        }
    if target_type == "post":
        row = conn.execute(
            """
            SELECT
                p.id,
                p.content,
                p.thread_id,
                t.title AS thread_title,
                s.required_role AS section_required_role,
                u.username AS author_name
            FROM posts p
            JOIN threads t ON t.id = p.thread_id
            JOIN sections s ON s.id = t.section_id
            JOIN users u ON u.id = p.author_id
            WHERE p.id = ? AND p.deleted_at IS NULL AND t.deleted_at IS NULL
            """,
            (target_id,),
        ).fetchone()
        if not row:
            raise APIError("Post not found.", HTTPStatus.NOT_FOUND)
        if not has_required_role(viewer, row["section_required_role"]):
            raise APIError("You do not have access to that post.", HTTPStatus.FORBIDDEN)
        return {
            "type": "post",
            "id": target_id,
            "label": f"Post by {row['author_name']}",
            "preview": short_preview(row["content"]),
            "contextThreadId": row["thread_id"],
            "threadTitle": row["thread_title"],
        }
    if target_type == "user":
        row = conn.execute(
            "SELECT * FROM users WHERE id = ?",
            (target_id,),
        ).fetchone()
        resolved = sync_user_restrictions(conn, row)
        if not resolved:
            raise APIError("User not found.", HTTPStatus.NOT_FOUND)
        role = ROLES.get(resolved["role"], ROLES["new"])
        return {
            "type": "user",
            "id": target_id,
            "label": resolved["username"],
            "preview": short_preview(resolved.get("bio") or f"{role['label']} account"),
            "contextThreadId": None,
        }
    raise APIError("Unsupported report target.")


def serialize_report_note(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "note": row["note"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "author": {
            "id": row["author_id"],
            "username": row["author_username"],
            "role": row["author_role"],
        },
    }


def list_report_notes(conn: sqlite3.Connection, report_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            rn.*,
            author.username AS author_username,
            author.role AS author_role
        FROM report_internal_notes rn
        JOIN users author ON author.id = rn.author_id
        WHERE rn.report_id = ?
        ORDER BY rn.created_at ASC, rn.id ASC
        """,
        (report_id,),
    ).fetchall()
    return [serialize_report_note(row) for row in rows]


def serialize_moderation_macro(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "body": row["body"],
        "category": row["category"] or "",
        "enabled": bool(row["enabled"]),
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "createdBy": (
            {"id": row["created_by"], "username": row["created_by_username"]}
            if row["created_by"] and row["created_by_username"]
            else None
        ),
    }


def list_moderation_macros(conn: sqlite3.Connection, *, include_disabled: bool = False) -> list[dict[str, Any]]:
    where = "" if include_disabled else "WHERE mm.enabled = 1"
    rows = conn.execute(
        f"""
        SELECT mm.*, creator.username AS created_by_username
        FROM moderation_macros mm
        LEFT JOIN users creator ON creator.id = mm.created_by
        {where}
        ORDER BY mm.enabled DESC, mm.title COLLATE NOCASE ASC, mm.id ASC
        """
    ).fetchall()
    return [serialize_moderation_macro(row) for row in rows]


def serialize_report(row: sqlite3.Row, conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    sla_due_at = parse_iso(row["sla_due_at"] if "sla_due_at" in row.keys() else None)
    sla_state = "none"
    if sla_due_at:
        sla_state = "overdue" if sla_due_at <= utc_now() and row["status"] == "open" else "active"
    return {
        "id": row["id"],
        "reason": row["reason"],
        "details": row["details"] or "",
        "status": row["status"],
        "adminNote": row["admin_note"] or "",
        "priority": row["triage_priority"] or "normal",
        "category": row["triage_category"] or "",
        "resolutionCode": row["resolution_code"] or "",
        "slaDueAt": row["sla_due_at"] if "sla_due_at" in row.keys() else None,
        "slaState": sla_state,
        "escalatedAt": row["escalated_at"] if "escalated_at" in row.keys() else None,
        "escalationNote": row["escalation_note"] if "escalation_note" in row.keys() else "",
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "handledAt": row["handled_at"],
        "target": {
            "type": row["target_type"],
            "id": row["target_id"],
            "label": row["target_label"],
            "preview": row["target_preview"] or "",
            "contextThreadId": row["context_thread_id"],
        },
        "reporter": {
            "id": row["reporter_id"],
            "username": row["reporter_username"],
            "role": row["reporter_role"],
        },
        "handledBy": (
            {
                "id": row["handled_by"],
                "username": row["handled_by_username"],
            }
            if row["handled_by"] and row["handled_by_username"]
            else None
        ),
        "assignedTo": (
            {
                "id": row["assigned_to"],
                "username": row["assigned_to_username"],
            }
            if row["assigned_to"] and row["assigned_to_username"]
            else None
        ),
        "internalNotes": list_report_notes(conn, row["id"]) if conn is not None else [],
    }


def list_reports(
    conn: sqlite3.Connection,
    *,
    status: str = "open",
    limit: int = 100,
) -> list[dict[str, Any]]:
    params: list[Any] = []
    where = ""
    if status in {"open", "resolved"}:
        where = "WHERE r.status = ?"
        params.append(status)
    rows = conn.execute(
        f"""
        SELECT
            r.*,
            reporter.username AS reporter_username,
            reporter.role AS reporter_role,
            handler.username AS handled_by_username,
            assigned.username AS assigned_to_username
        FROM reports r
        JOIN users reporter ON reporter.id = r.reporter_id
        LEFT JOIN users handler ON handler.id = r.handled_by
        LEFT JOIN users assigned ON assigned.id = r.assigned_to
        {where}
        ORDER BY
            CASE r.triage_priority
                WHEN 'urgent' THEN 0
                WHEN 'high' THEN 1
                WHEN 'normal' THEN 2
                ELSE 3
            END,
            CASE r.status WHEN 'open' THEN 0 ELSE 1 END,
            r.created_at DESC,
            r.id DESC
        LIMIT ?
        """,
        (*params, limit),
    ).fetchall()
    return [serialize_report(row, conn) for row in rows]


def serialize_appeal(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "message": row["message"],
        "status": row["status"],
        "staffNote": row["staff_note"] or "",
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "handledAt": row["handled_at"],
        "user": {
            "id": row["user_id"],
            "username": row["username"],
            "role": row["role"],
        },
        "handledBy": (
            {
                "id": row["handled_by"],
                "username": row["handled_by_username"],
            }
            if row["handled_by"] and row["handled_by_username"]
            else None
        ),
        "targetUserId": row["target_user_id"] or row["user_id"],
    }


def list_appeals_for_viewer(
    conn: sqlite3.Connection,
    viewer: dict[str, Any],
    *,
    status: str = "open",
    target_user_id: int | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    params: list[Any] = []
    clauses: list[str] = []
    if not is_staff(viewer):
        clauses.append("a.user_id = ?")
        params.append(viewer["id"])
    elif target_user_id:
        clauses.append("a.user_id = ?")
        params.append(target_user_id)
    if status in {"open", "resolved"}:
        clauses.append("a.status = ?")
        params.append(status)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"""
        SELECT
            a.*,
            u.username,
            u.role,
            handler.username AS handled_by_username
        FROM appeals a
        JOIN users u ON u.id = a.user_id
        LEFT JOIN users handler ON handler.id = a.handled_by
        {where}
        ORDER BY
            CASE a.status WHEN 'open' THEN 0 ELSE 1 END,
            a.created_at DESC,
            a.id DESC
        LIMIT ?
        """,
        (*params, limit),
    ).fetchall()
    return [serialize_appeal(row) for row in rows]
