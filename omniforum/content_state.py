"""Content deletion, shadow visibility, reactions, and poll helpers."""

from __future__ import annotations

import sqlite3
from http import HTTPStatus
from typing import Any

from .core import is_staff, utc_iso
from .errors import APIError
from .search import remove_search_index_entry, update_post_search_index, update_thread_search_index


def soft_delete_post(
    conn: sqlite3.Connection,
    *,
    post_id: int,
    actor_id: int,
    reason: str = "",
    deleted_at: str | None = None,
) -> None:
    now = deleted_at or utc_iso()
    conn.execute(
        """
        UPDATE posts
        SET deleted_at = ?, deleted_by = ?, delete_reason = ?, updated_at = ?
        WHERE id = ? AND deleted_at IS NULL
        """,
        (now, actor_id, reason, now, post_id),
    )
    remove_search_index_entry(conn, kind="post", source_id=post_id)


def soft_delete_thread(
    conn: sqlite3.Connection,
    *,
    thread_id: int,
    actor_id: int,
    reason: str = "",
    deleted_at: str | None = None,
) -> None:
    now = deleted_at or utc_iso()
    conn.execute(
        """
        UPDATE threads
        SET deleted_at = ?, deleted_by = ?, delete_reason = ?, updated_at = ?
        WHERE id = ? AND deleted_at IS NULL
        """,
        (now, actor_id, reason, now, thread_id),
    )
    remove_search_index_entry(conn, kind="thread", source_id=thread_id)
    conn.execute(
        """
        UPDATE posts
        SET deleted_at = COALESCE(deleted_at, ?),
            deleted_by = COALESCE(deleted_by, ?),
            delete_reason = CASE WHEN delete_reason = '' THEN ? ELSE delete_reason END,
            updated_at = ?
        WHERE thread_id = ? AND deleted_at IS NULL
        """,
        (now, actor_id, reason, now, thread_id),
    )
    for row in conn.execute("SELECT id FROM posts WHERE thread_id = ?", (thread_id,)).fetchall():
        remove_search_index_entry(conn, kind="post", source_id=row["id"])


def restore_deleted_post(conn: sqlite3.Connection, post_id: int) -> None:
    conn.execute(
        """
        UPDATE posts
        SET deleted_at = NULL, deleted_by = NULL, delete_reason = ''
        WHERE id = ?
        """,
        (post_id,),
    )
    update_post_search_index(conn, post_id)


def restore_deleted_thread(conn: sqlite3.Connection, thread_id: int) -> None:
    conn.execute(
        """
        UPDATE threads
        SET deleted_at = NULL, deleted_by = NULL, delete_reason = ''
        WHERE id = ?
        """,
        (thread_id,),
    )
    conn.execute(
        """
        UPDATE posts
        SET deleted_at = NULL, deleted_by = NULL, delete_reason = ''
        WHERE thread_id = ?
        """,
        (thread_id,),
    )
    update_thread_search_index(conn, thread_id)
    for row in conn.execute("SELECT id FROM posts WHERE thread_id = ?", (thread_id,)).fetchall():
        update_post_search_index(conn, row["id"])


def serialize_deleted_item(row: sqlite3.Row) -> dict[str, Any]:
    item_type = row["item_type"]
    payload = {
        "type": item_type,
        "id": row["id"],
        "title": row["title"],
        "preview": row["preview"] or "",
        "deletedAt": row["deleted_at"],
        "deleteReason": row["delete_reason"] or "",
        "author": {
            "id": row["author_id"],
            "username": row["author_username"],
            "role": row["author_role"],
        },
        "deletedBy": (
            {
                "id": row["deleted_by"],
                "username": row["deleted_by_username"],
            }
            if row["deleted_by"] and row["deleted_by_username"]
            else None
        ),
    }
    if item_type == "thread":
        payload["threadId"] = row["id"]
        payload["section"] = {
            "id": row["section_slug"],
            "name": row["section_name"],
        }
    else:
        payload["threadId"] = row["thread_id"]
        payload["threadTitle"] = row["thread_title"]
    return payload


def list_deleted_content(conn: sqlite3.Connection, *, limit: int = 120) -> list[dict[str, Any]]:
    thread_rows = conn.execute(
        """
        SELECT
            'thread' AS item_type,
            t.id,
            t.title,
            '' AS preview,
            t.deleted_at,
            t.delete_reason,
            t.author_id,
            author.username AS author_username,
            author.role AS author_role,
            t.deleted_by,
            deleter.username AS deleted_by_username,
            s.slug AS section_slug,
            s.name AS section_name,
            NULL AS thread_id,
            NULL AS thread_title
        FROM threads t
        JOIN users author ON author.id = t.author_id
        JOIN sections s ON s.id = t.section_id
        LEFT JOIN users deleter ON deleter.id = t.deleted_by
        WHERE t.deleted_at IS NOT NULL
        ORDER BY t.deleted_at DESC, t.id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    post_rows = conn.execute(
        """
        SELECT
            'post' AS item_type,
            p.id,
            ('Reply by ' || author.username) AS title,
            substr(trim(replace(replace(p.content, char(10), ' '), char(13), ' ')), 1, 220) AS preview,
            p.deleted_at,
            p.delete_reason,
            p.author_id,
            author.username AS author_username,
            author.role AS author_role,
            p.deleted_by,
            deleter.username AS deleted_by_username,
            NULL AS section_slug,
            NULL AS section_name,
            p.thread_id,
            t.title AS thread_title
        FROM posts p
        JOIN users author ON author.id = p.author_id
        JOIN threads t ON t.id = p.thread_id
        LEFT JOIN users deleter ON deleter.id = p.deleted_by
        WHERE p.deleted_at IS NOT NULL
          AND (t.deleted_at IS NULL OR p.delete_reason != COALESCE(t.delete_reason, ''))
        ORDER BY p.deleted_at DESC, p.id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    combined = [*thread_rows, *post_rows]
    combined.sort(key=lambda item: (item["deleted_at"], item["id"]), reverse=True)
    return [serialize_deleted_item(row) for row in combined[:limit]]


def can_view_shadow_content(viewer: dict[str, Any] | None, author_id: int | None) -> bool:
    return bool(viewer and (is_staff(viewer) or int(viewer["id"]) == int(author_id or 0)))


def is_shadow_hidden_to_viewer(
    *,
    hidden: Any,
    author_id: int | None,
    viewer: dict[str, Any] | None,
) -> bool:
    return bool(hidden) and not can_view_shadow_content(viewer, author_id)


def list_post_reactions_summary(
    conn: sqlite3.Connection,
    post_ids: list[int],
    viewer: dict[str, Any] | None,
) -> dict[int, dict[str, Any]]:
    if not post_ids:
        return {}
    placeholders = ", ".join("?" for _ in post_ids)
    rows = conn.execute(
        f"""
        SELECT post_id, emoji, COUNT(*) AS count
        FROM post_reactions
        WHERE post_id IN ({placeholders})
        GROUP BY post_id, emoji
        ORDER BY post_id ASC, count DESC, emoji ASC
        """,
        tuple(post_ids),
    ).fetchall()
    summary = {post_id: {"items": [], "viewer": []} for post_id in post_ids}
    for row in rows:
        summary.setdefault(row["post_id"], {"items": [], "viewer": []})["items"].append(
            {
                "emoji": row["emoji"],
                "count": row["count"],
            }
        )
    if viewer:
        viewer_rows = conn.execute(
            f"""
            SELECT post_id, emoji
            FROM post_reactions
            WHERE user_id = ? AND post_id IN ({placeholders})
            ORDER BY emoji ASC
            """,
            (viewer["id"], *post_ids),
        ).fetchall()
        for row in viewer_rows:
            summary.setdefault(row["post_id"], {"items": [], "viewer": []})["viewer"].append(row["emoji"])
    return summary


def create_thread_poll(
    conn: sqlite3.Connection,
    *,
    thread_id: int,
    poll: dict[str, Any],
    created_at: str,
) -> None:
    cur = conn.execute(
        """
        INSERT INTO thread_polls (thread_id, question, allows_multiple, is_closed, created_at, updated_at)
        VALUES (?, ?, ?, 0, ?, ?)
        """,
        (thread_id, poll["question"], int(bool(poll["allowsMultiple"])), created_at, created_at),
    )
    poll_id = cur.lastrowid
    for index, option in enumerate(poll["options"]):
        conn.execute(
            """
            INSERT INTO thread_poll_options (poll_id, option_text, sort_order)
            VALUES (?, ?, ?)
            """,
            (poll_id, option, index),
        )


def serialize_thread_poll(
    conn: sqlite3.Connection,
    thread_id: int,
    viewer: dict[str, Any] | None,
) -> dict[str, Any] | None:
    poll = conn.execute(
        "SELECT * FROM thread_polls WHERE thread_id = ?",
        (thread_id,),
    ).fetchone()
    if not poll:
        return None
    option_rows = conn.execute(
        """
        SELECT
            o.id,
            o.option_text,
            o.sort_order,
            COUNT(v.option_id) AS votes
        FROM thread_poll_options o
        LEFT JOIN thread_poll_votes v ON v.option_id = o.id
        WHERE o.poll_id = ?
        GROUP BY o.id, o.option_text, o.sort_order
        ORDER BY o.sort_order ASC, o.id ASC
        """,
        (poll["id"],),
    ).fetchall()
    viewer_votes: set[int] = set()
    if viewer:
        viewer_vote_rows = conn.execute(
            """
            SELECT option_id
            FROM thread_poll_votes
            WHERE poll_id = ? AND user_id = ?
            """,
            (poll["id"], viewer["id"]),
        ).fetchall()
        viewer_votes = {row["option_id"] for row in viewer_vote_rows}
    total_votes = sum(int(row["votes"] or 0) for row in option_rows)
    return {
        "question": poll["question"],
        "allowsMultiple": bool(poll["allows_multiple"]),
        "isClosed": bool(poll["is_closed"]),
        "totalVotes": total_votes,
        "hasVoted": bool(viewer_votes),
        "viewerVotes": list(viewer_votes),
        "options": [
            {
                "id": row["id"],
                "label": row["option_text"],
                "votes": row["votes"],
                "selectedByViewer": row["id"] in viewer_votes,
            }
            for row in option_rows
        ],
    }


def vote_in_thread_poll(
    conn: sqlite3.Connection,
    *,
    thread_id: int,
    viewer: dict[str, Any],
    option_ids: list[int],
) -> dict[str, Any]:
    poll = conn.execute(
        "SELECT * FROM thread_polls WHERE thread_id = ?",
        (thread_id,),
    ).fetchone()
    if not poll:
        raise APIError("This thread does not have an active poll.", HTTPStatus.NOT_FOUND)
    if poll["is_closed"]:
        raise APIError("This poll is closed.", HTTPStatus.FORBIDDEN)
    valid_rows = conn.execute(
        """
        SELECT id
        FROM thread_poll_options
        WHERE poll_id = ?
        ORDER BY sort_order ASC, id ASC
        """,
        (poll["id"],),
    ).fetchall()
    valid_option_ids = {row["id"] for row in valid_rows}
    if not option_ids or any(option_id not in valid_option_ids for option_id in option_ids):
        raise APIError("Choose one of the available poll options.")
    if not poll["allows_multiple"] and len(option_ids) > 1:
        raise APIError("This poll only allows one choice.")
    conn.execute(
        "DELETE FROM thread_poll_votes WHERE poll_id = ? AND user_id = ?",
        (poll["id"], viewer["id"]),
    )
    now = utc_iso()
    conn.executemany(
        """
        INSERT INTO thread_poll_votes (poll_id, option_id, user_id, created_at)
        VALUES (?, ?, ?, ?)
        """,
        [(poll["id"], option_id, viewer["id"], now) for option_id in option_ids],
    )
    conn.execute(
        "UPDATE thread_polls SET updated_at = ? WHERE id = ?",
        (now, poll["id"]),
    )
    conn.commit()
    return serialize_thread_poll(conn, thread_id, viewer)
