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


class PostContentApiMixin:
    def api_create_post(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        thread_id: int,
    ) -> dict[str, Any]:
        ensure_can_post_content(viewer)
        self.enforce_rate_limit("post_create", viewer)
        thread = get_thread_by_id(conn, thread_id)
        if not thread:
            raise APIError("Thread not found.", HTTPStatus.NOT_FOUND)
        if thread["locked"]:
            raise APIError("This thread is locked.", HTTPStatus.FORBIDDEN)
        if not has_required_role(viewer, thread["section_write_role"]):
            raise APIError("You do not have permission to reply here.", HTTPStatus.FORBIDDEN)
        enforce_recent_action_limit(
            conn,
            viewer,
            query="SELECT created_at FROM posts WHERE author_id = ? ORDER BY created_at DESC, id DESC LIMIT 1",
            params=(viewer["id"],),
            base_seconds=FLOOD_CONTROL_SECONDS["reply"],
            verb="reply again",
        )
        data = self.read_json()
        media_uploads = normalize_media_uploads(
            data.get("mediaUploads"),
            max_items=POST_MEDIA_MAX_COUNT,
        )
        content = clean_post_content(data.get("content"), has_media=bool(media_uploads))
        enforce_low_trust_content_limits(viewer, content)
        media_sensitive = bool(data.get("mediaSensitive"))
        ensure_user_media_quota(conn, viewer["id"], media_uploads)
        now = utc_iso()
        cur = conn.execute(
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
        post_id = cur.lastrowid
        save_post_media_entries(
            conn,
            post_id=post_id,
            uploads=media_uploads,
            created_at=now,
        )
        conn.execute(
            "UPDATE threads SET updated_at = ? WHERE id = ?",
            (now, thread_id),
        )
        mentioned_ids: set[int] = set()
        if not is_shadow_muted(viewer):
            mentioned_ids = notify_mentions_in_thread(
                conn,
                actor=viewer,
                content=content,
                thread_id=thread_id,
                post_id=post_id,
                required_role=thread["section_required_role"],
                created_at=now,
            )
            notify_thread_reply(
                conn,
                actor=viewer,
                thread=thread,
                post_id=post_id,
                content=content,
                skip_user_ids=mentioned_ids,
                created_at=now,
            )
        ensure_thread_subscription(conn, thread_id=thread_id, user_id=viewer["id"], created_at=now)
        update_thread_search_index(conn, thread_id)
        update_post_search_index(conn, post_id)
        conn.commit()
        award_xp(conn, viewer["id"], XP_REPLY)
        posts, _ = get_posts_for_thread(
            conn,
            thread_id,
            viewer,
            page=1,
            page_size=DEFAULT_POST_PAGE_SIZE,
            last_page=True,
        )
        new_post = next((post for post in posts if post["id"] == post_id), None)
        return {
            "currentUser": get_user_profile(conn, viewer["id"], viewer=viewer),
            "post": new_post,
            "thread": serialize_thread(get_thread_by_id(conn, thread_id), conn, viewer),
        }

    def api_update_post(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        post_id: int,
    ) -> dict[str, Any]:
        ensure_can_post_content(viewer)
        self.enforce_rate_limit("post_update", viewer)
        row = conn.execute(
            """
            SELECT p.*, t.author_id AS thread_author_id, t.title AS thread_title
            FROM posts p
            JOIN threads t ON t.id = p.thread_id
            WHERE p.id = ?
            """,
            (post_id,),
        ).fetchone()
        if not row:
            raise APIError("Post not found.", HTTPStatus.NOT_FOUND)
        if row["deleted_at"]:
            raise APIError("Deleted posts cannot be edited.")
        if not (viewer["id"] == row["author_id"] or is_staff(viewer)):
            raise APIError("You cannot edit this post.", HTTPStatus.FORBIDDEN)
        data = self.read_json()
        next_thread_title = None
        if row["id"] == thread_first_post_id(conn, row["thread_id"]) and data.get("title"):
            next_thread_title = clean_text(data.get("title"), min_len=4, max_len=120, field="Title")
        existing_media_rows = list_post_media_rows(conn, [post_id]).get(post_id, [])
        existing_media_ids = [item["id"] for item in existing_media_rows]
        should_update_media = "keepMediaIds" in data or "mediaUploads" in data
        keep_media_ids = (
            clean_id_list(
                data.get("keepMediaIds", existing_media_ids),
                field="Media list",
            )
            if should_update_media
            else existing_media_ids
        )
        if any(media_id not in existing_media_ids for media_id in keep_media_ids):
            raise APIError("One of the selected media items no longer exists.")
        new_uploads = normalize_media_uploads(
            data.get("mediaUploads"),
            max_items=max(0, POST_MEDIA_MAX_COUNT - len(keep_media_ids)),
        )
        content = clean_post_content(
            data.get("content", row["content"]),
            has_media=bool(keep_media_ids or new_uploads),
        )
        media_sensitive = bool(data.get("mediaSensitive", row["media_sensitive"]))
        enforce_low_trust_content_limits(viewer, content)
        now = utc_iso()
        media_summary = [
            {
                "alt": item["alt_text"] or "Forum image",
                "mimeType": item["mime_type"],
            }
            for item in existing_media_rows
        ]
        conn.execute(
            """
            INSERT INTO post_edits (
                post_id, editor_id, previous_content, previous_title,
                media_summary_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                post_id,
                viewer["id"],
                row["content"],
                row["thread_title"] if row["id"] == thread_first_post_id(conn, row["thread_id"]) else "",
                json.dumps(media_summary),
                now,
            ),
        )
        conn.execute(
            "UPDATE posts SET content = ?, media_sensitive = ?, updated_at = ?, edited_at = ? WHERE id = ?",
            (content, int(media_sensitive), now, now, post_id),
        )
        removed_media_paths: list[str] = []
        if should_update_media:
            keep_media_set = set(keep_media_ids)
            removed_media = [
                item for item in existing_media_rows if item["id"] not in keep_media_set
            ]
            if removed_media:
                removed_media_paths = [
                    path
                    for item in removed_media
                    for path in (item["storage_path"], item["thumbnail_path"])
                    if path
                ]
            ensure_user_media_quota(
                conn,
                viewer["id"],
                new_uploads,
                replacing_paths=removed_media_paths,
            )
            if removed_media:
                conn.execute(
                    f"DELETE FROM post_media WHERE id IN ({', '.join('?' for _ in removed_media)})",
                    tuple(item["id"] for item in removed_media),
                )
            for sort_order, media_id in enumerate(keep_media_ids):
                conn.execute(
                    "UPDATE post_media SET sort_order = ? WHERE id = ?",
                    (sort_order, media_id),
                )
            save_post_media_entries(
                conn,
                post_id=post_id,
                uploads=new_uploads,
                created_at=now,
                start_order=len(keep_media_ids),
            )
        if next_thread_title:
            conn.execute(
                "UPDATE threads SET title = ?, updated_at = ?, edited_at = ? WHERE id = ?",
                (
                    next_thread_title,
                    now,
                    now,
                    row["thread_id"],
                ),
            )
        conn.execute("UPDATE threads SET updated_at = ? WHERE id = ?", (now, row["thread_id"]))
        update_thread_search_index(conn, row["thread_id"])
        update_post_search_index(conn, post_id)
        if is_staff(viewer) and viewer["id"] != row["author_id"]:
            log_audit_event(
                conn,
                actor=viewer,
                action_type="post_edit",
                category="content",
                target_type="post",
                target_id=post_id,
                target_label=f"post #{post_id}",
                reason="Staff edited another user's post.",
                metadata={
                    "threadId": row["thread_id"],
                    "authorId": row["author_id"],
                    "removedMedia": len(removed_media_paths),
                    "addedMedia": len(new_uploads),
                },
                created_at=now,
            )
        conn.commit()
        for storage_path in removed_media_paths:
            delete_media_file(storage_path)
        posts, _ = get_posts_for_thread(conn, row["thread_id"], viewer)
        post = next((item for item in posts if item["id"] == post_id), None)
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "post": post,
            "thread": serialize_thread(get_thread_by_id(conn, row["thread_id"]), conn, viewer),
        }

    def api_delete_post(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        post_id: int,
    ) -> dict[str, Any]:
        ensure_can_post_content(viewer)
        row = conn.execute(
            "SELECT * FROM posts WHERE id = ?",
            (post_id,),
        ).fetchone()
        if not row:
            raise APIError("Post not found.", HTTPStatus.NOT_FOUND)
        if row["deleted_at"]:
            raise APIError("This reply is already deleted.")
        first_post_id = thread_first_post_id(conn, row["thread_id"])
        if row["id"] == first_post_id:
            raise APIError("Delete the thread instead of its first post.")
        if not (viewer["id"] == row["author_id"] or is_staff(viewer)):
            raise APIError("You cannot delete this post.", HTTPStatus.FORBIDDEN)
        now = utc_iso()
        soft_delete_post(conn, post_id=post_id, actor_id=viewer["id"], deleted_at=now)
        conn.execute(
            "UPDATE threads SET answer_post_id = NULL, solved = 0 WHERE id = ? AND answer_post_id = ?",
            (row["thread_id"], post_id),
        )
        conn.execute("UPDATE threads SET updated_at = ? WHERE id = ?", (now, row["thread_id"]))
        update_thread_search_index(conn, row["thread_id"])
        if is_staff(viewer) or viewer["id"] != row["author_id"]:
            log_audit_event(
                conn,
                actor=viewer,
                action_type="post_delete",
                category="content",
                target_type="post",
                target_id=post_id,
                target_label=f"post #{post_id}",
                reason="Post soft-deleted.",
                metadata={"threadId": row["thread_id"]},
                created_at=now,
            )
        conn.commit()
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "deleted": True,
            "softDeleted": True,
            "thread": serialize_thread(get_thread_by_id(conn, row["thread_id"]), conn, viewer),
        }

    def api_post_history(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        post_id: int,
    ) -> dict[str, Any]:
        row = conn.execute(
            """
            SELECT
                p.id,
                p.thread_id,
                s.required_role AS section_required_role
            FROM posts p
            JOIN threads t ON t.id = p.thread_id
            JOIN sections s ON s.id = t.section_id
            WHERE p.id = ? AND p.deleted_at IS NULL AND t.deleted_at IS NULL
            """,
            (post_id,),
        ).fetchone()
        if not row:
            raise APIError("Post not found.", HTTPStatus.NOT_FOUND)
        if not has_required_role(viewer, row["section_required_role"]):
            raise APIError("You do not have access to this post history.", HTTPStatus.FORBIDDEN)
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "history": list_post_edit_history(conn, post_id),
        }
