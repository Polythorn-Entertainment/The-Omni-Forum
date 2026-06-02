"""Forum category and section domain helpers."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from .core import has_required_role, is_admin, is_staff
from .content_state import is_shadow_hidden_to_viewer


def serialize_section_summary(
    section: sqlite3.Row | dict[str, Any],
    *,
    viewer: dict[str, Any] | None,
    thread_count: int,
    post_count: int,
    last_thread: sqlite3.Row | None = None,
    category_slug: str | None = None,
    category_label: str | None = None,
) -> dict[str, Any]:
    row = dict(section)
    required_role = row["required_role"]
    return {
        "id": row["slug"],
        "name": row["name"],
        "desc": row["description"],
        "icon": row["icon"],
        "iconBg": row["icon_bg"],
        "requiredRole": required_role,
        "writeRole": row["write_role"],
        "threadPrefixes": json.loads(row.get("thread_prefixes_json") or "[]"),
        "threadTemplate": row.get("thread_template") or "",
        "threadStateMode": row.get("thread_state_mode") or "discussion",
        "categoryId": category_slug or row.get("category_slug"),
        "categoryLabel": category_label or row.get("category_label"),
        "sortOrder": row["sort_order"],
        "threads": thread_count,
        "posts": post_count,
        "lastThread": (
            {
                "id": last_thread["id"],
                "title": last_thread["title"],
                "by": last_thread["username"],
                "updatedAt": last_thread["updated_at"],
            }
            if last_thread
            else None
        ),
        "canView": has_required_role(viewer, required_role),
        "canManage": is_admin(viewer),
    }


def get_category_by_slug(conn: sqlite3.Connection, slug: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM categories WHERE slug = ?", (slug,)).fetchone()


def get_next_section_sort_order(conn: sqlite3.Connection, category_id: int) -> int:
    row = conn.execute(
        "SELECT COALESCE(MAX(sort_order) + 1, 0) AS next_sort_order FROM sections WHERE category_id = ?",
        (category_id,),
    ).fetchone()
    return row["next_sort_order"]


def get_sections_with_stats(conn: sqlite3.Connection, viewer: dict[str, Any] | None) -> list[dict[str, Any]]:
    from .domain_users import is_ignored_author

    categories = conn.execute("SELECT * FROM categories ORDER BY sort_order ASC, id ASC").fetchall()
    output: list[dict[str, Any]] = []
    for category in categories:
        sections = conn.execute(
            """
            SELECT * FROM sections
            WHERE category_id = ?
            ORDER BY sort_order ASC, id ASC
            """,
            (category["id"],),
        ).fetchall()
        section_payload = []
        for section in sections:
            if not has_required_role(viewer, section["required_role"]):
                continue
            visible_clause = " AND t.deleted_at IS NULL AND (p.deleted_at IS NULL OR p.id IS NULL)"
            if not is_staff(viewer):
                visible_clause += " AND COALESCE(t.shadow_hidden, 0) = 0"
            counts = conn.execute(
                f"""
                SELECT
                    COUNT(DISTINCT t.id) AS thread_count,
                    COUNT(p.id) AS post_count
                FROM sections s
                LEFT JOIN threads t ON t.section_id = s.id
                LEFT JOIN posts p ON p.thread_id = t.id
                WHERE s.id = ?{visible_clause}
                """,
                (section["id"],),
            ).fetchone()
            last_thread = conn.execute(
                f"""
                SELECT t.id, t.title, t.updated_at, u.username, t.author_id
                FROM threads t
                JOIN users u ON u.id = t.author_id
                WHERE t.section_id = ?
                  AND t.deleted_at IS NULL
                  {"AND COALESCE(t.shadow_hidden, 0) = 0" if not is_staff(viewer) else ""}
                ORDER BY t.pinned DESC, t.updated_at DESC, t.id DESC
                LIMIT 1
                """,
                (section["id"],),
            ).fetchone()
            if last_thread and is_ignored_author(conn, viewer, last_thread["author_id"]):
                last_thread = None
            section_payload.append(
                serialize_section_summary(
                    section,
                    viewer=viewer,
                    thread_count=counts["thread_count"],
                    post_count=counts["post_count"],
                    last_thread=last_thread,
                    category_slug=category["slug"],
                    category_label=category["label"],
                )
            )
        if not section_payload:
            continue
        output.append(
            {
                "id": category["slug"],
                "label": category["label"],
                "sections": section_payload,
            }
        )
    return output


def get_section_by_slug(conn: sqlite3.Connection, slug: str) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT
            s.*,
            c.slug AS category_slug,
            c.label AS category_label
        FROM sections s
        JOIN categories c ON c.id = s.category_id
        WHERE s.slug = ?
        """,
        (slug,),
    ).fetchone()
