"""SQLite full-text search schema helpers."""

from __future__ import annotations

import sqlite3

from .runtime_logging import append_server_log


def ensure_search_index_schema(conn: sqlite3.Connection) -> bool:
    try:
        conn.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS posts_db.search_fts USING fts5(
                kind UNINDEXED,
                source_id UNINDEXED,
                section_slug UNINDEXED,
                author_username UNINDEXED,
                created_at UNINDEXED,
                updated_at UNINDEXED,
                title,
                content,
                tags,
                tokenize='porter unicode61'
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS posts_db.search_index_meta (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                thread_count INTEGER NOT NULL DEFAULT 0,
                post_count INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            )
            """
        )
        return True
    except sqlite3.OperationalError as exc:
        append_server_log(f"fts unavailable: {exc}")
        return False
