"""Focused forum domain helpers for notifications."""

from __future__ import annotations

import json
import sqlite3
from typing import Any
from .config import (
    MENTION_PATTERN,
    NOTIFICATION_PREFERENCE_COLUMNS,
    ROLES,
)
from .core import (
    has_required_role,
    is_admin,
    is_staff,
    utc_iso,
)
from .validation import pending_registration_count
from .account_state import sync_user_restrictions
from .text_utils import short_preview
from .admin_health import (
    get_open_appeal_count,
    get_open_contact_notice_count,
    get_open_report_count,
)

def user_prefers_notification(conn: sqlite3.Connection, user_id: int, kind: str) -> bool:
    column = NOTIFICATION_PREFERENCE_COLUMNS.get(kind)
    if not column:
        return True
    row = conn.execute(
        f"SELECT {column} AS enabled FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    return bool(row and row["enabled"])


def extract_mentioned_users(
    conn: sqlite3.Connection,
    text: Any,
    *,
    exclude_user_ids: set[int] | None = None,
) -> list[dict[str, Any]]:
    exclude = exclude_user_ids or set()
    usernames: list[str] = []
    for match in MENTION_PATTERN.findall(str(text or "")):
        normalized = match.strip().lower()
        if normalized and normalized not in usernames:
            usernames.append(normalized)
    users: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    for username in usernames:
        row = conn.execute(
            "SELECT * FROM users WHERE lower(username) = ? AND approval_status = 'approved'",
            (username,),
        ).fetchone()
        resolved = sync_user_restrictions(conn, row)
        if not resolved:
            continue
        user_id = int(resolved["id"])
        if user_id in exclude or user_id in seen_ids:
            continue
        seen_ids.add(user_id)
        users.append(resolved)
    return users


def create_notification(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    actor_id: int | None,
    kind: str,
    title: str,
    body: str = "",
    target_type: str = "",
    target_id: int | None = None,
    metadata: dict[str, Any] | None = None,
    created_at: str | None = None,
) -> None:
    if actor_id and actor_id == user_id:
        return
    if not user_prefers_notification(conn, user_id, kind):
        return
    conn.execute(
        """
        INSERT INTO notifications (
            user_id, actor_id, kind, title, body, target_type,
            target_id, metadata_json, read_at, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)
        """,
        (
            user_id,
            actor_id,
            kind,
            title,
            body,
            target_type,
            target_id,
            json.dumps(metadata or {}),
            created_at or utc_iso(),
        ),
    )


def create_staff_notifications(
    conn: sqlite3.Connection,
    *,
    actor_id: int | None,
    title: str,
    body: str = "",
    target_type: str = "",
    target_id: int | None = None,
    metadata: dict[str, Any] | None = None,
    created_at: str | None = None,
) -> None:
    rows = conn.execute(
        "SELECT id FROM users WHERE role IN ('mod', 'admin', 'owner') AND approval_status = 'approved'"
    ).fetchall()
    for row in rows:
        create_notification(
            conn,
            user_id=row["id"],
            actor_id=actor_id,
            kind="staff_alert",
            title=title,
            body=body,
            target_type=target_type,
            target_id=target_id,
            metadata=metadata,
            created_at=created_at,
        )


def get_unread_notification_count(conn: sqlite3.Connection, user_id: int) -> int:
    return conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM notifications
        WHERE user_id = ? AND read_at IS NULL
          AND NOT EXISTS (
            SELECT 1
            FROM user_relationships rel
            WHERE rel.user_id = ?
              AND rel.target_user_id = COALESCE(notifications.actor_id, -1)
              AND (rel.ignore_content = 1 OR rel.block_dm = 1)
          )
        """,
        (user_id, user_id),
    ).fetchone()["count"]


def get_notification_counts(
    conn: sqlite3.Connection,
    user_id: int,
    *,
    viewer: dict[str, Any] | None = None,
) -> dict[str, int]:
    from .domain_messages import get_unread_dm_count

    rows = conn.execute(
        """
        SELECT kind, target_type, COUNT(*) AS count
        FROM notifications
        WHERE user_id = ? AND read_at IS NULL
          AND NOT EXISTS (
            SELECT 1
            FROM user_relationships rel
            WHERE rel.user_id = ?
              AND rel.target_user_id = COALESCE(notifications.actor_id, -1)
              AND (rel.ignore_content = 1 OR rel.block_dm = 1)
          )
        GROUP BY kind, target_type
        """,
        (user_id, user_id),
    ).fetchall()
    counts = {
        "unread": 0,
        "replies": 0,
        "mentions": 0,
        "likes": 0,
        "dms": get_unread_dm_count(conn, user_id),
        "staff": 0,
        "reports": get_open_report_count(conn) if is_staff(viewer) else 0,
        "appeals": get_open_appeal_count(conn) if is_staff(viewer) else 0,
        "contactNotices": get_open_contact_notice_count(conn) if is_staff(viewer) else 0,
        "registrations": pending_registration_count(conn) if is_admin(viewer) else 0,
        "staffActions": 0,
    }
    for row in rows:
        count = int(row["count"] or 0)
        kind = row["kind"]
        target_type = row["target_type"] or ""
        counts["unread"] += count
        if kind == "reply":
            counts["replies"] += count
        elif kind == "mention":
            counts["mentions"] += count
        elif kind == "like":
            counts["likes"] += count
        elif kind == "dm":
            counts["dms"] = max(counts["dms"], count)
        elif kind == "staff_action":
            counts["staffActions"] += count
        if kind == "staff_alert" or target_type in {"report_queue", "appeal_queue", "contact_notice", "registration_queue"}:
            counts["staff"] += count
    counts["totalAttention"] = (
        counts["unread"]
        + counts["dms"]
        + counts["reports"]
        + counts["appeals"]
        + counts["contactNotices"]
        + counts["registrations"]
    )
    return counts


def serialize_notification(row: sqlite3.Row) -> dict[str, Any]:
    try:
        metadata = json.loads(row["metadata_json"] or "{}")
    except json.JSONDecodeError:
        metadata = {}
    return {
        "id": row["id"],
        "kind": row["kind"],
        "title": row["title"],
        "body": row["body"] or "",
        "targetType": row["target_type"] or "",
        "targetId": row["target_id"],
        "metadata": metadata,
        "readAt": row["read_at"],
        "createdAt": row["created_at"],
        "actor": (
            {
                "id": row["actor_id"],
                "username": row["actor_username"],
                "role": row["actor_role"],
            }
            if row["actor_id"] and row["actor_username"]
            else None
        ),
    }


def list_notifications(
    conn: sqlite3.Connection,
    user_id: int,
    *,
    status: str = "all",
    kind: str = "all",
    limit: int = 60,
) -> list[dict[str, Any]]:
    params: list[Any] = [user_id, user_id]
    where = """
    WHERE n.user_id = ?
      AND NOT EXISTS (
        SELECT 1
        FROM user_relationships rel
        WHERE rel.user_id = ?
          AND rel.target_user_id = COALESCE(n.actor_id, -1)
          AND (rel.ignore_content = 1 OR rel.block_dm = 1)
      )
    """
    if status == "unread":
        where += " AND n.read_at IS NULL"
    if kind == "replies":
        where += " AND n.kind = 'reply'"
    elif kind == "mentions":
        where += " AND n.kind = 'mention'"
    elif kind == "likes":
        where += " AND n.kind = 'like'"
    elif kind == "dms":
        where += " AND n.kind = 'dm'"
    elif kind == "staff":
        where += " AND (n.kind = 'staff_alert' OR n.target_type IN ('report_queue', 'appeal_queue', 'contact_notice', 'registration_queue'))"
    elif kind == "staff_actions":
        where += " AND n.kind = 'staff_action'"
    rows = conn.execute(
        f"""
        SELECT
            n.*,
            actor.username AS actor_username,
            actor.role AS actor_role
        FROM notifications n
        LEFT JOIN users actor ON actor.id = n.actor_id
        {where}
        ORDER BY n.created_at DESC, n.id DESC
        LIMIT ?
        """,
        (*params, limit),
    ).fetchall()
    return [serialize_notification(row) for row in rows]


def mark_notifications_read(
    conn: sqlite3.Connection,
    user_id: int,
    *,
    notification_ids: list[int] | None = None,
    target_type: str | None = None,
    target_id: int | None = None,
) -> int:
    clauses = ["user_id = ?", "read_at IS NULL"]
    params: list[Any] = [user_id]
    if notification_ids:
        placeholders = ", ".join("?" for _ in notification_ids)
        clauses.append(f"id IN ({placeholders})")
        params.extend(notification_ids)
    if target_type is not None:
        clauses.append("target_type = ?")
        params.append(target_type)
    if target_id is not None:
        clauses.append("target_id = ?")
        params.append(target_id)
    now = utc_iso()
    cur = conn.execute(
        f"""
        UPDATE notifications
        SET read_at = ?
        WHERE {" AND ".join(clauses)}
        """,
        (now, *params),
    )
    return cur.rowcount or 0


def notify_mentions_in_thread(
    conn: sqlite3.Connection,
    *,
    actor: dict[str, Any],
    content: str,
    thread_id: int,
    post_id: int,
    required_role: str,
    created_at: str,
) -> set[int]:
    mentioned_users = extract_mentioned_users(
        conn,
        content,
        exclude_user_ids={int(actor["id"])},
    )
    for user in mentioned_users:
        if not has_required_role(user, required_role):
            continue
        create_notification(
            conn,
            user_id=user["id"],
            actor_id=actor["id"],
            kind="mention",
            title=f"{actor['username']} mentioned you",
            body=short_preview(content, max_len=140),
            target_type="thread",
            target_id=thread_id,
            metadata={"postId": post_id, "threadId": thread_id},
            created_at=created_at,
        )
    return {user["id"] for user in mentioned_users}


def notify_thread_reply(
    conn: sqlite3.Connection,
    *,
    actor: dict[str, Any],
    thread: sqlite3.Row,
    post_id: int,
    content: str,
    skip_user_ids: set[int] | None = None,
    created_at: str,
) -> None:
    skip_ids = set(skip_user_ids or set())
    skip_ids.add(int(actor["id"]))
    participant_rows = conn.execute(
        """
        SELECT DISTINCT author_id
        FROM posts
        WHERE thread_id = ? AND author_id != ?
        """,
        (thread["id"], actor["id"]),
    ).fetchall()
    subscriber_rows = conn.execute(
        """
        SELECT user_id AS author_id
        FROM thread_subscriptions
        WHERE thread_id = ? AND user_id != ?
        """,
        (thread["id"], actor["id"]),
    ).fetchall()
    for row in [*participant_rows, *subscriber_rows]:
        recipient_id = int(row["author_id"])
        if recipient_id in skip_ids:
            continue
        create_notification(
            conn,
            user_id=recipient_id,
            actor_id=actor["id"],
            kind="reply",
            title=f"New reply in {thread['title']}",
            body=f"{actor['username']}: {short_preview(content, max_len=120)}",
            target_type="thread",
            target_id=thread["id"],
            metadata={"postId": post_id, "threadId": thread["id"]},
            created_at=created_at,
        )
        skip_ids.add(recipient_id)


def notify_post_like(
    conn: sqlite3.Connection,
    *,
    actor: dict[str, Any],
    post: sqlite3.Row,
    thread_title: str,
    created_at: str,
) -> None:
    if int(post["author_id"]) == int(actor["id"]):
        return
    create_notification(
        conn,
        user_id=post["author_id"],
        actor_id=actor["id"],
        kind="like",
        title=f"{actor['username']} liked your post",
        body=f"In {thread_title}",
        target_type="thread",
        target_id=post["thread_id"],
        metadata={"postId": post["id"], "threadId": post["thread_id"]},
        created_at=created_at,
    )


def notify_dm_message(
    conn: sqlite3.Connection,
    *,
    sender: dict[str, Any],
    recipient_id: int,
    thread_id: int,
    content: str,
    created_at: str,
) -> None:
    create_notification(
        conn,
        user_id=recipient_id,
        actor_id=sender["id"],
        kind="dm",
        title=f"New message from {sender['username']}",
        body=short_preview(content, max_len=140),
        target_type="dm_thread",
        target_id=thread_id,
        metadata={"threadId": thread_id},
        created_at=created_at,
    )


def notify_staff_action(
    conn: sqlite3.Connection,
    *,
    target_user_id: int,
    actor: dict[str, Any],
    action: str,
    created_at: str,
    reason: str = "",
    note: str = "",
    delta_xp: int = 0,
    metadata: dict[str, Any] | None = None,
) -> None:
    labels = {
        "warn": ("Staff warning issued", reason or "A staff warning was added to your account."),
        "timeout": ("Account timeout applied", reason or "Your account has been temporarily restricted."),
        "clear_timeout": ("Account timeout cleared", reason or "Your posting timeout has been lifted."),
        "mute": ("Account muted", reason or "Your account has been temporarily muted from posting and messaging."),
        "clear_mute": ("Account mute cleared", reason or "Your mute has been lifted."),
        "shadow_mute": ("Account shadow-muted", reason or "Your account has been shadow-muted."),
        "clear_shadow_mute": ("Shadow mute cleared", reason or "Your account is no longer shadow-muted."),
        "ban": ("Account banned", reason or "Your account has been banned."),
        "unban": ("Account restored", reason or "Your account has been unbanned."),
        "xp_adjust": (
            "XP adjusted by staff",
            f"{'Granted' if delta_xp > 0 else 'Removed'} {abs(delta_xp)} XP. {reason}".strip(),
        ),
        "temp_password": (
            "Recovery password issued",
            note or "A temporary password was created for this account. Reset it after login.",
        ),
        "role_change": (
            "Role updated by staff",
            reason or "Your account role was changed by staff.",
        ),
    }
    title, body = labels.get(action, ("Staff action", reason or note or "A staff action was taken on your account."))
    if metadata and metadata.get("toRole") in ROLES:
        body = f"New role: {ROLES[metadata['toRole']]['label']}."
    create_notification(
        conn,
        user_id=target_user_id,
        actor_id=actor["id"],
        kind="staff_action",
        title=title,
        body=body,
        target_type="user",
        target_id=target_user_id,
        metadata=metadata,
        created_at=created_at,
    )
