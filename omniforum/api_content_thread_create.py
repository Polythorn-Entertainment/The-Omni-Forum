"""Focused thread content API handlers for create operations."""

from __future__ import annotations

import json
import sqlite3
from datetime import timedelta
from http import HTTPStatus
from typing import Any

from .account_state import (
    award_xp,
    enforce_low_trust_content_limits,
    enforce_recent_action_limit,
    ensure_can_participate,
    ensure_can_post_content,
    is_shadow_muted,
)
from .audit import log_audit_event
from .config import (
    DEFAULT_PAGE_SIZE,
    DEFAULT_POST_PAGE_SIZE,
    FLOOD_CONTROL_SECONDS,
    POST_MEDIA_MAX_COUNT,
    XP_LIKE,
    XP_REPLY,
    XP_THREAD,
)
from .content_state import (
    create_thread_poll,
    is_shadow_hidden_to_viewer,
    list_post_reactions_summary,
    soft_delete_post,
    soft_delete_thread,
    vote_in_thread_poll,
)
from .core import has_required_role, is_admin, is_staff, role_level, utc_iso
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
from .errors import APIError
from .media import (
    collect_post_media_paths,
    delete_media_file,
    delete_post_artifact_rows,
    ensure_user_media_quota,
    list_post_media_rows,
    normalize_media_uploads,
    save_post_media_entries,
)
from .search import remove_search_index_entry, update_post_search_index, update_thread_search_index
from .text_utils import short_preview
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


class CreateThreadContentApiMixin:
    def api_create_thread(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        slug: str,
    ) -> dict[str, Any]:
        ensure_can_post_content(viewer)
        self.enforce_rate_limit("thread_create", viewer)
        section = get_section_by_slug(conn, slug)
        if not section:
            raise APIError("Section not found.", HTTPStatus.NOT_FOUND)
        if not has_required_role(viewer, section["write_role"]):
            raise APIError("You do not have permission to post here.", HTTPStatus.FORBIDDEN)
        enforce_recent_action_limit(
            conn,
            viewer,
            query="SELECT created_at FROM threads WHERE author_id = ? ORDER BY created_at DESC, id DESC LIMIT 1",
            params=(viewer["id"],),
            base_seconds=FLOOD_CONTROL_SECONDS["thread"],
            verb="start another thread",
        )
        data = self.read_json()
        title = clean_text(data.get("title"), min_len=4, max_len=120, field="Title")
        media_uploads = normalize_media_uploads(
            data.get("mediaUploads"),
            max_items=POST_MEDIA_MAX_COUNT,
        )
        content = clean_post_content(data.get("content"), has_media=bool(media_uploads))
        enforce_low_trust_content_limits(viewer, content)
        tags = normalize_tags(data.get("tags"))
        allowed_prefixes = json.loads(section["thread_prefixes_json"] or "[]")
        prefix = clean_thread_prefix(data.get("prefix"), allowed_prefixes)
        media_sensitive = bool(data.get("mediaSensitive"))
        poll = clean_poll_payload(data.get("poll"))
        ensure_user_media_quota(conn, viewer["id"], media_uploads)
        now = utc_iso()
        cur = conn.execute(
            """
                INSERT INTO threads (
                    section_id, author_id, title, prefix, tags_json, created_at, updated_at,
                    edited_at, view_count, pinned, locked, solved, answer_post_id, shadow_hidden
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, NULL, 1, 0, 0, 0, NULL, ?)
                """,
            (
                section["id"],
                viewer["id"],
                title,
                prefix,
                json.dumps(tags),
                now,
                now,
                int(is_shadow_muted(viewer)),
            ),
        )
        thread_id = cur.lastrowid
        first_post = conn.execute(
            """
                INSERT INTO posts (
                    thread_id, author_id, content, media_sensitive,
                    created_at, updated_at, edited_at, shadow_hidden
                )
                VALUES (?, ?, ?, ?, ?, ?, NULL, ?)
                """,
            (
                thread_id,
                viewer["id"],
                content,
                int(media_sensitive),
                now,
                now,
                int(is_shadow_muted(viewer)),
            ),
        )
        if poll:
            create_thread_poll(conn, thread_id=thread_id, poll=poll, created_at=now)
        save_post_media_entries(
            conn,
            post_id=first_post.lastrowid,
            uploads=media_uploads,
            created_at=now,
        )
        if not is_shadow_muted(viewer):
            notify_mentions_in_thread(
                conn,
                actor=viewer,
                content=content,
                thread_id=thread_id,
                post_id=first_post.lastrowid,
                required_role=section["required_role"],
                created_at=now,
            )
        ensure_thread_subscription(conn, thread_id=thread_id, user_id=viewer["id"], created_at=now)
        update_thread_search_index(conn, thread_id)
        update_post_search_index(conn, first_post.lastrowid)
        conn.commit()
        award_xp(conn, viewer["id"], XP_THREAD)
        return {
            "currentUser": get_user_profile(conn, viewer["id"], viewer=viewer),
            "thread": serialize_thread(get_thread_by_id(conn, thread_id), conn, viewer),
        }
