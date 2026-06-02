"""Post listing and edit-history helpers."""

from __future__ import annotations

import json
import math
import sqlite3
from typing import Any

from .config import DEFAULT_POST_PAGE_SIZE
from .content_state import list_post_reactions_summary
from .core import is_staff
from .domain_thread_membership import thread_first_post_id
from .media import list_post_media
from .validation import resolve_pagination


def get_posts_for_thread(
    conn: sqlite3.Connection,
    thread_id: int,
    viewer: dict[str, Any] | None,
    *,
    page: int = 1,
    page_size: int = DEFAULT_POST_PAGE_SIZE,
    last_page: bool = False,
    focus_post_id: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int | bool]]:
    from .domain_users import serialize_user, viewer_ignored_user_ids

    viewer_id = viewer["id"] if viewer else -1
    visibility_clause = "p.thread_id = ? AND p.deleted_at IS NULL"
    visibility_params: list[Any] = [thread_id]
    ignored_ids = viewer_ignored_user_ids(conn, viewer)
    if ignored_ids:
        placeholders = ", ".join("?" for _ in ignored_ids)
        visibility_clause += f" AND p.author_id NOT IN ({placeholders})"
        visibility_params.extend(sorted(ignored_ids))
    if not is_staff(viewer):
        visibility_clause += " AND (COALESCE(p.shadow_hidden, 0) = 0"
        if viewer:
            visibility_clause += " OR p.author_id = ?"
            visibility_params.append(viewer["id"])
        visibility_clause += ")"
    total_posts = conn.execute(
        f"SELECT COUNT(*) AS count FROM posts p WHERE {visibility_clause}",
        tuple(visibility_params),
    ).fetchone()["count"]
    if focus_post_id:
        focus_row = conn.execute(
            f"""
            SELECT COUNT(*) AS count
            FROM posts p
            WHERE {visibility_clause} AND id <= ?
            """,
            (*visibility_params, focus_post_id),
        ).fetchone()
        if focus_row and focus_row["count"]:
            page = max(1, math.ceil(int(focus_row["count"]) / page_size))
            last_page = False
    pagination = resolve_pagination(
        total_posts,
        page=page,
        page_size=page_size,
        last_page=last_page,
    )
    rows = conn.execute(
        f"""
        SELECT
            p.*,
            u.username,
            u.role,
            u.bio,
            u.avatar_path,
            u.signature,
            u.profile_badge,
            u.profile_accent,
            u.xp,
            u.created_at AS user_created_at,
            u.last_seen_at,
            t.author_id AS thread_author_id,
            (SELECT COUNT(*) FROM posts p2 WHERE p2.author_id = u.id AND p2.deleted_at IS NULL) AS author_posts,
            (SELECT COUNT(*) FROM threads t2 WHERE t2.author_id = u.id AND t2.deleted_at IS NULL) AS author_threads,
            (SELECT COUNT(*) FROM post_likes pl WHERE pl.post_id = p.id) AS likes_count,
            EXISTS(
                SELECT 1
                FROM post_likes pl2
                WHERE pl2.post_id = p.id AND pl2.user_id = ?
            ) AS liked_by_viewer
        FROM posts p
        JOIN threads t ON t.id = p.thread_id
        JOIN users u ON u.id = p.author_id
        WHERE {visibility_clause} AND t.deleted_at IS NULL
        ORDER BY p.id ASC
        LIMIT ? OFFSET ?
        """,
        (viewer_id, *visibility_params, pagination["pageSize"], pagination["offset"]),
    ).fetchall()
    first_post = thread_first_post_id(conn, thread_id)
    media_map = list_post_media(conn, [row["id"] for row in rows])
    reaction_map = list_post_reactions_summary(conn, [row["id"] for row in rows], viewer)
    payload = []
    for row in rows:
        author = {
            "id": row["author_id"],
            "username": row["username"],
            "role": row["role"],
            "bio": row["bio"],
            "avatar_path": row["avatar_path"] or "",
            "signature": row["signature"] or "",
            "profile_badge": row["profile_badge"] or "",
            "profile_accent": row["profile_accent"] or "",
            "xp": row["xp"],
            "created_at": row["user_created_at"],
            "last_seen_at": row["last_seen_at"],
            "posts_count": row["author_posts"],
            "threads_count": row["author_threads"],
            "likes_received": 0,
        }
        can_edit = bool(viewer and (viewer["id"] == row["author_id"] or is_staff(viewer)))
        can_delete = bool(viewer and row["id"] != first_post and (viewer["id"] == row["author_id"] or is_staff(viewer)))
        payload.append(
            {
                "id": row["id"],
                "threadId": row["thread_id"],
                "author": serialize_user(author),
                "content": row["content"],
                "media": media_map.get(row["id"], []),
                "mediaSensitive": bool(row["media_sensitive"]),
                "createdAt": row["created_at"],
                "updatedAt": row["updated_at"],
                "editedAt": row["edited_at"],
                "hasHistory": bool(row["edited_at"]),
                "likes": row["likes_count"],
                "likedByViewer": bool(row["liked_by_viewer"]),
                "isThreadStarter": row["id"] == first_post,
                "isAcceptedAnswer": False,
                "shadowHidden": bool(row["shadow_hidden"]),
                "reactions": reaction_map.get(row["id"], {}).get("items", []),
                "viewerReactions": reaction_map.get(row["id"], {}).get("viewer", []),
                "canEdit": can_edit,
                "canDelete": can_delete,
                "canMarkAnswer": bool(viewer and (viewer["id"] == row["thread_author_id"] or is_staff(viewer))),
            }
        )
    answer_row = conn.execute(
        "SELECT answer_post_id FROM threads WHERE id = ?",
        (thread_id,),
    ).fetchone()
    answer_post_id = answer_row["answer_post_id"] if answer_row else None
    for item in payload:
        item["isAcceptedAnswer"] = bool(answer_post_id and item["id"] == answer_post_id)
    return payload, pagination


def serialize_post_history_item(row: sqlite3.Row) -> dict[str, Any]:
    try:
        media_summary = json.loads(row["media_summary_json"] or "[]")
    except json.JSONDecodeError:
        media_summary = []
    return {
        "id": row["id"],
        "content": row["previous_content"],
        "title": row["previous_title"] or "",
        "mediaSummary": media_summary,
        "createdAt": row["created_at"],
        "editor": {
            "id": row["editor_id"],
            "username": row["editor_username"],
            "role": row["editor_role"],
        },
    }


def list_post_edit_history(conn: sqlite3.Connection, post_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            pe.*,
            editor.username AS editor_username,
            editor.role AS editor_role
        FROM post_edits pe
        JOIN users editor ON editor.id = pe.editor_id
        WHERE pe.post_id = ?
        ORDER BY pe.created_at DESC, pe.id DESC
        LIMIT 20
        """,
        (post_id,),
    ).fetchall()
    return [serialize_post_history_item(row) for row in rows]
