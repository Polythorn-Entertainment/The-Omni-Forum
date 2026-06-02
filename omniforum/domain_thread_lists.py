"""Thread listing, related, trending, and featured helpers."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from .config import DEFAULT_PAGE_SIZE
from .content_state import is_shadow_hidden_to_viewer
from .core import has_required_role
from .domain_thread_records import serialize_thread
from .validation import resolve_pagination


def get_related_threads(
    conn: sqlite3.Connection,
    thread_row: sqlite3.Row,
    viewer: dict[str, Any] | None,
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    from .domain_users import is_ignored_author

    current_tags = set(json.loads(thread_row["tags_json"] or "[]"))
    rows = conn.execute(
        """
        SELECT
            t.*,
            s.slug AS section_slug,
            s.name AS section_name,
            s.description AS section_description,
            s.icon AS section_icon,
            s.icon_bg AS section_icon_bg,
            s.required_role AS section_required_role,
            s.write_role AS section_write_role,
            s.thread_prefixes_json AS section_thread_prefixes_json,
            s.thread_template AS section_thread_template,
            s.thread_state_mode AS section_thread_state_mode,
            u.username AS author_name,
            u.role AS author_role,
            u.avatar_path AS author_avatar_path
        FROM threads t
        JOIN sections s ON s.id = t.section_id
        JOIN users u ON u.id = t.author_id
        WHERE t.id != ? AND t.section_id = ? AND t.deleted_at IS NULL
        ORDER BY t.updated_at DESC, t.id DESC
        LIMIT 40
        """,
        (thread_row["id"], thread_row["section_id"]),
    ).fetchall()
    scored: list[tuple[int, sqlite3.Row]] = []
    for row in rows:
        if not has_required_role(viewer, row["section_required_role"]):
            continue
        if is_ignored_author(conn, viewer, row["author_id"]):
            continue
        if is_shadow_hidden_to_viewer(hidden=row["shadow_hidden"], author_id=row["author_id"], viewer=viewer):
            continue
        row_tags = set(json.loads(row["tags_json"] or "[]"))
        score = len(current_tags & row_tags)
        scored.append((score, row))
    scored.sort(key=lambda item: (item[0], item[1]["updated_at"]), reverse=True)
    return [serialize_thread(row, conn, viewer) for _, row in scored[:limit]]


def get_trending_threads(
    conn: sqlite3.Connection,
    viewer: dict[str, Any] | None,
    *,
    limit: int = 6,
) -> list[dict[str, Any]]:
    from .domain_users import is_ignored_author

    rows = conn.execute(
        """
        SELECT
            t.*,
            s.slug AS section_slug,
            s.name AS section_name,
            s.description AS section_description,
            s.icon AS section_icon,
            s.icon_bg AS section_icon_bg,
            s.required_role AS section_required_role,
            s.write_role AS section_write_role,
            s.thread_prefixes_json AS section_thread_prefixes_json,
            s.thread_template AS section_thread_template,
            s.thread_state_mode AS section_thread_state_mode,
            u.username AS author_name,
            u.role AS author_role,
            u.avatar_path AS author_avatar_path
        FROM threads t
        JOIN sections s ON s.id = t.section_id
        JOIN users u ON u.id = t.author_id
        WHERE t.deleted_at IS NULL
        ORDER BY t.pinned DESC, t.view_count DESC, t.updated_at DESC, t.id DESC
        LIMIT 40
        """
    ).fetchall()
    visible_rows = [
        row
        for row in rows
        if has_required_role(viewer, row["section_required_role"])
        and not is_ignored_author(conn, viewer, row["author_id"])
        and not is_shadow_hidden_to_viewer(
            hidden=row["shadow_hidden"],
            author_id=row["author_id"],
            viewer=viewer,
        )
    ]
    return [serialize_thread(row, conn, viewer) for row in visible_rows[:limit]]


def get_featured_threads(
    conn: sqlite3.Connection,
    viewer: dict[str, Any] | None,
    *,
    limit: int = 4,
) -> list[dict[str, Any]]:
    from .domain_users import is_ignored_author

    rows = conn.execute(
        """
        SELECT
            t.*,
            s.slug AS section_slug,
            s.name AS section_name,
            s.description AS section_description,
            s.icon AS section_icon,
            s.icon_bg AS section_icon_bg,
            s.required_role AS section_required_role,
            s.write_role AS section_write_role,
            s.thread_prefixes_json AS section_thread_prefixes_json,
            s.thread_template AS section_thread_template,
            s.thread_state_mode AS section_thread_state_mode,
            u.username AS author_name,
            u.role AS author_role,
            u.avatar_path AS author_avatar_path
        FROM threads t
        JOIN sections s ON s.id = t.section_id
        JOIN users u ON u.id = t.author_id
        WHERE t.deleted_at IS NULL
        ORDER BY
            t.featured DESC,
            t.pinned DESC,
            CASE WHEN EXISTS(SELECT 1 FROM thread_polls tp WHERE tp.thread_id = t.id) THEN 1 ELSE 0 END DESC,
            t.solved DESC,
            t.view_count DESC,
            t.updated_at DESC,
            t.id DESC
        LIMIT 24
        """
    ).fetchall()
    featured: list[dict[str, Any]] = []
    for row in rows:
        if not has_required_role(viewer, row["section_required_role"]):
            continue
        if is_ignored_author(conn, viewer, row["author_id"]):
            continue
        if is_shadow_hidden_to_viewer(hidden=row["shadow_hidden"], author_id=row["author_id"], viewer=viewer):
            continue
        featured.append(serialize_thread(row, conn, viewer))
        if len(featured) >= limit:
            break
    return featured


def list_threads_for_section(
    conn: sqlite3.Connection,
    section: sqlite3.Row,
    viewer: dict[str, Any] | None,
    *,
    search: str = "",
    sort: str = "latest",
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    last_page: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, int | bool]]:
    from .domain_users import viewer_ignored_user_ids

    ignored_ids = viewer_ignored_user_ids(conn, viewer)
    params: list[Any] = [section["id"]]
    where = ["t.section_id = ?", "t.deleted_at IS NULL"]
    if ignored_ids:
        placeholders = ", ".join("?" for _ in ignored_ids)
        where.append(f"t.author_id NOT IN ({placeholders})")
        params.extend(sorted(ignored_ids))
    rows = conn.execute(
        f"""
        SELECT
            t.*,
            s.slug AS section_slug,
            s.name AS section_name,
            s.description AS section_description,
            s.icon AS section_icon,
            s.icon_bg AS section_icon_bg,
            s.required_role AS section_required_role,
            s.write_role AS section_write_role,
            s.thread_prefixes_json AS section_thread_prefixes_json,
            s.thread_template AS section_thread_template,
            s.thread_state_mode AS section_thread_state_mode,
            u.username AS author_name,
            u.role AS author_role,
            u.avatar_path AS author_avatar_path
        FROM threads t
        JOIN sections s ON s.id = t.section_id
        JOIN users u ON u.id = t.author_id
        WHERE {" AND ".join(where)}
        ORDER BY t.pinned DESC, t.updated_at DESC, t.id DESC
        """,
        tuple(params),
    ).fetchall()
    normalized_search = search.strip().lower()
    if normalized_search:
        rows = [
            row
            for row in rows
            if normalized_search in row["title"].lower()
            or normalized_search in (row["prefix"] or "").lower()
            or normalized_search in (row["tags_json"] or "").lower()
        ]
    rows = [
        row
        for row in rows
        if not is_shadow_hidden_to_viewer(
            hidden=row["shadow_hidden"],
            author_id=row["author_id"],
            viewer=viewer,
        )
    ]
    items = [serialize_thread(row, conn, viewer) for row in rows]
    if sort == "replies":
        items.sort(key=lambda item: (item["replies"], item["updatedAt"]), reverse=True)
    elif sort == "hot":
        items.sort(key=lambda item: (item["hot"], item["replies"], item["updatedAt"]), reverse=True)
    elif sort == "pinned":
        items.sort(key=lambda item: (item["pinned"], item["updatedAt"]), reverse=True)
    else:
        sort = "latest"
        items.sort(key=lambda item: item["updatedAt"], reverse=True)
    pagination = resolve_pagination(
        len(items),
        page=page,
        page_size=page_size,
        last_page=last_page,
    )
    start = int(pagination["offset"])
    end = start + int(pagination["pageSize"])
    return items[start:end], pagination
