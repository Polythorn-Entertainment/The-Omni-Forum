"""Pragmatic schema repair helpers for existing installs."""

from __future__ import annotations

import sqlite3

from .schema_defaults import (
    ensure_moderation_macro_defaults,
    ensure_registration_defaults,
    ensure_site_settings_defaults,
)


def ensure_column(
    conn: sqlite3.Connection,
    schema: str,
    table: str,
    column_name: str,
    definition: str,
) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA {schema}.table_info({table})").fetchall()}
    if column_name in columns:
        return
    conn.execute(f"ALTER TABLE {schema}.{table} ADD COLUMN {column_name} {definition}")


def ensure_database_schema(conn: sqlite3.Connection) -> None:
    ensure_column(conn, "users_db", "users", "avatar_path", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "users_db", "users", "email", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "users_db", "users", "email_verified_at", "TEXT")
    ensure_column(conn, "users_db", "users", "status_text", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "users_db", "users", "site_theme", "TEXT NOT NULL DEFAULT 'midnight'")
    ensure_column(conn, "users_db", "users", "dm_privacy", "TEXT NOT NULL DEFAULT 'everyone'")
    ensure_column(conn, "users_db", "users", "blur_sensitive_media", "INTEGER NOT NULL DEFAULT 1")
    ensure_column(conn, "users_db", "users", "compact_post_layout", "INTEGER NOT NULL DEFAULT 0")
    ensure_column(conn, "users_db", "users", "hide_ignored_content", "INTEGER NOT NULL DEFAULT 1")
    ensure_column(conn, "users_db", "users", "notify_replies", "INTEGER NOT NULL DEFAULT 1")
    ensure_column(conn, "users_db", "users", "notify_likes", "INTEGER NOT NULL DEFAULT 1")
    ensure_column(conn, "users_db", "users", "notify_mentions", "INTEGER NOT NULL DEFAULT 1")
    ensure_column(conn, "users_db", "users", "notify_dms", "INTEGER NOT NULL DEFAULT 1")
    ensure_column(conn, "users_db", "users", "timeout_until", "TEXT")
    ensure_column(conn, "users_db", "users", "timeout_reason", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "users_db", "users", "timeout_set_by", "INTEGER")
    ensure_column(conn, "users_db", "users", "banned_at", "TEXT")
    ensure_column(conn, "users_db", "users", "ban_reason", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "users_db", "users", "banned_by", "INTEGER")
    ensure_column(conn, "users_db", "users", "password_reset_required", "INTEGER NOT NULL DEFAULT 0")
    ensure_column(conn, "users_db", "users", "password_reset_set_by", "INTEGER")
    ensure_column(conn, "users_db", "users", "password_reset_set_at", "TEXT")
    ensure_column(conn, "users_db", "users", "password_reset_expires_at", "TEXT")
    ensure_column(conn, "users_db", "users", "recovery_discord_username", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "users_db", "users", "recovery_note", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "users_db", "users", "approval_status", "TEXT NOT NULL DEFAULT 'approved'")
    ensure_column(conn, "users_db", "users", "approval_note", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "users_db", "users", "approved_by", "INTEGER")
    ensure_column(conn, "users_db", "users", "approved_at", "TEXT")
    ensure_column(conn, "users_db", "users", "registration_ip", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "users_db", "users", "invite_code_used", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "users_db", "users", "signature", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "users_db", "users", "profile_badge", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "users_db", "users", "profile_accent", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "users_db", "users", "mute_until", "TEXT")
    ensure_column(conn, "users_db", "users", "mute_reason", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "users_db", "users", "mute_set_by", "INTEGER")
    ensure_column(conn, "users_db", "users", "shadow_muted", "INTEGER NOT NULL DEFAULT 0")
    ensure_column(conn, "sessions_db", "sessions", "ip_address", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "sessions_db", "sessions", "user_agent", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "sessions_db", "sessions", "last_seen_at", "TEXT")
    ensure_column(conn, "sessions_db", "sessions", "last_seen_ip", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "sessions_db", "sessions", "csrf_token", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "threads_db", "threads", "solved", "INTEGER NOT NULL DEFAULT 0")
    ensure_column(conn, "threads_db", "threads", "answer_post_id", "INTEGER")
    ensure_column(conn, "threads_db", "threads", "featured", "INTEGER NOT NULL DEFAULT 0")
    ensure_column(conn, "threads_db", "threads", "shadow_hidden", "INTEGER NOT NULL DEFAULT 0")
    ensure_column(conn, "threads_db", "threads", "prefix", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "threads_db", "threads", "deleted_at", "TEXT")
    ensure_column(conn, "threads_db", "threads", "deleted_by", "INTEGER")
    ensure_column(conn, "threads_db", "threads", "delete_reason", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "posts_db", "posts", "shadow_hidden", "INTEGER NOT NULL DEFAULT 0")
    ensure_column(conn, "posts_db", "posts", "media_sensitive", "INTEGER NOT NULL DEFAULT 0")
    ensure_column(conn, "posts_db", "posts", "deleted_at", "TEXT")
    ensure_column(conn, "posts_db", "posts", "deleted_by", "INTEGER")
    ensure_column(conn, "posts_db", "posts", "delete_reason", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "posts_db", "post_media", "width", "INTEGER NOT NULL DEFAULT 0")
    ensure_column(conn, "posts_db", "post_media", "height", "INTEGER NOT NULL DEFAULT 0")
    ensure_column(conn, "posts_db", "post_media", "thumbnail_path", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "sections_db", "sections", "thread_prefixes_json", "TEXT NOT NULL DEFAULT '[]'")
    ensure_column(conn, "sections_db", "sections", "thread_template", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "sections_db", "sections", "thread_state_mode", "TEXT NOT NULL DEFAULT 'discussion'")
    ensure_column(conn, "reports_db", "reports", "triage_priority", "TEXT NOT NULL DEFAULT 'normal'")
    ensure_column(conn, "reports_db", "reports", "triage_category", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "reports_db", "reports", "assigned_to", "INTEGER")
    ensure_column(conn, "reports_db", "reports", "resolution_code", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "reports_db", "reports", "sla_due_at", "TEXT")
    ensure_column(conn, "reports_db", "reports", "escalated_at", "TEXT")
    ensure_column(conn, "reports_db", "reports", "escalation_note", "TEXT NOT NULL DEFAULT ''")
    ensure_column(
        conn,
        "contact_db",
        "contact_submissions",
        "discord_username",
        "TEXT NOT NULL DEFAULT ''",
    )
    conn.executescript(
        """
            CREATE TABLE IF NOT EXISTS users_db.registration_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                public_registration_enabled INTEGER NOT NULL DEFAULT 1,
                invite_required INTEGER NOT NULL DEFAULT 0,
                approval_required INTEGER NOT NULL DEFAULT 0,
                blocked_username_patterns TEXT NOT NULL DEFAULT '',
                updated_by INTEGER,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS users_db.invite_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                note TEXT NOT NULL DEFAULT '',
                max_uses INTEGER NOT NULL DEFAULT 1,
                uses INTEGER NOT NULL DEFAULT 0,
                enabled INTEGER NOT NULL DEFAULT 1,
                expires_at TEXT,
                created_by INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS users_db.site_settings (
                key TEXT PRIMARY KEY,
                value_json TEXT NOT NULL,
                updated_by INTEGER,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS users_db.recovery_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                code_hash TEXT NOT NULL,
                label TEXT NOT NULL DEFAULT '',
                used_at TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS users_db.email_auth_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                purpose TEXT NOT NULL,
                email TEXT NOT NULL DEFAULT '',
                token_hash TEXT NOT NULL,
                used_at TEXT,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS audit_db.audit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor_id INTEGER,
                actor_username TEXT NOT NULL DEFAULT '',
                actor_role TEXT NOT NULL DEFAULT '',
                action_type TEXT NOT NULL,
                category TEXT NOT NULL,
                target_type TEXT NOT NULL DEFAULT '',
                target_id INTEGER,
                target_label TEXT NOT NULL DEFAULT '',
                reason TEXT NOT NULL DEFAULT '',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                ip_address TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS posts_db.post_reactions (
            post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL,
            emoji TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (post_id, user_id, emoji)
        );

        CREATE TABLE IF NOT EXISTS users_db.user_relationships (
            user_id INTEGER NOT NULL,
            target_user_id INTEGER NOT NULL,
            ignore_content INTEGER NOT NULL DEFAULT 0,
            block_dm INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (user_id, target_user_id)
        );

        CREATE TABLE IF NOT EXISTS reports_db.appeals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            target_user_id INTEGER NOT NULL DEFAULT 0,
            action_id INTEGER,
            message TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            staff_note TEXT NOT NULL DEFAULT '',
            handled_by INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            handled_at TEXT
        );

        CREATE TABLE IF NOT EXISTS reports_db.report_internal_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL,
            author_id INTEGER NOT NULL,
            note TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS reports_db.moderation_macros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT '',
            enabled INTEGER NOT NULL DEFAULT 1,
            created_by INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS threads_db.thread_polls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id INTEGER NOT NULL UNIQUE,
            question TEXT NOT NULL,
            allows_multiple INTEGER NOT NULL DEFAULT 0,
            is_closed INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS threads_db.thread_poll_options (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            poll_id INTEGER NOT NULL REFERENCES thread_polls(id) ON DELETE CASCADE,
            option_text TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS threads_db.thread_poll_votes (
            poll_id INTEGER NOT NULL REFERENCES thread_polls(id) ON DELETE CASCADE,
            option_id INTEGER NOT NULL REFERENCES thread_poll_options(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (poll_id, option_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS threads_db.thread_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id INTEGER NOT NULL,
            author_id INTEGER NOT NULL,
            note TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS audit_db.search_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            query TEXT NOT NULL,
            filters_json TEXT NOT NULL DEFAULT '{}',
            result_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS audit_db.rate_limit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            identity TEXT NOT NULL,
            created_at REAL NOT NULL
        );

        CREATE INDEX IF NOT EXISTS posts_db.idx_post_reactions_post
        ON post_reactions(post_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS posts_db.idx_post_reactions_user
        ON post_reactions(user_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS users_db.idx_relationships_target
        ON user_relationships(target_user_id, updated_at DESC);
        CREATE INDEX IF NOT EXISTS threads_db.idx_threads_deleted
        ON threads(deleted_at, updated_at DESC);
        CREATE INDEX IF NOT EXISTS posts_db.idx_posts_deleted
        ON posts(deleted_at, thread_id, created_at ASC);
        CREATE INDEX IF NOT EXISTS reports_db.idx_appeals_status
        ON appeals(status, created_at DESC);
        CREATE INDEX IF NOT EXISTS reports_db.idx_appeals_user
        ON appeals(user_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS threads_db.idx_thread_polls_thread
        ON thread_polls(thread_id);
            CREATE INDEX IF NOT EXISTS threads_db.idx_thread_poll_options_poll
            ON thread_poll_options(poll_id, sort_order, id);
            CREATE INDEX IF NOT EXISTS threads_db.idx_thread_poll_votes_poll
            ON thread_poll_votes(poll_id, user_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS users_db.idx_users_approval
            ON users(approval_status, created_at DESC);
            CREATE INDEX IF NOT EXISTS users_db.idx_invite_codes_code
            ON invite_codes(code);
            CREATE INDEX IF NOT EXISTS users_db.idx_invite_codes_enabled
            ON invite_codes(enabled, expires_at);
            CREATE INDEX IF NOT EXISTS audit_db.idx_audit_events_created
            ON audit_events(created_at DESC, id DESC);
            CREATE INDEX IF NOT EXISTS audit_db.idx_audit_events_category
            ON audit_events(category, created_at DESC);
            CREATE INDEX IF NOT EXISTS audit_db.idx_audit_events_actor
            ON audit_events(actor_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS audit_db.idx_audit_events_target
            ON audit_events(target_type, target_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS threads_db.idx_threads_featured
            ON threads(featured, updated_at DESC);
            CREATE INDEX IF NOT EXISTS threads_db.idx_threads_search_title
            ON threads(title COLLATE NOCASE);
            CREATE INDEX IF NOT EXISTS threads_db.idx_threads_author
            ON threads(author_id, updated_at DESC);
            CREATE INDEX IF NOT EXISTS threads_db.idx_threads_solved
            ON threads(solved, updated_at DESC);
            CREATE INDEX IF NOT EXISTS posts_db.idx_posts_created
            ON posts(created_at DESC);
            CREATE INDEX IF NOT EXISTS posts_db.idx_posts_content
            ON posts(content COLLATE NOCASE);
            CREATE INDEX IF NOT EXISTS threads_db.idx_thread_notes_thread
            ON thread_notes(thread_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS audit_db.idx_search_events_created
            ON search_events(created_at DESC);
            CREATE INDEX IF NOT EXISTS audit_db.idx_search_events_query
            ON search_events(query COLLATE NOCASE, created_at DESC);
            CREATE INDEX IF NOT EXISTS audit_db.idx_rate_limit_events_lookup
            ON rate_limit_events(action, identity, created_at DESC);
            CREATE INDEX IF NOT EXISTS users_db.idx_recovery_codes_user
            ON recovery_codes(user_id, used_at, created_at DESC);
            CREATE INDEX IF NOT EXISTS users_db.idx_email_auth_tokens_lookup
            ON email_auth_tokens(purpose, used_at, created_at DESC);
            CREATE INDEX IF NOT EXISTS reports_db.idx_report_notes_report
            ON report_internal_notes(report_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS reports_db.idx_moderation_macros_enabled
            ON moderation_macros(enabled, title COLLATE NOCASE);
            """
    )
    ensure_registration_defaults(conn)
    ensure_site_settings_defaults(conn)
    ensure_moderation_macro_defaults(conn)
    conn.commit()
