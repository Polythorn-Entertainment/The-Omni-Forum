"""Database bootstrap entrypoint."""

from __future__ import annotations

import sqlite3
from typing import Callable

from .db import get_connection
from .migrations import apply_schema_migrations, maybe_migrate_legacy_db
from .schema_defaults import (
    ensure_moderation_macro_defaults,
    ensure_registration_defaults,
    ensure_site_settings_defaults,
)
from .schema_maintenance import ensure_database_schema
from .schema_search import ensure_search_index_schema
from .schema_seed import seed_sections


def init_db(refresh_search_index_func: Callable[[sqlite3.Connection], bool] | None = None) -> None:
    with get_connection() as conn:
        conn.raw.executescript(
            """
            CREATE TABLE IF NOT EXISTS users_db.users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                password_hash TEXT NOT NULL,
                email TEXT NOT NULL DEFAULT '',
                email_verified_at TEXT,
                role TEXT NOT NULL DEFAULT 'new',
                bio TEXT NOT NULL DEFAULT '',
                avatar_path TEXT NOT NULL DEFAULT '',
                status_text TEXT NOT NULL DEFAULT '',
                site_theme TEXT NOT NULL DEFAULT 'midnight',
                dm_privacy TEXT NOT NULL DEFAULT 'everyone',
                blur_sensitive_media INTEGER NOT NULL DEFAULT 1,
                compact_post_layout INTEGER NOT NULL DEFAULT 0,
                hide_ignored_content INTEGER NOT NULL DEFAULT 1,
                notify_replies INTEGER NOT NULL DEFAULT 1,
                notify_likes INTEGER NOT NULL DEFAULT 1,
                notify_mentions INTEGER NOT NULL DEFAULT 1,
                notify_dms INTEGER NOT NULL DEFAULT 1,
                xp INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                    last_seen_at TEXT,
                    password_reset_required INTEGER NOT NULL DEFAULT 0,
                    password_reset_set_by INTEGER,
                    password_reset_set_at TEXT,
                    approval_status TEXT NOT NULL DEFAULT 'approved',
                    approval_note TEXT NOT NULL DEFAULT '',
                    approved_by INTEGER,
                    approved_at TEXT,
                    registration_ip TEXT NOT NULL DEFAULT '',
                    invite_code_used TEXT NOT NULL DEFAULT ''
                );

            CREATE TABLE IF NOT EXISTS users_db.moderation_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                actor_id INTEGER NOT NULL,
                action_type TEXT NOT NULL,
                reason TEXT NOT NULL DEFAULT '',
                note TEXT NOT NULL DEFAULT '',
                delta_xp INTEGER NOT NULL DEFAULT 0,
                expires_at TEXT,
                created_at TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}'
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

                CREATE TABLE IF NOT EXISTS sessions_db.sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                csrf_token TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                ip_address TEXT NOT NULL DEFAULT '',
                user_agent TEXT NOT NULL DEFAULT '',
                last_seen_at TEXT,
                last_seen_ip TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS sections_db.categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT NOT NULL UNIQUE,
                label TEXT NOT NULL,
                sort_order INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sections_db.sections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
                slug TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                icon TEXT NOT NULL,
                icon_bg TEXT NOT NULL,
                required_role TEXT NOT NULL DEFAULT 'new',
                write_role TEXT NOT NULL DEFAULT 'new',
                thread_prefixes_json TEXT NOT NULL DEFAULT '[]',
                thread_template TEXT NOT NULL DEFAULT '',
                thread_state_mode TEXT NOT NULL DEFAULT 'discussion',
                sort_order INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS threads_db.threads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                section_id INTEGER NOT NULL,
                author_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                prefix TEXT NOT NULL DEFAULT '',
                tags_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                edited_at TEXT,
                view_count INTEGER NOT NULL DEFAULT 0,
                pinned INTEGER NOT NULL DEFAULT 0,
                locked INTEGER NOT NULL DEFAULT 0,
                solved INTEGER NOT NULL DEFAULT 0,
                answer_post_id INTEGER,
                featured INTEGER NOT NULL DEFAULT 0,
                shadow_hidden INTEGER NOT NULL DEFAULT 0,
                deleted_at TEXT,
                deleted_by INTEGER,
                delete_reason TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS posts_db.posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id INTEGER NOT NULL,
                author_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                media_sensitive INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                edited_at TEXT,
                deleted_at TEXT,
                deleted_by INTEGER,
                delete_reason TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS posts_db.post_media (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
                storage_path TEXT NOT NULL,
                thumbnail_path TEXT NOT NULL DEFAULT '',
                mime_type TEXT NOT NULL,
                alt_text TEXT NOT NULL DEFAULT '',
                width INTEGER NOT NULL DEFAULT 0,
                height INTEGER NOT NULL DEFAULT 0,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS posts_db.post_edits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
                editor_id INTEGER NOT NULL,
                previous_content TEXT NOT NULL,
                previous_title TEXT NOT NULL DEFAULT '',
                media_summary_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS posts_db.post_likes (
                post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (post_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS messages_db.dm_threads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_low_id INTEGER NOT NULL,
                user_high_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_message_at TEXT NOT NULL,
                UNIQUE(user_low_id, user_high_id)
            );

            CREATE TABLE IF NOT EXISTS messages_db.dm_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id INTEGER NOT NULL,
                sender_id INTEGER NOT NULL,
                recipient_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                read_at TEXT
            );

            CREATE TABLE IF NOT EXISTS notifications_db.notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                actor_id INTEGER,
                kind TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL DEFAULT '',
                target_type TEXT NOT NULL DEFAULT '',
                target_id INTEGER,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                read_at TEXT,
                created_at TEXT NOT NULL
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

            CREATE TABLE IF NOT EXISTS reports_db.reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reporter_id INTEGER NOT NULL,
                target_type TEXT NOT NULL,
                target_id INTEGER NOT NULL,
                target_label TEXT NOT NULL,
                target_preview TEXT NOT NULL DEFAULT '',
                context_thread_id INTEGER,
                reason TEXT NOT NULL,
                details TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'open',
                admin_note TEXT NOT NULL DEFAULT '',
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

            CREATE TABLE IF NOT EXISTS contact_db.contact_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                discord_username TEXT NOT NULL DEFAULT '',
                subject TEXT NOT NULL,
                message TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                admin_note TEXT NOT NULL DEFAULT '',
                handled_by INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                handled_at TEXT
            );

            CREATE TABLE IF NOT EXISTS threads_db.thread_bookmarks (
                thread_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (thread_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS threads_db.thread_subscriptions (
                thread_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (thread_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS threads_db.thread_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id INTEGER NOT NULL,
                author_id INTEGER NOT NULL,
                note TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS threads_db.idx_threads_section ON threads(section_id, updated_at DESC);
            CREATE INDEX IF NOT EXISTS threads_db.idx_threads_search_title ON threads(title COLLATE NOCASE);
            CREATE INDEX IF NOT EXISTS threads_db.idx_threads_author ON threads(author_id, updated_at DESC);
            CREATE INDEX IF NOT EXISTS threads_db.idx_threads_solved ON threads(solved, updated_at DESC);
            CREATE INDEX IF NOT EXISTS threads_db.idx_thread_bookmarks_user ON thread_bookmarks(user_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS threads_db.idx_thread_subscriptions_user ON thread_subscriptions(user_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS posts_db.idx_posts_thread ON posts(thread_id, created_at ASC);
            CREATE INDEX IF NOT EXISTS posts_db.idx_posts_author ON posts(author_id);
            CREATE INDEX IF NOT EXISTS posts_db.idx_posts_created ON posts(created_at DESC);
            CREATE INDEX IF NOT EXISTS posts_db.idx_posts_content ON posts(content COLLATE NOCASE);
            CREATE INDEX IF NOT EXISTS posts_db.idx_post_media_post ON post_media(post_id, sort_order, id);
            CREATE INDEX IF NOT EXISTS posts_db.idx_post_edits_post ON post_edits(post_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS posts_db.idx_likes_post ON post_likes(post_id);
            CREATE INDEX IF NOT EXISTS messages_db.idx_dm_threads_last ON dm_threads(last_message_at DESC);
            CREATE INDEX IF NOT EXISTS messages_db.idx_dm_messages_thread ON dm_messages(thread_id, created_at ASC);
            CREATE INDEX IF NOT EXISTS messages_db.idx_dm_messages_recipient ON dm_messages(recipient_id, read_at, created_at DESC);
                CREATE INDEX IF NOT EXISTS notifications_db.idx_notifications_user ON notifications(user_id, read_at, created_at DESC);
                CREATE INDEX IF NOT EXISTS reports_db.idx_reports_status ON reports(status, created_at DESC);
                CREATE INDEX IF NOT EXISTS reports_db.idx_reports_reporter ON reports(reporter_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS users_db.idx_moderation_user ON moderation_actions(user_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS users_db.idx_moderation_actor ON moderation_actions(actor_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS users_db.idx_relationships_target ON user_relationships(target_user_id, updated_at DESC);
                CREATE INDEX IF NOT EXISTS users_db.idx_invite_codes_code ON invite_codes(code);
                CREATE INDEX IF NOT EXISTS users_db.idx_invite_codes_enabled ON invite_codes(enabled, expires_at);
                CREATE INDEX IF NOT EXISTS users_db.idx_recovery_codes_user ON recovery_codes(user_id, used_at, created_at DESC);
                CREATE INDEX IF NOT EXISTS users_db.idx_email_auth_tokens_lookup ON email_auth_tokens(purpose, used_at, created_at DESC);
                CREATE INDEX IF NOT EXISTS sessions_db.idx_sessions_user ON sessions(user_id);
                CREATE INDEX IF NOT EXISTS contact_db.idx_contact_status ON contact_submissions(status, created_at DESC);
                CREATE INDEX IF NOT EXISTS sections_db.idx_sections_category_sort ON sections(category_id, sort_order, id);
                CREATE INDEX IF NOT EXISTS audit_db.idx_search_events_created ON search_events(created_at DESC);
                CREATE INDEX IF NOT EXISTS audit_db.idx_search_events_query ON search_events(query COLLATE NOCASE, created_at DESC);
                CREATE INDEX IF NOT EXISTS audit_db.idx_rate_limit_events_lookup ON rate_limit_events(action, identity, created_at DESC);
                CREATE INDEX IF NOT EXISTS threads_db.idx_thread_notes_thread ON thread_notes(thread_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS reports_db.idx_report_notes_report ON report_internal_notes(report_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS reports_db.idx_moderation_macros_enabled ON moderation_macros(enabled, title COLLATE NOCASE);
                """
        )
        ensure_database_schema(conn.raw)
        ensure_search_index_schema(conn.raw)
        ensure_registration_defaults(conn)
        ensure_site_settings_defaults(conn)
        ensure_moderation_macro_defaults(conn)
        conn.raw.execute(
            """
                CREATE INDEX IF NOT EXISTS sessions_db.idx_sessions_seen
                ON sessions(user_id, last_seen_at DESC, created_at DESC)
            """
        )
        maybe_migrate_legacy_db(conn)
        apply_schema_migrations(conn.raw)
        seed_sections(conn)
        if refresh_search_index_func:
            refresh_search_index_func(conn.raw)
