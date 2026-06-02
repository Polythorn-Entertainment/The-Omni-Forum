"""Focused forum domain helpers for messages."""

from __future__ import annotations

import re
import sqlite3
from typing import Any
from .core import (
    is_staff,
    role_level,
    utc_iso,
)

def can_receive_direct_message(
    conn: sqlite3.Connection,
    recipient: sqlite3.Row | dict[str, Any] | None,
    sender: dict[str, Any] | None,
) -> bool:
    from .domain_users import has_dm_block_relationship

    if not recipient or not sender:
        return False
    if sender["id"] == dict(recipient)["id"]:
        return False
    if has_dm_block_relationship(conn, int(dict(recipient)["id"]), int(sender["id"])):
        return False
    if is_staff(sender):
        return True
    privacy = str(dict(recipient).get("dm_privacy") or "everyone")
    if privacy == "disabled":
        return False
    if privacy == "staff_only":
        return False
    if privacy == "members":
        return role_level(sender["role"]) >= role_level("member")
    return True


def normalize_dm_pair(user_a: int, user_b: int) -> tuple[int, int]:
    return (user_a, user_b) if user_a < user_b else (user_b, user_a)


def get_unread_dm_count(conn: sqlite3.Connection, user_id: int) -> int:
    return sum(int(item["unreadCount"] or 0) for item in list_dm_threads(conn, user_id, limit=200))


def serialize_dm_user_from_row(row: sqlite3.Row, prefix: str) -> dict[str, Any]:
    from .domain_users import serialize_user

    return serialize_user(
        {
            "id": row[f"{prefix}_id"],
            "username": row[f"{prefix}_username"],
            "role": row[f"{prefix}_role"],
            "bio": row[f"{prefix}_bio"] or "",
            "avatar_path": row[f"{prefix}_avatar_path"] or "",
            "xp": row[f"{prefix}_xp"] or 0,
            "created_at": row[f"{prefix}_created_at"],
            "last_seen_at": row[f"{prefix}_last_seen_at"],
            "posts_count": 0,
            "threads_count": 0,
            "likes_received": 0,
        }
    )


def serialize_dm_thread_summary(row: sqlite3.Row, viewer_id: int) -> dict[str, Any]:
    low_user = serialize_dm_user_from_row(row, "low")
    high_user = serialize_dm_user_from_row(row, "high")
    other_user = high_user if row["user_low_id"] == viewer_id else low_user
    last_content = row["last_message_content"] or ""
    preview = re.sub(r"\s+", " ", last_content).strip()
    if len(preview) > 140:
        preview = f"{preview[:137]}..."
    return {
        "id": row["id"],
        "updatedAt": row["updated_at"],
        "lastMessageAt": row["last_message_at"],
        "unreadCount": row["unread_count"] or 0,
        "otherUser": other_user,
        "lastMessage": (
            {
                "content": preview,
                "createdAt": row["last_message_created_at"],
                "senderId": row["last_message_sender_id"],
                "fromViewer": row["last_message_sender_id"] == viewer_id,
            }
            if row["last_message_created_at"]
            else None
        ),
    }


def list_dm_threads(
    conn: sqlite3.Connection,
    viewer_id: int,
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    from .domain_users import has_dm_block_relationship

    rows = conn.execute(
        """
        SELECT
            dt.*,
            low_user.id AS low_id,
            low_user.username AS low_username,
            low_user.role AS low_role,
            low_user.bio AS low_bio,
            low_user.avatar_path AS low_avatar_path,
            low_user.xp AS low_xp,
            low_user.created_at AS low_created_at,
            low_user.last_seen_at AS low_last_seen_at,
            high_user.id AS high_id,
            high_user.username AS high_username,
            high_user.role AS high_role,
            high_user.bio AS high_bio,
            high_user.avatar_path AS high_avatar_path,
            high_user.xp AS high_xp,
            high_user.created_at AS high_created_at,
            high_user.last_seen_at AS high_last_seen_at,
            (SELECT COUNT(*)
             FROM dm_messages dm_unread
             WHERE dm_unread.thread_id = dt.id
               AND dm_unread.recipient_id = ?
               AND dm_unread.read_at IS NULL) AS unread_count,
            (SELECT dm_last.content
             FROM dm_messages dm_last
             WHERE dm_last.thread_id = dt.id
             ORDER BY dm_last.created_at DESC, dm_last.id DESC
             LIMIT 1) AS last_message_content,
            (SELECT dm_last.created_at
             FROM dm_messages dm_last
             WHERE dm_last.thread_id = dt.id
             ORDER BY dm_last.created_at DESC, dm_last.id DESC
             LIMIT 1) AS last_message_created_at,
            (SELECT dm_last.sender_id
             FROM dm_messages dm_last
             WHERE dm_last.thread_id = dt.id
             ORDER BY dm_last.created_at DESC, dm_last.id DESC
             LIMIT 1) AS last_message_sender_id
        FROM dm_threads dt
        JOIN users low_user ON low_user.id = dt.user_low_id
        JOIN users high_user ON high_user.id = dt.user_high_id
        WHERE dt.user_low_id = ? OR dt.user_high_id = ?
        ORDER BY dt.last_message_at DESC, dt.id DESC
        LIMIT ?
        """,
        (viewer_id, viewer_id, viewer_id, limit),
    ).fetchall()
    output: list[dict[str, Any]] = []
    for row in rows:
        other_id = row["user_high_id"] if row["user_low_id"] == viewer_id else row["user_low_id"]
        if has_dm_block_relationship(conn, viewer_id, int(other_id)):
            continue
        output.append(serialize_dm_thread_summary(row, viewer_id))
        if len(output) >= limit:
            break
    return output


def get_dm_thread_summary(
    conn: sqlite3.Connection,
    thread_id: int,
    viewer_id: int,
) -> dict[str, Any] | None:
    from .domain_users import has_dm_block_relationship

    row = conn.execute(
        """
        SELECT
            dt.*,
            low_user.id AS low_id,
            low_user.username AS low_username,
            low_user.role AS low_role,
            low_user.bio AS low_bio,
            low_user.avatar_path AS low_avatar_path,
            low_user.xp AS low_xp,
            low_user.created_at AS low_created_at,
            low_user.last_seen_at AS low_last_seen_at,
            high_user.id AS high_id,
            high_user.username AS high_username,
            high_user.role AS high_role,
            high_user.bio AS high_bio,
            high_user.avatar_path AS high_avatar_path,
            high_user.xp AS high_xp,
            high_user.created_at AS high_created_at,
            high_user.last_seen_at AS high_last_seen_at,
            (SELECT COUNT(*)
             FROM dm_messages dm_unread
             WHERE dm_unread.thread_id = dt.id
               AND dm_unread.recipient_id = ?
               AND dm_unread.read_at IS NULL) AS unread_count,
            (SELECT dm_last.content
             FROM dm_messages dm_last
             WHERE dm_last.thread_id = dt.id
             ORDER BY dm_last.created_at DESC, dm_last.id DESC
             LIMIT 1) AS last_message_content,
            (SELECT dm_last.created_at
             FROM dm_messages dm_last
             WHERE dm_last.thread_id = dt.id
             ORDER BY dm_last.created_at DESC, dm_last.id DESC
             LIMIT 1) AS last_message_created_at,
            (SELECT dm_last.sender_id
             FROM dm_messages dm_last
             WHERE dm_last.thread_id = dt.id
             ORDER BY dm_last.created_at DESC, dm_last.id DESC
             LIMIT 1) AS last_message_sender_id
        FROM dm_threads dt
        JOIN users low_user ON low_user.id = dt.user_low_id
        JOIN users high_user ON high_user.id = dt.user_high_id
        WHERE dt.id = ? AND (dt.user_low_id = ? OR dt.user_high_id = ?)
        """,
        (viewer_id, thread_id, viewer_id, viewer_id),
    ).fetchone()
    if not row:
        return None
    other_id = row["user_high_id"] if row["user_low_id"] == viewer_id else row["user_low_id"]
    if has_dm_block_relationship(conn, viewer_id, int(other_id)):
        return None
    return serialize_dm_thread_summary(row, viewer_id)


def get_or_create_dm_thread(conn: sqlite3.Connection, user_a: int, user_b: int) -> int:
    user_low_id, user_high_id = normalize_dm_pair(user_a, user_b)
    row = conn.execute(
        """
        SELECT id
        FROM dm_threads
        WHERE user_low_id = ? AND user_high_id = ?
        """,
        (user_low_id, user_high_id),
    ).fetchone()
    if row:
        return row["id"]
    now = utc_iso()
    cur = conn.execute(
        """
        INSERT INTO dm_threads (
            user_low_id, user_high_id, created_at, updated_at, last_message_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_low_id, user_high_id, now, now, now),
    )
    return cur.lastrowid


def add_dm_message(
    conn: sqlite3.Connection,
    *,
    thread_id: int,
    sender_id: int,
    recipient_id: int,
    content: str,
    created_at: str | None = None,
) -> int:
    now = created_at or utc_iso()
    cur = conn.execute(
        """
        INSERT INTO dm_messages (
            thread_id, sender_id, recipient_id, content, created_at, updated_at, read_at
        )
        VALUES (?, ?, ?, ?, ?, ?, NULL)
        """,
        (thread_id, sender_id, recipient_id, content, now, now),
    )
    conn.execute(
        """
        UPDATE dm_threads
        SET updated_at = ?, last_message_at = ?
        WHERE id = ?
        """,
        (now, now, thread_id),
    )
    return cur.lastrowid


def mark_dm_thread_read(conn: sqlite3.Connection, thread_id: int, viewer_id: int) -> bool:
    unread = conn.execute(
        """
        SELECT id
        FROM dm_messages
        WHERE thread_id = ? AND recipient_id = ? AND read_at IS NULL
        LIMIT 1
        """,
        (thread_id, viewer_id),
    ).fetchone()
    if not unread:
        return False
    now = utc_iso()
    conn.execute(
        """
        UPDATE dm_messages
        SET read_at = ?, updated_at = ?
        WHERE thread_id = ? AND recipient_id = ? AND read_at IS NULL
        """,
        (now, now, thread_id, viewer_id),
    )
    return True


def list_dm_messages(
    conn: sqlite3.Connection,
    thread_id: int,
    viewer_id: int,
    *,
    limit: int = 200,
) -> list[dict[str, Any]]:
    from .domain_users import serialize_user

    rows = conn.execute(
        """
        SELECT
            dm.*,
            sender.username AS sender_username,
            sender.role AS sender_role,
            sender.bio AS sender_bio,
            sender.avatar_path AS sender_avatar_path,
            sender.xp AS sender_xp,
            sender.created_at AS sender_created_at,
            sender.last_seen_at AS sender_last_seen_at
        FROM dm_messages dm
        JOIN users sender ON sender.id = dm.sender_id
        WHERE dm.thread_id = ?
        ORDER BY dm.created_at ASC, dm.id ASC
        LIMIT ?
        """,
        (thread_id, limit),
    ).fetchall()
    return [
        {
            "id": row["id"],
            "content": row["content"],
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
            "readAt": row["read_at"],
            "isMine": row["sender_id"] == viewer_id,
            "sender": serialize_user(
                {
                    "id": row["sender_id"],
                    "username": row["sender_username"],
                    "role": row["sender_role"],
                    "bio": row["sender_bio"] or "",
                    "avatar_path": row["sender_avatar_path"] or "",
                    "xp": row["sender_xp"] or 0,
                    "created_at": row["sender_created_at"],
                    "last_seen_at": row["sender_last_seen_at"],
                    "posts_count": 0,
                    "threads_count": 0,
                    "likes_received": 0,
                }
            ),
        }
        for row in rows
    ]


def serialize_contact_submission(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "discordUsername": row["discord_username"] or "",
        "subject": row["subject"],
        "message": row["message"],
        "status": row["status"],
        "adminNote": row["admin_note"] or "",
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "handledAt": row["handled_at"],
        "submittedBy": (
            {
                "id": row["user_id"],
                "username": row["username"],
                "role": row["role"],
            }
            if row["user_id"] and row["username"]
            else None
        ),
        "handledBy": (
            {
                "id": row["handled_by"],
                "username": row["handled_by_username"],
            }
            if row["handled_by"] and row["handled_by_username"]
            else None
        ),
    }


def list_contact_submissions(
    conn: sqlite3.Connection,
    *,
    status: str = "open",
    limit: int = 50,
) -> list[dict[str, Any]]:
    params: list[Any] = []
    where = ""
    if status in {"open", "resolved"}:
        where = "WHERE cs.status = ?"
        params.append(status)
    rows = conn.execute(
        f"""
        SELECT
            cs.*,
            submitter.username AS username,
            submitter.role AS role,
            handler.username AS handled_by_username
        FROM contact_submissions cs
        LEFT JOIN users submitter ON submitter.id = cs.user_id
        LEFT JOIN users handler ON handler.id = cs.handled_by
        {where}
        ORDER BY
            CASE cs.status WHEN 'open' THEN 0 ELSE 1 END,
            cs.created_at DESC,
            cs.id DESC
        LIMIT ?
        """,
        (*params, limit),
    ).fetchall()
    return [serialize_contact_submission(row) for row in rows]
