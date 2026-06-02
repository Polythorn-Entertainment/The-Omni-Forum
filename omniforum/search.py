"""Search indexing and analytics helpers."""

from __future__ import annotations

import json
import re
import sqlite3
from typing import Any

from .core import utc_iso
from .runtime_logging import append_server_log
from .schema import ensure_search_index_schema


def thread_has_media(conn: sqlite3.Connection, thread_id: int) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM post_media pm
        JOIN posts p ON p.id = pm.post_id
        WHERE p.thread_id = ? AND p.deleted_at IS NULL
        LIMIT 1
        """,
        (thread_id,),
    ).fetchone()
    return bool(row)


def fts_query(value: str) -> str:
    terms = re.findall(r"[A-Za-z0-9_]{2,}", str(value or "").lower())
    return " ".join(f"{term}*" for term in terms[:8])


def refresh_search_index(conn: sqlite3.Connection) -> bool:
    try:
        counts = {
            "threads": conn.execute(
                "SELECT COUNT(*) AS count FROM threads WHERE deleted_at IS NULL"
            ).fetchone()["count"],
            "posts": conn.execute(
                "SELECT COUNT(*) AS count FROM posts WHERE deleted_at IS NULL"
            ).fetchone()["count"],
        }
        meta = conn.execute("SELECT * FROM search_index_meta WHERE id = 1").fetchone()
        if (
            meta
            and int(meta["thread_count"] or 0) == int(counts["threads"])
            and int(meta["post_count"] or 0) == int(counts["posts"])
        ):
            return True
        conn.execute("DELETE FROM search_fts")
        thread_rows = conn.execute(
            """
            SELECT
                t.id,
                t.title,
                t.tags_json,
                t.created_at,
                t.updated_at,
                s.slug AS section_slug,
                u.username AS author_username,
                COALESCE(fp.content, '') AS first_post_content
            FROM threads t
            JOIN sections s ON s.id = t.section_id
            JOIN users u ON u.id = t.author_id
            LEFT JOIN posts fp ON fp.id = (
                SELECT p.id
                FROM posts p
                WHERE p.thread_id = t.id AND p.deleted_at IS NULL
                ORDER BY p.created_at ASC, p.id ASC
                LIMIT 1
            )
            WHERE t.deleted_at IS NULL
            """
        ).fetchall()
        post_rows = conn.execute(
            """
            SELECT
                p.id,
                p.content,
                p.created_at,
                p.updated_at,
                t.title,
                t.tags_json,
                s.slug AS section_slug,
                u.username AS author_username
            FROM posts p
            JOIN threads t ON t.id = p.thread_id
            JOIN sections s ON s.id = t.section_id
            JOIN users u ON u.id = p.author_id
            WHERE p.deleted_at IS NULL AND t.deleted_at IS NULL
            """
        ).fetchall()
        conn.executemany(
            """
            INSERT INTO search_fts (
                kind, source_id, section_slug, author_username, created_at, updated_at,
                title, content, tags
            )
            VALUES ('thread', ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row["id"],
                    row["section_slug"],
                    row["author_username"],
                    row["created_at"],
                    row["updated_at"],
                    row["title"],
                    row["first_post_content"] or "",
                    " ".join(json.loads(row["tags_json"] or "[]")),
                )
                for row in thread_rows
            ],
        )
        conn.executemany(
            """
            INSERT INTO search_fts (
                kind, source_id, section_slug, author_username, created_at, updated_at,
                title, content, tags
            )
            VALUES ('post', ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row["id"],
                    row["section_slug"],
                    row["author_username"],
                    row["created_at"],
                    row["updated_at"],
                    row["title"],
                    row["content"],
                    " ".join(json.loads(row["tags_json"] or "[]")),
                )
                for row in post_rows
            ],
        )
        conn.execute(
            """
            INSERT INTO search_index_meta (id, thread_count, post_count, updated_at)
            VALUES (1, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                thread_count = excluded.thread_count,
                post_count = excluded.post_count,
                updated_at = excluded.updated_at
            """,
            (counts["threads"], counts["posts"], utc_iso()),
        )
        return True
    except (sqlite3.OperationalError, sqlite3.DatabaseError, json.JSONDecodeError) as exc:
        append_server_log(f"fts refresh failed: {exc}")
        return False


def search_index_tags(value: Any) -> str:
    try:
        tags = json.loads(value or "[]")
    except json.JSONDecodeError:
        tags = []
    return " ".join(str(tag).strip() for tag in tags if str(tag).strip())


def remove_search_index_entry(conn: sqlite3.Connection, *, kind: str, source_id: int) -> None:
    try:
        conn.execute("DELETE FROM search_fts WHERE kind = ? AND source_id = ?", (kind, source_id))
    except sqlite3.OperationalError:
        return


def update_thread_search_index(conn: sqlite3.Connection, thread_id: int) -> None:
    if not ensure_search_index_schema(conn):
        return
    remove_search_index_entry(conn, kind="thread", source_id=thread_id)
    row = conn.execute(
        """
        SELECT
            t.id,
            t.title,
            t.tags_json,
            t.created_at,
            t.updated_at,
            s.slug AS section_slug,
            u.username AS author_username,
            COALESCE(fp.content, '') AS first_post_content
        FROM threads t
        JOIN sections s ON s.id = t.section_id
        JOIN users u ON u.id = t.author_id
        LEFT JOIN posts fp ON fp.id = (
            SELECT p.id
            FROM posts p
            WHERE p.thread_id = t.id AND p.deleted_at IS NULL
            ORDER BY p.created_at ASC, p.id ASC
            LIMIT 1
        )
        WHERE t.id = ? AND t.deleted_at IS NULL
        """,
        (thread_id,),
    ).fetchone()
    if not row:
        return
    conn.execute(
        """
        INSERT INTO search_fts (
            kind, source_id, section_slug, author_username, created_at, updated_at,
            title, content, tags
        )
        VALUES ('thread', ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row["id"],
            row["section_slug"],
            row["author_username"],
            row["created_at"],
            row["updated_at"],
            row["title"],
            row["first_post_content"] or "",
            search_index_tags(row["tags_json"]),
        ),
    )


def update_post_search_index(conn: sqlite3.Connection, post_id: int) -> None:
    if not ensure_search_index_schema(conn):
        return
    remove_search_index_entry(conn, kind="post", source_id=post_id)
    row = conn.execute(
        """
        SELECT
            p.id,
            p.content,
            p.created_at,
            p.updated_at,
            t.title,
            t.tags_json,
            s.slug AS section_slug,
            u.username AS author_username
        FROM posts p
        JOIN threads t ON t.id = p.thread_id
        JOIN sections s ON s.id = t.section_id
        JOIN users u ON u.id = p.author_id
        WHERE p.id = ? AND p.deleted_at IS NULL AND t.deleted_at IS NULL
        """,
        (post_id,),
    ).fetchone()
    if not row:
        return
    conn.execute(
        """
        INSERT INTO search_fts (
            kind, source_id, section_slug, author_username, created_at, updated_at,
            title, content, tags
        )
        VALUES ('post', ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row["id"],
            row["section_slug"],
            row["author_username"],
            row["created_at"],
            row["updated_at"],
            row["title"],
            row["content"],
            search_index_tags(row["tags_json"]),
        ),
    )


def log_search_event(
    conn: sqlite3.Connection,
    *,
    viewer: dict[str, Any] | None,
    query: str,
    filters: dict[str, Any],
    result_count: int,
) -> None:
    normalized = " ".join(str(query or "").lower().split())[:160]
    if len(normalized) < 2 and not any(value for key, value in filters.items() if key != "sort"):
        return
    conn.execute(
        """
        INSERT INTO search_events (user_id, query, filters_json, result_count, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            viewer["id"] if viewer else None,
            normalized or "(filtered browse)",
            json.dumps(filters),
            int(result_count),
            utc_iso(),
        ),
    )
