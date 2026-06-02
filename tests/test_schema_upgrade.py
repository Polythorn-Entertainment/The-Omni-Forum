from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path


SCHEMAS = (
    "users_db",
    "sessions_db",
    "sections_db",
    "threads_db",
    "posts_db",
    "messages_db",
    "notifications_db",
    "reports_db",
    "contact_db",
    "audit_db",
)


def table_columns(conn: sqlite3.Connection, schema: str, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA {schema}.table_info({table})").fetchall()}


class SchemaUpgradeTests(unittest.TestCase):
    def test_schema_repair_upgrades_minimal_existing_tables(self) -> None:
        from omniforum.schema_maintenance import ensure_database_schema

        with tempfile.TemporaryDirectory(prefix="omniforum-schema-upgrade-") as temp_dir:
            conn = sqlite3.connect(":memory:")
            conn.row_factory = sqlite3.Row
            for schema in SCHEMAS:
                conn.execute("ATTACH DATABASE ? AS " + schema, (str(Path(temp_dir) / f"{schema}.db"),))
            conn.executescript(
                """
                CREATE TABLE users_db.users (
                    id INTEGER PRIMARY KEY,
                    username TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL,
                    bio TEXT NOT NULL DEFAULT '',
                    xp INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE sessions_db.sessions (
                    token TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                );
                CREATE TABLE threads_db.threads (
                    id INTEGER PRIMARY KEY,
                    section_id INTEGER NOT NULL,
                    author_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    view_count INTEGER NOT NULL DEFAULT 0,
                    pinned INTEGER NOT NULL DEFAULT 0,
                    locked INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE posts_db.posts (
                    id INTEGER PRIMARY KEY,
                    thread_id INTEGER NOT NULL,
                    author_id INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    edited_at TEXT
                );
                CREATE TABLE posts_db.post_media (
                    id INTEGER PRIMARY KEY,
                    post_id INTEGER NOT NULL,
                    storage_path TEXT NOT NULL,
                    mime_type TEXT NOT NULL,
                    alt_text TEXT NOT NULL DEFAULT '',
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE sections_db.sections (
                    id INTEGER PRIMARY KEY,
                    category_id INTEGER NOT NULL,
                    slug TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    icon TEXT NOT NULL,
                    icon_bg TEXT NOT NULL,
                    required_role TEXT NOT NULL DEFAULT 'new',
                    write_role TEXT NOT NULL DEFAULT 'new',
                    sort_order INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE reports_db.reports (
                    id INTEGER PRIMARY KEY,
                    reporter_id INTEGER NOT NULL,
                    target_type TEXT NOT NULL,
                    target_id INTEGER NOT NULL,
                    target_label TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'open',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE contact_db.contact_submissions (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    message TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'open',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )

            ensure_database_schema(conn)

            self.assertIn("email", table_columns(conn, "users_db", "users"))
            self.assertIn("email_verified_at", table_columns(conn, "users_db", "users"))
            self.assertIn("shadow_muted", table_columns(conn, "users_db", "users"))
            self.assertIn("csrf_token", table_columns(conn, "sessions_db", "sessions"))
            self.assertIn("featured", table_columns(conn, "threads_db", "threads"))
            self.assertIn("shadow_hidden", table_columns(conn, "posts_db", "posts"))
            self.assertIn("thumbnail_path", table_columns(conn, "posts_db", "post_media"))
            self.assertIn("thread_state_mode", table_columns(conn, "sections_db", "sections"))
            self.assertIn("sla_due_at", table_columns(conn, "reports_db", "reports"))
            self.assertIn("discord_username", table_columns(conn, "contact_db", "contact_submissions"))
            self.assertTrue(table_columns(conn, "audit_db", "rate_limit_events"))
            self.assertTrue(table_columns(conn, "users_db", "email_auth_tokens"))


if __name__ == "__main__":
    unittest.main()
