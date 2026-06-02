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


class SectionContentApiMixin:
    def api_create_section(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not viewer or not is_admin(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        data = self.read_json()
        name = clean_text(data.get("name"), min_len=2, max_len=60, field="Section name")
        slug = clean_slug(data.get("slug") or name, field="Section slug", fallback="section")
        category_slug = clean_slug(data.get("categoryId"), field="Category", fallback="category")
        category = get_category_by_slug(conn, category_slug)
        if not category:
            raise APIError("Category not found.", HTTPStatus.NOT_FOUND)
        description = clean_text(
            data.get("description"),
            min_len=4,
            max_len=180,
            field="Description",
        )
        icon = clean_text(data.get("icon", "◈"), min_len=1, max_len=12, field="Icon")
        icon_bg = clean_text(
            data.get("iconBg", "rgba(0,212,255,0.12)"),
            min_len=1,
            max_len=80,
            field="Icon background",
        )
        required_role = clean_role_name(data.get("requiredRole", "new"), field="read access role")
        write_role = clean_role_name(data.get("writeRole", required_role), field="post access role")
        if role_level(write_role) < role_level(required_role):
            raise APIError("Post access cannot be lower than read access.")
        thread_prefixes = normalize_thread_prefixes(data.get("threadPrefixes"))
        thread_template = clean_thread_template(data.get("threadTemplate"))
        thread_state_mode = clean_thread_state_mode(data.get("threadStateMode", "discussion"))
        sort_order = clean_sort_order(
            data.get("sortOrder"),
            default=get_next_section_sort_order(conn, category["id"]),
        )
        try:
            cur = conn.execute(
                """
                INSERT INTO sections (
                    category_id, slug, name, description, icon, icon_bg,
                    required_role, write_role, thread_prefixes_json, thread_template,
                    thread_state_mode, sort_order
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    category["id"],
                    slug,
                    name,
                    description,
                    icon,
                    icon_bg,
                    required_role,
                    write_role,
                    json.dumps(thread_prefixes),
                    thread_template,
                    thread_state_mode,
                    sort_order,
                ),
            )
            log_audit_event(
                conn,
                actor=viewer,
                action_type="section_create",
                category="sections",
                target_type="section",
                target_id=cur.lastrowid,
                target_label=name,
                reason=f"Section created: {name}.",
                metadata={
                    "slug": slug,
                    "category": category["slug"],
                    "requiredRole": required_role,
                    "writeRole": write_role,
                },
            )
            conn.commit()
        except sqlite3.IntegrityError as exc:
            raise APIError("A section with that slug already exists.") from exc

        section = get_section_by_slug(conn, slug)
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "section": serialize_section_summary(
                section,
                viewer=viewer,
                thread_count=0,
                post_count=0,
            ),
        }

    def api_update_section(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        slug: str,
    ) -> dict[str, Any]:
        if not viewer or not is_admin(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        section = get_section_by_slug(conn, slug)
        if not section:
            raise APIError("Section not found.", HTTPStatus.NOT_FOUND)
        data = self.read_json()
        name = clean_text(
            data.get("name", section["name"]),
            min_len=2,
            max_len=60,
            field="Section name",
        )
        next_slug = clean_slug(
            data.get("slug", section["slug"]) or name,
            field="Section slug",
            fallback="section",
        )
        category_slug = clean_slug(
            data.get("categoryId", section["category_slug"]),
            field="Category",
            fallback="category",
        )
        category = get_category_by_slug(conn, category_slug)
        if not category:
            raise APIError("Category not found.", HTTPStatus.NOT_FOUND)
        description = clean_text(
            data.get("description", section["description"]),
            min_len=4,
            max_len=180,
            field="Description",
        )
        icon = clean_text(data.get("icon", section["icon"]), min_len=1, max_len=12, field="Icon")
        icon_bg = clean_text(
            data.get("iconBg", section["icon_bg"]),
            min_len=1,
            max_len=80,
            field="Icon background",
        )
        required_role = clean_role_name(
            data.get("requiredRole", section["required_role"]),
            field="read access role",
        )
        write_role = clean_role_name(
            data.get("writeRole", section["write_role"]),
            field="post access role",
        )
        if role_level(write_role) < role_level(required_role):
            raise APIError("Post access cannot be lower than read access.")
        thread_prefixes = normalize_thread_prefixes(
            data.get("threadPrefixes", json.loads(section["thread_prefixes_json"] or "[]"))
        )
        thread_template = clean_thread_template(
            data.get("threadTemplate", section["thread_template"])
        )
        thread_state_mode = clean_thread_state_mode(
            data.get("threadStateMode", section["thread_state_mode"])
        )
        sort_order = clean_sort_order(
            data.get("sortOrder", section["sort_order"]),
            default=section["sort_order"],
        )
        try:
            conn.execute(
                """
                UPDATE sections
                SET category_id = ?, slug = ?, name = ?, description = ?, icon = ?, icon_bg = ?,
                    required_role = ?, write_role = ?, thread_prefixes_json = ?, thread_template = ?,
                    thread_state_mode = ?, sort_order = ?
                WHERE id = ?
                """,
                (
                    category["id"],
                    next_slug,
                    name,
                    description,
                    icon,
                    icon_bg,
                    required_role,
                    write_role,
                    json.dumps(thread_prefixes),
                    thread_template,
                    thread_state_mode,
                    sort_order,
                    section["id"],
                ),
            )
            log_audit_event(
                conn,
                actor=viewer,
                action_type="section_update",
                category="sections",
                target_type="section",
                target_id=section["id"],
                target_label=name,
                reason=f"Section updated: {section['name']} -> {name}.",
                metadata={
                    "fromSlug": section["slug"],
                    "toSlug": next_slug,
                    "fromName": section["name"],
                    "toName": name,
                    "fromRequiredRole": section["required_role"],
                    "toRequiredRole": required_role,
                    "fromWriteRole": section["write_role"],
                    "toWriteRole": write_role,
                },
            )
            conn.commit()
        except sqlite3.IntegrityError as exc:
            raise APIError("A section with that slug already exists.") from exc

        updated = get_section_by_slug(conn, next_slug)
        counts = conn.execute(
            """
            SELECT
                COUNT(DISTINCT t.id) AS thread_count,
                COUNT(p.id) AS post_count
            FROM threads t
            LEFT JOIN posts p ON p.thread_id = t.id
            WHERE t.section_id = ? AND t.deleted_at IS NULL AND (p.deleted_at IS NULL OR p.id IS NULL)
            """,
            (updated["id"],),
        ).fetchone()
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "section": serialize_section_summary(
                updated,
                viewer=viewer,
                thread_count=counts["thread_count"],
                post_count=counts["post_count"],
            ),
            "previousId": slug,
        }

    def api_delete_section(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        slug: str,
    ) -> dict[str, Any]:
        if not viewer or not is_admin(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        section = get_section_by_slug(conn, slug)
        if not section:
            raise APIError("Section not found.", HTTPStatus.NOT_FOUND)
        thread_ids = [
            row["id"]
            for row in conn.execute(
                "SELECT id FROM threads WHERE section_id = ?",
                (section["id"],),
            ).fetchall()
        ]
        if thread_ids:
            post_ids = [
                row["id"]
                for row in conn.execute(
                    f"SELECT id FROM posts WHERE thread_id IN ({', '.join('?' for _ in thread_ids)})",
                    tuple(thread_ids),
                ).fetchall()
            ]
            media_paths = collect_post_media_paths(conn, post_ids)
            delete_post_artifact_rows(conn, post_ids)
            placeholders = ", ".join("?" for _ in thread_ids)
            conn.execute(
                f"DELETE FROM posts WHERE thread_id IN ({placeholders})",
                tuple(thread_ids),
            )
            conn.execute(
                f"DELETE FROM thread_bookmarks WHERE thread_id IN ({placeholders})",
                tuple(thread_ids),
            )
            conn.execute(
                f"DELETE FROM thread_subscriptions WHERE thread_id IN ({placeholders})",
                tuple(thread_ids),
            )
            conn.execute(
                f"DELETE FROM thread_polls WHERE thread_id IN ({placeholders})",
                tuple(thread_ids),
            )
        conn.execute("DELETE FROM threads WHERE section_id = ?", (section["id"],))
        conn.execute("DELETE FROM sections WHERE id = ?", (section["id"],))
        log_audit_event(
            conn,
            actor=viewer,
            action_type="section_delete",
            category="sections",
            target_type="section",
            target_id=section["id"],
            target_label=section["name"],
            reason=f"Section deleted: {section['name']}.",
            metadata={
                "slug": section["slug"],
                "threadCount": len(thread_ids),
            },
        )
        conn.commit()
        if thread_ids:
            for post_id in post_ids:
                remove_search_index_entry(conn, kind="post", source_id=post_id)
            for thread_id in thread_ids:
                remove_search_index_entry(conn, kind="thread", source_id=thread_id)
            for storage_path in media_paths:
                delete_media_file(storage_path)
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "deleted": True,
            "sectionId": slug,
        }

    def api_section(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        slug: str,
        query: dict[str, list[str]],
    ) -> dict[str, Any]:
        section = get_section_by_slug(conn, slug)
        if not section:
            raise APIError("Section not found.", HTTPStatus.NOT_FOUND)
        if not has_required_role(viewer, section["required_role"]):
            raise APIError("You do not have access to this section.", HTTPStatus.FORBIDDEN)
        search = (query.get("q") or [""])[0].strip()
        sort = (query.get("sort") or ["latest"])[0].strip().lower()
        if sort not in {"latest", "replies", "hot", "pinned"}:
            sort = "latest"
        page, page_size, last_page = parse_pagination_query(
            query,
            default_page_size=DEFAULT_PAGE_SIZE,
        )
        threads, pagination = list_threads_for_section(
            conn,
            section,
            viewer,
            search=search,
            sort=sort,
            page=page,
            page_size=page_size,
            last_page=last_page,
        )
        counts = conn.execute(
            """
            SELECT
                COUNT(DISTINCT t.id) AS thread_count,
                COUNT(p.id) AS post_count
            FROM threads t
            LEFT JOIN posts p ON p.thread_id = t.id
            WHERE t.section_id = ? AND t.deleted_at IS NULL AND (p.deleted_at IS NULL OR p.id IS NULL)
            """,
            (section["id"],),
        ).fetchone()
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "topMembers": get_top_members(conn),
            "section": serialize_section_summary(
                section,
                viewer=viewer,
                thread_count=counts["thread_count"],
                post_count=counts["post_count"],
                category_slug=section["category_slug"],
                category_label=section["category_label"],
            ),
            "threads": threads,
            "filters": {
                "q": search,
                "sort": sort,
            },
            "pagination": pagination,
        }
