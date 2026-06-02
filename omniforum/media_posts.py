"""Post media serialization, persistence, and cleanup helpers."""

from __future__ import annotations

import sqlite3
from typing import Any

from .media_paths import delete_media_file, media_url_for_path
from .media_store import store_image_upload_paths


def serialize_post_media_row(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    payload = dict(row)
    return {
        "id": payload["id"],
        "url": media_url_for_path(payload.get("storage_path")),
        "thumbnailUrl": media_url_for_path(payload.get("thumbnail_path")),
        "mimeType": payload["mime_type"],
        "alt": payload.get("alt_text") or "Forum image",
        "width": payload.get("width") or 0,
        "height": payload.get("height") or 0,
    }


def list_post_media_rows(
    conn: sqlite3.Connection,
    post_ids: list[int],
) -> dict[int, list[sqlite3.Row]]:
    if not post_ids:
        return {}
    placeholders = ", ".join("?" for _ in post_ids)
    rows = conn.execute(
        f"""
        SELECT *
        FROM post_media
        WHERE post_id IN ({placeholders})
        ORDER BY post_id ASC, sort_order ASC, id ASC
        """,
        tuple(post_ids),
    ).fetchall()
    grouped = {post_id: [] for post_id in post_ids}
    for row in rows:
        grouped.setdefault(row["post_id"], []).append(row)
    return grouped


def list_post_media(
    conn: sqlite3.Connection,
    post_ids: list[int],
) -> dict[int, list[dict[str, Any]]]:
    grouped_rows = list_post_media_rows(conn, post_ids)
    return {post_id: [serialize_post_media_row(row) for row in rows] for post_id, rows in grouped_rows.items()}


def collect_post_media_paths(conn: sqlite3.Connection, post_ids: list[int]) -> list[str]:
    grouped_rows = list_post_media_rows(conn, post_ids)
    return [
        path
        for rows in grouped_rows.values()
        for row in rows
        for path in (row["storage_path"], row["thumbnail_path"])
        if path
    ]


def save_post_media_entries(
    conn: sqlite3.Connection,
    *,
    post_id: int,
    uploads: list[dict[str, Any]],
    created_at: str,
    start_order: int = 0,
) -> None:
    for offset, upload in enumerate(uploads):
        media_paths = store_image_upload_paths(upload, bucket="posts")
        conn.execute(
            """
            INSERT INTO post_media (
                post_id, storage_path, thumbnail_path, mime_type, alt_text,
                width, height, sort_order, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                post_id,
                media_paths["storage_path"],
                media_paths["thumbnail_path"],
                upload["mime_type"],
                upload["alt_text"],
                upload["width"],
                upload["height"],
                start_order + offset,
                created_at,
            ),
        )


def delete_post_media_files(conn: sqlite3.Connection, post_ids: list[int]) -> None:
    grouped_rows = list_post_media_rows(conn, post_ids)
    for rows in grouped_rows.values():
        for row in rows:
            delete_media_file(row["storage_path"])
            delete_media_file(row["thumbnail_path"])


def delete_post_artifact_rows(conn: sqlite3.Connection, post_ids: list[int]) -> None:
    if not post_ids:
        return
    placeholders = ", ".join("?" for _ in post_ids)
    params = tuple(post_ids)
    conn.execute(f"DELETE FROM post_media WHERE post_id IN ({placeholders})", params)
    conn.execute(f"DELETE FROM post_edits WHERE post_id IN ({placeholders})", params)
    conn.execute(f"DELETE FROM post_likes WHERE post_id IN ({placeholders})", params)
    conn.execute(f"DELETE FROM post_reactions WHERE post_id IN ({placeholders})", params)


def cleanup_orphan_post_artifacts(conn: sqlite3.Connection) -> dict[str, int]:
    orphan_media_rows = conn.execute(
        """
        SELECT pm.id, pm.storage_path, pm.thumbnail_path
        FROM post_media pm
        LEFT JOIN posts p ON p.id = pm.post_id
        WHERE p.id IS NULL
        """
    ).fetchall()
    orphan_media_ids = [int(row["id"]) for row in orphan_media_rows]
    orphan_media_paths = [
        path for row in orphan_media_rows for path in (row["storage_path"], row["thumbnail_path"]) if path
    ]
    deleted_counts = {
        "postMediaRows": len(orphan_media_ids),
        "postEditRows": 0,
        "postLikeRows": 0,
        "postReactionRows": 0,
    }
    if orphan_media_ids:
        conn.execute(
            f"DELETE FROM post_media WHERE id IN ({', '.join('?' for _ in orphan_media_ids)})",
            tuple(orphan_media_ids),
        )
    deleted_counts["postEditRows"] = conn.execute(
        """
        DELETE FROM post_edits
        WHERE post_id NOT IN (SELECT id FROM posts)
        """
    ).rowcount
    deleted_counts["postLikeRows"] = conn.execute(
        """
        DELETE FROM post_likes
        WHERE post_id NOT IN (SELECT id FROM posts)
        """
    ).rowcount
    deleted_counts["postReactionRows"] = conn.execute(
        """
        DELETE FROM post_reactions
        WHERE post_id NOT IN (SELECT id FROM posts)
        """
    ).rowcount
    conn.commit()
    for storage_path in orphan_media_paths:
        delete_media_file(storage_path)
    return deleted_counts
