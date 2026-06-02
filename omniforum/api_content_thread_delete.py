"""Focused thread content API handlers for delete operations."""

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


class DeleteThreadContentApiMixin:
    def api_delete_thread(
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
            raise APIError("You cannot delete this thread.", HTTPStatus.FORBIDDEN)
        reason = clean_text("", min_len=0, max_len=300, field="Delete reason")
        soft_delete_thread(
            conn,
            thread_id=thread_id,
            actor_id=viewer["id"],
            reason=reason,
        )
        if is_staff(viewer) or viewer["id"] != thread["author_id"]:
            log_audit_event(
                conn,
                actor=viewer,
                action_type="thread_delete",
                category="content",
                target_type="thread",
                target_id=thread_id,
                target_label=thread["title"],
                reason=reason or "Thread soft-deleted.",
            )
        conn.commit()
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "deleted": True,
            "softDeleted": True,
        }
