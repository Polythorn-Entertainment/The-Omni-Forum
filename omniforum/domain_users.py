"""Focused forum domain helpers for users."""

from __future__ import annotations

import json
import sqlite3
from datetime import timedelta
from http import HTTPStatus
from typing import Any
from .config import (
    ONLINE_WINDOW_MINUTES,
    ROLES,
)
from .core import (
    can_manage_user,
    can_moderate_user,
    is_admin,
    is_staff,
    parse_iso,
    recovery_code_summary,
    role_level,
    utc_iso,
    utc_now,
)
from .email_auth import EMAIL_AUTH_ENABLED, public_email_auth_features
from .media import (
    get_user_media_usage,
    media_url_for_path,
)
from .errors import APIError
from .validation import is_approved_user
from .account_state import (
    active_mute_until,
    active_timeout_until,
    is_banned_user,
    sync_user_restrictions,
    user_trust_summary,
)
from .sessions import list_recent_sessions
from .admin_health import (
    get_open_contact_notice_count,
    get_open_report_count,
)


def get_user_profile(
    conn: sqlite3.Connection,
    user_id: int,
    *,
    viewer: dict[str, Any] | None = None,
    include_detail: bool = True,
) -> dict[str, Any] | None:
    from .domain_moderation import (
        list_appeals_for_viewer,
        list_user_moderation_actions,
        serialize_user_moderation,
    )
    from .domain_notifications import get_notification_counts
    from .domain_threads import list_saved_threads

    row = conn.execute(
        """
        SELECT
            u.*,
            timeout_actor.username AS timeout_by_username,
            mute_actor.username AS mute_by_username,
            ban_actor.username AS banned_by_username,
            reset_actor.username AS password_reset_by_username,
            (SELECT COUNT(*) FROM posts p WHERE p.author_id = u.id AND p.deleted_at IS NULL) AS posts_count,
            (SELECT COUNT(*) FROM threads t WHERE t.author_id = u.id AND t.deleted_at IS NULL) AS threads_count,
            (SELECT COUNT(*) FROM post_likes pl
             JOIN posts p2 ON p2.id = pl.post_id
             WHERE p2.author_id = u.id AND p2.deleted_at IS NULL) AS likes_received
        FROM users u
        LEFT JOIN users timeout_actor ON timeout_actor.id = u.timeout_set_by
        LEFT JOIN users mute_actor ON mute_actor.id = u.mute_set_by
        LEFT JOIN users ban_actor ON ban_actor.id = u.banned_by
        LEFT JOIN users reset_actor ON reset_actor.id = u.password_reset_set_by
        WHERE u.id = ?
        """,
        (user_id,),
    ).fetchone()
    if not row:
        return None
    resolved = sync_user_restrictions(conn, row)
    if not resolved:
        return None
    if not is_approved_user(resolved) and not (viewer and is_admin(viewer)):
        return None
    profile = serialize_user(resolved)
    profile["noticeCount"] = (
        get_open_contact_notice_count(conn) if role_level(resolved["role"]) >= role_level("mod") else 0
    )
    profile["reportCount"] = get_open_report_count(conn) if role_level(resolved["role"]) >= role_level("mod") else 0
    relationship = (
        get_user_relationship(conn, viewer["id"], user_id)
        if viewer and viewer["id"] != user_id
        else {"ignoreContent": False, "blockDm": False}
    )
    profile["relationship"] = relationship
    profile["canMessage"] = bool(
        viewer
        and viewer["id"] != user_id
        and not relationship["blockDm"]
        and not has_dm_block_relationship(conn, viewer["id"], user_id)
    )
    if viewer and viewer["id"] == user_id:
        if viewer.get("session_csrf_token"):
            profile["csrfToken"] = viewer.get("session_csrf_token")
        profile["mustResetPassword"] = bool(resolved.get("password_reset_required"))
        notification_counts = get_notification_counts(conn, user_id, viewer=viewer)
        profile["messageCount"] = notification_counts["dms"]
        profile["notificationCount"] = notification_counts["unread"]
        profile["notificationCounts"] = notification_counts
        profile["registrationCount"] = notification_counts["registrations"]
        profile["appealCount"] = notification_counts["appeals"]
        profile["preferences"] = {
            "siteTheme": resolved.get("site_theme") or "midnight",
            "dmPrivacy": resolved.get("dm_privacy") or "everyone",
            "blurSensitiveMedia": bool(resolved.get("blur_sensitive_media", 1)),
            "compactPostLayout": bool(resolved.get("compact_post_layout", 0)),
            "hideIgnoredContent": bool(resolved.get("hide_ignored_content", 1)),
            "notifyReplies": bool(resolved.get("notify_replies", 1)),
            "notifyLikes": bool(resolved.get("notify_likes", 1)),
            "notifyMentions": bool(resolved.get("notify_mentions", 1)),
            "notifyDms": bool(resolved.get("notify_dms", 1)),
        }
        profile["community"] = {
            "statusText": resolved.get("status_text") or "",
            "signature": resolved.get("signature") or "",
            "profileBadge": resolved.get("profile_badge") or "",
            "profileAccent": resolved.get("profile_accent") or "",
        }
        profile["authFeatures"] = {"email": public_email_auth_features()}
        if EMAIL_AUTH_ENABLED:
            profile["email"] = resolved.get("email") or ""
            profile["emailVerified"] = bool(resolved.get("email_verified_at"))
        profile["recovery"] = {
            "discordUsername": resolved.get("recovery_discord_username") or "",
            "codes": recovery_code_summary(conn, user_id),
        }
        if include_detail:
            profile["recentSessions"] = list_recent_sessions(conn, user_id)
            profile["library"] = {
                "bookmarks": list_saved_threads(
                    conn,
                    table="thread_bookmarks",
                    user_id=user_id,
                    viewer=viewer,
                ),
                "subscriptions": list_saved_threads(
                    conn,
                    table="thread_subscriptions",
                    user_id=user_id,
                    viewer=viewer,
                ),
            }
            profile["relationships"] = list_user_relationships(conn, user_id)
            profile["mediaUsage"] = get_user_media_usage(conn, user_id)
    if viewer and (viewer["id"] == user_id or is_staff(viewer)):
        profile["moderation"] = serialize_user_moderation(resolved)
    if (
        viewer
        and viewer["id"] == user_id
        and include_detail
        and (is_banned_user(resolved) or active_timeout_until(resolved) or active_mute_until(resolved))
    ):
        profile["appeals"] = list_appeals_for_viewer(conn, viewer, status="all")
    if viewer and include_detail and (viewer["id"] == user_id or is_staff(viewer)):
        profile["sessionAudit"] = list_recent_sessions(conn, user_id)
    if viewer and is_staff(viewer):
        if include_detail:
            profile["moderationHistory"] = list_user_moderation_actions(conn, user_id)
            profile["appeals"] = list_appeals_for_viewer(conn, viewer, status="all", target_user_id=user_id)
        profile["canModerate"] = can_moderate_user(viewer, resolved)
        profile["canManageRole"] = can_manage_user(viewer, resolved["role"]) and viewer["id"] != user_id
        profile["canIssueTempPassword"] = is_admin(viewer) and can_moderate_user(viewer, resolved)
    return profile


def serialize_user(row: dict[str, Any]) -> dict[str, Any]:
    last_seen = parse_iso(row.get("last_seen_at"))
    online_threshold = utc_now() - timedelta(minutes=ONLINE_WINDOW_MINUTES)
    return {
        "id": row["id"],
        "username": row["username"],
        "role": row["role"],
        "bio": row.get("bio") or "",
        "avatarUrl": media_url_for_path(row.get("avatar_path")),
        "statusText": row.get("status_text") or "",
        "signature": row.get("signature") or "",
        "profileBadge": row.get("profile_badge") or "",
        "profileAccent": row.get("profile_accent") or "",
        "xp": row.get("xp", 0),
        "posts": row.get("posts_count", 0),
        "threads": row.get("threads_count", 0),
        "likesReceived": row.get("likes_received", 0),
        "joined": row["created_at"],
        "online": bool(last_seen and last_seen >= online_threshold),
        "trust": user_trust_summary(row),
    }


def get_user_relationship(
    conn: sqlite3.Connection,
    user_id: int,
    target_user_id: int,
) -> dict[str, bool]:
    if int(user_id or 0) <= 0 or int(target_user_id or 0) <= 0 or int(user_id) == int(target_user_id):
        return {"ignoreContent": False, "blockDm": False}
    row = conn.execute(
        """
        SELECT ignore_content, block_dm
        FROM user_relationships
        WHERE user_id = ? AND target_user_id = ?
        """,
        (user_id, target_user_id),
    ).fetchone()
    return {
        "ignoreContent": bool(row and row["ignore_content"]),
        "blockDm": bool(row and row["block_dm"]),
    }


def list_user_relationships(
    conn: sqlite3.Connection,
    user_id: int,
    *,
    limit: int = 80,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            rel.*,
            u.id AS target_id,
            u.username AS target_username,
            u.role AS target_role,
            u.bio AS target_bio,
            u.avatar_path AS target_avatar_path,
            u.status_text AS target_status_text,
            u.xp AS target_xp,
            u.created_at AS target_created_at,
            u.last_seen_at AS target_last_seen_at
        FROM user_relationships rel
        JOIN users u ON u.id = rel.target_user_id
        WHERE rel.user_id = ? AND (rel.ignore_content = 1 OR rel.block_dm = 1)
        ORDER BY rel.updated_at DESC, rel.target_user_id DESC
        LIMIT ?
        """,
        (user_id, limit),
    ).fetchall()
    output: list[dict[str, Any]] = []
    for row in rows:
        output.append(
            {
                "user": serialize_user(
                    {
                        "id": row["target_id"],
                        "username": row["target_username"],
                        "role": row["target_role"],
                        "bio": row["target_bio"] or "",
                        "avatar_path": row["target_avatar_path"] or "",
                        "status_text": row["target_status_text"] or "",
                        "xp": row["target_xp"] or 0,
                        "created_at": row["target_created_at"],
                        "last_seen_at": row["target_last_seen_at"],
                        "posts_count": 0,
                        "threads_count": 0,
                        "likes_received": 0,
                    }
                ),
                "ignoreContent": bool(row["ignore_content"]),
                "blockDm": bool(row["block_dm"]),
                "updatedAt": row["updated_at"],
            }
        )
    return output


def upsert_user_relationship(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    target_user_id: int,
    ignore_content: bool,
    block_dm: bool,
) -> dict[str, bool]:
    if int(user_id or 0) <= 0 or int(target_user_id or 0) <= 0:
        raise APIError("Relationship target is invalid.")
    if user_id == target_user_id:
        raise APIError("You cannot apply safety controls to your own account.")
    now = utc_iso()
    if not ignore_content and not block_dm:
        conn.execute(
            "DELETE FROM user_relationships WHERE user_id = ? AND target_user_id = ?",
            (user_id, target_user_id),
        )
        conn.commit()
        return {"ignoreContent": False, "blockDm": False}
    conn.execute(
        """
        INSERT INTO user_relationships (
            user_id, target_user_id, ignore_content, block_dm, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, target_user_id)
        DO UPDATE SET
            ignore_content = excluded.ignore_content,
            block_dm = excluded.block_dm,
            updated_at = excluded.updated_at
        """,
        (user_id, target_user_id, int(ignore_content), int(block_dm), now, now),
    )
    conn.commit()
    return {"ignoreContent": bool(ignore_content), "blockDm": bool(block_dm)}


def viewer_ignored_user_ids(
    conn: sqlite3.Connection,
    viewer: dict[str, Any] | None,
) -> set[int]:
    if not viewer or not bool(viewer.get("hide_ignored_content", 1)):
        return set()
    cached = viewer.get("_ignored_user_ids")
    if isinstance(cached, set):
        return cached
    rows = conn.execute(
        """
        SELECT target_user_id
        FROM user_relationships
        WHERE user_id = ? AND ignore_content = 1
        """,
        (viewer["id"],),
    ).fetchall()
    ignored = {int(row["target_user_id"]) for row in rows}
    viewer["_ignored_user_ids"] = ignored
    return ignored


def is_ignored_author(
    conn: sqlite3.Connection,
    viewer: dict[str, Any] | None,
    author_id: int | None,
) -> bool:
    return bool(author_id and int(author_id) in viewer_ignored_user_ids(conn, viewer))


def has_dm_block_relationship(conn: sqlite3.Connection, user_a: int, user_b: int) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM user_relationships
        WHERE ((user_id = ? AND target_user_id = ?) OR (user_id = ? AND target_user_id = ?))
          AND block_dm = 1
        LIMIT 1
        """,
        (user_a, user_b, user_b, user_a),
    ).fetchone()
    return bool(row)


def get_top_members(conn: sqlite3.Connection, limit: int = 5) -> list[dict[str, Any]]:
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
            ORDER BY posts_count DESC, u.xp DESC, u.created_at ASC
            LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [serialize_user(dict(row)) for row in rows]


def list_members(conn: sqlite3.Connection) -> list[dict[str, Any]]:
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
            ORDER BY u.created_at DESC
        """
    ).fetchall()
    return [serialize_user(dict(row)) for row in rows]


def get_role_breakdown(conn: sqlite3.Connection) -> dict[str, int]:
    counts = {role: 0 for role in ROLES}
    rows = conn.execute(
        "SELECT role, COUNT(*) AS count FROM users WHERE approval_status = 'approved' GROUP BY role"
    ).fetchall()
    for row in rows:
        counts[row["role"]] = row["count"]
    return counts


def get_current_user_payload(conn: sqlite3.Connection, viewer: dict[str, Any] | None) -> dict[str, Any] | None:
    if not viewer:
        return None
    return get_user_profile(conn, viewer["id"], viewer=viewer, include_detail=False)


def build_user_export(conn: sqlite3.Connection, user_id: int) -> dict[str, Any]:
    profile = get_user_profile(conn, user_id, viewer={"id": user_id, "role": "owner"}, include_detail=True)
    if not profile:
        raise APIError("User not found.", HTTPStatus.NOT_FOUND)
    thread_rows = conn.execute(
        """
        SELECT t.id, t.title, t.prefix, t.tags_json, t.created_at, t.updated_at,
               s.slug AS section_slug, s.name AS section_name
        FROM threads t
        JOIN sections s ON s.id = t.section_id
        WHERE t.author_id = ?
        ORDER BY t.created_at DESC, t.id DESC
        """,
        (user_id,),
    ).fetchall()
    post_rows = conn.execute(
        """
        SELECT p.id, p.thread_id, p.content, p.created_at, p.updated_at, p.edited_at,
               p.deleted_at, p.media_sensitive, t.title AS thread_title
        FROM posts p
        JOIN threads t ON t.id = p.thread_id
        WHERE p.author_id = ?
        ORDER BY p.created_at DESC, p.id DESC
        """,
        (user_id,),
    ).fetchall()
    dm_rows = conn.execute(
        """
        SELECT
            dm.id,
            dm.thread_id,
            dm.sender_id,
            dm.recipient_id,
            dm.content,
            dm.created_at,
            dm.updated_at,
            dm.read_at,
            dt.user_low_id,
            dt.user_high_id,
            sender.username AS sender_username,
            recipient.username AS recipient_username
        FROM dm_messages dm
        JOIN dm_threads dt ON dt.id = dm.thread_id
        JOIN users sender ON sender.id = dm.sender_id
        JOIN users recipient ON recipient.id = dm.recipient_id
        WHERE dm.sender_id = ? OR dm.recipient_id = ?
        ORDER BY dm.created_at DESC, dm.id DESC
        """,
        (user_id, user_id),
    ).fetchall()
    notification_rows = conn.execute(
        """
        SELECT id, kind, title, body, target_type, target_id, read_at, created_at
        FROM notifications
        WHERE user_id = ?
        ORDER BY created_at DESC, id DESC
        LIMIT 500
        """,
        (user_id,),
    ).fetchall()
    report_rows = conn.execute(
        """
        SELECT id, target_type, target_label, reason, status, created_at, updated_at
        FROM reports
        WHERE reporter_id = ?
        ORDER BY created_at DESC, id DESC
        """,
        (user_id,),
    ).fetchall()
    appeal_rows = conn.execute(
        """
        SELECT id, message, status, created_at, updated_at, handled_at
        FROM appeals
        WHERE user_id = ?
        ORDER BY created_at DESC, id DESC
        """,
        (user_id,),
    ).fetchall()
    return {
        "exportedAt": utc_iso(),
        "site": "OmniForum",
        "account": profile,
        "user": profile,
        "threads": [
            {
                "id": row["id"],
                "title": row["title"],
                "prefix": row["prefix"] or "",
                "tags": json.loads(row["tags_json"] or "[]"),
                "section": {"id": row["section_slug"], "name": row["section_name"]},
                "createdAt": row["created_at"],
                "updatedAt": row["updated_at"],
            }
            for row in thread_rows
        ],
        "posts": [
            {
                "id": row["id"],
                "threadId": row["thread_id"],
                "threadTitle": row["thread_title"],
                "content": row["content"],
                "mediaSensitive": bool(row["media_sensitive"]),
                "createdAt": row["created_at"],
                "updatedAt": row["updated_at"],
                "editedAt": row["edited_at"],
                "deletedAt": row["deleted_at"],
            }
            for row in post_rows
        ],
        "messages": [
            {
                "id": row["id"],
                "threadId": row["thread_id"],
                "content": row["content"],
                "createdAt": row["created_at"],
                "updatedAt": row["updated_at"],
                "readAt": row["read_at"],
                "sender": {
                    "id": row["sender_id"],
                    "username": row["sender_username"],
                },
                "recipient": {
                    "id": row["recipient_id"],
                    "username": row["recipient_username"],
                },
                "participants": [row["user_low_id"], row["user_high_id"]],
            }
            for row in dm_rows
        ],
        "notifications": [
            {
                "id": row["id"],
                "kind": row["kind"],
                "title": row["title"],
                "body": row["body"],
                "targetType": row["target_type"],
                "targetId": row["target_id"],
                "readAt": row["read_at"],
                "createdAt": row["created_at"],
            }
            for row in notification_rows
        ],
        "reports": [dict(row) for row in report_rows],
        "appeals": [dict(row) for row in appeal_rows],
        "relationships": profile.get("relationships") or [],
        "mediaUsage": get_user_media_usage(conn, user_id),
    }
