"""Focused thread content API handlers for split operations."""

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


class SplitThreadContentApiMixin:
    def api_split_thread(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        thread_id: int,
    ) -> dict[str, Any]:
        if not viewer or not is_staff(viewer):
            raise APIError("Only staff can split threads.", HTTPStatus.FORBIDDEN)
        ensure_can_participate(viewer)
        thread = get_thread_by_id(conn, thread_id)
        if not thread:
            raise APIError("Thread not found.", HTTPStatus.NOT_FOUND)
        data = self.read_json()
        try:
            post_id = int(data.get("postId"))
        except (TypeError, ValueError) as exc:
            raise APIError("Choose the reply where the split should begin.") from exc
        first_post_id = thread_first_post_id(conn, thread_id)
        if post_id == first_post_id:
            raise APIError("Use thread edit instead of splitting from the opening post.")
        split_post = conn.execute(
            """
                SELECT *
                FROM posts
                WHERE id = ? AND thread_id = ? AND deleted_at IS NULL
                """,
            (post_id, thread_id),
        ).fetchone()
        if not split_post:
            raise APIError("Split point not found.", HTTPStatus.NOT_FOUND)
        title = clean_text(
            data.get("title") or f"Split from: {thread['title']}",
            min_len=4,
            max_len=120,
            field="New thread title",
        )
        section_slug = str(data.get("sectionId") or thread["section_slug"]).strip()
        target_section = get_section_by_slug(conn, section_slug)
        if not target_section:
            raise APIError("Destination section not found.", HTTPStatus.NOT_FOUND)
        tags = normalize_tags(data.get("tags", json.loads(thread["tags_json"] or "[]")))
        split_rows = conn.execute(
            """
                SELECT id
                FROM posts
                WHERE thread_id = ? AND deleted_at IS NULL
                  AND (created_at > ? OR (created_at = ? AND id >= ?))
                ORDER BY created_at ASC, id ASC
                """,
            (thread_id, split_post["created_at"], split_post["created_at"], post_id),
        ).fetchall()
        split_post_ids = [int(row["id"]) for row in split_rows]
        if not split_post_ids:
            raise APIError("There are no posts to split from that point.")
        now = utc_iso()
        cur = conn.execute(
            """
                INSERT INTO threads (
                    section_id, author_id, title, prefix, tags_json, created_at, updated_at,
                    edited_at, view_count, pinned, locked, solved, answer_post_id, featured, shadow_hidden
                )
                VALUES (?, ?, ?, '', ?, ?, ?, NULL, 0, 0, 0, 0, NULL, 0, ?)
                """,
            (
                target_section["id"],
                split_post["author_id"],
                title,
                json.dumps(tags),
                now,
                now,
                int(split_post["shadow_hidden"]),
            ),
        )
        new_thread_id = int(cur.lastrowid)
        placeholders = ", ".join("?" for _ in split_post_ids)
        conn.execute(
            f"UPDATE posts SET thread_id = ?, updated_at = ? WHERE id IN ({placeholders})",
            (new_thread_id, now, *split_post_ids),
        )
        if thread["answer_post_id"] in split_post_ids:
            conn.execute(
                "UPDATE threads SET solved = 0, answer_post_id = NULL WHERE id = ?",
                (thread_id,),
            )
        conn.execute("UPDATE threads SET updated_at = ? WHERE id = ?", (now, thread_id))
        ensure_thread_subscription(conn, thread_id=new_thread_id, user_id=viewer["id"], created_at=now)
        ensure_thread_subscription(conn, thread_id=new_thread_id, user_id=split_post["author_id"], created_at=now)
        update_thread_search_index(conn, thread_id)
        update_thread_search_index(conn, new_thread_id)
        for moved_post_id in split_post_ids:
            update_post_search_index(conn, moved_post_id)
        log_audit_event(
            conn,
            actor=viewer,
            action_type="thread_split",
            category="content",
            target_type="thread",
            target_id=thread_id,
            target_label=thread["title"],
            reason=f"Split {len(split_post_ids)} posts into thread {new_thread_id}.",
            metadata={
                "sourceThreadId": thread_id,
                "newThreadId": new_thread_id,
                "postIds": split_post_ids,
                "destinationSection": target_section["slug"],
            },
            created_at=now,
        )
        conn.commit()
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "thread": serialize_thread(get_thread_by_id(conn, new_thread_id), conn, viewer),
            "sourceThread": serialize_thread(get_thread_by_id(conn, thread_id), conn, viewer),
            "message": "Thread split created.",
        }
