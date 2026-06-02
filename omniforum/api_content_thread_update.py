"""Focused thread content API handlers for update operations."""

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


class UpdateThreadContentApiMixin:
    def api_update_thread(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        thread_id: int,
    ) -> dict[str, Any]:
        ensure_can_post_content(viewer)
        thread = get_thread_by_id(conn, thread_id)
        if not thread:
            raise APIError("Thread not found.", HTTPStatus.NOT_FOUND)
        if not (viewer["id"] == thread["author_id"] or is_staff(viewer)):
            raise APIError("You cannot edit this thread.", HTTPStatus.FORBIDDEN)
        data = self.read_json()
        merge_to_thread_id = None
        if data.get("mergeToThreadId") not in {None, "", 0}:
            if not is_staff(viewer):
                raise APIError("Only staff can merge threads.", HTTPStatus.FORBIDDEN)
            try:
                merge_to_thread_id = int(data.get("mergeToThreadId"))
            except (TypeError, ValueError) as exc:
                raise APIError("Choose a valid destination thread.") from exc
            if merge_to_thread_id == thread_id:
                raise APIError("Pick a different destination thread.")
        if merge_to_thread_id:
            destination = get_thread_by_id(conn, merge_to_thread_id)
            if not destination:
                raise APIError("Destination thread not found.", HTTPStatus.NOT_FOUND)
            source_poll = conn.execute(
                "SELECT id FROM thread_polls WHERE thread_id = ?",
                (thread_id,),
            ).fetchone()
            destination_poll = conn.execute(
                "SELECT id FROM thread_polls WHERE thread_id = ?",
                (merge_to_thread_id,),
            ).fetchone()
            if source_poll or destination_poll:
                raise APIError("Threads with polls cannot be merged right now.")
            now = utc_iso()
            conn.execute(
                "UPDATE posts SET thread_id = ? WHERE thread_id = ? AND deleted_at IS NULL",
                (merge_to_thread_id, thread_id),
            )
            conn.execute(
                """
                    INSERT OR IGNORE INTO thread_bookmarks (thread_id, user_id, created_at)
                    SELECT ?, user_id, created_at
                    FROM thread_bookmarks
                    WHERE thread_id = ?
                    """,
                (merge_to_thread_id, thread_id),
            )
            conn.execute(
                """
                    INSERT OR IGNORE INTO thread_subscriptions (thread_id, user_id, created_at)
                    SELECT ?, user_id, created_at
                    FROM thread_subscriptions
                    WHERE thread_id = ?
                    """,
                (merge_to_thread_id, thread_id),
            )
            conn.execute("DELETE FROM thread_bookmarks WHERE thread_id = ?", (thread_id,))
            conn.execute("DELETE FROM thread_subscriptions WHERE thread_id = ?", (thread_id,))
            moved_post_ids = [
                int(row["id"])
                for row in conn.execute(
                    "SELECT id FROM posts WHERE thread_id = ? AND deleted_at IS NULL",
                    (merge_to_thread_id,),
                ).fetchall()
            ]
            conn.execute(
                "UPDATE threads SET updated_at = ? WHERE id = ?",
                (now, merge_to_thread_id),
            )
            soft_delete_thread(
                conn,
                thread_id=thread_id,
                actor_id=viewer["id"],
                reason=f"Merged into thread {merge_to_thread_id}.",
                deleted_at=now,
            )
            log_audit_event(
                conn,
                actor=viewer,
                action_type="thread_merge",
                category="content",
                target_type="thread",
                target_id=thread_id,
                target_label=thread["title"],
                reason=f"Merged into thread {merge_to_thread_id}.",
                metadata={
                    "sourceThreadId": thread_id,
                    "destinationThreadId": merge_to_thread_id,
                    "destinationTitle": destination["title"],
                },
                created_at=now,
            )
            update_thread_search_index(conn, merge_to_thread_id)
            for moved_post_id in moved_post_ids:
                update_post_search_index(conn, moved_post_id)
            conn.commit()
            return {
                "currentUser": get_current_user_payload(conn, viewer),
                "merged": True,
                "thread": serialize_thread(get_thread_by_id(conn, merge_to_thread_id), conn, viewer),
            }
        title = clean_text(
            data.get("title", thread["title"]),
            min_len=4,
            max_len=120,
            field="Title",
        )
        allowed_prefixes = json.loads(thread["section_thread_prefixes_json"] or "[]")
        prefix = clean_thread_prefix(data.get("prefix", thread["prefix"]), allowed_prefixes)
        tags = normalize_tags(data.get("tags", json.loads(thread["tags_json"] or "[]")))
        pinned = bool(data.get("pinned", thread["pinned"]))
        locked = bool(data.get("locked", thread["locked"]))
        featured = bool(data.get("featured", thread["featured"]))
        solved = bool(data.get("solved", thread["solved"]))
        answer_post_id = thread["answer_post_id"]
        if "answerPostId" in data:
            if not (viewer["id"] == thread["author_id"] or is_staff(viewer)):
                raise APIError("Only the thread author or staff can pick an accepted answer.", HTTPStatus.FORBIDDEN)
            if data.get("answerPostId") in {None, "", 0}:
                answer_post_id = None
            else:
                try:
                    answer_post_id = int(data.get("answerPostId"))
                except (TypeError, ValueError) as exc:
                    raise APIError("Choose a valid reply as the answer.") from exc
                answer_row = conn.execute(
                    "SELECT id FROM posts WHERE id = ? AND thread_id = ? AND deleted_at IS NULL",
                    (answer_post_id, thread_id),
                ).fetchone()
                if not answer_row:
                    raise APIError("That answer must be a post inside this thread.")
        if answer_post_id is None and "answerPostId" in data and "solved" not in data:
            solved = False
        next_section_id = thread["section_id"]
        if data.get("sectionId") not in {None, "", thread["section_slug"]}:
            if not is_staff(viewer):
                raise APIError("Only staff can move threads between sections.", HTTPStatus.FORBIDDEN)
            target_section = get_section_by_slug(conn, str(data.get("sectionId")))
            if not target_section:
                raise APIError("Destination section not found.", HTTPStatus.NOT_FOUND)
            next_section_id = target_section["id"]
        if not is_staff(viewer):
            pinned = bool(thread["pinned"])
            locked = bool(thread["locked"])
            featured = bool(thread["featured"])
        staff_note = ""
        if is_staff(viewer) and "staffNote" in data:
            staff_note = clean_text(
                data.get("staffNote"),
                min_len=0,
                max_len=1200,
                field="Staff note",
            )
        now = utc_iso()
        conn.execute(
            """
                UPDATE threads
                SET section_id = ?, title = ?, prefix = ?, tags_json = ?, pinned = ?, locked = ?, featured = ?,
                    solved = ?, answer_post_id = ?, edited_at = ?, updated_at = ?
                WHERE id = ?
                """,
            (
                next_section_id,
                title,
                prefix,
                json.dumps(tags),
                int(pinned),
                int(locked),
                int(featured),
                int(solved),
                answer_post_id,
                now,
                now,
                thread_id,
            ),
        )
        if "pollClosed" in data:
            conn.execute(
                "UPDATE thread_polls SET is_closed = ?, updated_at = ? WHERE thread_id = ?",
                (int(bool(data.get("pollClosed"))), now, thread_id),
            )
        if is_staff(viewer):
            moderation_changes = {
                "fromSectionId": thread["section_id"],
                "toSectionId": next_section_id,
                "fromPinned": bool(thread["pinned"]),
                "toPinned": pinned,
                "fromLocked": bool(thread["locked"]),
                "toLocked": locked,
                "fromFeatured": bool(thread["featured"]),
                "toFeatured": featured,
                "fromSolved": bool(thread["solved"]),
                "toSolved": solved,
                "fromTitle": thread["title"],
                "toTitle": title,
            }
            if (
                next_section_id != thread["section_id"]
                or pinned != bool(thread["pinned"])
                or locked != bool(thread["locked"])
                or featured != bool(thread["featured"])
                or solved != bool(thread["solved"])
                or title != thread["title"]
                or "pollClosed" in data
            ):
                log_audit_event(
                    conn,
                    actor=viewer,
                    action_type="thread_update",
                    category="content",
                    target_type="thread",
                    target_id=thread_id,
                    target_label=title,
                    reason=f"Thread updated: {thread['title']}.",
                    metadata=moderation_changes,
                    created_at=now,
                )
        if staff_note:
            note_id = add_thread_note(
                conn,
                thread_id=thread_id,
                author_id=viewer["id"],
                note=staff_note,
                created_at=now,
            )
            log_audit_event(
                conn,
                actor=viewer,
                action_type="thread_note_create",
                category="content",
                target_type="thread",
                target_id=thread_id,
                target_label=title,
                reason=short_preview(staff_note, max_len=160),
                metadata={"noteId": note_id},
                created_at=now,
            )
        update_thread_search_index(conn, thread_id)
        conn.commit()
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "thread": serialize_thread(get_thread_by_id(conn, thread_id), conn, viewer),
        }
