"""Thread lookup, serialization, and staff-note helpers."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from .content_state import can_view_shadow_content, is_shadow_hidden_to_viewer, serialize_thread_poll
from .core import is_staff
from .media import media_url_for_path
from .domain_thread_membership import thread_user_flags


def get_thread_by_id(conn: sqlite3.Connection, thread_id: int) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT
            t.*,
            s.slug AS section_slug,
            s.name AS section_name,
            s.description AS section_description,
            s.icon AS section_icon,
            s.icon_bg AS section_icon_bg,
            s.required_role AS section_required_role,
            s.write_role AS section_write_role,
            s.thread_prefixes_json AS section_thread_prefixes_json,
            s.thread_template AS section_thread_template,
            s.thread_state_mode AS section_thread_state_mode,
            u.username AS author_name,
            u.role AS author_role,
            u.avatar_path AS author_avatar_path
        FROM threads t
        JOIN sections s ON s.id = t.section_id
        JOIN users u ON u.id = t.author_id
        WHERE t.id = ? AND t.deleted_at IS NULL
        """,
        (thread_id,),
    ).fetchone()


def serialize_thread_note(row: sqlite3.Row) -> dict[str, Any]:
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


def list_thread_notes(
    conn: sqlite3.Connection,
    thread_id: int,
    *,
    limit: int = 12,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT tn.*, u.username AS author_username, u.role AS author_role
        FROM thread_notes tn
        JOIN users u ON u.id = tn.author_id
        WHERE tn.thread_id = ?
        ORDER BY tn.created_at DESC, tn.id DESC
        LIMIT ?
        """,
        (thread_id, limit),
    ).fetchall()
    return [serialize_thread_note(row) for row in rows]


def add_thread_note(
    conn: sqlite3.Connection,
    *,
    thread_id: int,
    author_id: int,
    note: str,
    created_at: str,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO thread_notes (thread_id, author_id, note, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (thread_id, author_id, note, created_at, created_at),
    )
    return int(cur.lastrowid)


def serialize_thread(
    thread_row: sqlite3.Row,
    conn: sqlite3.Connection,
    viewer: dict[str, Any] | None,
) -> dict[str, Any]:
    stats_where = "thread_id = ? AND deleted_at IS NULL"
    stats_params: list[Any] = [thread_row["id"]]
    if is_shadow_hidden_to_viewer(
        hidden=thread_row["shadow_hidden"],
        author_id=thread_row["author_id"],
        viewer=viewer,
    ):
        stats_where += " AND 1 = 0"
    elif not can_view_shadow_content(viewer, thread_row["author_id"]):
        stats_where += " AND COALESCE(shadow_hidden, 0) = 0"
    stats = conn.execute(
        f"""
        SELECT
            COUNT(*) AS post_count,
            MAX(created_at) AS last_post_at
        FROM posts
        WHERE {stats_where}
        """,
        tuple(stats_params),
    ).fetchone()
    last_post_where = "p.thread_id = ? AND p.deleted_at IS NULL"
    last_post_params: list[Any] = [thread_row["id"]]
    if not can_view_shadow_content(viewer, thread_row["author_id"]):
        last_post_where += " AND COALESCE(p.shadow_hidden, 0) = 0"
    last_post = conn.execute(
        f"""
        SELECT u.username
        FROM posts p
        JOIN users u ON u.id = p.author_id
        WHERE {last_post_where}
        ORDER BY p.created_at DESC, p.id DESC
        LIMIT 1
        """,
        tuple(last_post_params),
    ).fetchone()
    author_id = thread_row["author_id"]
    can_edit = bool(viewer and (viewer["id"] == author_id or is_staff(viewer)))
    can_moderate = bool(viewer and is_staff(viewer))
    can_delete = bool(viewer and (viewer["id"] == author_id or is_staff(viewer)))
    can_mark_answer = bool(viewer and (viewer["id"] == author_id or is_staff(viewer)))
    flags = thread_user_flags(conn, thread_row["id"], viewer)
    return {
        "id": thread_row["id"],
        "title": thread_row["title"],
        "prefix": thread_row["prefix"] or "",
        "authorId": author_id,
        "authorName": thread_row["author_name"],
        "authorRole": thread_row["author_role"],
        "authorAvatarUrl": media_url_for_path(thread_row["author_avatar_path"]),
        "createdAt": thread_row["created_at"],
        "updatedAt": thread_row["updated_at"],
        "editedAt": thread_row["edited_at"],
        "views": thread_row["view_count"],
        "pinned": bool(thread_row["pinned"]),
        "featured": bool(thread_row["featured"]),
        "hot": stats["post_count"] >= 15,
        "locked": bool(thread_row["locked"]),
        "solved": bool(thread_row["solved"]),
        "answered": bool(thread_row["answer_post_id"]) and not bool(thread_row["solved"]),
        "answerPostId": thread_row["answer_post_id"],
        "shadowHidden": bool(thread_row["shadow_hidden"]),
        "tags": json.loads(thread_row["tags_json"] or "[]"),
        "replies": max(0, stats["post_count"] - 1),
        "lastPostAt": stats["last_post_at"],
        "lastPostBy": last_post["username"] if last_post else None,
        "poll": serialize_thread_poll(conn, thread_row["id"], viewer),
        "section": {
            "id": thread_row["section_slug"],
            "name": thread_row["section_name"],
            "desc": thread_row["section_description"],
            "icon": thread_row["section_icon"],
            "iconBg": thread_row["section_icon_bg"],
            "requiredRole": thread_row["section_required_role"],
            "writeRole": thread_row["section_write_role"],
            "threadPrefixes": json.loads(thread_row["section_thread_prefixes_json"] or "[]"),
            "threadTemplate": thread_row["section_thread_template"] or "",
            "threadStateMode": thread_row["section_thread_state_mode"] or "discussion",
        },
        "canEdit": can_edit,
        "canDelete": can_delete,
        "canModerate": can_moderate,
        "canMarkAnswer": can_mark_answer,
        "bookmarkedByViewer": flags["bookmarked"],
        "subscribedByViewer": flags["subscribed"],
        "staffNotes": list_thread_notes(conn, thread_row["id"]) if can_moderate else [],
    }
