"""Focused forum domain helpers for home."""

from __future__ import annotations

import sqlite3
from typing import Any
from .core import (
    has_required_role,
    is_staff,
    utc_iso,
)
from .content_state import is_shadow_hidden_to_viewer
from .admin_health import get_site_stats

def get_latest_activity(
    conn: sqlite3.Connection,
    viewer: dict[str, Any] | None = None,
    limit: int = 8,
) -> list[dict[str, Any]]:
    from .domain_users import is_ignored_author

    activities: list[dict[str, Any]] = []

    new_users = conn.execute(
        """
            SELECT username, created_at
            FROM users
            WHERE approval_status = 'approved'
            ORDER BY created_at DESC
        LIMIT 4
        """
    ).fetchall()
    for row in new_users:
        activities.append(
            {
                "kind": "join",
                "user": row["username"],
                "action": "joined the forum",
                "target": "",
                "createdAt": row["created_at"],
            }
        )

    new_threads = conn.execute(
        """
        SELECT u.username, s.name AS section_name, t.title, t.created_at, t.author_id
        FROM threads t
        JOIN users u ON u.id = t.author_id
        JOIN sections s ON s.id = t.section_id
        WHERE COALESCE(t.shadow_hidden, 0) = 0
          AND t.deleted_at IS NULL
        ORDER BY t.created_at DESC
        LIMIT 6
        """
    ).fetchall()
    for row in new_threads:
        if is_ignored_author(conn, viewer, row["author_id"]):
            continue
        activities.append(
            {
                "kind": "thread",
                "user": row["username"],
                "action": "started a thread in",
                "target": row["section_name"],
                "detail": row["title"],
                "createdAt": row["created_at"],
            }
        )

    replies = conn.execute(
        """
        SELECT u.username, t.title, p.created_at, p.author_id
        FROM posts p
        JOIN users u ON u.id = p.author_id
        JOIN threads t ON t.id = p.thread_id
        WHERE COALESCE(p.shadow_hidden, 0) = 0
          AND p.deleted_at IS NULL
          AND p.id NOT IN (
            SELECT MIN(id)
            FROM posts
            WHERE deleted_at IS NULL
            GROUP BY thread_id
        )
        ORDER BY p.created_at DESC
        LIMIT 6
        """
    ).fetchall()
    for row in replies:
        if is_ignored_author(conn, viewer, row["author_id"]):
            continue
        activities.append(
            {
                "kind": "reply",
                "user": row["username"],
                "action": "replied in",
                "target": row["title"],
                "createdAt": row["created_at"],
            }
        )

    activities.sort(key=lambda item: item["createdAt"], reverse=True)
    return activities[:limit]


def get_live_snapshot(
    conn: sqlite3.Connection,
    viewer: dict[str, Any] | None,
    *,
    thread_id: int | None = None,
    section_slug: str = "",
) -> dict[str, Any]:
    from .domain_notifications import get_notification_counts
    from .domain_threads import get_section_by_slug, get_thread_by_id
    from .domain_users import get_current_user_payload, viewer_ignored_user_ids

    payload: dict[str, Any] = {
        "serverTime": utc_iso(),
        "stats": get_site_stats(conn),
        "currentUser": get_current_user_payload(conn, viewer),
    }
    if viewer:
        counts = get_notification_counts(conn, viewer["id"], viewer=viewer)
        payload["attention"] = {
            "notifications": counts["unread"],
            "messages": counts["dms"],
            "reports": counts["reports"],
            "appeals": counts["appeals"],
            "notices": counts["contactNotices"],
            "registrations": counts["registrations"],
        }
    if thread_id:
        thread = get_thread_by_id(conn, thread_id)
        if thread and has_required_role(viewer, thread["section_required_role"]) and not is_shadow_hidden_to_viewer(
            hidden=thread["shadow_hidden"],
            author_id=thread["author_id"],
            viewer=viewer,
        ):
            visibility_clause = "thread_id = ? AND deleted_at IS NULL"
            params: list[Any] = [thread_id]
            ignored_ids = viewer_ignored_user_ids(conn, viewer)
            if ignored_ids:
                placeholders = ", ".join("?" for _ in ignored_ids)
                visibility_clause += f" AND author_id NOT IN ({placeholders})"
                params.extend(sorted(ignored_ids))
            if not is_staff(viewer):
                visibility_clause += " AND (COALESCE(shadow_hidden, 0) = 0"
                if viewer:
                    visibility_clause += " OR author_id = ?"
                    params.append(viewer["id"])
                visibility_clause += ")"
            thread_counts = conn.execute(
                f"""
                SELECT COUNT(*) AS post_count, MAX(id) AS last_post_id, MAX(updated_at) AS last_post_at
                FROM posts
                WHERE {visibility_clause}
                """,
                tuple(params),
            ).fetchone()
            payload["thread"] = {
                "id": thread_id,
                "updatedAt": thread["updated_at"],
                "postCount": int(thread_counts["post_count"] or 0),
                "lastPostId": int(thread_counts["last_post_id"] or 0),
                "lastPostAt": thread_counts["last_post_at"],
            }
    if section_slug:
        section = get_section_by_slug(conn, section_slug)
        if section and has_required_role(viewer, section["required_role"]):
            ignored_ids = viewer_ignored_user_ids(conn, viewer)
            clauses = ["t.section_id = ?", "t.deleted_at IS NULL"]
            params: list[Any] = [section["id"]]
            if ignored_ids:
                placeholders = ", ".join("?" for _ in ignored_ids)
                clauses.append(f"t.author_id NOT IN ({placeholders})")
                params.extend(sorted(ignored_ids))
            if not is_staff(viewer):
                clauses.append("COALESCE(t.shadow_hidden, 0) = 0")
            row = conn.execute(
                f"""
                SELECT COUNT(*) AS thread_count, MAX(t.updated_at) AS last_thread_at
                FROM threads t
                WHERE {" AND ".join(clauses)}
                """,
                tuple(params),
            ).fetchone()
            payload["section"] = {
                "id": section_slug,
                "threadCount": int(row["thread_count"] or 0),
                "lastThreadAt": row["last_thread_at"],
            }
    return payload
