"""Thread bookmark and subscription helpers."""

from __future__ import annotations

import sqlite3
from typing import Any

from .core import has_required_role, utc_iso
from .content_state import is_shadow_hidden_to_viewer


def thread_first_post_id(conn: sqlite3.Connection, thread_id: int) -> int | None:
    row = conn.execute(
        "SELECT id FROM posts WHERE thread_id = ? AND deleted_at IS NULL ORDER BY id ASC LIMIT 1",
        (thread_id,),
    ).fetchone()
    return row["id"] if row else None


def thread_user_flags(
    conn: sqlite3.Connection,
    thread_id: int,
    viewer: dict[str, Any] | None,
) -> dict[str, bool]:
    if not viewer:
        return {"bookmarked": False, "subscribed": False}
    row = conn.execute(
        """
        SELECT
            EXISTS(
                SELECT 1 FROM thread_bookmarks tb
                WHERE tb.thread_id = ? AND tb.user_id = ?
            ) AS bookmarked,
            EXISTS(
                SELECT 1 FROM thread_subscriptions ts
                WHERE ts.thread_id = ? AND ts.user_id = ?
            ) AS subscribed
        """,
        (thread_id, viewer["id"], thread_id, viewer["id"]),
    ).fetchone()
    return {
        "bookmarked": bool(row and row["bookmarked"]),
        "subscribed": bool(row and row["subscribed"]),
    }


def ensure_thread_subscription(
    conn: sqlite3.Connection,
    *,
    thread_id: int,
    user_id: int,
    created_at: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO thread_subscriptions (thread_id, user_id, created_at)
        VALUES (?, ?, ?)
        """,
        (thread_id, user_id, created_at or utc_iso()),
    )


def toggle_thread_membership(
    conn: sqlite3.Connection,
    *,
    table: str,
    thread_id: int,
    user_id: int,
) -> bool:
    existing = conn.execute(
        f"SELECT 1 FROM {table} WHERE thread_id = ? AND user_id = ?",
        (thread_id, user_id),
    ).fetchone()
    if existing:
        conn.execute(
            f"DELETE FROM {table} WHERE thread_id = ? AND user_id = ?",
            (thread_id, user_id),
        )
        conn.commit()
        return False
    conn.execute(
        f"INSERT INTO {table} (thread_id, user_id, created_at) VALUES (?, ?, ?)",
        (thread_id, user_id, utc_iso()),
    )
    conn.commit()
    return True


def list_saved_threads(
    conn: sqlite3.Connection,
    *,
    table: str,
    user_id: int,
    viewer: dict[str, Any] | None,
    limit: int = 8,
) -> list[dict[str, Any]]:
    from .domain_thread_records import serialize_thread
    from .domain_users import is_ignored_author

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
            u.avatar_path AS author_avatar_path,
            x.created_at AS saved_at
        FROM {table} x
        JOIN threads t ON t.id = x.thread_id
        JOIN sections s ON s.id = t.section_id
        JOIN users u ON u.id = t.author_id
        WHERE x.user_id = ? AND t.deleted_at IS NULL
        ORDER BY x.created_at DESC, x.thread_id DESC
        LIMIT ?
        """,
        (user_id, limit * 3),
    ).fetchall()
    output: list[dict[str, Any]] = []
    for row in rows:
        if not has_required_role(viewer, row["section_required_role"]):
            continue
        if is_ignored_author(conn, viewer, row["author_id"]):
            continue
        if is_shadow_hidden_to_viewer(hidden=row["shadow_hidden"], author_id=row["author_id"], viewer=viewer):
            continue
        item = serialize_thread(row, conn, viewer)
        item["savedAt"] = row["saved_at"]
        output.append(item)
        if len(output) >= limit:
            break
    return output
