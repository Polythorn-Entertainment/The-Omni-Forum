"""Audit event logging and query helpers."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from .config import AUDIT_CATEGORIES
from .core import utc_iso
from .validation import clean_text


def audit_actor_snapshot(
    conn: sqlite3.Connection,
    actor: dict[str, Any] | sqlite3.Row | None = None,
    actor_id: int | None = None,
) -> dict[str, Any]:
    if actor:
        actor_row = dict(actor)
        return {
            "id": actor_row.get("id"),
            "username": actor_row.get("username") or "",
            "role": actor_row.get("role") or "",
        }
    if actor_id:
        row = conn.execute("SELECT id, username, role FROM users WHERE id = ?", (actor_id,)).fetchone()
        if row:
            return {
                "id": row["id"],
                "username": row["username"],
                "role": row["role"],
            }
    return {
        "id": actor_id,
        "username": "",
        "role": "",
    }


def log_audit_event(
    conn: sqlite3.Connection,
    *,
    actor: dict[str, Any] | sqlite3.Row | None = None,
    actor_id: int | None = None,
    action_type: str,
    category: str,
    target_type: str = "",
    target_id: int | None = None,
    target_label: str = "",
    reason: str = "",
    metadata: dict[str, Any] | None = None,
    ip_address: str = "",
    created_at: str | None = None,
) -> None:
    normalized_category = str(category or "operations").strip().lower()
    if normalized_category not in AUDIT_CATEGORIES:
        normalized_category = "operations"
    actor_snapshot = audit_actor_snapshot(conn, actor=actor, actor_id=actor_id)
    conn.execute(
        """
        INSERT INTO audit_events (
            actor_id, actor_username, actor_role, action_type, category,
            target_type, target_id, target_label, reason, metadata_json,
            ip_address, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            actor_snapshot["id"],
            actor_snapshot["username"],
            actor_snapshot["role"],
            clean_text(action_type, min_len=1, max_len=80, field="Audit action"),
            normalized_category,
            clean_text(target_type, min_len=0, max_len=40, field="Audit target type"),
            target_id,
            clean_text(target_label, min_len=0, max_len=160, field="Audit target"),
            clean_text(reason, min_len=0, max_len=1000, field="Audit reason"),
            json.dumps(metadata or {}, sort_keys=True),
            clean_text(ip_address, min_len=0, max_len=80, field="Audit IP"),
            created_at or utc_iso(),
        ),
    )


def serialize_audit_event(row: sqlite3.Row) -> dict[str, Any]:
    try:
        metadata = json.loads(row["metadata_json"] or "{}")
    except json.JSONDecodeError:
        metadata = {}
    return {
        "id": row["id"],
        "action": row["action_type"],
        "category": row["category"],
        "targetType": row["target_type"] or "",
        "targetId": row["target_id"],
        "targetLabel": row["target_label"] or "",
        "reason": row["reason"] or "",
        "metadata": metadata,
        "ipAddress": row["ip_address"] or "",
        "createdAt": row["created_at"],
        "actor": {
            "id": row["actor_id"],
            "username": row["actor_username"] or "System",
            "role": row["actor_role"] or "",
        },
    }


def audit_filter_value(query: dict[str, list[str]], key: str, *, max_len: int = 80) -> str:
    return clean_text((query.get(key) or [""])[0], min_len=0, max_len=max_len, field=key)


def list_audit_events(
    conn: sqlite3.Connection,
    query: dict[str, list[str]],
) -> dict[str, Any]:
    try:
        limit = int((query.get("limit") or ["80"])[0])
    except (TypeError, ValueError):
        limit = 80
    limit = max(10, min(200, limit))
    category = audit_filter_value(query, "category", max_len=40).lower()
    action = audit_filter_value(query, "action", max_len=80).lower()
    target_type = audit_filter_value(query, "targetType", max_len=40).lower()
    search = audit_filter_value(query, "q", max_len=120)
    actor = audit_filter_value(query, "actor", max_len=80)
    date_from = audit_filter_value(query, "from", max_len=40)
    date_to = audit_filter_value(query, "to", max_len=40)
    params: list[Any] = []
    clauses: list[str] = ["1 = 1"]
    if category in AUDIT_CATEGORIES:
        clauses.append("category = ?")
        params.append(category)
    if action:
        clauses.append("lower(action_type) = ?")
        params.append(action)
    if target_type:
        clauses.append("lower(target_type) = ?")
        params.append(target_type)
    if actor:
        if actor.isdigit():
            clauses.append("actor_id = ?")
            params.append(int(actor))
        else:
            clauses.append("lower(actor_username) LIKE ?")
            params.append(f"%{actor.lower()}%")
    if search:
        like = f"%{search.lower()}%"
        clauses.append(
            """
            (
                lower(action_type) LIKE ?
                OR lower(category) LIKE ?
                OR lower(target_type) LIKE ?
                OR lower(target_label) LIKE ?
                OR lower(actor_username) LIKE ?
                OR lower(reason) LIKE ?
            )
            """
        )
        params.extend([like, like, like, like, like, like])
    if date_from:
        clauses.append("created_at >= ?")
        params.append(date_from if "T" in date_from else f"{date_from}T00:00:00Z")
    if date_to:
        clauses.append("created_at <= ?")
        params.append(date_to if "T" in date_to else f"{date_to}T23:59:59Z")

    where_sql = " AND ".join(clauses)
    rows = conn.execute(
        f"""
        SELECT *
        FROM audit_events
        WHERE {where_sql}
        ORDER BY created_at DESC, id DESC
        LIMIT ?
        """,
        (*params, limit),
    ).fetchall()
    category_rows = conn.execute(
        """
        SELECT category, COUNT(*) AS count
        FROM audit_events
        GROUP BY category
        ORDER BY category ASC
        """
    ).fetchall()
    total = conn.execute("SELECT COUNT(*) AS count FROM audit_events").fetchone()["count"]
    latest = conn.execute(
        "SELECT created_at FROM audit_events ORDER BY created_at DESC, id DESC LIMIT 1"
    ).fetchone()
    return {
        "items": [serialize_audit_event(row) for row in rows],
        "filters": {
            "category": category if category in AUDIT_CATEGORIES else "",
            "action": action,
            "targetType": target_type,
            "actor": actor,
            "q": search,
            "from": date_from,
            "to": date_to,
            "limit": limit,
        },
        "summary": {
            "total": total,
            "latestAt": latest["created_at"] if latest else "",
            "categories": {row["category"]: row["count"] for row in category_rows},
        },
        "categories": sorted(AUDIT_CATEGORIES),
    }
