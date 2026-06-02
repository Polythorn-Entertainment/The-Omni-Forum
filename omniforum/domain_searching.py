"""Focused forum domain helpers for searching."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Any
from .core import (
    has_required_role,
    utc_iso,
    utc_now,
)
from .search import (
    fts_query,
    refresh_search_index,
)
from .content_state import is_shadow_hidden_to_viewer
from .text_utils import short_preview

def search_members(conn: sqlite3.Connection, query: str, *, limit: int = 8) -> list[dict[str, Any]]:
    from .domain_users import serialize_user

    pattern = f"%{query.lower()}%"
    rows = conn.execute(
        """
        SELECT
            u.*,
            (SELECT COUNT(*) FROM posts p WHERE p.author_id = u.id AND p.deleted_at IS NULL) AS posts_count,
            (SELECT COUNT(*) FROM threads t WHERE t.author_id = u.id AND t.deleted_at IS NULL) AS threads_count,
            (SELECT COUNT(*) FROM post_likes pl
             JOIN posts p2 ON p2.id = pl.post_id
             WHERE p2.author_id = u.id AND p2.deleted_at IS NULL) AS likes_received
            FROM users u
            WHERE u.approval_status = 'approved'
              AND (lower(u.username) LIKE ? OR lower(u.bio) LIKE ?)
        ORDER BY
            CASE WHEN lower(u.username) = ? THEN 0 ELSE 1 END,
            CASE WHEN lower(u.username) LIKE ? THEN 0 ELSE 1 END,
            u.username COLLATE NOCASE ASC
        LIMIT ?
        """,
        (pattern, pattern, query.lower(), f"{query.lower()}%", limit),
    ).fetchall()
    return [serialize_user(dict(row)) for row in rows]


def search_date_cutoff(date_filter: str) -> datetime | None:
    now = utc_now()
    if date_filter == "today":
        return now - timedelta(days=1)
    if date_filter == "week":
        return now - timedelta(days=7)
    if date_filter == "month":
        return now - timedelta(days=30)
    if date_filter == "year":
        return now - timedelta(days=365)
    return None


def search_threads(
    conn: sqlite3.Connection,
    query: str,
    *,
    viewer: dict[str, Any] | None,
    section_slug: str = "",
    author: str = "",
    tag: str = "",
    solved: str = "all",
    media: str = "all",
    replies: str = "all",
    date: str = "all",
    sort: str = "relevance",
    limit: int = 8,
) -> list[dict[str, Any]]:
    from .domain_threads import serialize_thread
    from .domain_users import is_ignored_author

    normalized_query = query.lower().strip()
    pattern = f"%{normalized_query}%" if normalized_query else "%"
    cutoff = search_date_cutoff(date)
    fts = fts_query(query)
    clauses = [
        "t.deleted_at IS NULL",
    ]
    params: list[Any] = []
    fts_thread_ids: list[int] = []
    if fts and refresh_search_index(conn):
        try:
            fts_thread_ids = [
                int(row["source_id"])
                for row in conn.execute(
                    """
                    SELECT source_id
                    FROM search_fts
                    WHERE kind = 'thread' AND search_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (fts, limit * 10),
                ).fetchall()
            ]
        except sqlite3.OperationalError:
            fts_thread_ids = []
    if fts_thread_ids:
        clauses.append(f"t.id IN ({','.join('?' for _ in fts_thread_ids)})")
        params.extend(fts_thread_ids)
    else:
        clauses.append("(lower(t.title) LIKE ? OR lower(t.tags_json) LIKE ? OR lower(t.prefix) LIKE ?)")
        params.extend([pattern, pattern, pattern])
    if section_slug:
        clauses.append("s.slug = ?")
        params.append(section_slug)
    if author:
        clauses.append("lower(u.username) = lower(?)")
        params.append(author)
    if solved == "solved":
        clauses.append("COALESCE(t.solved, 0) = 1")
    elif solved == "unsolved":
        clauses.append("COALESCE(t.solved, 0) = 0")
    if cutoff:
        clauses.append("t.created_at >= ?")
        params.append(utc_iso(cutoff))
    if media == "with_media":
        clauses.append(
            """
            EXISTS (
                SELECT 1
                FROM post_media pm
                JOIN posts p2 ON p2.id = pm.post_id
                WHERE p2.thread_id = t.id AND p2.deleted_at IS NULL
            )
            """
        )
    if replies == "unanswered":
        clauses.append("(SELECT COUNT(*) FROM posts rp WHERE rp.thread_id = t.id AND rp.deleted_at IS NULL) <= 1")
    elif replies == "answered":
        clauses.append("(SELECT COUNT(*) FROM posts rp WHERE rp.thread_id = t.id AND rp.deleted_at IS NULL) > 1")
    where_sql = " AND ".join(clauses)
    params.extend([normalized_query, f"{normalized_query}%", limit * 5])
    rows = conn.execute(
        f"""
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
        WHERE {where_sql}
        ORDER BY
            CASE WHEN lower(t.title) = ? THEN 0 ELSE 1 END,
            CASE WHEN lower(t.title) LIKE ? THEN 0 ELSE 1 END,
            t.updated_at DESC,
            t.id DESC
        LIMIT ?
        """,
        tuple(params),
    ).fetchall()
    output: list[dict[str, Any]] = []
    for row in rows:
        if not has_required_role(viewer, row["section_required_role"]):
            continue
        if is_ignored_author(conn, viewer, row["author_id"]):
            continue
        if tag and tag not in set(json.loads(row["tags_json"] or "[]")):
            continue
        if is_shadow_hidden_to_viewer(hidden=row["shadow_hidden"], author_id=row["author_id"], viewer=viewer):
            continue
        item = serialize_thread(row, conn, viewer)
        output.append(item)
    if sort == "latest":
        output.sort(key=lambda item: item["updatedAt"], reverse=True)
    elif sort == "trending":
        output.sort(key=lambda item: (item["views"], item["replies"], item["updatedAt"]), reverse=True)
    else:
        output.sort(
            key=lambda item: (
                1 if item["title"].lower() == query.lower() else 0,
                1 if query.lower() in item["title"].lower() else 0,
                item["updatedAt"],
            ),
            reverse=True,
        )
    return output[:limit]


def search_posts(
    conn: sqlite3.Connection,
    query: str,
    *,
    viewer: dict[str, Any] | None,
    section_slug: str = "",
    author: str = "",
    media: str = "all",
    date: str = "all",
    limit: int = 8,
) -> list[dict[str, Any]]:
    from .domain_users import is_ignored_author, serialize_user

    normalized_query = query.lower().strip()
    pattern = f"%{normalized_query}%" if normalized_query else "%"
    cutoff = search_date_cutoff(date)
    fts = fts_query(query)
    clauses = [
        "p.deleted_at IS NULL",
        "t.deleted_at IS NULL",
    ]
    params: list[Any] = []
    fts_post_ids: list[int] = []
    if fts and refresh_search_index(conn):
        try:
            fts_post_ids = [
                int(row["source_id"])
                for row in conn.execute(
                    """
                    SELECT source_id
                    FROM search_fts
                    WHERE kind = 'post' AND search_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (fts, limit * 10),
                ).fetchall()
            ]
        except sqlite3.OperationalError:
            fts_post_ids = []
    if fts_post_ids:
        clauses.append(f"p.id IN ({','.join('?' for _ in fts_post_ids)})")
        params.extend(fts_post_ids)
    else:
        clauses.append("lower(p.content) LIKE ?")
        params.append(pattern)
    if section_slug:
        clauses.append("s.slug = ?")
        params.append(section_slug)
    if author:
        clauses.append("lower(u.username) = lower(?)")
        params.append(author)
    if cutoff:
        clauses.append("p.created_at >= ?")
        params.append(utc_iso(cutoff))
    if media == "with_media":
        clauses.append("EXISTS(SELECT 1 FROM post_media pm WHERE pm.post_id = p.id)")
    where_sql = " AND ".join(clauses)
    params.extend([f"{normalized_query}%", limit * 5])
    rows = conn.execute(
        f"""
        SELECT
            p.id,
            p.thread_id,
            p.content,
            p.created_at,
            p.updated_at,
            p.shadow_hidden,
            p.deleted_at,
            u.id AS author_id,
            u.username AS author_username,
            u.role AS author_role,
            u.bio AS author_bio,
            u.avatar_path AS author_avatar_path,
            u.xp AS author_xp,
            u.created_at AS author_created_at,
            u.last_seen_at AS author_last_seen_at,
            t.title AS thread_title,
            s.slug AS section_slug,
            s.name AS section_name,
            s.required_role AS section_required_role
        FROM posts p
        JOIN users u ON u.id = p.author_id
        JOIN threads t ON t.id = p.thread_id
        JOIN sections s ON s.id = t.section_id
        WHERE {where_sql}
        ORDER BY
            CASE WHEN lower(p.content) LIKE ? THEN 0 ELSE 1 END,
            p.created_at DESC,
            p.id DESC
        LIMIT ?
        """,
        tuple(params),
    ).fetchall()
    output: list[dict[str, Any]] = []
    for row in rows:
        if not has_required_role(viewer, row["section_required_role"]):
            continue
        if is_ignored_author(conn, viewer, row["author_id"]):
            continue
        if is_shadow_hidden_to_viewer(hidden=row["shadow_hidden"], author_id=row["author_id"], viewer=viewer):
            continue
        output.append(
            {
                "id": row["id"],
                "threadId": row["thread_id"],
                "threadTitle": row["thread_title"],
                "sectionId": row["section_slug"],
                "sectionName": row["section_name"],
                "content": short_preview(row["content"], max_len=220),
                "createdAt": row["created_at"],
                "updatedAt": row["updated_at"],
                "author": serialize_user(
                    {
                        "id": row["author_id"],
                        "username": row["author_username"],
                        "role": row["author_role"],
                        "bio": row["author_bio"] or "",
                        "avatar_path": row["author_avatar_path"] or "",
                        "xp": row["author_xp"] or 0,
                        "created_at": row["author_created_at"],
                        "last_seen_at": row["author_last_seen_at"],
                        "posts_count": 0,
                        "threads_count": 0,
                        "likes_received": 0,
                    }
                ),
            }
        )
        if len(output) == limit:
            break
    return output
