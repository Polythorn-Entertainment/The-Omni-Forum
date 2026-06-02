from __future__ import annotations

import json
import sqlite3
from datetime import timedelta
from http import HTTPStatus
from typing import Any

from .config import (
    DEFAULT_PAGE_SIZE,
    DEFAULT_POST_PAGE_SIZE,
    FLOOD_CONTROL_SECONDS,
    POST_MEDIA_MAX_COUNT,
    XP_LIKE,
    XP_REPLY,
    XP_THREAD,
)
from .core import (
    has_required_role,
    is_admin,
    is_staff,
    role_level,
    utc_iso,
)
from .media import (
    collect_post_media_paths,
    delete_media_file,
    delete_post_artifact_rows,
    ensure_user_media_quota,
    list_post_media_rows,
    normalize_media_uploads,
    save_post_media_entries,
)
from .search import (
    remove_search_index_entry,
    update_post_search_index,
    update_thread_search_index,
)
from .validation import (
    clean_id_list,
    clean_poll_payload,
    clean_post_content,
    clean_reaction_emoji,
    clean_role_name,
    clean_slug,
    clean_sort_order,
    clean_text,
    clean_thread_prefix,
    clean_thread_state_mode,
    clean_thread_template,
    normalize_tags,
    normalize_thread_prefixes,
    parse_pagination_query,
)
from .audit import log_audit_event
from .account_state import (
    award_xp,
    enforce_low_trust_content_limits,
    enforce_recent_action_limit,
    ensure_can_participate,
    ensure_can_post_content,
    is_shadow_muted,
)
from .content_state import (
    create_thread_poll,
    is_shadow_hidden_to_viewer,
    list_post_reactions_summary,
    soft_delete_post,
    soft_delete_thread,
    vote_in_thread_poll,
)
from .domain import (
    add_thread_note,
    ensure_thread_subscription,
    get_category_by_slug,
    get_current_user_payload,
    get_next_section_sort_order,
    get_posts_for_thread,
    get_related_threads,
    get_section_by_slug,
    get_thread_by_id,
    get_top_members,
    get_user_profile,
    list_post_edit_history,
    list_threads_for_section,
    mark_notifications_read,
    notify_mentions_in_thread,
    notify_post_like,
    notify_thread_reply,
    serialize_section_summary,
    serialize_thread,
    thread_first_post_id,
    toggle_thread_membership,
)
from .text_utils import short_preview
from .errors import APIError


class ReactionContentApiMixin:
    def api_toggle_like(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        post_id: int,
    ) -> dict[str, Any]:
        ensure_can_post_content(viewer)
        self.enforce_rate_limit("like_toggle", viewer)
        post = conn.execute(
            """
            SELECT
                p.*,
                t.title AS thread_title,
                s.required_role AS section_required_role
            FROM posts p
            JOIN threads t ON t.id = p.thread_id
            JOIN sections s ON s.id = t.section_id
            WHERE p.id = ? AND p.deleted_at IS NULL AND t.deleted_at IS NULL
            """,
            (post_id,),
        ).fetchone()
        if not post:
            raise APIError("Post not found.", HTTPStatus.NOT_FOUND)
        if not has_required_role(viewer, post["section_required_role"]):
            raise APIError("You do not have access to this post.", HTTPStatus.FORBIDDEN)
        if is_shadow_hidden_to_viewer(hidden=post["shadow_hidden"], author_id=post["author_id"], viewer=viewer):
            raise APIError("Post not found.", HTTPStatus.NOT_FOUND)
        existing = conn.execute(
            "SELECT 1 FROM post_likes WHERE post_id = ? AND user_id = ?",
            (post_id, viewer["id"]),
        ).fetchone()
        if existing:
            conn.execute(
                "DELETE FROM post_likes WHERE post_id = ? AND user_id = ?",
                (post_id, viewer["id"]),
            )
            conn.commit()
            if post["author_id"] != viewer["id"]:
                award_xp(conn, post["author_id"], -XP_LIKE)
            liked = False
        else:
            now = utc_iso()
            conn.execute(
                "INSERT INTO post_likes (post_id, user_id, created_at) VALUES (?, ?, ?)",
                (post_id, viewer["id"], now),
            )
            if post["author_id"] != viewer["id"]:
                award_xp(conn, post["author_id"], XP_LIKE)
                notify_post_like(
                    conn,
                    actor=viewer,
                    post=post,
                    thread_title=post["thread_title"],
                    created_at=now,
                )
            conn.commit()
            liked = True
        likes = conn.execute(
            "SELECT COUNT(*) AS count FROM post_likes WHERE post_id = ?",
            (post_id,),
        ).fetchone()["count"]
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "liked": liked,
            "likes": likes,
        }

    def api_toggle_reaction(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        post_id: int,
    ) -> dict[str, Any]:
        ensure_can_post_content(viewer)
        self.enforce_rate_limit("like_toggle", viewer)
        data = self.read_json()
        emoji = clean_reaction_emoji(data.get("emoji"))
        post = conn.execute(
            """
            SELECT
                p.*,
                s.required_role AS section_required_role
            FROM posts p
            JOIN threads t ON t.id = p.thread_id
            JOIN sections s ON s.id = t.section_id
            WHERE p.id = ? AND p.deleted_at IS NULL AND t.deleted_at IS NULL
            """,
            (post_id,),
        ).fetchone()
        if not post:
            raise APIError("Post not found.", HTTPStatus.NOT_FOUND)
        if not has_required_role(viewer, post["section_required_role"]):
            raise APIError("You do not have access to this post.", HTTPStatus.FORBIDDEN)
        if is_shadow_hidden_to_viewer(hidden=post["shadow_hidden"], author_id=post["author_id"], viewer=viewer):
            raise APIError("Post not found.", HTTPStatus.NOT_FOUND)
        existing = conn.execute(
            "SELECT 1 FROM post_reactions WHERE post_id = ? AND user_id = ? AND emoji = ?",
            (post_id, viewer["id"], emoji),
        ).fetchone()
        if existing:
            conn.execute(
                "DELETE FROM post_reactions WHERE post_id = ? AND user_id = ? AND emoji = ?",
                (post_id, viewer["id"], emoji),
            )
            active = False
        else:
            conn.execute(
                "INSERT INTO post_reactions (post_id, user_id, emoji, created_at) VALUES (?, ?, ?, ?)",
                (post_id, viewer["id"], emoji, utc_iso()),
            )
            active = True
        conn.commit()
        reaction_summary = list_post_reactions_summary(conn, [post_id], viewer).get(post_id, {"items": [], "viewer": []})
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "active": active,
            "reactions": reaction_summary["items"],
            "viewerReactions": reaction_summary["viewer"],
        }
