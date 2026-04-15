#!/usr/bin/env python3
"""OmniForum application server.

This keeps the existing static frontend structure but backs it with a real
SQLite-powered API, cookie sessions, and persistent forum data stored in
separate files under ``data/``.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import math
import mimetypes
import os
import re
import secrets
import shutil
import sqlite3
import time
import zipfile
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
LEGACY_DB_PATH = BASE_DIR / "forum.db"
DATA_FILES = {
    "users_db": DATA_DIR / "users.db",
    "sessions_db": DATA_DIR / "sessions.db",
    "sections_db": DATA_DIR / "sections.db",
    "threads_db": DATA_DIR / "threads.db",
    "posts_db": DATA_DIR / "posts.db",
    "messages_db": DATA_DIR / "messages.db",
    "notifications_db": DATA_DIR / "notifications.db",
    "reports_db": DATA_DIR / "reports.db",
    "contact_db": DATA_DIR / "contact.db",
}
MEDIA_ROUTE = "/media"
EXPORT_ROUTE = "/exports"
MEDIA_DIR = DATA_DIR / "uploads"
EXPORTS_DIR = DATA_DIR / "exports"
BACKUP_DIR = EXPORTS_DIR / "backups"
LOG_DIR = DATA_DIR / "logs"
LOG_FILE = LOG_DIR / "server.log"
MEDIA_FOLDERS = {
    "avatars": MEDIA_DIR / "avatars",
    "posts": MEDIA_DIR / "posts",
}
HOST = os.getenv("OMNIFORUM_HOST", "127.0.0.1")
PORT = int(os.getenv("OMNIFORUM_PORT", "8000"))
SECURE_COOKIES = os.getenv("OMNIFORUM_SECURE_COOKIES", "0") == "1"
SESSION_COOKIE = "nexus_session"
SESSION_DAYS = 30
ONLINE_WINDOW_MINUTES = 15
PBKDF2_ROUNDS = 200_000
XP_THREAD = 50
XP_REPLY = 25
XP_LIKE = 10
AVATAR_MAX_BYTES = 3 * 1024 * 1024
POST_MEDIA_MAX_BYTES = 8 * 1024 * 1024
POST_MEDIA_MAX_COUNT = 4
MAX_IMAGE_WIDTH = 6_000
MAX_IMAGE_HEIGHT = 6_000
MAX_IMAGE_PIXELS = 24_000_000
MAX_REQUEST_BYTES = int(os.getenv("OMNIFORUM_MAX_REQUEST_BYTES", str(48 * 1024 * 1024)))
DEFAULT_PAGE_SIZE = 20
DEFAULT_POST_PAGE_SIZE = 20
DEFAULT_MEMBER_PAGE_SIZE = 24
DEFAULT_LEADERBOARD_PAGE_SIZE = 18
MAX_PAGE_SIZE = 50
BACKUP_ROTATION_LIMIT = int(os.getenv("OMNIFORUM_BACKUP_ROTATION", "8"))
DM_PRIVACY_OPTIONS = {"everyone", "members", "staff_only", "disabled"}
ALLOWED_REACTIONS = {"👍", "❤️", "😂", "🎉", "🔥", "👀"}
ALLOWED_PROFILE_ACCENTS = {
    "#00d4ff",
    "#7b5ea7",
    "#ff6b6b",
    "#ffd166",
    "#06d6a0",
    "#6b7a94",
}
SITE_THEME_OPTIONS = {
    "midnight",
    "ember",
    "verdant",
    "sunset",
    "arctic",
    "aurora",
    "cobaltforge",
    "matchawire",
    "ultraviolet",
    "rosewater",
    "deepsea",
    "dune",
    "reactor",
    "lilacstorm",
    "monolith",
    "ivorysignal",
    "seaglass",
    "petalpaper",
}
REPORT_PRIORITIES = {"low", "normal", "high", "urgent"}
REPORT_CATEGORIES = {
    "",
    "spam",
    "abuse",
    "safety",
    "privacy",
    "impersonation",
    "copyright",
    "other",
}
NOTIFICATION_PREFERENCE_COLUMNS = {
    "reply": "notify_replies",
    "like": "notify_likes",
    "mention": "notify_mentions",
    "dm": "notify_dms",
}
SERVER_STARTED_AT = datetime.now(timezone.utc)
RATE_LIMIT_RULES = {
    "register": (5, 900, "registrations"),
    "login": (12, 600, "login attempts"),
    "contact": (5, 600, "contact submissions"),
    "report": (8, 600, "reports"),
    "profile_update": (12, 600, "profile changes"),
    "thread_create": (8, 900, "new threads"),
    "post_create": (20, 600, "replies"),
    "post_update": (20, 600, "post edits"),
    "dm_send": (30, 300, "messages"),
    "like_toggle": (80, 300, "reactions"),
    "search": (80, 120, "searches"),
}
FLOOD_CONTROL_SECONDS = {
    "thread": 45,
    "reply": 15,
    "message": 6,
    "contact": 90,
    "report": 30,
}
LOW_TRUST_MAX_LINKS = 3
LOW_TRUST_MAX_MENTIONS = 6
URL_PATTERN = re.compile(r"(https?://|www\.)", re.IGNORECASE)
RATE_LIMIT_STATE: dict[str, list[float]] = {}

TABLE_SCHEMAS = {
    "users": "users_db.users",
    "moderation_actions": "users_db.moderation_actions",
    "sessions": "sessions_db.sessions",
    "categories": "sections_db.categories",
    "sections": "sections_db.sections",
    "threads": "threads_db.threads",
    "posts": "posts_db.posts",
    "post_media": "posts_db.post_media",
    "post_reactions": "posts_db.post_reactions",
    "post_likes": "posts_db.post_likes",
    "dm_threads": "messages_db.dm_threads",
    "dm_messages": "messages_db.dm_messages",
    "notifications": "notifications_db.notifications",
    "reports": "reports_db.reports",
    "appeals": "reports_db.appeals",
    "contact_submissions": "contact_db.contact_submissions",
    "thread_polls": "threads_db.thread_polls",
    "thread_poll_options": "threads_db.thread_poll_options",
    "thread_poll_votes": "threads_db.thread_poll_votes",
}
TABLE_PATTERN = re.compile(
    r"(?<!\.)\b(" + "|".join(sorted(TABLE_SCHEMAS, key=len, reverse=True)) + r")\b"
)
MENTION_PATTERN = re.compile(r"(?<![\w-])@([A-Za-z0-9_-]{3,24})")

ROLE_LEVELS = {
    "new": 0,
    "member": 1,
    "veteran": 2,
    "mod": 3,
    "admin": 4,
    "owner": 5,
}

ROLES = {
    "owner": {
        "label": "Owner",
        "icon": "\U0001F451",
        "level": 5,
        "color": "#ff6b6b",
        "cssClass": "owner",
    },
    "admin": {
        "label": "Admin",
        "icon": "\u26a1",
        "level": 4,
        "color": "#ff9f9f",
        "cssClass": "admin",
    },
    "mod": {
        "label": "Mod",
        "icon": "\U0001F6E1\ufe0f",
        "level": 3,
        "color": "#00d4ff",
        "cssClass": "mod",
    },
    "veteran": {
        "label": "Veteran",
        "icon": "\u2b50",
        "level": 2,
        "color": "#b39ddb",
        "cssClass": "veteran",
    },
    "member": {
        "label": "Member",
        "icon": "\U0001F48E",
        "level": 1,
        "color": "#6b7a94",
        "cssClass": "member",
    },
    "new": {
        "label": "New",
        "icon": "\U0001F331",
        "level": 0,
        "color": "#06d6a0",
        "cssClass": "new",
    },
}

AUTO_ROLES = [
    ("veteran", 600),
    ("member", 100),
    ("new", 0),
]

SECTION_SEEDS = [
    {
        "slug": "cat-announcements",
        "label": "\U0001F4E2 Official",
        "sections": [
            {
                "slug": "s-announcements",
                "name": "Announcements",
                "description": "Official news, updates, and announcements from staff",
                "icon": "\U0001F4E3",
                "icon_bg": "rgba(255,107,107,0.15)",
                "required_role": "new",
                "write_role": "admin",
            },
            {
                "slug": "s-rules",
                "name": "Rules & Guidelines",
                "description": "Community rules, conduct guidelines, and policies",
                "icon": "\U0001F4DC",
                "icon_bg": "rgba(255,209,102,0.15)",
                "required_role": "new",
                "write_role": "admin",
            },
        ],
    },
    {
        "slug": "cat-general",
        "label": "\U0001F4AC General",
        "sections": [
            {
                "slug": "s-general",
                "name": "General Discussion",
                "description": "Talk about anything and everything here",
                "icon": "\U0001F4AC",
                "icon_bg": "rgba(0,212,255,0.1)",
                "required_role": "new",
                "write_role": "new",
            },
            {
                "slug": "s-introductions",
                "name": "Introductions",
                "description": "New here? Say hello and introduce yourself",
                "icon": "\U0001F44B",
                "icon_bg": "rgba(6,214,160,0.1)",
                "required_role": "new",
                "write_role": "new",
            },
            {
                "slug": "s-lounge",
                "name": "Member Lounge",
                "description": "Exclusive lounge for members and above",
                "icon": "\U0001F378",
                "icon_bg": "rgba(123,94,167,0.15)",
                "required_role": "member",
                "write_role": "member",
            },
            {
                "slug": "s-veterans",
                "name": "Veterans Den",
                "description": "A private space for veteran members and staff",
                "icon": "\U0001F3DB\ufe0f",
                "icon_bg": "rgba(123,94,167,0.2)",
                "required_role": "veteran",
                "write_role": "veteran",
            },
        ],
    },
    {
        "slug": "cat-tech",
        "label": "\u2699\ufe0f Technology",
        "sections": [
            {
                "slug": "s-programming",
                "name": "Programming",
                "description": "Code talk, debugging help, project showcases, and dev discussion",
                "icon": "\U0001F4BB",
                "icon_bg": "rgba(0,212,255,0.12)",
                "required_role": "new",
                "write_role": "new",
            },
            {
                "slug": "s-gaming",
                "name": "Gaming",
                "description": "Video games, reviews, recommendations, and gaming culture",
                "icon": "\U0001F3AE",
                "icon_bg": "rgba(123,94,167,0.12)",
                "required_role": "new",
                "write_role": "new",
            },
            {
                "slug": "s-ai",
                "name": "AI & Machine Learning",
                "description": "Artificial intelligence, ML models, tools, ethics, and the future",
                "icon": "\U0001F916",
                "icon_bg": "rgba(255,107,107,0.1)",
                "required_role": "new",
                "write_role": "new",
            },
            {
                "slug": "s-security",
                "name": "Cybersecurity",
                "description": "InfoSec, CTFs, vulnerability research, and best practices",
                "icon": "\U0001F510",
                "icon_bg": "rgba(255,107,107,0.12)",
                "required_role": "new",
                "write_role": "new",
            },
        ],
    },
    {
        "slug": "cat-creative",
        "label": "\U0001F3A8 Creative",
        "sections": [
            {
                "slug": "s-music",
                "name": "Music",
                "description": "Discover and share music, discuss artists, genres, and production",
                "icon": "\U0001F3B5",
                "icon_bg": "rgba(123,94,167,0.12)",
                "required_role": "new",
                "write_role": "new",
            },
            {
                "slug": "s-art-design",
                "name": "Art & Design",
                "description": "Visual art, UI/UX design, photography, and digital creation",
                "icon": "\U0001F58C\ufe0f",
                "icon_bg": "rgba(255,209,102,0.1)",
                "required_role": "new",
                "write_role": "new",
            },
            {
                "slug": "s-writing",
                "name": "Writing & Literature",
                "description": "Fiction, poetry, essays, critique, and writing craft",
                "icon": "\u270d\ufe0f",
                "icon_bg": "rgba(6,214,160,0.1)",
                "required_role": "new",
                "write_role": "new",
            },
        ],
    },
    {
        "slug": "cat-lifestyle",
        "label": "\U0001F30D Lifestyle",
        "sections": [
            {
                "slug": "s-health",
                "name": "Health & Fitness",
                "description": "Wellness, fitness routines, nutrition, and mental health",
                "icon": "\U0001F4AA",
                "icon_bg": "rgba(6,214,160,0.1)",
                "required_role": "new",
                "write_role": "new",
            },
            {
                "slug": "s-travel",
                "name": "Travel & Culture",
                "description": "Destinations, tips, cultural exchange, and travel stories",
                "icon": "\u2708\ufe0f",
                "icon_bg": "rgba(0,212,255,0.08)",
                "required_role": "new",
                "write_role": "new",
            },
            {
                "slug": "s-finance",
                "name": "Finance & Crypto",
                "description": "Personal finance, investing, crypto, and economic discussion",
                "icon": "\U0001F4C8",
                "icon_bg": "rgba(255,209,102,0.1)",
                "required_role": "new",
                "write_role": "new",
            },
        ],
    },
    {
        "slug": "cat-staff",
        "label": "\U0001F512 Staff Only",
        "sections": [
            {
                "slug": "s-staff-room",
                "name": "Staff Room",
                "description": "Private area for moderators and administrators",
                "icon": "\U0001F512",
                "icon_bg": "rgba(255,107,107,0.1)",
                "required_role": "mod",
                "write_role": "mod",
            },
            {
                "slug": "s-admin-panel",
                "name": "Admin Control Panel",
                "description": "Administrative discussion, decisions, and forum management",
                "icon": "\u26a1",
                "icon_bg": "rgba(255,107,107,0.15)",
                "required_role": "admin",
                "write_role": "admin",
            },
        ],
    },
]


class APIError(Exception):
    def __init__(self, message: str, status: int = HTTPStatus.BAD_REQUEST) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_iso(value: datetime | None = None) -> str:
    if value is None:
        value = utc_now()
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def role_level(role: str | None) -> int:
    return ROLE_LEVELS.get(role or "new", 0)


def guest_can_view(required_role: str) -> bool:
    return role_level(required_role) <= role_level("new")


def has_required_role(user: dict[str, Any] | None, required_role: str) -> bool:
    if user is None:
        return guest_can_view(required_role)
    return role_level(user["role"]) >= role_level(required_role)


def is_staff(user: dict[str, Any] | None) -> bool:
    return role_level(user["role"]) >= role_level("mod") if user else False


def is_admin(user: dict[str, Any] | None) -> bool:
    return role_level(user["role"]) >= role_level("admin") if user else False


def can_manage_user(actor: dict[str, Any] | None, target_role: str) -> bool:
    if not actor:
        return False
    if actor["role"] == "owner":
        return True
    if actor["role"] == "admin":
        return role_level(target_role) <= role_level("mod")
    return False


def can_moderate_user(
    actor: dict[str, Any] | None,
    target: sqlite3.Row | dict[str, Any] | None,
) -> bool:
    if not actor or not target or not is_staff(actor):
        return False
    target_row = dict(target)
    if actor["id"] == target_row["id"]:
        return False
    return role_level(actor["role"]) > role_level(target_row["role"])


def make_password_hash(password: str, salt_hex: str | None = None) -> str:
    salt_hex = salt_hex or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt_hex),
        PBKDF2_ROUNDS,
    )
    return f"{salt_hex}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt_hex, digest_hex = stored_hash.split("$", 1)
    except ValueError:
        return False
    candidate = make_password_hash(password, salt_hex)
    return hmac.compare_digest(candidate, stored_hash)


def qualify_sql(sql: str) -> str:
    return TABLE_PATTERN.sub(lambda match: TABLE_SCHEMAS[match.group(1)], sql)


class DataConnection:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    @property
    def raw(self) -> sqlite3.Connection:
        return self._connection

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        return self._connection.execute(qualify_sql(sql), params)

    def executemany(self, sql: str, params: Any) -> sqlite3.Cursor:
        return self._connection.executemany(qualify_sql(sql), params)

    def commit(self) -> None:
        self._connection.commit()

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "DataConnection":
        self._connection.__enter__()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool | None:
        return self._connection.__exit__(exc_type, exc, tb)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._connection, name)


def get_connection() -> DataConnection:
    ensure_runtime_dirs()
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    for schema, path in DATA_FILES.items():
        conn.execute(f"ATTACH DATABASE ? AS {schema}", (str(path),))
    return DataConnection(conn)


def ensure_runtime_dirs() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    MEDIA_DIR.mkdir(exist_ok=True)
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    for directory in MEDIA_FOLDERS.values():
        directory.mkdir(parents=True, exist_ok=True)


def maybe_migrate_legacy_db(conn: DataConnection) -> None:
    if not LEGACY_DB_PATH.exists():
        return

    counts = {
        "users": conn.execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"],
        "threads": conn.execute("SELECT COUNT(*) AS count FROM threads").fetchone()["count"],
        "posts": conn.execute("SELECT COUNT(*) AS count FROM posts").fetchone()["count"],
        "sessions": conn.execute("SELECT COUNT(*) AS count FROM sessions").fetchone()["count"],
        "contacts": conn.execute(
            "SELECT COUNT(*) AS count FROM contact_submissions"
        ).fetchone()["count"],
    }
    if any(counts.values()):
        return

    raw = conn.raw
    raw.execute("ATTACH DATABASE ? AS legacy_db", (str(LEGACY_DB_PATH),))
    try:
        legacy_tables = {
            row["name"]
            for row in raw.execute(
                "SELECT name FROM legacy_db.sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        required_tables = {"users", "categories", "sections", "threads", "posts"}
        if not required_tables.issubset(legacy_tables):
            return

        raw.execute("DELETE FROM sections_db.sections")
        raw.execute("DELETE FROM sections_db.categories")

        raw.execute(
            """
            INSERT INTO users_db.users (
                id, username, password_hash, role, bio, xp, created_at, updated_at, last_seen_at
            )
            SELECT
                id, username, password_hash, role, bio, xp, created_at, updated_at, last_seen_at
            FROM legacy_db.users
            """
        )
        if "sessions" in legacy_tables:
            raw.execute("INSERT INTO sessions_db.sessions SELECT * FROM legacy_db.sessions")
        raw.execute("INSERT INTO sections_db.categories SELECT * FROM legacy_db.categories")
        raw.execute("INSERT INTO sections_db.sections SELECT * FROM legacy_db.sections")
        raw.execute("INSERT INTO threads_db.threads SELECT * FROM legacy_db.threads")
        raw.execute("INSERT INTO posts_db.posts SELECT * FROM legacy_db.posts")
        if "post_likes" in legacy_tables:
            raw.execute("INSERT INTO posts_db.post_likes SELECT * FROM legacy_db.post_likes")
        if "contact_submissions" in legacy_tables:
            raw.execute(
                """
                INSERT INTO contact_db.contact_submissions (
                    id, user_id, name, email, discord_username, subject, message,
                    status, admin_note, handled_by, created_at, updated_at, handled_at
                )
                SELECT
                    id, user_id, name, COALESCE(email, ''), '', subject, message,
                    status, admin_note, handled_by, created_at, updated_at, handled_at
                FROM legacy_db.contact_submissions
                """
            )
        raw.commit()
    finally:
        raw.execute("DETACH DATABASE legacy_db")


def init_db() -> None:
    with get_connection() as conn:
        conn.raw.executescript(
            """
            CREATE TABLE IF NOT EXISTS users_db.users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'new',
                bio TEXT NOT NULL DEFAULT '',
                avatar_path TEXT NOT NULL DEFAULT '',
                site_theme TEXT NOT NULL DEFAULT 'midnight',
                dm_privacy TEXT NOT NULL DEFAULT 'everyone',
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
                password_reset_set_at TEXT
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

            CREATE TABLE IF NOT EXISTS sessions_db.sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
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
                sort_order INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS threads_db.threads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                section_id INTEGER NOT NULL,
                author_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                tags_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                edited_at TEXT,
                view_count INTEGER NOT NULL DEFAULT 0,
                pinned INTEGER NOT NULL DEFAULT 0,
                locked INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS posts_db.posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id INTEGER NOT NULL,
                author_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                edited_at TEXT
            );

            CREATE TABLE IF NOT EXISTS posts_db.post_media (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
                storage_path TEXT NOT NULL,
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

            CREATE INDEX IF NOT EXISTS threads_db.idx_threads_section ON threads(section_id, updated_at DESC);
            CREATE INDEX IF NOT EXISTS threads_db.idx_thread_bookmarks_user ON thread_bookmarks(user_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS threads_db.idx_thread_subscriptions_user ON thread_subscriptions(user_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS posts_db.idx_posts_thread ON posts(thread_id, created_at ASC);
            CREATE INDEX IF NOT EXISTS posts_db.idx_posts_author ON posts(author_id);
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
            CREATE INDEX IF NOT EXISTS sessions_db.idx_sessions_user ON sessions(user_id);
            CREATE INDEX IF NOT EXISTS contact_db.idx_contact_status ON contact_submissions(status, created_at DESC);
            """
        )
        ensure_database_schema(conn.raw)
        conn.raw.execute(
            """
            CREATE INDEX IF NOT EXISTS sessions_db.idx_sessions_seen
            ON sessions(user_id, last_seen_at DESC, created_at DESC)
            """
        )
        maybe_migrate_legacy_db(conn)
        seed_sections(conn)


def ensure_column(
    conn: sqlite3.Connection,
    schema: str,
    table: str,
    column_name: str,
    definition: str,
) -> None:
    columns = {
        row["name"]
        for row in conn.execute(f"PRAGMA {schema}.table_info({table})").fetchall()
    }
    if column_name in columns:
        return
    conn.execute(f"ALTER TABLE {schema}.{table} ADD COLUMN {column_name} {definition}")


def ensure_database_schema(conn: sqlite3.Connection) -> None:
    ensure_column(conn, "users_db", "users", "avatar_path", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "users_db", "users", "site_theme", "TEXT NOT NULL DEFAULT 'midnight'")
    ensure_column(conn, "users_db", "users", "dm_privacy", "TEXT NOT NULL DEFAULT 'everyone'")
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
    ensure_column(conn, "threads_db", "threads", "solved", "INTEGER NOT NULL DEFAULT 0")
    ensure_column(conn, "threads_db", "threads", "answer_post_id", "INTEGER")
    ensure_column(conn, "threads_db", "threads", "shadow_hidden", "INTEGER NOT NULL DEFAULT 0")
    ensure_column(conn, "posts_db", "posts", "shadow_hidden", "INTEGER NOT NULL DEFAULT 0")
    ensure_column(conn, "posts_db", "post_media", "width", "INTEGER NOT NULL DEFAULT 0")
    ensure_column(conn, "posts_db", "post_media", "height", "INTEGER NOT NULL DEFAULT 0")
    ensure_column(conn, "reports_db", "reports", "triage_priority", "TEXT NOT NULL DEFAULT 'normal'")
    ensure_column(conn, "reports_db", "reports", "triage_category", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "reports_db", "reports", "assigned_to", "INTEGER")
    ensure_column(conn, "reports_db", "reports", "resolution_code", "TEXT NOT NULL DEFAULT ''")
    ensure_column(
        conn,
        "contact_db",
        "contact_submissions",
        "discord_username",
        "TEXT NOT NULL DEFAULT ''",
    )
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS posts_db.post_reactions (
            post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL,
            emoji TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (post_id, user_id, emoji)
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

        CREATE INDEX IF NOT EXISTS posts_db.idx_post_reactions_post
        ON post_reactions(post_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS posts_db.idx_post_reactions_user
        ON post_reactions(user_id, created_at DESC);
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
        """
    )
    conn.commit()


def seed_sections(conn: sqlite3.Connection) -> None:
    existing = conn.execute("SELECT COUNT(*) AS count FROM sections").fetchone()["count"]
    if existing:
        return
    for category_index, category in enumerate(SECTION_SEEDS):
        cur = conn.execute(
            "INSERT INTO categories (slug, label, sort_order) VALUES (?, ?, ?)",
            (category["slug"], category["label"], category_index),
        )
        category_id = cur.lastrowid
        for section_index, section in enumerate(category["sections"]):
            conn.execute(
                """
                INSERT INTO sections (
                    category_id, slug, name, description, icon, icon_bg,
                    required_role, write_role, sort_order
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    category_id,
                    section["slug"],
                    section["name"],
                    section["description"],
                    section["icon"],
                    section["icon_bg"],
                    section["required_role"],
                    section["write_role"],
                    section_index,
                ),
            )
    conn.commit()


def clean_text(value: Any, *, min_len: int = 0, max_len: int = 10000, field: str = "Value") -> str:
    text = str(value or "").strip()
    if len(text) < min_len:
        raise APIError(f"{field} is too short.")
    if len(text) > max_len:
        raise APIError(f"{field} is too long.")
    return text


def clean_username(value: Any) -> str:
    username = clean_text(value, min_len=3, max_len=24, field="Username")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", username):
        raise APIError("Username can only contain letters, numbers, _ and -.")
    return username


def clean_password(value: Any) -> str:
    return clean_text(value, min_len=8, max_len=128, field="Password")


def clean_email(value: Any) -> str:
    email = clean_text(value, min_len=5, max_len=200, field="Email").lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise APIError("Please enter a valid email address.")
    return email


def clean_discord_username(value: Any) -> str:
    username = clean_text(value, min_len=0, max_len=64, field="Discord username")
    if not username:
        return ""
    normalized = username.lstrip("@")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{2,32}", normalized):
        raise APIError("Discord username should look like a normal handle, such as omniforum.staff.")
    return normalized


def slugify_text(value: Any, *, fallback: str = "item") -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"[^a-z0-9_-]", "", text)
    text = re.sub(r"-{2,}", "-", text).strip("-_")
    return text or fallback


def clean_slug(value: Any, *, field: str = "Slug", fallback: str = "item") -> str:
    slug = slugify_text(value, fallback=fallback)
    if len(slug) < 2:
        raise APIError(f"{field} is too short.")
    if len(slug) > 48:
        raise APIError(f"{field} is too long.")
    return slug


def clean_role_name(value: Any, *, field: str = "Role") -> str:
    role = str(value or "").strip()
    if role not in ROLES:
        raise APIError(f"Invalid {field.lower()}.")
    return role


def clean_sort_order(value: Any, *, default: int) -> int:
    if value in {None, ""}:
        return default
    try:
        sort_order = int(value)
    except (TypeError, ValueError) as exc:
        raise APIError("Sort order must be a whole number.") from exc
    if sort_order < 0 or sort_order > 999:
        raise APIError("Sort order must be between 0 and 999.")
    return sort_order


def normalize_tags(value: Any) -> list[str]:
    if isinstance(value, str):
        raw_tags = [part.strip() for part in value.split(",")]
    elif isinstance(value, list):
        raw_tags = [str(part).strip() for part in value]
    else:
        raw_tags = []
    tags: list[str] = []
    for tag in raw_tags:
        normalized = re.sub(r"\s+", "-", tag.lower())
        normalized = re.sub(r"[^a-z0-9_-]", "", normalized).strip("-_")
        if normalized and normalized not in tags:
            tags.append(normalized[:20])
        if len(tags) == 5:
            break
    return tags


def clean_post_content(value: Any, *, has_media: bool = False) -> str:
    content = clean_text(value, min_len=0, max_len=10000, field="Content")
    if not content and not has_media:
        raise APIError("Content is too short.")
    return content


def clean_dm_privacy(value: Any) -> str:
    privacy = str(value or "everyone").strip().lower()
    if privacy not in DM_PRIVACY_OPTIONS:
        raise APIError("Direct message privacy setting is invalid.")
    return privacy


def clean_signature(value: Any) -> str:
    return clean_text(value, min_len=0, max_len=240, field="Signature")


def clean_profile_badge(value: Any) -> str:
    return clean_text(value, min_len=0, max_len=32, field="Profile badge")


def clean_profile_accent(value: Any) -> str:
    accent = str(value or "").strip().lower()
    if not accent:
        return ""
    if accent not in ALLOWED_PROFILE_ACCENTS:
        raise APIError("Choose one of the supported profile accent colors.")
    return accent


def clean_site_theme(value: Any) -> str:
    theme = str(value or "midnight").strip().lower()
    if theme not in SITE_THEME_OPTIONS:
        raise APIError("Choose one of the supported site themes.")
    return theme


def clean_reaction_emoji(value: Any) -> str:
    emoji = str(value or "").strip()
    if emoji not in ALLOWED_REACTIONS:
        raise APIError("That reaction is not supported.")
    return emoji


def clean_report_priority(value: Any) -> str:
    priority = str(value or "normal").strip().lower()
    if priority not in REPORT_PRIORITIES:
        raise APIError("Invalid report priority.")
    return priority


def clean_report_category(value: Any) -> str:
    category = str(value or "").strip().lower()
    if category not in REPORT_CATEGORIES:
        raise APIError("Invalid report category.")
    return category


def clean_report_status(value: Any) -> str:
    status = str(value or "open").strip().lower()
    if status not in {"open", "resolved"}:
        raise APIError("Invalid report status.")
    return status


def clean_poll_payload(value: Any) -> dict[str, Any] | None:
    if value is None or value == "":
        return None
    if not isinstance(value, dict):
        raise APIError("Poll settings are invalid.")
    question = clean_text(value.get("question"), min_len=4, max_len=120, field="Poll question")
    raw_options = value.get("options")
    if not isinstance(raw_options, list):
        raise APIError("Poll options must be a list.")
    options: list[str] = []
    for item in raw_options:
        option = clean_text(item, min_len=1, max_len=80, field="Poll option")
        if option.lower() not in {entry.lower() for entry in options}:
            options.append(option)
    if len(options) < 2:
        raise APIError("Polls need at least 2 options.")
    if len(options) > 6:
        raise APIError("Polls can include up to 6 options.")
    return {
        "question": question,
        "options": options,
        "allowsMultiple": bool(value.get("allowsMultiple")),
    }


def parse_pagination_value(
    value: Any,
    *,
    default: int,
    field: str,
    maximum: int = MAX_PAGE_SIZE,
) -> int:
    if value in {None, ""}:
        return default
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise APIError(f"{field} must be a whole number.") from exc
    if number < 1:
        raise APIError(f"{field} must be at least 1.")
    return min(number, maximum)


def resolve_pagination(
    total_items: int,
    *,
    page: int,
    page_size: int,
    last_page: bool = False,
) -> dict[str, int]:
    total_pages = max(1, math.ceil(max(total_items, 1) / page_size))
    resolved_page = total_pages if last_page else min(max(page, 1), total_pages)
    offset = (resolved_page - 1) * page_size
    return {
        "page": resolved_page,
        "pageSize": page_size,
        "totalItems": total_items,
        "totalPages": total_pages,
        "offset": offset,
        "hasPrev": resolved_page > 1,
        "hasNext": resolved_page < total_pages,
    }


def parse_pagination_query(
    query: dict[str, list[str]],
    *,
    default_page_size: int,
) -> tuple[int, int, bool]:
    raw_page = (query.get("page") or ["1"])[0].strip().lower()
    last_page = raw_page == "last"
    page = 1 if last_page else parse_pagination_value(raw_page, default=1, field="Page")
    page_size = parse_pagination_value(
        (query.get("pageSize") or [str(default_page_size)])[0],
        default=default_page_size,
        field="Page size",
    )
    return page, page_size, last_page


def count_links(text: str) -> int:
    return len(URL_PATTERN.findall(str(text or "")))


def enforce_low_trust_content_limits(viewer: dict[str, Any] | None, text: str) -> None:
    if not viewer or role_level(viewer["role"]) >= role_level("member"):
        return
    if count_links(text) > LOW_TRUST_MAX_LINKS:
        raise APIError(
            f"New accounts can only include up to {LOW_TRUST_MAX_LINKS} links in one post.",
            HTTPStatus.TOO_MANY_REQUESTS,
        )
    if len(MENTION_PATTERN.findall(text)) > LOW_TRUST_MAX_MENTIONS:
        raise APIError(
            f"New accounts can only mention up to {LOW_TRUST_MAX_MENTIONS} people at once.",
            HTTPStatus.TOO_MANY_REQUESTS,
        )


def clean_id_list(value: Any, *, field: str = "Items") -> list[int]:
    if value is None or value == "":
        return []
    if not isinstance(value, list):
        raise APIError(f"{field} must be a list.")
    output: list[int] = []
    seen: set[int] = set()
    for item in value:
        try:
            identifier = int(item)
        except (TypeError, ValueError) as exc:
            raise APIError(f"{field} contains an invalid id.") from exc
        if identifier <= 0 or identifier in seen:
            continue
        seen.add(identifier)
        output.append(identifier)
    return output


def media_url_for_path(storage_path: str | None) -> str | None:
    relative = str(storage_path or "").strip().replace("\\", "/").strip("/")
    if not relative:
        return None
    return f"{MEDIA_ROUTE}/{relative}"


def resolve_media_path(storage_path: str | None) -> Path | None:
    relative = str(storage_path or "").strip().replace("\\", "/").strip("/")
    if not relative:
        return None
    parts = Path(relative).parts
    if len(parts) != 2 or parts[0] not in MEDIA_FOLDERS:
        return None
    candidate = (MEDIA_FOLDERS[parts[0]] / parts[1]).resolve()
    root = MEDIA_FOLDERS[parts[0]].resolve()
    if candidate.parent != root:
        return None
    return candidate


def delete_media_file(storage_path: str | None) -> None:
    path = resolve_media_path(storage_path)
    if path and path.exists():
        path.unlink()


def detect_image_type(data: bytes) -> tuple[str, str]:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", "jpg"
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return "image/gif", "gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", "webp"
    raise APIError("Only PNG, JPG, GIF, and WEBP images are supported.")


def jpeg_dimensions(data: bytes) -> tuple[int, int]:
    index = 2
    while index < len(data):
        while index < len(data) and data[index] != 0xFF:
            index += 1
        while index < len(data) and data[index] == 0xFF:
            index += 1
        if index >= len(data):
            break
        marker = data[index]
        index += 1
        if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
            continue
        if index + 2 > len(data):
            break
        segment_length = int.from_bytes(data[index : index + 2], "big")
        if segment_length < 2 or index + segment_length > len(data):
            break
        if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
            if index + 7 > len(data):
                break
            height = int.from_bytes(data[index + 3 : index + 5], "big")
            width = int.from_bytes(data[index + 5 : index + 7], "big")
            return width, height
        index += segment_length
    raise APIError("Could not read that JPEG image.")


def webp_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 30:
        raise APIError("Could not read that WEBP image.")
    chunk = data[12:16]
    if chunk == b"VP8X" and len(data) >= 30:
        width = 1 + int.from_bytes(data[24:27], "little")
        height = 1 + int.from_bytes(data[27:30], "little")
        return width, height
    if chunk == b"VP8L" and len(data) >= 25:
        bits = int.from_bytes(data[21:25], "little")
        width = (bits & 0x3FFF) + 1
        height = ((bits >> 14) & 0x3FFF) + 1
        return width, height
    if chunk == b"VP8 " and len(data) >= 30:
        width = int.from_bytes(data[26:28], "little") & 0x3FFF
        height = int.from_bytes(data[28:30], "little") & 0x3FFF
        return width, height
    raise APIError("Could not read that WEBP image.")


def image_dimensions_from_bytes(data: bytes, mime_type: str) -> tuple[int, int]:
    if mime_type == "image/png":
        if len(data) < 24:
            raise APIError("Could not read that PNG image.")
        return (
            int.from_bytes(data[16:20], "big"),
            int.from_bytes(data[20:24], "big"),
        )
    if mime_type == "image/gif":
        if len(data) < 10:
            raise APIError("Could not read that GIF image.")
        return (
            int.from_bytes(data[6:8], "little"),
            int.from_bytes(data[8:10], "little"),
        )
    if mime_type == "image/jpeg":
        return jpeg_dimensions(data)
    if mime_type == "image/webp":
        return webp_dimensions(data)
    raise APIError("Unsupported image type.")


def validate_image_geometry(data: bytes, mime_type: str, *, field: str) -> tuple[int, int]:
    width, height = image_dimensions_from_bytes(data, mime_type)
    if width < 1 or height < 1:
        raise APIError(f"{field} dimensions are invalid.")
    if width > MAX_IMAGE_WIDTH or height > MAX_IMAGE_HEIGHT:
        raise APIError(
            f"{field} is too large. Keep images under {MAX_IMAGE_WIDTH}px by {MAX_IMAGE_HEIGHT}px.",
        )
    if width * height > MAX_IMAGE_PIXELS:
        raise APIError(f"{field} has too many pixels for safe inline display.")
    return width, height


def decode_image_upload(
    payload: Any,
    *,
    field: str,
    max_bytes: int,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise APIError(f"{field} upload is invalid.")
    data_url = str(payload.get("dataUrl") or "")
    if not data_url.startswith("data:"):
        raise APIError(f"{field} upload is missing file data.")
    try:
        header, encoded = data_url.split(",", 1)
    except ValueError as exc:
        raise APIError(f"{field} upload is malformed.") from exc
    if ";base64" not in header:
        raise APIError(f"{field} upload is malformed.")
    try:
        binary = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise APIError(f"{field} upload could not be decoded.") from exc
    if not binary:
        raise APIError(f"{field} upload is empty.")
    if len(binary) > max_bytes:
        max_mb = max_bytes / (1024 * 1024)
        raise APIError(f"{field} must stay under {max_mb:.0f}MB.")
    mime_type, extension = detect_image_type(binary)
    width, height = validate_image_geometry(binary, mime_type, field=field)
    filename = Path(str(payload.get("name") or payload.get("filename") or "")).name.strip()
    if not filename:
        filename = f"{slugify_text(field, fallback='image')}.{extension}"
    alt_text = clean_text(
        payload.get("alt") or Path(filename).stem.replace("-", " ").replace("_", " "),
        min_len=0,
        max_len=120,
        field=f"{field} description",
    )
    return {
        "bytes": binary,
        "mime_type": mime_type,
        "extension": extension,
        "filename": filename,
        "alt_text": alt_text or "Forum image",
        "width": width,
        "height": height,
    }


def normalize_media_uploads(
    value: Any,
    *,
    max_items: int,
    field: str = "Images",
    max_bytes: int = POST_MEDIA_MAX_BYTES,
) -> list[dict[str, Any]]:
    if value is None or value == "":
        return []
    if not isinstance(value, list):
        raise APIError(f"{field} must be sent as a list.")
    if len(value) > max_items:
        raise APIError(f"You can attach up to {max_items} images per post.")
    return [
        decode_image_upload(item, field=f"{field} #{index}", max_bytes=max_bytes)
        for index, item in enumerate(value, start=1)
    ]


def store_image_upload(upload: dict[str, Any], *, bucket: str) -> str:
    if bucket not in MEDIA_FOLDERS:
        raise APIError("Upload destination is invalid.", HTTPStatus.INTERNAL_SERVER_ERROR)
    filename = f"{utc_now().strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(8)}.{upload['extension']}"
    path = MEDIA_FOLDERS[bucket] / filename
    path.write_bytes(upload["bytes"])
    return f"{bucket}/{filename}"


def serialize_post_media_row(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    payload = dict(row)
    return {
        "id": payload["id"],
        "url": media_url_for_path(payload.get("storage_path")),
        "mimeType": payload["mime_type"],
        "alt": payload.get("alt_text") or "Forum image",
        "width": payload.get("width") or 0,
        "height": payload.get("height") or 0,
    }


def list_post_media_rows(
    conn: sqlite3.Connection,
    post_ids: list[int],
) -> dict[int, list[sqlite3.Row]]:
    if not post_ids:
        return {}
    placeholders = ", ".join("?" for _ in post_ids)
    rows = conn.execute(
        f"""
        SELECT *
        FROM post_media
        WHERE post_id IN ({placeholders})
        ORDER BY post_id ASC, sort_order ASC, id ASC
        """,
        tuple(post_ids),
    ).fetchall()
    grouped = {post_id: [] for post_id in post_ids}
    for row in rows:
        grouped.setdefault(row["post_id"], []).append(row)
    return grouped


def list_post_media(
    conn: sqlite3.Connection,
    post_ids: list[int],
) -> dict[int, list[dict[str, Any]]]:
    grouped_rows = list_post_media_rows(conn, post_ids)
    return {
        post_id: [serialize_post_media_row(row) for row in rows]
        for post_id, rows in grouped_rows.items()
    }


def collect_post_media_paths(conn: sqlite3.Connection, post_ids: list[int]) -> list[str]:
    grouped_rows = list_post_media_rows(conn, post_ids)
    return [
        row["storage_path"]
        for rows in grouped_rows.values()
        for row in rows
        if row["storage_path"]
    ]


def save_post_media_entries(
    conn: sqlite3.Connection,
    *,
    post_id: int,
    uploads: list[dict[str, Any]],
    created_at: str,
    start_order: int = 0,
) -> None:
    for offset, upload in enumerate(uploads):
        storage_path = store_image_upload(upload, bucket="posts")
        conn.execute(
            """
            INSERT INTO post_media (
                post_id, storage_path, mime_type, alt_text, width, height, sort_order, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                post_id,
                storage_path,
                upload["mime_type"],
                upload["alt_text"],
                upload["width"],
                upload["height"],
                start_order + offset,
                created_at,
            ),
        )


def delete_post_media_files(conn: sqlite3.Connection, post_ids: list[int]) -> None:
    grouped_rows = list_post_media_rows(conn, post_ids)
    for rows in grouped_rows.values():
        for row in rows:
            delete_media_file(row["storage_path"])


def delete_post_artifact_rows(conn: sqlite3.Connection, post_ids: list[int]) -> None:
    if not post_ids:
        return
    placeholders = ", ".join("?" for _ in post_ids)
    params = tuple(post_ids)
    conn.execute(f"DELETE FROM post_media WHERE post_id IN ({placeholders})", params)
    conn.execute(f"DELETE FROM post_edits WHERE post_id IN ({placeholders})", params)
    conn.execute(f"DELETE FROM post_likes WHERE post_id IN ({placeholders})", params)
    conn.execute(f"DELETE FROM post_reactions WHERE post_id IN ({placeholders})", params)


def cleanup_orphan_post_artifacts(conn: sqlite3.Connection) -> dict[str, int]:
    orphan_media_rows = conn.execute(
        """
        SELECT pm.id, pm.storage_path
        FROM post_media pm
        LEFT JOIN posts p ON p.id = pm.post_id
        WHERE p.id IS NULL
        """
    ).fetchall()
    orphan_media_ids = [int(row["id"]) for row in orphan_media_rows]
    orphan_media_paths = [row["storage_path"] for row in orphan_media_rows if row["storage_path"]]
    deleted_counts = {
        "postMediaRows": len(orphan_media_ids),
        "postEditRows": 0,
        "postLikeRows": 0,
        "postReactionRows": 0,
    }
    if orphan_media_ids:
        conn.execute(
            f"DELETE FROM post_media WHERE id IN ({', '.join('?' for _ in orphan_media_ids)})",
            tuple(orphan_media_ids),
        )
    deleted_counts["postEditRows"] = conn.execute(
        """
        DELETE FROM post_edits
        WHERE post_id NOT IN (SELECT id FROM posts)
        """
    ).rowcount
    deleted_counts["postLikeRows"] = conn.execute(
        """
        DELETE FROM post_likes
        WHERE post_id NOT IN (SELECT id FROM posts)
        """
    ).rowcount
    deleted_counts["postReactionRows"] = conn.execute(
        """
        DELETE FROM post_reactions
        WHERE post_id NOT IN (SELECT id FROM posts)
        """
    ).rowcount
    conn.commit()
    for storage_path in orphan_media_paths:
        delete_media_file(storage_path)
    return deleted_counts


def can_view_shadow_content(viewer: dict[str, Any] | None, author_id: int | None) -> bool:
    return bool(viewer and (is_staff(viewer) or int(viewer["id"]) == int(author_id or 0)))


def is_shadow_hidden_to_viewer(
    *,
    hidden: Any,
    author_id: int | None,
    viewer: dict[str, Any] | None,
) -> bool:
    return bool(hidden) and not can_view_shadow_content(viewer, author_id)


def list_post_reactions_summary(
    conn: sqlite3.Connection,
    post_ids: list[int],
    viewer: dict[str, Any] | None,
) -> dict[int, dict[str, Any]]:
    if not post_ids:
        return {}
    placeholders = ", ".join("?" for _ in post_ids)
    rows = conn.execute(
        f"""
        SELECT post_id, emoji, COUNT(*) AS count
        FROM post_reactions
        WHERE post_id IN ({placeholders})
        GROUP BY post_id, emoji
        ORDER BY post_id ASC, count DESC, emoji ASC
        """,
        tuple(post_ids),
    ).fetchall()
    summary = {post_id: {"items": [], "viewer": []} for post_id in post_ids}
    for row in rows:
        summary.setdefault(row["post_id"], {"items": [], "viewer": []})["items"].append(
            {
                "emoji": row["emoji"],
                "count": row["count"],
            }
        )
    if viewer:
        viewer_rows = conn.execute(
            f"""
            SELECT post_id, emoji
            FROM post_reactions
            WHERE user_id = ? AND post_id IN ({placeholders})
            ORDER BY emoji ASC
            """,
            (viewer["id"], *post_ids),
        ).fetchall()
        for row in viewer_rows:
            summary.setdefault(row["post_id"], {"items": [], "viewer": []})["viewer"].append(row["emoji"])
    return summary


def create_thread_poll(
    conn: sqlite3.Connection,
    *,
    thread_id: int,
    poll: dict[str, Any],
    created_at: str,
) -> None:
    cur = conn.execute(
        """
        INSERT INTO thread_polls (thread_id, question, allows_multiple, is_closed, created_at, updated_at)
        VALUES (?, ?, ?, 0, ?, ?)
        """,
        (thread_id, poll["question"], int(bool(poll["allowsMultiple"])), created_at, created_at),
    )
    poll_id = cur.lastrowid
    for index, option in enumerate(poll["options"]):
        conn.execute(
            """
            INSERT INTO thread_poll_options (poll_id, option_text, sort_order)
            VALUES (?, ?, ?)
            """,
            (poll_id, option, index),
        )


def serialize_thread_poll(
    conn: sqlite3.Connection,
    thread_id: int,
    viewer: dict[str, Any] | None,
) -> dict[str, Any] | None:
    poll = conn.execute(
        "SELECT * FROM thread_polls WHERE thread_id = ?",
        (thread_id,),
    ).fetchone()
    if not poll:
        return None
    option_rows = conn.execute(
        """
        SELECT
            o.id,
            o.option_text,
            o.sort_order,
            COUNT(v.option_id) AS votes
        FROM thread_poll_options o
        LEFT JOIN thread_poll_votes v ON v.option_id = o.id
        WHERE o.poll_id = ?
        GROUP BY o.id, o.option_text, o.sort_order
        ORDER BY o.sort_order ASC, o.id ASC
        """,
        (poll["id"],),
    ).fetchall()
    viewer_votes: set[int] = set()
    if viewer:
        viewer_vote_rows = conn.execute(
            """
            SELECT option_id
            FROM thread_poll_votes
            WHERE poll_id = ? AND user_id = ?
            """,
            (poll["id"], viewer["id"]),
        ).fetchall()
        viewer_votes = {row["option_id"] for row in viewer_vote_rows}
    total_votes = sum(int(row["votes"] or 0) for row in option_rows)
    return {
        "question": poll["question"],
        "allowsMultiple": bool(poll["allows_multiple"]),
        "isClosed": bool(poll["is_closed"]),
        "totalVotes": total_votes,
        "hasVoted": bool(viewer_votes),
        "viewerVotes": list(viewer_votes),
        "options": [
            {
                "id": row["id"],
                "label": row["option_text"],
                "votes": row["votes"],
                "selectedByViewer": row["id"] in viewer_votes,
            }
            for row in option_rows
        ],
    }


def vote_in_thread_poll(
    conn: sqlite3.Connection,
    *,
    thread_id: int,
    viewer: dict[str, Any],
    option_ids: list[int],
) -> dict[str, Any]:
    poll = conn.execute(
        "SELECT * FROM thread_polls WHERE thread_id = ?",
        (thread_id,),
    ).fetchone()
    if not poll:
        raise APIError("This thread does not have an active poll.", HTTPStatus.NOT_FOUND)
    if poll["is_closed"]:
        raise APIError("This poll is closed.", HTTPStatus.FORBIDDEN)
    valid_rows = conn.execute(
        """
        SELECT id
        FROM thread_poll_options
        WHERE poll_id = ?
        ORDER BY sort_order ASC, id ASC
        """,
        (poll["id"],),
    ).fetchall()
    valid_option_ids = {row["id"] for row in valid_rows}
    if not option_ids or any(option_id not in valid_option_ids for option_id in option_ids):
        raise APIError("Choose one of the available poll options.")
    if not poll["allows_multiple"] and len(option_ids) > 1:
        raise APIError("This poll only allows one choice.")
    conn.execute(
        "DELETE FROM thread_poll_votes WHERE poll_id = ? AND user_id = ?",
        (poll["id"], viewer["id"]),
    )
    now = utc_iso()
    conn.executemany(
        """
        INSERT INTO thread_poll_votes (poll_id, option_id, user_id, created_at)
        VALUES (?, ?, ?, ?)
        """,
        [(poll["id"], option_id, viewer["id"], now) for option_id in option_ids],
    )
    conn.execute(
        "UPDATE thread_polls SET updated_at = ? WHERE id = ?",
        (now, poll["id"]),
    )
    conn.commit()
    return serialize_thread_poll(conn, thread_id, viewer)


def session_token_from_headers(headers: Any) -> str | None:
    cookie_header = headers.get("Cookie")
    if not cookie_header:
        return None
    cookie = SimpleCookie()
    cookie.load(cookie_header)
    session = cookie.get(SESSION_COOKIE)
    return session.value if session else None


def summarize_user_agent(user_agent: str | None) -> str:
    value = short_preview(user_agent or "", max_len=72)
    return value or "Unknown browser"


def recent_session_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "createdAt": row["created_at"],
        "expiresAt": row["expires_at"],
        "lastSeenAt": row["last_seen_at"] or row["created_at"],
        "ip": row["ip_address"] or row["last_seen_ip"] or "Unknown",
        "lastSeenIp": row["last_seen_ip"] or row["ip_address"] or "",
        "userAgent": summarize_user_agent(row["user_agent"]),
        "active": parse_iso(row["expires_at"]) > utc_now() if row["expires_at"] else False,
    }


def list_recent_sessions(
    conn: sqlite3.Connection,
    user_id: int,
    *,
    limit: int = 8,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT *
        FROM sessions
        WHERE user_id = ?
        ORDER BY COALESCE(last_seen_at, created_at) DESC, created_at DESC
        LIMIT ?
        """,
        (user_id, limit),
    ).fetchall()
    return [recent_session_payload(row) for row in rows]


def revoke_other_sessions(conn: sqlite3.Connection, user_id: int, keep_token: str | None) -> int:
    if keep_token:
        cur = conn.execute(
            "DELETE FROM sessions WHERE user_id = ? AND token != ?",
            (user_id, keep_token),
        )
    else:
        cur = conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    conn.commit()
    return cur.rowcount or 0


def current_user_from_request(
    conn: sqlite3.Connection,
    headers: Any,
    client_ip: str = "",
) -> dict[str, Any] | None:
    token = session_token_from_headers(headers)
    if not token:
        return None
    now = utc_iso()
    conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
    row = conn.execute(
        """
        SELECT u.*
        FROM sessions s
        JOIN users u ON u.id = s.user_id
        WHERE s.token = ? AND s.expires_at > ?
        """,
        (token, now),
    ).fetchone()
    if not row:
        return None
    user = sync_user_restrictions(conn, row)
    if not user:
        return None
    conn.execute(
        "UPDATE users SET last_seen_at = ?, updated_at = ? WHERE id = ?",
        (now, now, user["id"]),
    )
    conn.execute(
        """
        UPDATE sessions
        SET last_seen_at = ?, last_seen_ip = ?
        WHERE token = ?
        """,
        (now, client_ip or "", token),
    )
    conn.commit()
    user["last_seen_at"] = now
    user["updated_at"] = now
    return user


def create_session(
    conn: sqlite3.Connection,
    user_id: int,
    *,
    ip_address: str = "",
    user_agent: str = "",
) -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    created_at = utc_iso()
    expires_at = utc_iso(utc_now() + timedelta(days=SESSION_DAYS))
    conn.execute(
        """
        INSERT INTO sessions (
            token, user_id, created_at, expires_at,
            ip_address, user_agent, last_seen_at, last_seen_ip
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            token,
            user_id,
            created_at,
            expires_at,
            ip_address or "",
            user_agent or "",
            created_at,
            ip_address or "",
        ),
    )
    conn.commit()
    return token, expires_at


def delete_session(conn: sqlite3.Connection, token: str | None) -> None:
    if not token:
        return
    conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
    conn.commit()


def delete_sessions_for_user(conn: sqlite3.Connection, user_id: int) -> None:
    conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    conn.commit()


def set_auto_role(conn: sqlite3.Connection, user_id: int) -> None:
    row = conn.execute("SELECT role, xp FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row or row["role"] in {"mod", "admin", "owner"}:
        return
    new_role = "new"
    for role_name, threshold in AUTO_ROLES:
        if row["xp"] >= threshold:
            new_role = role_name
            break
    if new_role != row["role"]:
        now = utc_iso()
        conn.execute(
            "UPDATE users SET role = ?, updated_at = ? WHERE id = ?",
            (new_role, now, user_id),
        )
        conn.commit()


def award_xp(conn: sqlite3.Connection, user_id: int, delta: int) -> None:
    if delta == 0:
        return
    now = utc_iso()
    conn.execute(
        "UPDATE users SET xp = MAX(0, xp + ?), updated_at = ? WHERE id = ?",
        (delta, now, user_id),
    )
    conn.commit()
    set_auto_role(conn, user_id)


def clear_timeout_state(conn: sqlite3.Connection, user_id: int) -> None:
    conn.execute(
        """
        UPDATE users
        SET timeout_until = NULL, timeout_reason = '', timeout_set_by = NULL, updated_at = ?
        WHERE id = ?
        """,
        (utc_iso(), user_id),
    )
    conn.commit()


def sync_user_restrictions(
    conn: sqlite3.Connection,
    row: sqlite3.Row | dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not row:
        return None
    payload = dict(row)
    timeout_until = parse_iso(payload.get("timeout_until"))
    if timeout_until and timeout_until <= utc_now():
        clear_timeout_state(conn, payload["id"])
        payload["timeout_until"] = None
        payload["timeout_reason"] = ""
        payload["timeout_set_by"] = None
    mute_until = parse_iso(payload.get("mute_until"))
    if mute_until and mute_until <= utc_now():
        conn.execute(
            """
            UPDATE users
            SET mute_until = NULL, mute_reason = '', mute_set_by = NULL, updated_at = ?
            WHERE id = ?
            """,
            (utc_iso(), payload["id"]),
        )
        conn.commit()
        payload["mute_until"] = None
        payload["mute_reason"] = ""
        payload["mute_set_by"] = None
    return payload


def is_banned_user(row: sqlite3.Row | dict[str, Any] | None) -> bool:
    return bool(row and dict(row).get("banned_at"))


def active_timeout_until(row: sqlite3.Row | dict[str, Any] | None) -> datetime | None:
    if not row:
        return None
    timeout_until = parse_iso(dict(row).get("timeout_until"))
    if not timeout_until or timeout_until <= utc_now():
        return None
    return timeout_until


def active_mute_until(row: sqlite3.Row | dict[str, Any] | None) -> datetime | None:
    if not row:
        return None
    mute_until = parse_iso(dict(row).get("mute_until"))
    if not mute_until or mute_until <= utc_now():
        return None
    return mute_until


def is_shadow_muted(row: sqlite3.Row | dict[str, Any] | None) -> bool:
    return bool(row and dict(row).get("shadow_muted"))


def ensure_can_participate(viewer: dict[str, Any] | None) -> None:
    if not viewer:
        raise APIError("You must be logged in.", HTTPStatus.UNAUTHORIZED)
    if is_banned_user(viewer):
        reason = str(viewer.get("ban_reason") or "").strip()
        detail = f" Reason: {reason.rstrip('.!?')}" if reason else ""
        raise APIError(f"This account is banned.{detail}", HTTPStatus.FORBIDDEN)
    if bool(viewer.get("password_reset_required")):
        raise APIError(
            "You need to reset your password before using the forum.",
            HTTPStatus.FORBIDDEN,
        )
    timeout_until = active_timeout_until(viewer)
    if timeout_until:
        detail = f" until {utc_iso(timeout_until)}"
        reason = str(viewer.get("timeout_reason") or "").strip()
        if reason:
            detail += f". Reason: {reason.rstrip('.!?')}"
        raise APIError(f"Your account is timed out{detail}.", HTTPStatus.FORBIDDEN)


def ensure_can_post_content(viewer: dict[str, Any] | None) -> None:
    ensure_can_participate(viewer)
    mute_until = active_mute_until(viewer)
    if mute_until:
        detail = f" until {utc_iso(mute_until)}"
        reason = str(viewer.get("mute_reason") or "").strip()
        if reason:
            detail += f". Reason: {reason.rstrip('.!?')}"
        raise APIError(f"Your account is muted from posting{detail}.", HTTPStatus.FORBIDDEN)


def ensure_can_send_message(viewer: dict[str, Any] | None) -> None:
    ensure_can_participate(viewer)
    mute_until = active_mute_until(viewer)
    if mute_until:
        raise APIError("Your account is currently muted from sending messages.", HTTPStatus.FORBIDDEN)


def scaled_cooldown_seconds(viewer: dict[str, Any] | None, base_seconds: int) -> int:
    if not viewer:
        return base_seconds
    level = role_level(viewer["role"])
    if level >= role_level("veteran"):
        return 0
    if level >= role_level("member"):
        return max(2, base_seconds // 2)
    return base_seconds


def enforce_recent_action_limit(
    conn: sqlite3.Connection,
    viewer: dict[str, Any] | None,
    *,
    query: str,
    params: tuple[Any, ...],
    base_seconds: int,
    verb: str,
) -> None:
    cooldown = scaled_cooldown_seconds(viewer, base_seconds)
    if cooldown <= 0:
        return
    row = conn.execute(query, params).fetchone()
    last_at = parse_iso(row["created_at"]) if row and row["created_at"] else None
    if not last_at:
        return
    wait_until = last_at + timedelta(seconds=cooldown)
    if wait_until <= utc_now():
        return
    remaining = max(1, math.ceil((wait_until - utc_now()).total_seconds()))
    raise APIError(
        f"Slow down a little. You can {verb} again in about {remaining}s.",
        HTTPStatus.TOO_MANY_REQUESTS,
    )


def user_prefers_notification(conn: sqlite3.Connection, user_id: int, kind: str) -> bool:
    column = NOTIFICATION_PREFERENCE_COLUMNS.get(kind)
    if not column:
        return True
    row = conn.execute(
        f"SELECT {column} AS enabled FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    return bool(row and row["enabled"])


def can_receive_direct_message(
    recipient: sqlite3.Row | dict[str, Any] | None,
    sender: dict[str, Any] | None,
) -> bool:
    if not recipient or not sender:
        return False
    if sender["id"] == dict(recipient)["id"]:
        return False
    if is_staff(sender):
        return True
    privacy = str(dict(recipient).get("dm_privacy") or "everyone")
    if privacy == "disabled":
        return False
    if privacy == "staff_only":
        return False
    if privacy == "members":
        return role_level(sender["role"]) >= role_level("member")
    return True


def log_moderation_action(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    actor_id: int,
    action_type: str,
    reason: str = "",
    note: str = "",
    delta_xp: int = 0,
    expires_at: str | None = None,
    metadata: dict[str, Any] | None = None,
    created_at: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO moderation_actions (
            user_id, actor_id, action_type, reason, note, delta_xp,
            expires_at, created_at, metadata_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            actor_id,
            action_type,
            reason,
            note,
            delta_xp,
            expires_at,
            created_at or utc_iso(),
            json.dumps(metadata or {}),
        ),
    )


def serialize_moderation_action(row: sqlite3.Row) -> dict[str, Any]:
    try:
        metadata = json.loads(row["metadata_json"] or "{}")
    except json.JSONDecodeError:
        metadata = {}
    return {
        "id": row["id"],
        "type": row["action_type"],
        "reason": row["reason"] or "",
        "note": row["note"] or "",
        "deltaXp": row["delta_xp"] or 0,
        "expiresAt": row["expires_at"],
        "createdAt": row["created_at"],
        "metadata": metadata,
        "actor": {
            "id": row["actor_id"],
            "username": row["actor_username"],
            "role": row["actor_role"],
        },
    }


def list_user_moderation_actions(
    conn: sqlite3.Connection,
    user_id: int,
    *,
    limit: int = 16,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            ma.*,
            actor.username AS actor_username,
            actor.role AS actor_role
        FROM moderation_actions ma
        JOIN users actor ON actor.id = ma.actor_id
        WHERE ma.user_id = ?
        ORDER BY ma.created_at DESC, ma.id DESC
        LIMIT ?
        """,
        (user_id, limit),
    ).fetchall()
    return [serialize_moderation_action(row) for row in rows]


def serialize_user_moderation(row: dict[str, Any]) -> dict[str, Any]:
    timeout_until = active_timeout_until(row)
    mute_until = active_mute_until(row)
    return {
        "isBanned": bool(row.get("banned_at")),
        "bannedAt": row.get("banned_at"),
        "banReason": row.get("ban_reason") or "",
        "bannedBy": (
            {
                "id": row.get("banned_by"),
                "username": row.get("banned_by_username"),
            }
            if row.get("banned_by") and row.get("banned_by_username")
            else None
        ),
        "isTimedOut": bool(timeout_until),
        "timeoutUntil": utc_iso(timeout_until) if timeout_until else None,
        "timeoutReason": row.get("timeout_reason") or "",
        "timeoutBy": (
            {
                "id": row.get("timeout_set_by"),
                "username": row.get("timeout_by_username"),
            }
            if row.get("timeout_set_by") and row.get("timeout_by_username")
            else None
        ),
        "isMuted": bool(mute_until),
        "muteUntil": utc_iso(mute_until) if mute_until else None,
        "muteReason": row.get("mute_reason") or "",
        "muteBy": (
            {
                "id": row.get("mute_set_by"),
                "username": row.get("mute_by_username"),
            }
            if row.get("mute_set_by") and row.get("mute_by_username")
            else None
        ),
        "isShadowMuted": bool(row.get("shadow_muted")),
        "passwordResetRequired": bool(row.get("password_reset_required")),
        "passwordResetSetAt": row.get("password_reset_set_at"),
        "passwordResetBy": (
            {
                "id": row.get("password_reset_set_by"),
                "username": row.get("password_reset_by_username"),
            }
            if row.get("password_reset_set_by") and row.get("password_reset_by_username")
            else None
        ),
    }


def thread_first_post_id(conn: sqlite3.Connection, thread_id: int) -> int | None:
    row = conn.execute(
        "SELECT id FROM posts WHERE thread_id = ? ORDER BY id ASC LIMIT 1",
        (thread_id,),
    ).fetchone()
    return row["id"] if row else None


def thread_user_flags(
    conn: sqlite3.Connection,
    thread_id: int,
    viewer: dict[str, Any] | None,
) -> dict[str, bool]:
    if not viewer:
        return {"bookmarked": False, "subscribed": False}
    row = conn.execute(
        """
        SELECT
            EXISTS(
                SELECT 1 FROM thread_bookmarks tb
                WHERE tb.thread_id = ? AND tb.user_id = ?
            ) AS bookmarked,
            EXISTS(
                SELECT 1 FROM thread_subscriptions ts
                WHERE ts.thread_id = ? AND ts.user_id = ?
            ) AS subscribed
        """,
        (thread_id, viewer["id"], thread_id, viewer["id"]),
    ).fetchone()
    return {
        "bookmarked": bool(row and row["bookmarked"]),
        "subscribed": bool(row and row["subscribed"]),
    }


def ensure_thread_subscription(
    conn: sqlite3.Connection,
    *,
    thread_id: int,
    user_id: int,
    created_at: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO thread_subscriptions (thread_id, user_id, created_at)
        VALUES (?, ?, ?)
        """,
        (thread_id, user_id, created_at or utc_iso()),
    )


def toggle_thread_membership(
    conn: sqlite3.Connection,
    *,
    table: str,
    thread_id: int,
    user_id: int,
) -> bool:
    existing = conn.execute(
        f"SELECT 1 FROM {table} WHERE thread_id = ? AND user_id = ?",
        (thread_id, user_id),
    ).fetchone()
    if existing:
        conn.execute(
            f"DELETE FROM {table} WHERE thread_id = ? AND user_id = ?",
            (thread_id, user_id),
        )
        conn.commit()
        return False
    conn.execute(
        f"INSERT INTO {table} (thread_id, user_id, created_at) VALUES (?, ?, ?)",
        (thread_id, user_id, utc_iso()),
    )
    conn.commit()
    return True


def list_saved_threads(
    conn: sqlite3.Connection,
    *,
    table: str,
    user_id: int,
    viewer: dict[str, Any] | None,
    limit: int = 8,
) -> list[dict[str, Any]]:
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
            u.username AS author_name,
            u.role AS author_role,
            u.avatar_path AS author_avatar_path,
            x.created_at AS saved_at
        FROM {table} x
        JOIN threads t ON t.id = x.thread_id
        JOIN sections s ON s.id = t.section_id
        JOIN users u ON u.id = t.author_id
        WHERE x.user_id = ?
        ORDER BY x.created_at DESC, x.thread_id DESC
        LIMIT ?
        """,
        (user_id, limit * 3),
    ).fetchall()
    output: list[dict[str, Any]] = []
    for row in rows:
        if not has_required_role(viewer, row["section_required_role"]):
            continue
        if is_shadow_hidden_to_viewer(hidden=row["shadow_hidden"], author_id=row["author_id"], viewer=viewer):
            continue
        item = serialize_thread(row, conn, viewer)
        item["savedAt"] = row["saved_at"]
        output.append(item)
        if len(output) >= limit:
            break
    return output


def get_user_profile(
    conn: sqlite3.Connection,
    user_id: int,
    *,
    viewer: dict[str, Any] | None = None,
    include_detail: bool = True,
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT
            u.*,
            timeout_actor.username AS timeout_by_username,
            mute_actor.username AS mute_by_username,
            ban_actor.username AS banned_by_username,
            reset_actor.username AS password_reset_by_username,
            (SELECT COUNT(*) FROM posts p WHERE p.author_id = u.id) AS posts_count,
            (SELECT COUNT(*) FROM threads t WHERE t.author_id = u.id) AS threads_count,
            (SELECT COUNT(*) FROM post_likes pl
             JOIN posts p2 ON p2.id = pl.post_id
             WHERE p2.author_id = u.id) AS likes_received
        FROM users u
        LEFT JOIN users timeout_actor ON timeout_actor.id = u.timeout_set_by
        LEFT JOIN users mute_actor ON mute_actor.id = u.mute_set_by
        LEFT JOIN users ban_actor ON ban_actor.id = u.banned_by
        LEFT JOIN users reset_actor ON reset_actor.id = u.password_reset_set_by
        WHERE u.id = ?
        """,
        (user_id,),
    ).fetchone()
    if not row:
        return None
    resolved = sync_user_restrictions(conn, row)
    if not resolved:
        return None
    profile = serialize_user(resolved)
    profile["noticeCount"] = (
        get_open_contact_notice_count(conn)
        if role_level(resolved["role"]) >= role_level("mod")
        else 0
    )
    profile["reportCount"] = (
        get_open_report_count(conn)
        if role_level(resolved["role"]) >= role_level("mod")
        else 0
    )
    profile["canMessage"] = bool(viewer and viewer["id"] != user_id)
    if viewer and viewer["id"] == user_id:
        profile["mustResetPassword"] = bool(resolved.get("password_reset_required"))
        profile["messageCount"] = get_unread_dm_count(conn, user_id)
        profile["notificationCount"] = get_unread_notification_count(conn, user_id)
        profile["appealCount"] = conn.execute(
            "SELECT COUNT(*) AS count FROM appeals WHERE status = 'open'"
        ).fetchone()["count"] if is_staff(viewer) else 0
        profile["preferences"] = {
            "siteTheme": resolved.get("site_theme") or "midnight",
            "dmPrivacy": resolved.get("dm_privacy") or "everyone",
            "notifyReplies": bool(resolved.get("notify_replies", 1)),
            "notifyLikes": bool(resolved.get("notify_likes", 1)),
            "notifyMentions": bool(resolved.get("notify_mentions", 1)),
            "notifyDms": bool(resolved.get("notify_dms", 1)),
        }
        profile["community"] = {
            "signature": resolved.get("signature") or "",
            "profileBadge": resolved.get("profile_badge") or "",
            "profileAccent": resolved.get("profile_accent") or "",
        }
        if include_detail:
            profile["recentSessions"] = list_recent_sessions(conn, user_id)
            profile["library"] = {
                "bookmarks": list_saved_threads(
                    conn,
                    table="thread_bookmarks",
                    user_id=user_id,
                    viewer=viewer,
                ),
                "subscriptions": list_saved_threads(
                    conn,
                    table="thread_subscriptions",
                    user_id=user_id,
                    viewer=viewer,
                ),
            }
    if viewer and (viewer["id"] == user_id or is_staff(viewer)):
        profile["moderation"] = serialize_user_moderation(resolved)
    if viewer and viewer["id"] == user_id and include_detail and (
        is_banned_user(resolved) or active_timeout_until(resolved) or active_mute_until(resolved)
    ):
        profile["appeals"] = list_appeals_for_viewer(conn, viewer, status="all")
    if viewer and include_detail and (viewer["id"] == user_id or is_staff(viewer)):
        profile["sessionAudit"] = list_recent_sessions(conn, user_id)
    if viewer and is_staff(viewer):
        if include_detail:
            profile["moderationHistory"] = list_user_moderation_actions(conn, user_id)
            profile["appeals"] = list_appeals_for_viewer(conn, viewer, status="all", target_user_id=user_id)
        profile["canModerate"] = can_moderate_user(viewer, resolved)
        profile["canManageRole"] = can_manage_user(viewer, resolved["role"]) and viewer["id"] != user_id
        profile["canIssueTempPassword"] = is_admin(viewer) and can_moderate_user(viewer, resolved)
    return profile


def serialize_user(row: dict[str, Any]) -> dict[str, Any]:
    last_seen = parse_iso(row.get("last_seen_at"))
    online_threshold = utc_now() - timedelta(minutes=ONLINE_WINDOW_MINUTES)
    return {
        "id": row["id"],
        "username": row["username"],
        "role": row["role"],
        "bio": row.get("bio") or "",
        "avatarUrl": media_url_for_path(row.get("avatar_path")),
        "signature": row.get("signature") or "",
        "profileBadge": row.get("profile_badge") or "",
        "profileAccent": row.get("profile_accent") or "",
        "xp": row.get("xp", 0),
        "posts": row.get("posts_count", 0),
        "threads": row.get("threads_count", 0),
        "likesReceived": row.get("likes_received", 0),
        "joined": row["created_at"],
        "online": bool(last_seen and last_seen >= online_threshold),
    }


def get_top_members(conn: sqlite3.Connection, limit: int = 5) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            u.*,
            (SELECT COUNT(*) FROM posts p WHERE p.author_id = u.id) AS posts_count,
            (SELECT COUNT(*) FROM threads t WHERE t.author_id = u.id) AS threads_count,
            (SELECT COUNT(*) FROM post_likes pl
             JOIN posts p2 ON p2.id = pl.post_id
             WHERE p2.author_id = u.id) AS likes_received
        FROM users u
        ORDER BY posts_count DESC, u.xp DESC, u.created_at ASC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [serialize_user(dict(row)) for row in rows]


def list_members(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            u.*,
            (SELECT COUNT(*) FROM posts p WHERE p.author_id = u.id) AS posts_count,
            (SELECT COUNT(*) FROM threads t WHERE t.author_id = u.id) AS threads_count,
            (SELECT COUNT(*) FROM post_likes pl
             JOIN posts p2 ON p2.id = pl.post_id
             WHERE p2.author_id = u.id) AS likes_received
        FROM users u
        ORDER BY u.created_at DESC
        """
    ).fetchall()
    return [serialize_user(dict(row)) for row in rows]


def get_role_breakdown(conn: sqlite3.Connection) -> dict[str, int]:
    counts = {role: 0 for role in ROLES}
    rows = conn.execute("SELECT role, COUNT(*) AS count FROM users GROUP BY role").fetchall()
    for row in rows:
        counts[row["role"]] = row["count"]
    return counts


def get_open_contact_notice_count(conn: sqlite3.Connection) -> int:
    return conn.execute(
        "SELECT COUNT(*) AS count FROM contact_submissions WHERE status = 'open'"
    ).fetchone()["count"]


def normalize_dm_pair(user_a: int, user_b: int) -> tuple[int, int]:
    return (user_a, user_b) if user_a < user_b else (user_b, user_a)


def get_unread_dm_count(conn: sqlite3.Connection, user_id: int) -> int:
    return conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM dm_messages
        WHERE recipient_id = ? AND read_at IS NULL
        """,
        (user_id,),
    ).fetchone()["count"]


def serialize_dm_user_from_row(row: sqlite3.Row, prefix: str) -> dict[str, Any]:
    return serialize_user(
        {
            "id": row[f"{prefix}_id"],
            "username": row[f"{prefix}_username"],
            "role": row[f"{prefix}_role"],
            "bio": row[f"{prefix}_bio"] or "",
            "avatar_path": row[f"{prefix}_avatar_path"] or "",
            "xp": row[f"{prefix}_xp"] or 0,
            "created_at": row[f"{prefix}_created_at"],
            "last_seen_at": row[f"{prefix}_last_seen_at"],
            "posts_count": 0,
            "threads_count": 0,
            "likes_received": 0,
        }
    )


def serialize_dm_thread_summary(row: sqlite3.Row, viewer_id: int) -> dict[str, Any]:
    low_user = serialize_dm_user_from_row(row, "low")
    high_user = serialize_dm_user_from_row(row, "high")
    other_user = high_user if row["user_low_id"] == viewer_id else low_user
    last_content = row["last_message_content"] or ""
    preview = re.sub(r"\s+", " ", last_content).strip()
    if len(preview) > 140:
        preview = f"{preview[:137]}..."
    return {
        "id": row["id"],
        "updatedAt": row["updated_at"],
        "lastMessageAt": row["last_message_at"],
        "unreadCount": row["unread_count"] or 0,
        "otherUser": other_user,
        "lastMessage": (
            {
                "content": preview,
                "createdAt": row["last_message_created_at"],
                "senderId": row["last_message_sender_id"],
                "fromViewer": row["last_message_sender_id"] == viewer_id,
            }
            if row["last_message_created_at"]
            else None
        ),
    }


def list_dm_threads(
    conn: sqlite3.Connection,
    viewer_id: int,
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            dt.*,
            low_user.id AS low_id,
            low_user.username AS low_username,
            low_user.role AS low_role,
            low_user.bio AS low_bio,
            low_user.avatar_path AS low_avatar_path,
            low_user.xp AS low_xp,
            low_user.created_at AS low_created_at,
            low_user.last_seen_at AS low_last_seen_at,
            high_user.id AS high_id,
            high_user.username AS high_username,
            high_user.role AS high_role,
            high_user.bio AS high_bio,
            high_user.avatar_path AS high_avatar_path,
            high_user.xp AS high_xp,
            high_user.created_at AS high_created_at,
            high_user.last_seen_at AS high_last_seen_at,
            (SELECT COUNT(*)
             FROM dm_messages dm_unread
             WHERE dm_unread.thread_id = dt.id
               AND dm_unread.recipient_id = ?
               AND dm_unread.read_at IS NULL) AS unread_count,
            (SELECT dm_last.content
             FROM dm_messages dm_last
             WHERE dm_last.thread_id = dt.id
             ORDER BY dm_last.created_at DESC, dm_last.id DESC
             LIMIT 1) AS last_message_content,
            (SELECT dm_last.created_at
             FROM dm_messages dm_last
             WHERE dm_last.thread_id = dt.id
             ORDER BY dm_last.created_at DESC, dm_last.id DESC
             LIMIT 1) AS last_message_created_at,
            (SELECT dm_last.sender_id
             FROM dm_messages dm_last
             WHERE dm_last.thread_id = dt.id
             ORDER BY dm_last.created_at DESC, dm_last.id DESC
             LIMIT 1) AS last_message_sender_id
        FROM dm_threads dt
        JOIN users low_user ON low_user.id = dt.user_low_id
        JOIN users high_user ON high_user.id = dt.user_high_id
        WHERE dt.user_low_id = ? OR dt.user_high_id = ?
        ORDER BY dt.last_message_at DESC, dt.id DESC
        LIMIT ?
        """,
        (viewer_id, viewer_id, viewer_id, limit),
    ).fetchall()
    return [serialize_dm_thread_summary(row, viewer_id) for row in rows]


def get_dm_thread_summary(
    conn: sqlite3.Connection,
    thread_id: int,
    viewer_id: int,
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT
            dt.*,
            low_user.id AS low_id,
            low_user.username AS low_username,
            low_user.role AS low_role,
            low_user.bio AS low_bio,
            low_user.avatar_path AS low_avatar_path,
            low_user.xp AS low_xp,
            low_user.created_at AS low_created_at,
            low_user.last_seen_at AS low_last_seen_at,
            high_user.id AS high_id,
            high_user.username AS high_username,
            high_user.role AS high_role,
            high_user.bio AS high_bio,
            high_user.avatar_path AS high_avatar_path,
            high_user.xp AS high_xp,
            high_user.created_at AS high_created_at,
            high_user.last_seen_at AS high_last_seen_at,
            (SELECT COUNT(*)
             FROM dm_messages dm_unread
             WHERE dm_unread.thread_id = dt.id
               AND dm_unread.recipient_id = ?
               AND dm_unread.read_at IS NULL) AS unread_count,
            (SELECT dm_last.content
             FROM dm_messages dm_last
             WHERE dm_last.thread_id = dt.id
             ORDER BY dm_last.created_at DESC, dm_last.id DESC
             LIMIT 1) AS last_message_content,
            (SELECT dm_last.created_at
             FROM dm_messages dm_last
             WHERE dm_last.thread_id = dt.id
             ORDER BY dm_last.created_at DESC, dm_last.id DESC
             LIMIT 1) AS last_message_created_at,
            (SELECT dm_last.sender_id
             FROM dm_messages dm_last
             WHERE dm_last.thread_id = dt.id
             ORDER BY dm_last.created_at DESC, dm_last.id DESC
             LIMIT 1) AS last_message_sender_id
        FROM dm_threads dt
        JOIN users low_user ON low_user.id = dt.user_low_id
        JOIN users high_user ON high_user.id = dt.user_high_id
        WHERE dt.id = ? AND (dt.user_low_id = ? OR dt.user_high_id = ?)
        """,
        (viewer_id, thread_id, viewer_id, viewer_id),
    ).fetchone()
    if not row:
        return None
    return serialize_dm_thread_summary(row, viewer_id)


def get_or_create_dm_thread(conn: sqlite3.Connection, user_a: int, user_b: int) -> int:
    user_low_id, user_high_id = normalize_dm_pair(user_a, user_b)
    row = conn.execute(
        """
        SELECT id
        FROM dm_threads
        WHERE user_low_id = ? AND user_high_id = ?
        """,
        (user_low_id, user_high_id),
    ).fetchone()
    if row:
        return row["id"]
    now = utc_iso()
    cur = conn.execute(
        """
        INSERT INTO dm_threads (
            user_low_id, user_high_id, created_at, updated_at, last_message_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_low_id, user_high_id, now, now, now),
    )
    return cur.lastrowid


def add_dm_message(
    conn: sqlite3.Connection,
    *,
    thread_id: int,
    sender_id: int,
    recipient_id: int,
    content: str,
    created_at: str | None = None,
) -> int:
    now = created_at or utc_iso()
    cur = conn.execute(
        """
        INSERT INTO dm_messages (
            thread_id, sender_id, recipient_id, content, created_at, updated_at, read_at
        )
        VALUES (?, ?, ?, ?, ?, ?, NULL)
        """,
        (thread_id, sender_id, recipient_id, content, now, now),
    )
    conn.execute(
        """
        UPDATE dm_threads
        SET updated_at = ?, last_message_at = ?
        WHERE id = ?
        """,
        (now, now, thread_id),
    )
    return cur.lastrowid


def mark_dm_thread_read(conn: sqlite3.Connection, thread_id: int, viewer_id: int) -> bool:
    unread = conn.execute(
        """
        SELECT id
        FROM dm_messages
        WHERE thread_id = ? AND recipient_id = ? AND read_at IS NULL
        LIMIT 1
        """,
        (thread_id, viewer_id),
    ).fetchone()
    if not unread:
        return False
    now = utc_iso()
    conn.execute(
        """
        UPDATE dm_messages
        SET read_at = ?, updated_at = ?
        WHERE thread_id = ? AND recipient_id = ? AND read_at IS NULL
        """,
        (now, now, thread_id, viewer_id),
    )
    return True


def list_dm_messages(
    conn: sqlite3.Connection,
    thread_id: int,
    viewer_id: int,
    *,
    limit: int = 200,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            dm.*,
            sender.username AS sender_username,
            sender.role AS sender_role,
            sender.bio AS sender_bio,
            sender.avatar_path AS sender_avatar_path,
            sender.xp AS sender_xp,
            sender.created_at AS sender_created_at,
            sender.last_seen_at AS sender_last_seen_at
        FROM dm_messages dm
        JOIN users sender ON sender.id = dm.sender_id
        WHERE dm.thread_id = ?
        ORDER BY dm.created_at ASC, dm.id ASC
        LIMIT ?
        """,
        (thread_id, limit),
    ).fetchall()
    return [
        {
            "id": row["id"],
            "content": row["content"],
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
            "readAt": row["read_at"],
            "isMine": row["sender_id"] == viewer_id,
            "sender": serialize_user(
                {
                    "id": row["sender_id"],
                    "username": row["sender_username"],
                    "role": row["sender_role"],
                    "bio": row["sender_bio"] or "",
                    "avatar_path": row["sender_avatar_path"] or "",
                    "xp": row["sender_xp"] or 0,
                    "created_at": row["sender_created_at"],
                    "last_seen_at": row["sender_last_seen_at"],
                    "posts_count": 0,
                    "threads_count": 0,
                    "likes_received": 0,
                }
            ),
        }
        for row in rows
    ]


def short_preview(text: Any, *, max_len: int = 180) -> str:
    preview = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(preview) <= max_len:
        return preview
    return f"{preview[: max_len - 3].rstrip()}..."


def extract_mentioned_users(
    conn: sqlite3.Connection,
    text: Any,
    *,
    exclude_user_ids: set[int] | None = None,
) -> list[dict[str, Any]]:
    exclude = exclude_user_ids or set()
    usernames: list[str] = []
    for match in MENTION_PATTERN.findall(str(text or "")):
        normalized = match.strip().lower()
        if normalized and normalized not in usernames:
            usernames.append(normalized)
    users: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    for username in usernames:
        row = conn.execute(
            "SELECT * FROM users WHERE lower(username) = ?",
            (username,),
        ).fetchone()
        resolved = sync_user_restrictions(conn, row)
        if not resolved:
            continue
        user_id = int(resolved["id"])
        if user_id in exclude or user_id in seen_ids:
            continue
        seen_ids.add(user_id)
        users.append(resolved)
    return users


def create_notification(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    actor_id: int | None,
    kind: str,
    title: str,
    body: str = "",
    target_type: str = "",
    target_id: int | None = None,
    metadata: dict[str, Any] | None = None,
    created_at: str | None = None,
) -> None:
    if actor_id and actor_id == user_id:
        return
    if not user_prefers_notification(conn, user_id, kind):
        return
    conn.execute(
        """
        INSERT INTO notifications (
            user_id, actor_id, kind, title, body, target_type,
            target_id, metadata_json, read_at, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)
        """,
        (
            user_id,
            actor_id,
            kind,
            title,
            body,
            target_type,
            target_id,
            json.dumps(metadata or {}),
            created_at or utc_iso(),
        ),
    )


def create_staff_notifications(
    conn: sqlite3.Connection,
    *,
    actor_id: int | None,
    title: str,
    body: str = "",
    target_type: str = "",
    target_id: int | None = None,
    metadata: dict[str, Any] | None = None,
    created_at: str | None = None,
) -> None:
    rows = conn.execute(
        "SELECT id FROM users WHERE role IN ('mod', 'admin', 'owner')"
    ).fetchall()
    for row in rows:
        create_notification(
            conn,
            user_id=row["id"],
            actor_id=actor_id,
            kind="staff_alert",
            title=title,
            body=body,
            target_type=target_type,
            target_id=target_id,
            metadata=metadata,
            created_at=created_at,
        )


def get_unread_notification_count(conn: sqlite3.Connection, user_id: int) -> int:
    return conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM notifications
        WHERE user_id = ? AND read_at IS NULL
        """,
        (user_id,),
    ).fetchone()["count"]


def serialize_notification(row: sqlite3.Row) -> dict[str, Any]:
    try:
        metadata = json.loads(row["metadata_json"] or "{}")
    except json.JSONDecodeError:
        metadata = {}
    return {
        "id": row["id"],
        "kind": row["kind"],
        "title": row["title"],
        "body": row["body"] or "",
        "targetType": row["target_type"] or "",
        "targetId": row["target_id"],
        "metadata": metadata,
        "readAt": row["read_at"],
        "createdAt": row["created_at"],
        "actor": (
            {
                "id": row["actor_id"],
                "username": row["actor_username"],
                "role": row["actor_role"],
            }
            if row["actor_id"] and row["actor_username"]
            else None
        ),
    }


def list_notifications(
    conn: sqlite3.Connection,
    user_id: int,
    *,
    status: str = "all",
    limit: int = 60,
) -> list[dict[str, Any]]:
    params: list[Any] = [user_id]
    where = "WHERE n.user_id = ?"
    if status == "unread":
        where += " AND n.read_at IS NULL"
    rows = conn.execute(
        f"""
        SELECT
            n.*,
            actor.username AS actor_username,
            actor.role AS actor_role
        FROM notifications n
        LEFT JOIN users actor ON actor.id = n.actor_id
        {where}
        ORDER BY n.created_at DESC, n.id DESC
        LIMIT ?
        """,
        (*params, limit),
    ).fetchall()
    return [serialize_notification(row) for row in rows]


def mark_notifications_read(
    conn: sqlite3.Connection,
    user_id: int,
    *,
    notification_ids: list[int] | None = None,
    target_type: str | None = None,
    target_id: int | None = None,
) -> int:
    clauses = ["user_id = ?", "read_at IS NULL"]
    params: list[Any] = [user_id]
    if notification_ids:
        placeholders = ", ".join("?" for _ in notification_ids)
        clauses.append(f"id IN ({placeholders})")
        params.extend(notification_ids)
    if target_type is not None:
        clauses.append("target_type = ?")
        params.append(target_type)
    if target_id is not None:
        clauses.append("target_id = ?")
        params.append(target_id)
    now = utc_iso()
    cur = conn.execute(
        f"""
        UPDATE notifications
        SET read_at = ?
        WHERE {" AND ".join(clauses)}
        """,
        (now, *params),
    )
    return cur.rowcount or 0


def get_open_report_count(conn: sqlite3.Connection) -> int:
    return conn.execute(
        "SELECT COUNT(*) AS count FROM reports WHERE status = 'open'"
    ).fetchone()["count"]


def get_open_appeal_count(conn: sqlite3.Connection) -> int:
    return conn.execute(
        "SELECT COUNT(*) AS count FROM appeals WHERE status = 'open'"
    ).fetchone()["count"]


def resolve_report_target(
    conn: sqlite3.Connection,
    target_type: str,
    target_id: int,
    *,
    viewer: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if target_type == "thread":
        thread = get_thread_by_id(conn, target_id)
        if not thread:
            raise APIError("Thread not found.", HTTPStatus.NOT_FOUND)
        if not has_required_role(viewer, thread["section_required_role"]):
            raise APIError("You do not have access to that thread.", HTTPStatus.FORBIDDEN)
        return {
            "type": "thread",
            "id": target_id,
            "label": thread["title"],
            "preview": f"In {thread['section_name']} · started by {thread['author_name']}",
            "contextThreadId": target_id,
        }
    if target_type == "post":
        row = conn.execute(
            """
            SELECT
                p.id,
                p.content,
                p.thread_id,
                t.title AS thread_title,
                s.required_role AS section_required_role,
                u.username AS author_name
            FROM posts p
            JOIN threads t ON t.id = p.thread_id
            JOIN sections s ON s.id = t.section_id
            JOIN users u ON u.id = p.author_id
            WHERE p.id = ?
            """,
            (target_id,),
        ).fetchone()
        if not row:
            raise APIError("Post not found.", HTTPStatus.NOT_FOUND)
        if not has_required_role(viewer, row["section_required_role"]):
            raise APIError("You do not have access to that post.", HTTPStatus.FORBIDDEN)
        return {
            "type": "post",
            "id": target_id,
            "label": f"Post by {row['author_name']}",
            "preview": short_preview(row["content"]),
            "contextThreadId": row["thread_id"],
            "threadTitle": row["thread_title"],
        }
    if target_type == "user":
        row = conn.execute(
            "SELECT * FROM users WHERE id = ?",
            (target_id,),
        ).fetchone()
        resolved = sync_user_restrictions(conn, row)
        if not resolved:
            raise APIError("User not found.", HTTPStatus.NOT_FOUND)
        role = ROLES.get(resolved["role"], ROLES["new"])
        return {
            "type": "user",
            "id": target_id,
            "label": resolved["username"],
            "preview": short_preview(resolved.get("bio") or f"{role['label']} account"),
            "contextThreadId": None,
        }
    raise APIError("Unsupported report target.")


def serialize_report(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "reason": row["reason"],
        "details": row["details"] or "",
        "status": row["status"],
        "adminNote": row["admin_note"] or "",
        "priority": row["triage_priority"] or "normal",
        "category": row["triage_category"] or "",
        "resolutionCode": row["resolution_code"] or "",
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "handledAt": row["handled_at"],
        "target": {
            "type": row["target_type"],
            "id": row["target_id"],
            "label": row["target_label"],
            "preview": row["target_preview"] or "",
            "contextThreadId": row["context_thread_id"],
        },
        "reporter": {
            "id": row["reporter_id"],
            "username": row["reporter_username"],
            "role": row["reporter_role"],
        },
        "handledBy": (
            {
                "id": row["handled_by"],
                "username": row["handled_by_username"],
            }
            if row["handled_by"] and row["handled_by_username"]
            else None
        ),
        "assignedTo": (
            {
                "id": row["assigned_to"],
                "username": row["assigned_to_username"],
            }
            if row["assigned_to"] and row["assigned_to_username"]
            else None
        ),
    }


def list_reports(
    conn: sqlite3.Connection,
    *,
    status: str = "open",
    limit: int = 100,
) -> list[dict[str, Any]]:
    params: list[Any] = []
    where = ""
    if status in {"open", "resolved"}:
        where = "WHERE r.status = ?"
        params.append(status)
    rows = conn.execute(
        f"""
        SELECT
            r.*,
            reporter.username AS reporter_username,
            reporter.role AS reporter_role,
            handler.username AS handled_by_username,
            assigned.username AS assigned_to_username
        FROM reports r
        JOIN users reporter ON reporter.id = r.reporter_id
        LEFT JOIN users handler ON handler.id = r.handled_by
        LEFT JOIN users assigned ON assigned.id = r.assigned_to
        {where}
        ORDER BY
            CASE r.triage_priority
                WHEN 'urgent' THEN 0
                WHEN 'high' THEN 1
                WHEN 'normal' THEN 2
                ELSE 3
            END,
            CASE r.status WHEN 'open' THEN 0 ELSE 1 END,
            r.created_at DESC,
            r.id DESC
        LIMIT ?
        """,
        (*params, limit),
    ).fetchall()
    return [serialize_report(row) for row in rows]


def serialize_appeal(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "message": row["message"],
        "status": row["status"],
        "staffNote": row["staff_note"] or "",
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "handledAt": row["handled_at"],
        "user": {
            "id": row["user_id"],
            "username": row["username"],
            "role": row["role"],
        },
        "handledBy": (
            {
                "id": row["handled_by"],
                "username": row["handled_by_username"],
            }
            if row["handled_by"] and row["handled_by_username"]
            else None
        ),
        "targetUserId": row["target_user_id"] or row["user_id"],
    }


def list_appeals_for_viewer(
    conn: sqlite3.Connection,
    viewer: dict[str, Any],
    *,
    status: str = "open",
    target_user_id: int | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    params: list[Any] = []
    clauses: list[str] = []
    if not is_staff(viewer):
        clauses.append("a.user_id = ?")
        params.append(viewer["id"])
    elif target_user_id:
        clauses.append("a.user_id = ?")
        params.append(target_user_id)
    if status in {"open", "resolved"}:
        clauses.append("a.status = ?")
        params.append(status)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"""
        SELECT
            a.*,
            u.username,
            u.role,
            handler.username AS handled_by_username
        FROM appeals a
        JOIN users u ON u.id = a.user_id
        LEFT JOIN users handler ON handler.id = a.handled_by
        {where}
        ORDER BY
            CASE a.status WHEN 'open' THEN 0 ELSE 1 END,
            a.created_at DESC,
            a.id DESC
        LIMIT ?
        """,
        (*params, limit),
    ).fetchall()
    return [serialize_appeal(row) for row in rows]


def search_members(conn: sqlite3.Connection, query: str, *, limit: int = 8) -> list[dict[str, Any]]:
    pattern = f"%{query.lower()}%"
    rows = conn.execute(
        """
        SELECT
            u.*,
            (SELECT COUNT(*) FROM posts p WHERE p.author_id = u.id) AS posts_count,
            (SELECT COUNT(*) FROM threads t WHERE t.author_id = u.id) AS threads_count,
            (SELECT COUNT(*) FROM post_likes pl
             JOIN posts p2 ON p2.id = pl.post_id
             WHERE p2.author_id = u.id) AS likes_received
        FROM users u
        WHERE lower(u.username) LIKE ? OR lower(u.bio) LIKE ?
        ORDER BY
            CASE WHEN lower(u.username) = ? THEN 0 ELSE 1 END,
            CASE WHEN lower(u.username) LIKE ? THEN 0 ELSE 1 END,
            u.username COLLATE NOCASE ASC
        LIMIT ?
        """,
        (pattern, pattern, query.lower(), f"{query.lower()}%", limit),
    ).fetchall()
    return [serialize_user(dict(row)) for row in rows]


def search_threads(
    conn: sqlite3.Connection,
    query: str,
    *,
    viewer: dict[str, Any] | None,
    section_slug: str = "",
    author: str = "",
    tag: str = "",
    solved: str = "all",
    sort: str = "relevance",
    limit: int = 8,
) -> list[dict[str, Any]]:
    pattern = f"%{query.lower()}%"
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
            u.username AS author_name,
            u.role AS author_role,
            u.avatar_path AS author_avatar_path
        FROM threads t
        JOIN sections s ON s.id = t.section_id
        JOIN users u ON u.id = t.author_id
        WHERE lower(t.title) LIKE ? OR lower(t.tags_json) LIKE ?
        ORDER BY
            CASE WHEN lower(t.title) = ? THEN 0 ELSE 1 END,
            CASE WHEN lower(t.title) LIKE ? THEN 0 ELSE 1 END,
            t.updated_at DESC,
            t.id DESC
        LIMIT ?
        """,
        (pattern, pattern, query.lower(), f"{query.lower()}%", limit * 4),
    ).fetchall()
    output: list[dict[str, Any]] = []
    for row in rows:
        if not has_required_role(viewer, row["section_required_role"]):
            continue
        if section_slug and row["section_slug"] != section_slug:
            continue
        if author and row["author_name"].lower() != author.lower():
            continue
        if tag and tag not in set(json.loads(row["tags_json"] or "[]")):
            continue
        if solved == "solved" and not bool(row["solved"]):
            continue
        if solved == "unsolved" and bool(row["solved"]):
            continue
        if is_shadow_hidden_to_viewer(hidden=row["shadow_hidden"], author_id=row["author_id"], viewer=viewer):
            continue
        output.append(serialize_thread(row, conn, viewer))
    if sort == "latest":
        output.sort(key=lambda item: item["updatedAt"], reverse=True)
    elif sort == "trending":
        output.sort(key=lambda item: (item["views"], item["replies"], item["updatedAt"]), reverse=True)
    else:
        output.sort(
            key=lambda item: (
                1 if item["title"].lower() == query.lower() else 0,
                1 if query.lower() in item["title"].lower() else 0,
                item["updatedAt"],
            ),
            reverse=True,
        )
    return output[:limit]


def search_posts(
    conn: sqlite3.Connection,
    query: str,
    *,
    viewer: dict[str, Any] | None,
    section_slug: str = "",
    author: str = "",
    limit: int = 8,
) -> list[dict[str, Any]]:
    pattern = f"%{query.lower()}%"
    rows = conn.execute(
        """
        SELECT
            p.id,
            p.thread_id,
            p.content,
            p.created_at,
            p.updated_at,
            p.shadow_hidden,
            u.id AS author_id,
            u.username AS author_username,
            u.role AS author_role,
            u.bio AS author_bio,
            u.avatar_path AS author_avatar_path,
            u.xp AS author_xp,
            u.created_at AS author_created_at,
            u.last_seen_at AS author_last_seen_at,
            t.title AS thread_title,
            s.slug AS section_slug,
            s.name AS section_name,
            s.required_role AS section_required_role
        FROM posts p
        JOIN users u ON u.id = p.author_id
        JOIN threads t ON t.id = p.thread_id
        JOIN sections s ON s.id = t.section_id
        WHERE lower(p.content) LIKE ?
        ORDER BY
            CASE WHEN lower(p.content) LIKE ? THEN 0 ELSE 1 END,
            p.created_at DESC,
            p.id DESC
        LIMIT ?
        """,
        (pattern, f"{query.lower()}%", limit * 5),
    ).fetchall()
    output: list[dict[str, Any]] = []
    for row in rows:
        if not has_required_role(viewer, row["section_required_role"]):
            continue
        if section_slug and row["section_slug"] != section_slug:
            continue
        if author and row["author_username"].lower() != author.lower():
            continue
        if is_shadow_hidden_to_viewer(hidden=row["shadow_hidden"], author_id=row["author_id"], viewer=viewer):
            continue
        output.append(
            {
                "id": row["id"],
                "threadId": row["thread_id"],
                "threadTitle": row["thread_title"],
                "sectionId": row["section_slug"],
                "sectionName": row["section_name"],
                "content": short_preview(row["content"], max_len=220),
                "createdAt": row["created_at"],
                "updatedAt": row["updated_at"],
                "author": serialize_user(
                    {
                        "id": row["author_id"],
                        "username": row["author_username"],
                        "role": row["author_role"],
                        "bio": row["author_bio"] or "",
                        "avatar_path": row["author_avatar_path"] or "",
                        "xp": row["author_xp"] or 0,
                        "created_at": row["author_created_at"],
                        "last_seen_at": row["author_last_seen_at"],
                        "posts_count": 0,
                        "threads_count": 0,
                        "likes_received": 0,
                    }
                ),
            }
        )
        if len(output) == limit:
            break
    return output


def notify_mentions_in_thread(
    conn: sqlite3.Connection,
    *,
    actor: dict[str, Any],
    content: str,
    thread_id: int,
    post_id: int,
    required_role: str,
    created_at: str,
) -> set[int]:
    mentioned_users = extract_mentioned_users(
        conn,
        content,
        exclude_user_ids={int(actor["id"])},
    )
    for user in mentioned_users:
        if not has_required_role(user, required_role):
            continue
        create_notification(
            conn,
            user_id=user["id"],
            actor_id=actor["id"],
            kind="mention",
            title=f"{actor['username']} mentioned you",
            body=short_preview(content, max_len=140),
            target_type="thread",
            target_id=thread_id,
            metadata={"postId": post_id, "threadId": thread_id},
            created_at=created_at,
        )
    return {user["id"] for user in mentioned_users}


def notify_thread_reply(
    conn: sqlite3.Connection,
    *,
    actor: dict[str, Any],
    thread: sqlite3.Row,
    post_id: int,
    content: str,
    skip_user_ids: set[int] | None = None,
    created_at: str,
) -> None:
    skip_ids = set(skip_user_ids or set())
    skip_ids.add(int(actor["id"]))
    participant_rows = conn.execute(
        """
        SELECT DISTINCT author_id
        FROM posts
        WHERE thread_id = ? AND author_id != ?
        """,
        (thread["id"], actor["id"]),
    ).fetchall()
    subscriber_rows = conn.execute(
        """
        SELECT user_id AS author_id
        FROM thread_subscriptions
        WHERE thread_id = ? AND user_id != ?
        """,
        (thread["id"], actor["id"]),
    ).fetchall()
    for row in [*participant_rows, *subscriber_rows]:
        recipient_id = int(row["author_id"])
        if recipient_id in skip_ids:
            continue
        create_notification(
            conn,
            user_id=recipient_id,
            actor_id=actor["id"],
            kind="reply",
            title=f"New reply in {thread['title']}",
            body=f"{actor['username']}: {short_preview(content, max_len=120)}",
            target_type="thread",
            target_id=thread["id"],
            metadata={"postId": post_id, "threadId": thread["id"]},
            created_at=created_at,
        )
        skip_ids.add(recipient_id)


def notify_post_like(
    conn: sqlite3.Connection,
    *,
    actor: dict[str, Any],
    post: sqlite3.Row,
    thread_title: str,
    created_at: str,
) -> None:
    if int(post["author_id"]) == int(actor["id"]):
        return
    create_notification(
        conn,
        user_id=post["author_id"],
        actor_id=actor["id"],
        kind="like",
        title=f"{actor['username']} liked your post",
        body=f"In {thread_title}",
        target_type="thread",
        target_id=post["thread_id"],
        metadata={"postId": post["id"], "threadId": post["thread_id"]},
        created_at=created_at,
    )


def notify_dm_message(
    conn: sqlite3.Connection,
    *,
    sender: dict[str, Any],
    recipient_id: int,
    thread_id: int,
    content: str,
    created_at: str,
) -> None:
    create_notification(
        conn,
        user_id=recipient_id,
        actor_id=sender["id"],
        kind="dm",
        title=f"New message from {sender['username']}",
        body=short_preview(content, max_len=140),
        target_type="dm_thread",
        target_id=thread_id,
        metadata={"threadId": thread_id},
        created_at=created_at,
    )


def notify_staff_action(
    conn: sqlite3.Connection,
    *,
    target_user_id: int,
    actor: dict[str, Any],
    action: str,
    created_at: str,
    reason: str = "",
    note: str = "",
    delta_xp: int = 0,
    metadata: dict[str, Any] | None = None,
) -> None:
    labels = {
        "warn": ("Staff warning issued", reason or "A staff warning was added to your account."),
        "timeout": ("Account timeout applied", reason or "Your account has been temporarily restricted."),
        "clear_timeout": ("Account timeout cleared", reason or "Your posting timeout has been lifted."),
        "mute": ("Account muted", reason or "Your account has been temporarily muted from posting and messaging."),
        "clear_mute": ("Account mute cleared", reason or "Your mute has been lifted."),
        "shadow_mute": ("Account shadow-muted", reason or "Your account has been shadow-muted."),
        "clear_shadow_mute": ("Shadow mute cleared", reason or "Your account is no longer shadow-muted."),
        "ban": ("Account banned", reason or "Your account has been banned."),
        "unban": ("Account restored", reason or "Your account has been unbanned."),
        "xp_adjust": (
            "XP adjusted by staff",
            f"{'Granted' if delta_xp > 0 else 'Removed'} {abs(delta_xp)} XP. {reason}".strip(),
        ),
        "temp_password": (
            "Recovery password issued",
            note or "A temporary password was created for this account. Reset it after login.",
        ),
        "role_change": (
            "Role updated by staff",
            reason or "Your account role was changed by staff.",
        ),
    }
    title, body = labels.get(action, ("Staff action", reason or note or "A staff action was taken on your account."))
    if metadata and metadata.get("toRole") in ROLES:
        body = f"New role: {ROLES[metadata['toRole']]['label']}."
    create_notification(
        conn,
        user_id=target_user_id,
        actor_id=actor["id"],
        kind="staff_action",
        title=title,
        body=body,
        target_type="user",
        target_id=target_user_id,
        metadata=metadata,
        created_at=created_at,
    )


def serialize_contact_submission(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "discordUsername": row["discord_username"] or "",
        "subject": row["subject"],
        "message": row["message"],
        "status": row["status"],
        "adminNote": row["admin_note"] or "",
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "handledAt": row["handled_at"],
        "submittedBy": (
            {
                "id": row["user_id"],
                "username": row["username"],
                "role": row["role"],
            }
            if row["user_id"] and row["username"]
            else None
        ),
        "handledBy": (
            {
                "id": row["handled_by"],
                "username": row["handled_by_username"],
            }
            if row["handled_by"] and row["handled_by_username"]
            else None
        ),
    }


def list_contact_submissions(
    conn: sqlite3.Connection,
    *,
    status: str = "open",
    limit: int = 50,
) -> list[dict[str, Any]]:
    params: list[Any] = []
    where = ""
    if status in {"open", "resolved"}:
        where = "WHERE cs.status = ?"
        params.append(status)
    rows = conn.execute(
        f"""
        SELECT
            cs.*,
            submitter.username AS username,
            submitter.role AS role,
            handler.username AS handled_by_username
        FROM contact_submissions cs
        LEFT JOIN users submitter ON submitter.id = cs.user_id
        LEFT JOIN users handler ON handler.id = cs.handled_by
        {where}
        ORDER BY
            CASE cs.status WHEN 'open' THEN 0 ELSE 1 END,
            cs.created_at DESC,
            cs.id DESC
        LIMIT ?
        """,
        (*params, limit),
    ).fetchall()
    return [serialize_contact_submission(row) for row in rows]


def get_latest_activity(conn: sqlite3.Connection, limit: int = 8) -> list[dict[str, Any]]:
    activities: list[dict[str, Any]] = []

    new_users = conn.execute(
        """
        SELECT username, created_at
        FROM users
        ORDER BY created_at DESC
        LIMIT 4
        """
    ).fetchall()
    for row in new_users:
        activities.append(
            {
                "kind": "join",
                "user": row["username"],
                "action": "joined the forum",
                "target": "",
                "createdAt": row["created_at"],
            }
        )

    new_threads = conn.execute(
        """
        SELECT u.username, s.name AS section_name, t.title, t.created_at
        FROM threads t
        JOIN users u ON u.id = t.author_id
        JOIN sections s ON s.id = t.section_id
        WHERE COALESCE(t.shadow_hidden, 0) = 0
        ORDER BY t.created_at DESC
        LIMIT 6
        """
    ).fetchall()
    for row in new_threads:
        activities.append(
            {
                "kind": "thread",
                "user": row["username"],
                "action": "started a thread in",
                "target": row["section_name"],
                "detail": row["title"],
                "createdAt": row["created_at"],
            }
        )

    replies = conn.execute(
        """
        SELECT u.username, t.title, p.created_at
        FROM posts p
        JOIN users u ON u.id = p.author_id
        JOIN threads t ON t.id = p.thread_id
        WHERE COALESCE(p.shadow_hidden, 0) = 0
          AND p.id NOT IN (
            SELECT MIN(id)
            FROM posts
            GROUP BY thread_id
        )
        ORDER BY p.created_at DESC
        LIMIT 6
        """
    ).fetchall()
    for row in replies:
        activities.append(
            {
                "kind": "reply",
                "user": row["username"],
                "action": "replied in",
                "target": row["title"],
                "createdAt": row["created_at"],
            }
        )

    activities.sort(key=lambda item: item["createdAt"], reverse=True)
    return activities[:limit]


def get_home_announcements(conn: sqlite3.Connection) -> list[str]:
    stats = get_site_stats(conn)
    items = [
        "OmniForum is live with a real persistent backend.",
        f"{stats['members']} member{'s' if stats['members'] != 1 else ''} registered so far.",
        f"{stats['threads']} thread{'s' if stats['threads'] != 1 else ''} across the forum.",
        f"{stats['posts']} post{'s' if stats['posts'] != 1 else ''} and counting.",
    ]
    latest_thread = conn.execute(
        """
        SELECT title
        FROM threads
        WHERE COALESCE(shadow_hidden, 0) = 0
        ORDER BY pinned DESC, updated_at DESC
        LIMIT 1
        """
    ).fetchone()
    if latest_thread:
        items.append(f"Latest conversation: {latest_thread['title']}")
    else:
        items.append("Be the first to start a thread and shape the community.")
    return items


def get_site_stats(conn: sqlite3.Connection) -> dict[str, int]:
    member_count = conn.execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"]
    thread_count = conn.execute(
        "SELECT COUNT(*) AS count FROM threads WHERE COALESCE(shadow_hidden, 0) = 0"
    ).fetchone()["count"]
    post_count = conn.execute(
        "SELECT COUNT(*) AS count FROM posts WHERE COALESCE(shadow_hidden, 0) = 0"
    ).fetchone()["count"]
    online_since = utc_iso(utc_now() - timedelta(minutes=ONLINE_WINDOW_MINUTES))
    online_count = conn.execute(
        "SELECT COUNT(*) AS count FROM users WHERE last_seen_at >= ?",
        (online_since,),
    ).fetchone()["count"]
    return {
        "members": member_count,
        "threads": thread_count,
        "posts": post_count,
        "online": online_count,
    }


def human_size(value: int) -> str:
    size = float(max(0, value))
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(size)}{unit}"
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


def append_server_log(message: str) -> None:
    ensure_runtime_dirs()
    with LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(f"[{utc_iso()}] {message}\n")


def read_recent_logs(*, limit_lines: int = 120) -> list[str]:
    if not LOG_FILE.exists():
        return []
    lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
    return lines[-limit_lines:]


def rotate_backup_archives() -> None:
    backups = sorted(BACKUP_DIR.glob("omniforum-backup-*.zip"), key=lambda path: path.stat().st_mtime, reverse=True)
    for path in backups[BACKUP_ROTATION_LIMIT:]:
        path.unlink(missing_ok=True)


def create_backup_archive() -> Path:
    ensure_runtime_dirs()
    filename = f"omniforum-backup-{utc_now().strftime('%Y%m%d-%H%M%S')}.zip"
    target = BACKUP_DIR / filename
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for db_path in DATA_FILES.values():
            if db_path.exists():
                archive.write(db_path, arcname=f"data/{db_path.name}")
        if LOG_FILE.exists():
            archive.write(LOG_FILE, arcname="data/logs/server.log")
        for bucket, directory in MEDIA_FOLDERS.items():
            for file_path in sorted(directory.glob("*")):
                if file_path.is_file():
                    archive.write(file_path, arcname=f"data/uploads/{bucket}/{file_path.name}")
    rotate_backup_archives()
    return target


def referenced_media_paths(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        """
        SELECT storage_path FROM post_media WHERE storage_path != ''
        UNION
        SELECT avatar_path AS storage_path FROM users WHERE avatar_path != ''
        """
    ).fetchall()
    return {row["storage_path"] for row in rows if row["storage_path"]}


def cleanup_missing_avatar_paths(conn: sqlite3.Connection) -> int:
    stale_ids: list[int] = []
    rows = conn.execute("SELECT id, avatar_path FROM users WHERE avatar_path != ''").fetchall()
    for row in rows:
        storage_path = row["avatar_path"]
        parts = storage_path.split("/", 1)
        if len(parts) != 2 or parts[0] not in MEDIA_FOLDERS:
            stale_ids.append(int(row["id"]))
            continue
        if not (MEDIA_FOLDERS[parts[0]] / parts[1]).exists():
            stale_ids.append(int(row["id"]))
    if stale_ids:
        conn.execute(
            f"UPDATE users SET avatar_path = '' WHERE id IN ({', '.join('?' for _ in stale_ids)})",
            tuple(stale_ids),
        )
        conn.commit()
    return len(stale_ids)


def cleanup_orphan_media(conn: sqlite3.Connection) -> dict[str, Any]:
    broken_avatar_refs = cleanup_missing_avatar_paths(conn)
    orphaned_rows = cleanup_orphan_post_artifacts(conn)
    referenced = referenced_media_paths(conn)
    deleted_files: list[str] = []
    total_bytes = 0
    for file_path in MEDIA_DIR.iterdir():
        if not file_path.is_file():
            continue
        total_bytes += file_path.stat().st_size
        file_path.unlink(missing_ok=True)
        deleted_files.append(f"uploads/{file_path.name}")
    for bucket, directory in MEDIA_FOLDERS.items():
        for file_path in directory.glob("*"):
            if not file_path.is_file():
                continue
            storage_path = f"{bucket}/{file_path.name}"
            if storage_path in referenced:
                continue
            total_bytes += file_path.stat().st_size
            file_path.unlink(missing_ok=True)
            deleted_files.append(storage_path)
    return {
        "deletedCount": len(deleted_files),
        "deletedBytes": total_bytes,
        "deletedSize": human_size(total_bytes),
        "deletedFiles": deleted_files[:50],
        "brokenAvatarRefsCleared": broken_avatar_refs,
        "orphanRowsRemoved": orphaned_rows,
    }


def get_storage_sizes() -> dict[str, str]:
    sizes: dict[str, str] = {}
    for key, path in DATA_FILES.items():
        sizes[path.name] = human_size(path.stat().st_size) if path.exists() else "0B"
    return sizes


def count_media_assets() -> int:
    total = 0
    for directory in MEDIA_FOLDERS.values():
        total += sum(1 for file_path in directory.glob("*") if file_path.is_file())
    return total


def get_admin_health(conn: sqlite3.Connection) -> dict[str, Any]:
    return {
        "uptimeSeconds": int((utc_now() - SERVER_STARTED_AT).total_seconds()),
        "startedAt": utc_iso(SERVER_STARTED_AT),
        "stats": get_site_stats(conn),
        "storage": {
            "databases": get_storage_sizes(),
            "mediaAssets": count_media_assets(),
            "backupCount": len(list(BACKUP_DIR.glob("omniforum-backup-*.zip"))),
        },
        "queues": {
            "reports": get_open_report_count(conn),
            "appeals": get_open_appeal_count(conn),
            "contactNotices": get_open_contact_notice_count(conn),
        },
        "runtime": {
            "host": HOST,
            "port": PORT,
            "maxRequestBytes": MAX_REQUEST_BYTES,
            "secureCookies": SECURE_COOKIES,
        },
        "recentLogs": read_recent_logs(limit_lines=40),
    }


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
    categories = conn.execute(
        "SELECT * FROM categories ORDER BY sort_order ASC, id ASC"
    ).fetchall()
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
            visible_clause = ""
            if not is_staff(viewer):
                visible_clause = " AND COALESCE(t.shadow_hidden, 0) = 0"
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
                SELECT t.id, t.title, t.updated_at, u.username
                FROM threads t
                JOIN users u ON u.id = t.author_id
                WHERE t.section_id = ?
                  {"AND COALESCE(t.shadow_hidden, 0) = 0" if not is_staff(viewer) else ""}
                ORDER BY t.pinned DESC, t.updated_at DESC, t.id DESC
                LIMIT 1
                """,
                (section["id"],),
            ).fetchone()
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


def get_thread_by_id(conn: sqlite3.Connection, thread_id: int) -> sqlite3.Row | None:
    return conn.execute(
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
            u.username AS author_name,
            u.role AS author_role,
            u.avatar_path AS author_avatar_path
        FROM threads t
        JOIN sections s ON s.id = t.section_id
        JOIN users u ON u.id = t.author_id
        WHERE t.id = ?
        """,
        (thread_id,),
    ).fetchone()


def serialize_thread(
    thread_row: sqlite3.Row,
    conn: sqlite3.Connection,
    viewer: dict[str, Any] | None,
) -> dict[str, Any]:
    stats_where = "thread_id = ?"
    stats_params: list[Any] = [thread_row["id"]]
    if is_shadow_hidden_to_viewer(
        hidden=thread_row["shadow_hidden"],
        author_id=thread_row["author_id"],
        viewer=viewer,
    ):
        stats_where += " AND 1 = 0"
    elif not can_view_shadow_content(viewer, thread_row["author_id"]):
        stats_where += " AND COALESCE(shadow_hidden, 0) = 0"
    stats = conn.execute(
        f"""
        SELECT
            COUNT(*) AS post_count,
            MAX(created_at) AS last_post_at
        FROM posts
        WHERE {stats_where}
        """,
        tuple(stats_params),
    ).fetchone()
    last_post_where = "p.thread_id = ?"
    last_post_params: list[Any] = [thread_row["id"]]
    if not can_view_shadow_content(viewer, thread_row["author_id"]):
        last_post_where += " AND COALESCE(p.shadow_hidden, 0) = 0"
    last_post = conn.execute(
        f"""
        SELECT u.username
        FROM posts p
        JOIN users u ON u.id = p.author_id
        WHERE {last_post_where}
        ORDER BY p.created_at DESC, p.id DESC
        LIMIT 1
        """,
        tuple(last_post_params),
    ).fetchone()
    author_id = thread_row["author_id"]
    can_edit = bool(viewer and (viewer["id"] == author_id or is_staff(viewer)))
    can_moderate = bool(viewer and is_staff(viewer))
    can_delete = bool(viewer and (viewer["id"] == author_id or is_staff(viewer)))
    can_mark_answer = bool(viewer and (viewer["id"] == author_id or is_staff(viewer)))
    flags = thread_user_flags(conn, thread_row["id"], viewer)
    return {
        "id": thread_row["id"],
        "title": thread_row["title"],
        "authorId": author_id,
        "authorName": thread_row["author_name"],
        "authorRole": thread_row["author_role"],
        "authorAvatarUrl": media_url_for_path(thread_row["author_avatar_path"]),
        "createdAt": thread_row["created_at"],
        "updatedAt": thread_row["updated_at"],
        "editedAt": thread_row["edited_at"],
        "views": thread_row["view_count"],
        "pinned": bool(thread_row["pinned"]),
        "hot": stats["post_count"] >= 15,
        "locked": bool(thread_row["locked"]),
        "solved": bool(thread_row["solved"]),
        "answerPostId": thread_row["answer_post_id"],
        "shadowHidden": bool(thread_row["shadow_hidden"]),
        "tags": json.loads(thread_row["tags_json"] or "[]"),
        "replies": max(0, stats["post_count"] - 1),
        "lastPostAt": stats["last_post_at"],
        "lastPostBy": last_post["username"] if last_post else None,
        "poll": serialize_thread_poll(conn, thread_row["id"], viewer),
        "section": {
            "id": thread_row["section_slug"],
            "name": thread_row["section_name"],
            "desc": thread_row["section_description"],
            "icon": thread_row["section_icon"],
            "iconBg": thread_row["section_icon_bg"],
            "requiredRole": thread_row["section_required_role"],
            "writeRole": thread_row["section_write_role"],
        },
        "canEdit": can_edit,
        "canDelete": can_delete,
        "canModerate": can_moderate,
        "canMarkAnswer": can_mark_answer,
        "bookmarkedByViewer": flags["bookmarked"],
        "subscribedByViewer": flags["subscribed"],
    }


def get_related_threads(
    conn: sqlite3.Connection,
    thread_row: sqlite3.Row,
    viewer: dict[str, Any] | None,
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
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
            u.username AS author_name,
            u.role AS author_role,
            u.avatar_path AS author_avatar_path
        FROM threads t
        JOIN sections s ON s.id = t.section_id
        JOIN users u ON u.id = t.author_id
        WHERE t.id != ? AND t.section_id = ?
        ORDER BY t.updated_at DESC, t.id DESC
        LIMIT 40
        """,
        (thread_row["id"], thread_row["section_id"]),
    ).fetchall()
    scored: list[tuple[int, sqlite3.Row]] = []
    for row in rows:
        if not has_required_role(viewer, row["section_required_role"]):
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
            u.username AS author_name,
            u.role AS author_role,
            u.avatar_path AS author_avatar_path
        FROM threads t
        JOIN sections s ON s.id = t.section_id
        JOIN users u ON u.id = t.author_id
        ORDER BY t.pinned DESC, t.view_count DESC, t.updated_at DESC, t.id DESC
        LIMIT 40
        """
    ).fetchall()
    visible_rows = [
        row for row in rows
        if has_required_role(viewer, row["section_required_role"])
        and not is_shadow_hidden_to_viewer(
            hidden=row["shadow_hidden"],
            author_id=row["author_id"],
            viewer=viewer,
        )
    ]
    return [serialize_thread(row, conn, viewer) for row in visible_rows[:limit]]


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
            u.username AS author_name,
            u.role AS author_role,
            u.avatar_path AS author_avatar_path
        FROM threads t
        JOIN sections s ON s.id = t.section_id
        JOIN users u ON u.id = t.author_id
        WHERE t.section_id = ?
        ORDER BY t.pinned DESC, t.updated_at DESC, t.id DESC
        """,
        (section["id"],),
    ).fetchall()
    normalized_search = search.strip().lower()
    if normalized_search:
        rows = [
            row
            for row in rows
            if normalized_search in row["title"].lower()
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


def get_posts_for_thread(
    conn: sqlite3.Connection,
    thread_id: int,
    viewer: dict[str, Any] | None,
    *,
    page: int = 1,
    page_size: int = DEFAULT_POST_PAGE_SIZE,
    last_page: bool = False,
    focus_post_id: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int | bool]]:
    viewer_id = viewer["id"] if viewer else -1
    visibility_clause = "thread_id = ?"
    visibility_params: list[Any] = [thread_id]
    if not is_staff(viewer):
        visibility_clause += " AND (COALESCE(shadow_hidden, 0) = 0"
        if viewer:
            visibility_clause += " OR author_id = ?"
            visibility_params.append(viewer["id"])
        visibility_clause += ")"
    total_posts = conn.execute(
        f"SELECT COUNT(*) AS count FROM posts WHERE {visibility_clause}",
        tuple(visibility_params),
    ).fetchone()["count"]
    if focus_post_id:
        focus_row = conn.execute(
            f"""
            SELECT COUNT(*) AS count
            FROM posts
            WHERE {visibility_clause} AND id <= ?
            """,
            (*visibility_params, focus_post_id),
        ).fetchone()
        if focus_row and focus_row["count"]:
            page = max(1, math.ceil(int(focus_row["count"]) / page_size))
            last_page = False
    pagination = resolve_pagination(
        total_posts,
        page=page,
        page_size=page_size,
        last_page=last_page,
    )
    rows = conn.execute(
        f"""
        SELECT
            p.*,
            u.username,
            u.role,
            u.bio,
            u.avatar_path,
            u.signature,
            u.profile_badge,
            u.profile_accent,
            u.xp,
            u.created_at AS user_created_at,
            u.last_seen_at,
            t.author_id AS thread_author_id,
            (SELECT COUNT(*) FROM posts p2 WHERE p2.author_id = u.id) AS author_posts,
            (SELECT COUNT(*) FROM threads t2 WHERE t2.author_id = u.id) AS author_threads,
            (SELECT COUNT(*) FROM post_likes pl WHERE pl.post_id = p.id) AS likes_count,
            EXISTS(
                SELECT 1
                FROM post_likes pl2
                WHERE pl2.post_id = p.id AND pl2.user_id = ?
            ) AS liked_by_viewer
        FROM posts p
        JOIN threads t ON t.id = p.thread_id
        JOIN users u ON u.id = p.author_id
        WHERE {visibility_clause.replace("thread_id", "p.thread_id")}
        ORDER BY p.id ASC
        LIMIT ? OFFSET ?
        """,
        (viewer_id, *visibility_params, pagination["pageSize"], pagination["offset"]),
    ).fetchall()
    first_post = thread_first_post_id(conn, thread_id)
    media_map = list_post_media(conn, [row["id"] for row in rows])
    reaction_map = list_post_reactions_summary(conn, [row["id"] for row in rows], viewer)
    payload = []
    for row in rows:
        author = {
            "id": row["author_id"],
            "username": row["username"],
            "role": row["role"],
            "bio": row["bio"],
            "avatar_path": row["avatar_path"] or "",
            "signature": row["signature"] or "",
            "profile_badge": row["profile_badge"] or "",
            "profile_accent": row["profile_accent"] or "",
            "xp": row["xp"],
            "created_at": row["user_created_at"],
            "last_seen_at": row["last_seen_at"],
            "posts_count": row["author_posts"],
            "threads_count": row["author_threads"],
            "likes_received": 0,
        }
        can_edit = bool(viewer and (viewer["id"] == row["author_id"] or is_staff(viewer)))
        can_delete = bool(
            viewer
            and row["id"] != first_post
            and (viewer["id"] == row["author_id"] or is_staff(viewer))
        )
        payload.append(
            {
                "id": row["id"],
                "threadId": row["thread_id"],
                "author": serialize_user(author),
                "content": row["content"],
                "media": media_map.get(row["id"], []),
                "createdAt": row["created_at"],
                "updatedAt": row["updated_at"],
                "editedAt": row["edited_at"],
                "hasHistory": bool(row["edited_at"]),
                "likes": row["likes_count"],
                "likedByViewer": bool(row["liked_by_viewer"]),
                "isThreadStarter": row["id"] == first_post,
                "isAcceptedAnswer": False,
                "shadowHidden": bool(row["shadow_hidden"]),
                "reactions": reaction_map.get(row["id"], {}).get("items", []),
                "viewerReactions": reaction_map.get(row["id"], {}).get("viewer", []),
                "canEdit": can_edit,
                "canDelete": can_delete,
                "canMarkAnswer": bool(viewer and (viewer["id"] == row["thread_author_id"] or is_staff(viewer))),
            }
        )
    answer_row = conn.execute(
        "SELECT answer_post_id FROM threads WHERE id = ?",
        (thread_id,),
    ).fetchone()
    answer_post_id = answer_row["answer_post_id"] if answer_row else None
    for item in payload:
        item["isAcceptedAnswer"] = bool(answer_post_id and item["id"] == answer_post_id)
    return payload, pagination


def serialize_post_history_item(row: sqlite3.Row) -> dict[str, Any]:
    try:
        media_summary = json.loads(row["media_summary_json"] or "[]")
    except json.JSONDecodeError:
        media_summary = []
    return {
        "id": row["id"],
        "content": row["previous_content"],
        "title": row["previous_title"] or "",
        "mediaSummary": media_summary,
        "createdAt": row["created_at"],
        "editor": {
            "id": row["editor_id"],
            "username": row["editor_username"],
            "role": row["editor_role"],
        },
    }


def list_post_edit_history(conn: sqlite3.Connection, post_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            pe.*,
            editor.username AS editor_username,
            editor.role AS editor_role
        FROM post_edits pe
        JOIN users editor ON editor.id = pe.editor_id
        WHERE pe.post_id = ?
        ORDER BY pe.created_at DESC, pe.id DESC
        LIMIT 20
        """,
        (post_id,),
    ).fetchall()
    return [serialize_post_history_item(row) for row in rows]


def get_current_user_payload(conn: sqlite3.Connection, viewer: dict[str, Any] | None) -> dict[str, Any] | None:
    if not viewer:
        return None
    return get_user_profile(conn, viewer["id"], viewer=viewer, include_detail=False)


class ForumHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(BASE_DIR), **kwargs)

    def request_ip(self) -> str:
        forwarded = str(self.headers.get("X-Forwarded-For") or "").split(",", 1)[0].strip()
        return forwarded or (self.client_address[0] if self.client_address else "")

    def request_user_agent(self) -> str:
        return str(self.headers.get("User-Agent") or "").strip()

    def current_session_token(self) -> str | None:
        return session_token_from_headers(self.headers)

    def enforce_same_origin(self) -> None:
        allowed_hosts = {
            str(self.headers.get("Host") or "").strip(),
            f"{HOST}:{PORT}",
            f"localhost:{PORT}",
            f"127.0.0.1:{PORT}",
        }
        headers_to_check = [self.headers.get("Origin"), self.headers.get("Referer")]
        checked = False
        for raw_value in headers_to_check:
            if not raw_value:
                continue
            checked = True
            parsed = urlparse(raw_value)
            if parsed.netloc in allowed_hosts:
                return
        if checked:
            raise APIError("This request origin is not allowed.", HTTPStatus.FORBIDDEN)

    def enforce_rate_limit(self, action: str, viewer: dict[str, Any] | None = None) -> None:
        rule = RATE_LIMIT_RULES.get(action)
        if not rule:
            return
        limit, window_seconds, label = rule
        identity = f"user:{viewer['id']}" if viewer else f"ip:{self.request_ip() or 'unknown'}"
        key = f"{action}:{identity}"
        now = time.monotonic()
        cutoff = now - window_seconds
        attempts = [stamp for stamp in RATE_LIMIT_STATE.get(key, []) if stamp > cutoff]
        if len(attempts) >= limit:
            retry_after = max(1, math.ceil(window_seconds - (now - attempts[0])))
            raise APIError(
                f"Too many {label}. Please wait about {retry_after}s and try again.",
                HTTPStatus.TOO_MANY_REQUESTS,
            )
        attempts.append(now)
        RATE_LIMIT_STATE[key] = attempts

    def end_headers(self) -> None:
        if not urlparse(self.path).path.startswith(f"{MEDIA_ROUTE}/"):
            self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; "
            "object-src 'none'; base-uri 'self'; form-action 'self'",
        )
        super().end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self.handle_api("GET")
            return
        if parsed.path == "/data" or parsed.path.startswith("/data/"):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if parsed.path.startswith(f"{EXPORT_ROUTE}/"):
            self.serve_export(parsed.path)
            return
        if parsed.path.startswith(f"{MEDIA_ROUTE}/"):
            self.serve_media(parsed.path)
            return
        super().do_GET()

    def do_POST(self) -> None:
        if self.path.startswith("/api/"):
            self.handle_api("POST")
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_PATCH(self) -> None:
        if self.path.startswith("/api/"):
            self.handle_api("PATCH")
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_DELETE(self) -> None:
        if self.path.startswith("/api/"):
            self.handle_api("DELETE")
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def log_message(self, fmt: str, *args: Any) -> None:
        message = f"{self.address_string()} {fmt % args}"
        print(f"[{self.log_date_time_string()}] {message}")
        append_server_log(message)

    def serve_media(self, path: str) -> None:
        relative = unquote(path[len(MEDIA_ROUTE) :]).strip("/")
        parts = [part for part in relative.split("/") if part]
        if len(parts) != 2 or parts[0] not in MEDIA_FOLDERS:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not re.fullmatch(r"[A-Za-z0-9._-]+", parts[1]):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        file_path = resolve_media_path("/".join(parts))
        if not file_path or not file_path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header(
            "Content-Type",
            mimetypes.guess_type(file_path.name)[0] or "application/octet-stream",
        )
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "public, max-age=86400")
        self.end_headers()
        self.wfile.write(body)

    def serve_export(self, path: str) -> None:
        with get_connection() as conn:
            viewer = current_user_from_request(conn, self.headers, self.request_ip())
            if not viewer or not is_admin(viewer):
                self.send_error(HTTPStatus.FORBIDDEN)
                return
        relative = unquote(path[len(EXPORT_ROUTE) :]).strip("/")
        parts = [part for part in relative.split("/") if part]
        if len(parts) != 2 or parts[0] != "backups":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not re.fullmatch(r"[A-Za-z0-9._-]+", parts[1]):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        file_path = (BACKUP_DIR / parts[1]).resolve()
        if file_path.parent != BACKUP_DIR.resolve() or not file_path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Disposition", f'attachment; filename="{file_path.name}"')
        self.end_headers()
        self.wfile.write(body)

    def handle_api(self, method: str) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        conn = get_connection()
        try:
            if method != "GET":
                self.enforce_same_origin()
            viewer = current_user_from_request(conn, self.headers, self.request_ip())
            payload = self.dispatch_api(conn, method, path, query, viewer)
            status = payload.pop("__status__", HTTPStatus.OK)
            cookie_header = payload.pop("__cookie_header__", None)
            self.respond_json(payload, status=status, cookie_header=cookie_header)
        except APIError as exc:
            self.respond_json({"error": exc.message}, status=exc.status)
        except Exception as exc:  # pragma: no cover - last-resort guardrail
            self.respond_json(
                {"error": "Unexpected server error.", "detail": str(exc)},
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )
        finally:
            conn.close()

    def dispatch_api(
        self,
        conn: sqlite3.Connection,
        method: str,
        path: str,
        query: dict[str, list[str]],
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if method == "GET" and path == "/api/health":
            return {"ok": True, "time": utc_iso()}
        if method == "GET" and path == "/api/home":
            return self.api_home(conn, viewer)
        if method == "GET" and path == "/api/me":
            return {"currentUser": get_current_user_payload(conn, viewer)}
        if method == "POST" and path == "/api/register":
            return self.api_register(conn)
        if method == "POST" and path == "/api/login":
            return self.api_login(conn)
        if method == "POST" and path == "/api/logout":
            return self.api_logout(conn)
        if method == "PATCH" and path == "/api/me":
            return self.api_update_me(conn, viewer)
        if method == "PATCH" and path == "/api/me/password":
            return self.api_update_password(conn, viewer)
        if method == "POST" and path == "/api/me/sessions/revoke-others":
            return self.api_revoke_other_sessions(conn, viewer)
        if method == "GET" and path == "/api/search":
            return self.api_search(conn, viewer, query)
        if method == "GET" and path == "/api/notifications":
            return self.api_notifications(conn, viewer, query)
        if method == "POST" and path == "/api/notifications/read-all":
            return self.api_mark_notifications(conn, viewer)
        if method == "GET" and path == "/api/messages":
            return self.api_messages(conn, viewer)
        if method == "POST" and path == "/api/messages":
            return self.api_send_message(conn, viewer)
        if method == "POST" and path == "/api/contact":
            return self.api_contact(conn, viewer)
        if method == "GET" and path == "/api/reports":
            return self.api_reports(conn, viewer, query)
        if method == "POST" and path == "/api/reports":
            return self.api_create_report(conn, viewer)
        if method == "POST" and path == "/api/reports/bulk":
            return self.api_bulk_update_reports(conn, viewer)
        if method == "GET" and path == "/api/appeals":
            return self.api_appeals(conn, viewer, query)
        if method == "POST" and path == "/api/appeals":
            return self.api_create_appeal(conn, viewer)
        if method == "POST" and path == "/api/sections":
            return self.api_create_section(conn, viewer)
        if method == "GET" and path == "/api/users":
            return self.api_users(conn, viewer, query)
        if method == "GET" and path == "/api/leaderboard":
            return self.api_leaderboard(conn, viewer, query)
        if method == "GET" and path == "/api/notices":
            return self.api_notices(conn, viewer, query)
        if method == "GET" and path == "/api/admin/health":
            return self.api_admin_health(conn, viewer)
        if method == "POST" and path == "/api/admin/backup":
            return self.api_admin_backup(conn, viewer)
        if method == "GET" and path == "/api/admin/logs":
            return self.api_admin_logs(conn, viewer)
        if method == "POST" and path == "/api/admin/media-cleanup":
            return self.api_admin_media_cleanup(conn, viewer)

        user_match = re.fullmatch(r"/api/users/(\d+)", path)
        if method == "GET" and user_match:
            return self.api_user_detail(conn, viewer, int(user_match.group(1)))

        role_match = re.fullmatch(r"/api/users/(\d+)/role", path)
        if method == "PATCH" and role_match:
            return self.api_update_role(conn, viewer, int(role_match.group(1)))

        moderation_match = re.fullmatch(r"/api/users/(\d+)/moderation", path)
        if method == "POST" and moderation_match:
            return self.api_moderate_user(conn, viewer, int(moderation_match.group(1)))

        dm_thread_match = re.fullmatch(r"/api/messages/(\d+)", path)
        if method == "GET" and dm_thread_match:
            return self.api_message_thread(conn, viewer, int(dm_thread_match.group(1)))
        if method == "POST" and dm_thread_match:
            return self.api_reply_message(conn, viewer, int(dm_thread_match.group(1)))

        notification_match = re.fullmatch(r"/api/notifications/(\d+)", path)
        if method == "PATCH" and notification_match:
            return self.api_mark_notifications(conn, viewer, int(notification_match.group(1)))

        report_match = re.fullmatch(r"/api/reports/(\d+)", path)
        if method == "PATCH" and report_match:
            return self.api_update_report(conn, viewer, int(report_match.group(1)))

        appeal_match = re.fullmatch(r"/api/appeals/(\d+)", path)
        if method == "PATCH" and appeal_match:
            return self.api_update_appeal(conn, viewer, int(appeal_match.group(1)))

        section_match = re.fullmatch(r"/api/sections/([A-Za-z0-9_-]+)", path)
        if method == "GET" and section_match:
            return self.api_section(conn, viewer, section_match.group(1), query)
        if method == "POST" and section_match:
            return self.api_create_thread(conn, viewer, section_match.group(1))
        if method == "PATCH" and section_match:
            return self.api_update_section(conn, viewer, section_match.group(1))
        if method == "DELETE" and section_match:
            return self.api_delete_section(conn, viewer, section_match.group(1))

        thread_match = re.fullmatch(r"/api/threads/(\d+)", path)
        if method == "GET" and thread_match:
            return self.api_thread(conn, viewer, int(thread_match.group(1)), query)
        if method == "PATCH" and thread_match:
            return self.api_update_thread(conn, viewer, int(thread_match.group(1)))
        if method == "DELETE" and thread_match:
            return self.api_delete_thread(conn, viewer, int(thread_match.group(1)))

        thread_bookmark_match = re.fullmatch(r"/api/threads/(\d+)/bookmark", path)
        if method == "POST" and thread_bookmark_match:
            return self.api_toggle_thread_bookmark(conn, viewer, int(thread_bookmark_match.group(1)))

        thread_subscription_match = re.fullmatch(r"/api/threads/(\d+)/subscription", path)
        if method == "POST" and thread_subscription_match:
            return self.api_toggle_thread_subscription(conn, viewer, int(thread_subscription_match.group(1)))

        reply_match = re.fullmatch(r"/api/threads/(\d+)/posts", path)
        if method == "POST" and reply_match:
            return self.api_create_post(conn, viewer, int(reply_match.group(1)))

        post_match = re.fullmatch(r"/api/posts/(\d+)", path)
        if method == "GET" and post_match:
            return self.api_post_history(conn, viewer, int(post_match.group(1)))
        if method == "PATCH" and post_match:
            return self.api_update_post(conn, viewer, int(post_match.group(1)))
        if method == "DELETE" and post_match:
            return self.api_delete_post(conn, viewer, int(post_match.group(1)))

        like_match = re.fullmatch(r"/api/posts/(\d+)/like", path)
        if method == "POST" and like_match:
            return self.api_toggle_like(conn, viewer, int(like_match.group(1)))

        reaction_match = re.fullmatch(r"/api/posts/(\d+)/reactions", path)
        if method == "POST" and reaction_match:
            return self.api_toggle_reaction(conn, viewer, int(reaction_match.group(1)))

        notice_match = re.fullmatch(r"/api/notices/contact/(\d+)", path)
        if method == "PATCH" and notice_match:
            return self.api_update_contact_notice(conn, viewer, int(notice_match.group(1)))

        poll_match = re.fullmatch(r"/api/threads/(\d+)/poll", path)
        if method == "POST" and poll_match:
            return self.api_vote_thread_poll(conn, viewer, int(poll_match.group(1)))

        raise APIError("Endpoint not found.", HTTPStatus.NOT_FOUND)

    def read_json(self) -> dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length > MAX_REQUEST_BYTES:
            raise APIError("That request body is too large.", HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
        raw = self.rfile.read(content_length) if content_length else b"{}"
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise APIError("Malformed JSON body.") from exc

    def respond_json(
        self,
        payload: dict[str, Any],
        status: int = HTTPStatus.OK,
        cookie_header: str | None = None,
    ) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if cookie_header:
            self.send_header("Set-Cookie", cookie_header)
        self.end_headers()
        self.wfile.write(body)

    def make_session_cookie(self, token: str, expires_at: str) -> str:
        cookie = SimpleCookie()
        cookie[SESSION_COOKIE] = token
        cookie[SESSION_COOKIE]["path"] = "/"
        cookie[SESSION_COOKIE]["httponly"] = True
        cookie[SESSION_COOKIE]["samesite"] = "Lax"
        if SECURE_COOKIES or str(self.headers.get("X-Forwarded-Proto") or "").strip().lower() == "https":
            cookie[SESSION_COOKIE]["secure"] = True
        cookie[SESSION_COOKIE]["expires"] = parse_iso(expires_at).strftime(
            "%a, %d %b %Y %H:%M:%S GMT"
        )
        return cookie.output(header="").strip()

    def clear_session_cookie_header(self) -> str:
        cookie = SimpleCookie()
        cookie[SESSION_COOKIE] = ""
        cookie[SESSION_COOKIE]["path"] = "/"
        cookie[SESSION_COOKIE]["httponly"] = True
        cookie[SESSION_COOKIE]["samesite"] = "Lax"
        if SECURE_COOKIES or str(self.headers.get("X-Forwarded-Proto") or "").strip().lower() == "https":
            cookie[SESSION_COOKIE]["secure"] = True
        cookie[SESSION_COOKIE]["expires"] = "Thu, 01 Jan 1970 00:00:00 GMT"
        cookie[SESSION_COOKIE]["max-age"] = 0
        return cookie.output(header="").strip()

    def api_home(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        return {
            "roles": ROLES,
            "currentUser": get_current_user_payload(conn, viewer),
            "stats": get_site_stats(conn),
            "categories": get_sections_with_stats(conn, viewer),
            "topMembers": get_top_members(conn),
            "trendingThreads": get_trending_threads(conn, viewer),
            "activity": get_latest_activity(conn),
            "announcements": get_home_announcements(conn),
        }

    def api_register(self, conn: sqlite3.Connection) -> dict[str, Any]:
        self.enforce_rate_limit("register")
        data = self.read_json()
        username = clean_username(data.get("username"))
        password = clean_password(data.get("password"))
        now = utc_iso()
        current_count = conn.execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"]
        role = "owner" if current_count == 0 else "new"
        bio = "New to OmniForum. Say hello and start the first thread."
        try:
            cur = conn.execute(
                """
                INSERT INTO users (username, password_hash, role, bio, xp, created_at, updated_at, last_seen_at)
                VALUES (?, ?, ?, ?, 0, ?, ?, ?)
                """,
                (username, make_password_hash(password), role, bio, now, now, now),
            )
            conn.commit()
        except sqlite3.IntegrityError as exc:
            raise APIError("Username already taken.") from exc

        token, expires_at = create_session(
            conn,
            cur.lastrowid,
            ip_address=self.request_ip(),
            user_agent=self.request_user_agent(),
        )
        user = get_user_profile(
            conn,
            cur.lastrowid,
            viewer={"id": cur.lastrowid, "role": role},
        )
        return {
            "currentUser": user,
            "__status__": HTTPStatus.CREATED,
            "__cookie_header__": self.make_session_cookie(token, expires_at),
        }

    def api_login(self, conn: sqlite3.Connection) -> dict[str, Any]:
        self.enforce_rate_limit("login")
        data = self.read_json()
        username = clean_username(data.get("username"))
        password = clean_text(data.get("password"), min_len=1, max_len=128, field="Password")
        row = conn.execute(
            "SELECT * FROM users WHERE lower(username) = lower(?)",
            (username,),
        ).fetchone()
        if not row or not verify_password(password, row["password_hash"]):
            raise APIError("Invalid username or password.", HTTPStatus.UNAUTHORIZED)
        user_row = sync_user_restrictions(conn, row)
        if not user_row:
            raise APIError("Invalid username or password.", HTTPStatus.UNAUTHORIZED)
        token, expires_at = create_session(
            conn,
            user_row["id"],
            ip_address=self.request_ip(),
            user_agent=self.request_user_agent(),
        )
        now = utc_iso()
        conn.execute(
            "UPDATE users SET last_seen_at = ?, updated_at = ? WHERE id = ?",
            (now, now, user_row["id"]),
        )
        conn.commit()
        user = get_user_profile(conn, user_row["id"], viewer=user_row)
        return {
            "currentUser": user,
            "__cookie_header__": self.make_session_cookie(token, expires_at),
        }

    def api_logout(self, conn: sqlite3.Connection) -> dict[str, Any]:
        token = self.current_session_token()
        delete_session(conn, token)
        return {
            "currentUser": None,
            "__cookie_header__": self.clear_session_cookie_header(),
        }

    def api_update_me(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        ensure_can_participate(viewer)
        self.enforce_rate_limit("profile_update", viewer)
        data = self.read_json()
        username = clean_username(
            data.get("username", viewer.get("username", "")),
        )
        bio = clean_text(
            data.get("bio", viewer.get("bio", "")),
            min_len=0,
            max_len=280,
            field="Bio",
        )
        avatar_upload = data.get("avatarUpload")
        remove_avatar = bool(data.get("removeAvatar"))
        site_theme = clean_site_theme(data.get("siteTheme", viewer.get("site_theme", "midnight")))
        dm_privacy = clean_dm_privacy(data.get("dmPrivacy", viewer.get("dm_privacy", "everyone")))
        notify_replies = bool(data.get("notifyReplies", viewer.get("notify_replies", 1)))
        notify_likes = bool(data.get("notifyLikes", viewer.get("notify_likes", 1)))
        notify_mentions = bool(data.get("notifyMentions", viewer.get("notify_mentions", 1)))
        notify_dms = bool(data.get("notifyDms", viewer.get("notify_dms", 1)))
        signature = clean_signature(data.get("signature", viewer.get("signature", "")))
        profile_badge = clean_profile_badge(data.get("profileBadge", viewer.get("profile_badge", "")))
        profile_accent = clean_profile_accent(data.get("profileAccent", viewer.get("profile_accent", "")))
        current_avatar_path = str(viewer.get("avatar_path") or "")
        next_avatar_path = current_avatar_path
        if avatar_upload:
            next_avatar_path = store_image_upload(
                decode_image_upload(
                    avatar_upload,
                    field="Avatar",
                    max_bytes=AVATAR_MAX_BYTES,
                ),
                bucket="avatars",
            )
        elif remove_avatar:
            next_avatar_path = ""
        now = utc_iso()
        try:
            conn.execute(
                """
                UPDATE users
                SET username = ?, bio = ?, avatar_path = ?, site_theme = ?, dm_privacy = ?,
                    notify_replies = ?, notify_likes = ?, notify_mentions = ?, notify_dms = ?,
                    signature = ?, profile_badge = ?, profile_accent = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    username,
                    bio,
                    next_avatar_path,
                    site_theme,
                    dm_privacy,
                    int(notify_replies),
                    int(notify_likes),
                    int(notify_mentions),
                    int(notify_dms),
                    signature,
                    profile_badge,
                    profile_accent,
                    now,
                    viewer["id"],
                ),
            )
        except sqlite3.IntegrityError as exc:
            if next_avatar_path != current_avatar_path:
                delete_media_file(next_avatar_path)
            raise APIError("Username already taken.") from exc
        conn.commit()
        if next_avatar_path != current_avatar_path:
            delete_media_file(current_avatar_path)
        refreshed = sync_user_restrictions(
            conn,
            conn.execute("SELECT * FROM users WHERE id = ?", (viewer["id"],)).fetchone(),
        )
        return {
            "currentUser": get_user_profile(conn, viewer["id"], viewer=refreshed),
            "message": "Profile updated.",
        }

    def api_update_password(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not viewer:
            raise APIError("You must be logged in.", HTTPStatus.UNAUTHORIZED)
        row = conn.execute("SELECT * FROM users WHERE id = ?", (viewer["id"],)).fetchone()
        if not row:
            raise APIError("User not found.", HTTPStatus.NOT_FOUND)
        user_row = sync_user_restrictions(conn, row)
        if not user_row:
            raise APIError("User not found.", HTTPStatus.NOT_FOUND)

        data = self.read_json()
        new_password = clean_password(data.get("newPassword"))
        current_password = str(data.get("currentPassword") or "")

        if not bool(user_row.get("password_reset_required")):
            if not verify_password(current_password, user_row["password_hash"]):
                raise APIError("Current password is incorrect.", HTTPStatus.FORBIDDEN)

        if verify_password(new_password, user_row["password_hash"]):
            raise APIError("Choose a password different from the current one.")

        now = utc_iso()
        conn.execute(
            """
            UPDATE users
            SET password_hash = ?, password_reset_required = 0,
                password_reset_set_by = NULL, password_reset_set_at = NULL,
                updated_at = ?
            WHERE id = ?
            """,
            (make_password_hash(new_password), now, viewer["id"]),
        )
        conn.commit()
        refreshed = sync_user_restrictions(
            conn,
            conn.execute("SELECT * FROM users WHERE id = ?", (viewer["id"],)).fetchone(),
        )
        return {
            "currentUser": get_user_profile(conn, viewer["id"], viewer=refreshed),
            "message": "Password updated.",
        }

    def api_revoke_other_sessions(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        ensure_can_participate(viewer)
        if not viewer:
            raise APIError("You must be logged in.", HTTPStatus.UNAUTHORIZED)
        revoked = revoke_other_sessions(conn, viewer["id"], self.current_session_token())
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "revoked": revoked,
            "message": "Other active sessions were signed out." if revoked else "No other active sessions were found.",
        }

    def api_search(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        query: dict[str, list[str]],
    ) -> dict[str, Any]:
        term = (query.get("q") or [""])[0].strip()
        section_filter = (query.get("section") or [""])[0].strip()
        author_filter = (query.get("author") or [""])[0].strip()
        tag_filter = (query.get("tag") or [""])[0].strip().lower()
        solved_filter = (query.get("solved") or ["all"])[0].strip().lower()
        sort = (query.get("sort") or ["relevance"])[0].strip().lower()
        if len(term) < 2:
            return {
                "currentUser": get_current_user_payload(conn, viewer),
                "query": term,
                "filters": {
                    "section": section_filter,
                    "author": author_filter,
                    "tag": tag_filter,
                    "solved": solved_filter,
                    "sort": sort,
                },
                "threads": [],
                "posts": [],
                "members": [],
                "sections": [
                    {"id": item["id"], "name": item["name"]}
                    for category in get_sections_with_stats(conn, viewer)
                    for item in category["sections"]
                ],
            }
        self.enforce_rate_limit("search", viewer)
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "query": term,
            "filters": {
                "section": section_filter,
                "author": author_filter,
                "tag": tag_filter,
                "solved": solved_filter,
                "sort": sort,
            },
            "threads": search_threads(
                conn,
                term,
                viewer=viewer,
                section_slug=section_filter,
                author=author_filter,
                tag=tag_filter,
                solved=solved_filter,
                sort=sort,
                limit=12,
            ),
            "posts": search_posts(
                conn,
                term,
                viewer=viewer,
                section_slug=section_filter,
                author=author_filter,
                limit=12,
            ),
            "members": search_members(conn, term, limit=12),
            "sections": [
                {"id": item["id"], "name": item["name"]}
                for category in get_sections_with_stats(conn, viewer)
                for item in category["sections"]
            ],
        }

    def api_notifications(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        query: dict[str, list[str]],
    ) -> dict[str, Any]:
        if not viewer:
            raise APIError("You must be logged in.", HTTPStatus.UNAUTHORIZED)
        status = (query.get("status") or ["all"])[0]
        if status not in {"all", "unread"}:
            status = "all"
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "items": list_notifications(conn, viewer["id"], status=status),
            "counts": {
                "unread": get_unread_notification_count(conn, viewer["id"]),
            },
        }

    def api_mark_notifications(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        notification_id: int | None = None,
    ) -> dict[str, Any]:
        if not viewer:
            raise APIError("You must be logged in.", HTTPStatus.UNAUTHORIZED)
        if notification_id is not None:
            updated = mark_notifications_read(
                conn,
                viewer["id"],
                notification_ids=[notification_id],
            )
        else:
            data = self.read_json()
            raw_ids = data.get("ids") or []
            ids: list[int] = []
            if isinstance(raw_ids, list):
                for value in raw_ids:
                    try:
                        ids.append(int(value))
                    except (TypeError, ValueError):
                        continue
            updated = mark_notifications_read(
                conn,
                viewer["id"],
                notification_ids=ids or None,
            )
        conn.commit()
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "updated": updated,
        }

    def api_messages(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not viewer:
            raise APIError("You must be logged in.", HTTPStatus.UNAUTHORIZED)
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "threads": list_dm_threads(conn, viewer["id"]),
        }

    def api_message_thread(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        thread_id: int,
    ) -> dict[str, Any]:
        if not viewer:
            raise APIError("You must be logged in.", HTTPStatus.UNAUTHORIZED)
        thread = get_dm_thread_summary(conn, thread_id, viewer["id"])
        if not thread:
            raise APIError("Conversation not found.", HTTPStatus.NOT_FOUND)
        updated_reads = 0
        if mark_dm_thread_read(conn, thread_id, viewer["id"]):
            updated_reads += 1
        updated_reads += mark_notifications_read(
            conn,
            viewer["id"],
            target_type="dm_thread",
            target_id=thread_id,
        )
        if updated_reads:
            conn.commit()
            thread = get_dm_thread_summary(conn, thread_id, viewer["id"])
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "thread": thread,
            "messages": list_dm_messages(conn, thread_id, viewer["id"]),
        }

    def api_send_message(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        ensure_can_send_message(viewer)
        self.enforce_rate_limit("dm_send", viewer)
        if not viewer:
            raise APIError("You must be logged in.", HTTPStatus.UNAUTHORIZED)
        data = self.read_json()
        try:
            recipient_id = int(data.get("recipientUserId"))
        except (TypeError, ValueError) as exc:
            raise APIError("Choose a valid member to message.") from exc
        if recipient_id == viewer["id"]:
            raise APIError("You cannot direct message yourself.")
        recipient = conn.execute("SELECT * FROM users WHERE id = ?", (recipient_id,)).fetchone()
        if not recipient:
            raise APIError("Member not found.", HTTPStatus.NOT_FOUND)
        if not can_receive_direct_message(recipient, viewer):
            raise APIError("That user is not accepting new direct messages.", HTTPStatus.FORBIDDEN)
        enforce_recent_action_limit(
            conn,
            viewer,
            query="SELECT created_at FROM dm_messages WHERE sender_id = ? ORDER BY created_at DESC, id DESC LIMIT 1",
            params=(viewer["id"],),
            base_seconds=FLOOD_CONTROL_SECONDS["message"],
            verb="send another message",
        )
        content = clean_text(data.get("content"), min_len=1, max_len=4000, field="Message")
        thread_id = get_or_create_dm_thread(conn, viewer["id"], recipient_id)
        now = utc_iso()
        add_dm_message(
            conn,
            thread_id=thread_id,
            sender_id=viewer["id"],
            recipient_id=recipient_id,
            content=content,
            created_at=now,
        )
        notify_dm_message(
            conn,
            sender=viewer,
            recipient_id=recipient_id,
            thread_id=thread_id,
            content=content,
            created_at=now,
        )
        conn.commit()
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "thread": get_dm_thread_summary(conn, thread_id, viewer["id"]),
            "message": "Direct message sent.",
        }

    def api_reply_message(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        thread_id: int,
    ) -> dict[str, Any]:
        ensure_can_send_message(viewer)
        self.enforce_rate_limit("dm_send", viewer)
        if not viewer:
            raise APIError("You must be logged in.", HTTPStatus.UNAUTHORIZED)
        data = self.read_json()
        thread_row = conn.execute(
            """
            SELECT *
            FROM dm_threads
            WHERE id = ? AND (user_low_id = ? OR user_high_id = ?)
            """,
            (thread_id, viewer["id"], viewer["id"]),
        ).fetchone()
        if not thread_row:
            raise APIError("Conversation not found.", HTTPStatus.NOT_FOUND)
        recipient_id = (
            thread_row["user_high_id"]
            if thread_row["user_low_id"] == viewer["id"]
            else thread_row["user_low_id"]
        )
        recipient = conn.execute("SELECT * FROM users WHERE id = ?", (recipient_id,)).fetchone()
        if not recipient:
            raise APIError("Member not found.", HTTPStatus.NOT_FOUND)
        if not can_receive_direct_message(recipient, viewer):
            raise APIError("That user is not accepting new direct messages.", HTTPStatus.FORBIDDEN)
        enforce_recent_action_limit(
            conn,
            viewer,
            query="SELECT created_at FROM dm_messages WHERE sender_id = ? ORDER BY created_at DESC, id DESC LIMIT 1",
            params=(viewer["id"],),
            base_seconds=FLOOD_CONTROL_SECONDS["message"],
            verb="send another message",
        )
        content = clean_text(data.get("content"), min_len=1, max_len=4000, field="Message")
        now = utc_iso()
        add_dm_message(
            conn,
            thread_id=thread_id,
            sender_id=viewer["id"],
            recipient_id=recipient_id,
            content=content,
            created_at=now,
        )
        notify_dm_message(
            conn,
            sender=viewer,
            recipient_id=recipient_id,
            thread_id=thread_id,
            content=content,
            created_at=now,
        )
        conn.commit()
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "thread": get_dm_thread_summary(conn, thread_id, viewer["id"]),
            "messages": list_dm_messages(conn, thread_id, viewer["id"]),
            "message": "Reply sent.",
        }

    def api_reports(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        query: dict[str, list[str]],
    ) -> dict[str, Any]:
        if not viewer or not is_staff(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        status = (query.get("status") or ["open"])[0]
        if status not in {"open", "resolved", "all"}:
            status = "open"
        if mark_notifications_read(conn, viewer["id"], target_type="report_queue"):
            conn.commit()
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "items": list_reports(conn, status=status),
            "counts": {
                "open": get_open_report_count(conn),
                "resolved": conn.execute(
                    "SELECT COUNT(*) AS count FROM reports WHERE status = 'resolved'"
                ).fetchone()["count"],
                "appeals": get_open_appeal_count(conn),
            },
        }

    def api_create_report(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not viewer:
            raise APIError("You must be logged in.", HTTPStatus.UNAUTHORIZED)
        self.enforce_rate_limit("report", viewer)
        enforce_recent_action_limit(
            conn,
            viewer,
            query="SELECT created_at FROM reports WHERE reporter_id = ? ORDER BY created_at DESC, id DESC LIMIT 1",
            params=(viewer["id"],),
            base_seconds=FLOOD_CONTROL_SECONDS["report"],
            verb="submit another report",
        )
        data = self.read_json()
        target_type = str(data.get("targetType") or "").strip().lower()
        try:
            target_id = int(data.get("targetId"))
        except (TypeError, ValueError) as exc:
            raise APIError("Choose something valid to report.") from exc
        target = resolve_report_target(conn, target_type, target_id, viewer=viewer)
        reason = clean_text(data.get("reason"), min_len=3, max_len=80, field="Reason")
        details = clean_text(data.get("details"), min_len=0, max_len=1500, field="Details")
        now = utc_iso()
        conn.execute(
            """
            INSERT INTO reports (
                reporter_id, target_type, target_id, target_label, target_preview,
                context_thread_id, reason, details, status, admin_note,
                handled_by, created_at, updated_at, handled_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open', '', NULL, ?, ?, NULL)
            """,
            (
                viewer["id"],
                target["type"],
                target["id"],
                target["label"],
                target["preview"],
                target.get("contextThreadId"),
                reason,
                details,
                now,
                now,
            ),
        )
        create_staff_notifications(
            conn,
            actor_id=viewer["id"],
            title=f"New report: {reason}",
            body=f"{viewer['username']} reported {target['label']}.",
            target_type="report_queue",
            metadata={"targetType": target["type"], "targetId": target["id"]},
            created_at=now,
        )
        conn.commit()
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "submitted": True,
            "message": "Report submitted to the moderation team.",
        }

    def api_update_report(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        report_id: int,
    ) -> dict[str, Any]:
        if not viewer or not is_staff(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        ensure_can_participate(viewer)
        row = conn.execute(
            "SELECT * FROM reports WHERE id = ?",
            (report_id,),
        ).fetchone()
        if not row:
            raise APIError("Report not found.", HTTPStatus.NOT_FOUND)
        data = self.read_json()
        status = clean_report_status(data.get("status", row["status"]))
        admin_note = clean_text(
            data.get("adminNote", row["admin_note"]),
            min_len=0,
            max_len=1200,
            field="Admin note",
        )
        priority = clean_report_priority(data.get("priority", row["triage_priority"]))
        category = clean_report_category(data.get("category", row["triage_category"]))
        resolution_code = clean_text(
            data.get("resolutionCode", row["resolution_code"]),
            min_len=0,
            max_len=80,
            field="Resolution code",
        )
        assigned_to = row["assigned_to"]
        if "assignedTo" in data:
            if data.get("assignedTo") in {None, "", 0}:
                assigned_to = None
            else:
                try:
                    assigned_to = int(data.get("assignedTo"))
                except (TypeError, ValueError) as exc:
                    raise APIError("Assigned moderator is invalid.") from exc
                assignee = conn.execute("SELECT id, role FROM users WHERE id = ?", (assigned_to,)).fetchone()
                if not assignee or not is_staff(dict(assignee)):
                    raise APIError("Assigned moderator must be a staff account.")
        now = utc_iso()
        handled_at = now if status == "resolved" else None
        handled_by = viewer["id"] if status == "resolved" else None
        conn.execute(
            """
            UPDATE reports
            SET status = ?, admin_note = ?, triage_priority = ?, triage_category = ?,
                resolution_code = ?, assigned_to = ?, handled_by = ?, handled_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (status, admin_note, priority, category, resolution_code, assigned_to, handled_by, handled_at, now, report_id),
        )
        conn.commit()
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "message": "Report updated.",
            "items": list_reports(conn, status="all"),
        }

    def api_bulk_update_reports(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not viewer or not is_staff(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        ensure_can_participate(viewer)
        data = self.read_json()
        report_ids = clean_id_list(data.get("reportIds"), field="Reports")
        if not report_ids:
            raise APIError("Choose at least one report.")
        updates: list[tuple[str, Any]] = []
        if "status" in data:
            updates.append(("status", clean_report_status(data.get("status"))))
        if "priority" in data:
            updates.append(("triage_priority", clean_report_priority(data.get("priority"))))
        if "category" in data:
            updates.append(("triage_category", clean_report_category(data.get("category"))))
        if "resolutionCode" in data:
            updates.append((
                "resolution_code",
                clean_text(data.get("resolutionCode"), min_len=0, max_len=80, field="Resolution code"),
            ))
        if "assignedTo" in data:
            assigned_to = data.get("assignedTo")
            if assigned_to in {None, "", 0}:
                updates.append(("assigned_to", None))
            else:
                try:
                    assigned_id = int(assigned_to)
                except (TypeError, ValueError) as exc:
                    raise APIError("Assigned moderator is invalid.") from exc
                assignee = conn.execute("SELECT id, role FROM users WHERE id = ?", (assigned_id,)).fetchone()
                if not assignee or not is_staff(dict(assignee)):
                    raise APIError("Assigned moderator must be a staff account.")
                updates.append(("assigned_to", assigned_id))
        if not updates:
            raise APIError("Choose at least one change to apply.")
        now = utc_iso()
        if any(field == "status" and value == "resolved" for field, value in updates):
            updates.extend([("handled_by", viewer["id"]), ("handled_at", now)])
        elif any(field == "status" and value == "open" for field, value in updates):
            updates.extend([("handled_by", None), ("handled_at", None)])
        updates.append(("updated_at", now))
        set_clause = ", ".join(f"{field} = ?" for field, _ in updates)
        placeholders = ", ".join("?" for _ in report_ids)
        conn.execute(
            f"UPDATE reports SET {set_clause} WHERE id IN ({placeholders})",
            tuple(value for _, value in updates) + tuple(report_ids),
        )
        conn.commit()
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "message": "Report queue updated.",
            "items": list_reports(conn, status="all"),
        }

    def api_appeals(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        query: dict[str, list[str]],
    ) -> dict[str, Any]:
        if not viewer:
            raise APIError("You must be logged in.", HTTPStatus.UNAUTHORIZED)
        status = (query.get("status") or ["open"])[0].strip().lower()
        if status not in {"open", "resolved", "all"}:
            status = "open"
        target_user_id = None
        if is_staff(viewer):
            raw_user_id = (query.get("userId") or [""])[0].strip()
            if raw_user_id:
                try:
                    target_user_id = int(raw_user_id)
                except (TypeError, ValueError):
                    target_user_id = None
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "items": list_appeals_for_viewer(
                conn,
                viewer,
                status=status,
                target_user_id=target_user_id,
            ),
            "counts": {
                "open": get_open_appeal_count(conn),
                "resolved": conn.execute(
                    "SELECT COUNT(*) AS count FROM appeals WHERE status = 'resolved'"
                ).fetchone()["count"],
            },
        }

    def api_create_appeal(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not viewer:
            raise APIError("You must be logged in.", HTTPStatus.UNAUTHORIZED)
        if not (is_banned_user(viewer) or active_timeout_until(viewer) or active_mute_until(viewer)):
            raise APIError("There is no active restriction on this account to appeal.")
        existing = conn.execute(
            "SELECT id FROM appeals WHERE user_id = ? AND status = 'open' ORDER BY created_at DESC LIMIT 1",
            (viewer["id"],),
        ).fetchone()
        if existing:
            raise APIError("You already have an open appeal under review.")
        data = self.read_json()
        message = clean_text(data.get("message"), min_len=12, max_len=2000, field="Appeal")
        now = utc_iso()
        cur = conn.execute(
            """
            INSERT INTO appeals (
                user_id, target_user_id, action_id, message, status,
                staff_note, handled_by, created_at, updated_at, handled_at
            )
            VALUES (?, ?, NULL, ?, 'open', '', NULL, ?, ?, NULL)
            """,
            (viewer["id"], viewer["id"], message, now, now),
        )
        create_staff_notifications(
            conn,
            actor_id=viewer["id"],
            title=f"New appeal from {viewer['username']}",
            body=short_preview(message, max_len=140),
            target_type="appeal_queue",
            target_id=cur.lastrowid,
            created_at=now,
        )
        conn.commit()
        return {
            "currentUser": get_user_profile(conn, viewer["id"], viewer=viewer),
            "message": "Appeal submitted for staff review.",
            "items": list_appeals_for_viewer(conn, viewer, status="all"),
        }

    def api_update_appeal(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        appeal_id: int,
    ) -> dict[str, Any]:
        if not viewer or not is_staff(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        ensure_can_participate(viewer)
        row = conn.execute("SELECT * FROM appeals WHERE id = ?", (appeal_id,)).fetchone()
        if not row:
            raise APIError("Appeal not found.", HTTPStatus.NOT_FOUND)
        data = self.read_json()
        status = clean_report_status(data.get("status", row["status"]))
        staff_note = clean_text(
            data.get("staffNote", row["staff_note"]),
            min_len=0,
            max_len=1200,
            field="Staff note",
        )
        now = utc_iso()
        handled_at = now if status == "resolved" else None
        handled_by = viewer["id"] if status == "resolved" else None
        conn.execute(
            """
            UPDATE appeals
            SET status = ?, staff_note = ?, handled_by = ?, handled_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (status, staff_note, handled_by, handled_at, now, appeal_id),
        )
        conn.commit()
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "message": "Appeal updated.",
            "items": list_appeals_for_viewer(conn, viewer, status="all"),
        }

    def api_contact(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        self.enforce_rate_limit("contact", viewer)
        data = self.read_json()
        now = utc_iso()
        submitted_name = data.get("name") or (viewer.get("username") if viewer else "")
        name = clean_text(submitted_name, min_len=2, max_len=80, field="Name")
        discord_username = clean_discord_username(data.get("discordUsername"))
        if viewer:
            enforce_recent_action_limit(
                conn,
                viewer,
                query="SELECT created_at FROM contact_submissions WHERE user_id = ? ORDER BY created_at DESC, id DESC LIMIT 1",
                params=(viewer["id"],),
                base_seconds=FLOOD_CONTROL_SECONDS["contact"],
                verb="contact staff",
            )
        subject = clean_text(data.get("subject"), min_len=4, max_len=120, field="Subject")
        message = clean_text(data.get("message"), min_len=10, max_len=4000, field="Message")
        conn.execute(
            """
            INSERT INTO contact_submissions (
                user_id, name, email, discord_username, subject, message, status,
                admin_note, handled_by, created_at, updated_at, handled_at
            )
            VALUES (?, ?, '', ?, ?, ?, 'open', '', NULL, ?, ?, NULL)
            """,
            (
                viewer["id"] if viewer else None,
                name,
                discord_username,
                subject,
                message,
                now,
                now,
            ),
        )
        create_staff_notifications(
            conn,
            actor_id=viewer["id"] if viewer else None,
            title=f"New contact notice: {subject}",
            body=f"{name} sent a staff contact form message.",
            target_type="contact_notice",
            created_at=now,
        )
        conn.commit()
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "submitted": True,
            "message": "Your message has been sent to the moderation team for review.",
        }

    def api_notices(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        query: dict[str, list[str]],
    ) -> dict[str, Any]:
        if not viewer or not is_staff(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        status = (query.get("status") or ["open"])[0]
        if status not in {"open", "resolved", "all"}:
            status = "open"
        if mark_notifications_read(conn, viewer["id"], target_type="contact_notice"):
            conn.commit()
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "items": list_contact_submissions(conn, status=status),
            "counts": {
                "open": get_open_contact_notice_count(conn),
                "resolved": conn.execute(
                    "SELECT COUNT(*) AS count FROM contact_submissions WHERE status = 'resolved'"
                ).fetchone()["count"],
            },
        }

    def api_update_contact_notice(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        submission_id: int,
    ) -> dict[str, Any]:
        if not viewer or not is_staff(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        ensure_can_participate(viewer)
        row = conn.execute(
            "SELECT * FROM contact_submissions WHERE id = ?",
            (submission_id,),
        ).fetchone()
        if not row:
            raise APIError("Contact submission not found.", HTTPStatus.NOT_FOUND)
        data = self.read_json()
        new_status = data.get("status", row["status"])
        if new_status not in {"open", "resolved"}:
            raise APIError("Invalid notice status.")
        admin_note = clean_text(
            data.get("adminNote", row["admin_note"]),
            min_len=0,
            max_len=1000,
            field="Admin note",
        )
        now = utc_iso()
        handled_at = now if new_status == "resolved" else None
        handled_by = viewer["id"] if new_status == "resolved" else None
        conn.execute(
            """
            UPDATE contact_submissions
            SET status = ?, admin_note = ?, handled_by = ?, handled_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (new_status, admin_note, handled_by, handled_at, now, submission_id),
        )
        conn.commit()
        updated = list_contact_submissions(conn, status="all", limit=200)
        item = next((entry for entry in updated if entry["id"] == submission_id), None)
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "item": item,
            "counts": {
                "open": get_open_contact_notice_count(conn),
                "resolved": conn.execute(
                    "SELECT COUNT(*) AS count FROM contact_submissions WHERE status = 'resolved'"
                ).fetchone()["count"],
            },
        }

    def api_users(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        query: dict[str, list[str]],
    ) -> dict[str, Any]:
        members = list_members(conn)
        search = (query.get("q") or [""])[0].strip().lower()
        role_filter = (query.get("role") or ["all"])[0].strip()
        page, page_size, last_page = parse_pagination_query(
            query,
            default_page_size=DEFAULT_MEMBER_PAGE_SIZE,
        )
        if search:
            members = [m for m in members if search in m["username"].lower()]
        if role_filter and role_filter != "all":
            members = [m for m in members if m["role"] == role_filter]
        pagination = resolve_pagination(
            len(members),
            page=page,
            page_size=page_size,
            last_page=last_page,
        )
        members = members[pagination["offset"] : pagination["offset"] + pagination["pageSize"]]
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "members": members,
            "counts": get_role_breakdown(conn),
            "pagination": pagination,
        }

    def api_user_detail(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        user_id: int,
    ) -> dict[str, Any]:
        profile = get_user_profile(conn, user_id, viewer=viewer)
        if not profile:
            raise APIError("User not found.", HTTPStatus.NOT_FOUND)
        return {"currentUser": get_current_user_payload(conn, viewer), "user": profile}

    def api_update_role(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        user_id: int,
    ) -> dict[str, Any]:
        if not viewer or not can_manage_user(viewer, "new"):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        ensure_can_participate(viewer)
        target = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not target:
            raise APIError("User not found.", HTTPStatus.NOT_FOUND)
        data = self.read_json()
        new_role = data.get("role")
        if new_role not in ROLES:
            raise APIError("Invalid role.")
        if target["role"] == "owner" and viewer["role"] != "owner":
            raise APIError("Only the owner can modify the owner role.", HTTPStatus.FORBIDDEN)
        if viewer["role"] == "admin" and role_level(new_role) > role_level("mod"):
            raise APIError("Admins can only assign up to mod.", HTTPStatus.FORBIDDEN)
        if viewer["role"] == "admin" and role_level(target["role"]) >= role_level("admin"):
            raise APIError("Admins cannot change admin or owner accounts.", HTTPStatus.FORBIDDEN)
        now = utc_iso()
        conn.execute(
            "UPDATE users SET role = ?, updated_at = ? WHERE id = ?",
            (new_role, now, user_id),
        )
        log_moderation_action(
            conn,
            user_id=user_id,
            actor_id=viewer["id"],
            action_type="role_change",
            reason=f"Role updated from {target['role']} to {new_role}.",
            metadata={"fromRole": target["role"], "toRole": new_role},
            created_at=now,
        )
        notify_staff_action(
            conn,
            target_user_id=user_id,
            actor=viewer,
            action="role_change",
            reason=f"Role updated from {target['role']} to {new_role}.",
            metadata={"fromRole": target["role"], "toRole": new_role},
            created_at=now,
        )
        conn.commit()
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "user": get_user_profile(conn, user_id, viewer=viewer),
        }

    def api_moderate_user(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        user_id: int,
    ) -> dict[str, Any]:
        if not viewer or not is_staff(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        ensure_can_participate(viewer)
        target_row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not target_row:
            raise APIError("User not found.", HTTPStatus.NOT_FOUND)
        target = sync_user_restrictions(conn, target_row)
        if not target or not can_moderate_user(viewer, target):
            raise APIError("You cannot moderate that user.", HTTPStatus.FORBIDDEN)

        data = self.read_json()
        action = str(data.get("action") or "").strip().lower()
        now = utc_iso()
        message = "Moderation action saved."

        if action == "note":
            note = clean_text(data.get("note") or data.get("reason"), min_len=2, max_len=1000, field="Note")
            log_moderation_action(
                conn,
                user_id=user_id,
                actor_id=viewer["id"],
                action_type="note",
                note=note,
                created_at=now,
            )
            conn.commit()
            message = "Staff note saved."
        elif action == "warn":
            reason = clean_text(data.get("reason"), min_len=4, max_len=500, field="Warning reason")
            log_moderation_action(
                conn,
                user_id=user_id,
                actor_id=viewer["id"],
                action_type="warn",
                reason=reason,
                created_at=now,
            )
            notify_staff_action(
                conn,
                target_user_id=user_id,
                actor=viewer,
                action="warn",
                reason=reason,
                created_at=now,
            )
            conn.commit()
            message = "Warning logged."
        elif action == "timeout":
            if is_banned_user(target):
                raise APIError("Banned users cannot also receive a timeout.")
            try:
                minutes = int(data.get("minutes"))
            except (TypeError, ValueError) as exc:
                raise APIError("Timeout duration must be a whole number of minutes.") from exc
            if minutes < 1 or minutes > 43_200:
                raise APIError("Timeout duration must be between 1 minute and 30 days.")
            reason = clean_text(data.get("reason"), min_len=4, max_len=500, field="Timeout reason")
            expires_at = utc_iso(utc_now() + timedelta(minutes=minutes))
            conn.execute(
                """
                UPDATE users
                SET timeout_until = ?, timeout_reason = ?, timeout_set_by = ?, updated_at = ?
                WHERE id = ?
                """,
                (expires_at, reason, viewer["id"], now, user_id),
            )
            log_moderation_action(
                conn,
                user_id=user_id,
                actor_id=viewer["id"],
                action_type="timeout",
                reason=reason,
                expires_at=expires_at,
                metadata={"minutes": minutes},
                created_at=now,
            )
            notify_staff_action(
                conn,
                target_user_id=user_id,
                actor=viewer,
                action="timeout",
                reason=reason,
                metadata={"minutes": minutes},
                created_at=now,
            )
            conn.commit()
            message = "User timed out."
        elif action == "clear_timeout":
            if not active_timeout_until(target):
                raise APIError("This user is not currently timed out.")
            reason = clean_text(data.get("reason"), min_len=0, max_len=500, field="Reason")
            conn.execute(
                """
                UPDATE users
                SET timeout_until = NULL, timeout_reason = '', timeout_set_by = NULL, updated_at = ?
                WHERE id = ?
                """,
                (now, user_id),
            )
            log_moderation_action(
                conn,
                user_id=user_id,
                actor_id=viewer["id"],
                action_type="clear_timeout",
                reason=reason,
                created_at=now,
            )
            notify_staff_action(
                conn,
                target_user_id=user_id,
                actor=viewer,
                action="clear_timeout",
                reason=reason,
                created_at=now,
            )
            conn.commit()
            message = "Timeout cleared."
        elif action == "mute":
            try:
                minutes = int(data.get("minutes"))
            except (TypeError, ValueError) as exc:
                raise APIError("Mute duration must be a whole number of minutes.") from exc
            if minutes < 1 or minutes > 43_200:
                raise APIError("Mute duration must be between 1 minute and 30 days.")
            reason = clean_text(data.get("reason"), min_len=4, max_len=500, field="Mute reason")
            expires_at = utc_iso(utc_now() + timedelta(minutes=minutes))
            conn.execute(
                """
                UPDATE users
                SET mute_until = ?, mute_reason = ?, mute_set_by = ?, updated_at = ?
                WHERE id = ?
                """,
                (expires_at, reason, viewer["id"], now, user_id),
            )
            log_moderation_action(
                conn,
                user_id=user_id,
                actor_id=viewer["id"],
                action_type="mute",
                reason=reason,
                expires_at=expires_at,
                metadata={"minutes": minutes},
                created_at=now,
            )
            notify_staff_action(
                conn,
                target_user_id=user_id,
                actor=viewer,
                action="mute",
                reason=reason,
                metadata={"minutes": minutes},
                created_at=now,
            )
            conn.commit()
            message = "User muted."
        elif action == "clear_mute":
            if not active_mute_until(target):
                raise APIError("This user is not currently muted.")
            reason = clean_text(data.get("reason"), min_len=0, max_len=500, field="Reason")
            conn.execute(
                """
                UPDATE users
                SET mute_until = NULL, mute_reason = '', mute_set_by = NULL, updated_at = ?
                WHERE id = ?
                """,
                (now, user_id),
            )
            log_moderation_action(
                conn,
                user_id=user_id,
                actor_id=viewer["id"],
                action_type="clear_mute",
                reason=reason,
                created_at=now,
            )
            notify_staff_action(
                conn,
                target_user_id=user_id,
                actor=viewer,
                action="clear_mute",
                reason=reason,
                created_at=now,
            )
            conn.commit()
            message = "Mute cleared."
        elif action == "shadow_mute":
            reason = clean_text(data.get("reason"), min_len=4, max_len=500, field="Shadow mute reason")
            conn.execute(
                """
                UPDATE users
                SET shadow_muted = 1, updated_at = ?
                WHERE id = ?
                """,
                (now, user_id),
            )
            log_moderation_action(
                conn,
                user_id=user_id,
                actor_id=viewer["id"],
                action_type="shadow_mute",
                reason=reason,
                created_at=now,
            )
            conn.commit()
            message = "User shadow-muted."
        elif action == "clear_shadow_mute":
            if not bool(target.get("shadow_muted")):
                raise APIError("This user is not currently shadow-muted.")
            reason = clean_text(data.get("reason"), min_len=0, max_len=500, field="Reason")
            conn.execute(
                """
                UPDATE users
                SET shadow_muted = 0, updated_at = ?
                WHERE id = ?
                """,
                (now, user_id),
            )
            log_moderation_action(
                conn,
                user_id=user_id,
                actor_id=viewer["id"],
                action_type="clear_shadow_mute",
                reason=reason,
                created_at=now,
            )
            conn.commit()
            message = "Shadow mute cleared."
        elif action == "ban":
            if is_banned_user(target):
                raise APIError("This user is already banned.")
            reason = clean_text(data.get("reason"), min_len=4, max_len=500, field="Ban reason")
            conn.execute(
                """
                UPDATE users
                SET banned_at = ?, ban_reason = ?, banned_by = ?,
                    timeout_until = NULL, timeout_reason = '', timeout_set_by = NULL,
                    mute_until = NULL, mute_reason = '', mute_set_by = NULL,
                    updated_at = ?
                WHERE id = ?
                """,
                (now, reason, viewer["id"], now, user_id),
            )
            log_moderation_action(
                conn,
                user_id=user_id,
                actor_id=viewer["id"],
                action_type="ban",
                reason=reason,
                created_at=now,
            )
            notify_staff_action(
                conn,
                target_user_id=user_id,
                actor=viewer,
                action="ban",
                reason=reason,
                created_at=now,
            )
            conn.commit()
            delete_sessions_for_user(conn, user_id)
            message = "User banned."
        elif action == "unban":
            if not is_banned_user(target):
                raise APIError("This user is not currently banned.")
            reason = clean_text(data.get("reason"), min_len=0, max_len=500, field="Reason")
            conn.execute(
                """
                UPDATE users
                SET banned_at = NULL, ban_reason = '', banned_by = NULL, updated_at = ?
                WHERE id = ?
                """,
                (now, user_id),
            )
            log_moderation_action(
                conn,
                user_id=user_id,
                actor_id=viewer["id"],
                action_type="unban",
                reason=reason,
                created_at=now,
            )
            notify_staff_action(
                conn,
                target_user_id=user_id,
                actor=viewer,
                action="unban",
                reason=reason,
                created_at=now,
            )
            conn.commit()
            message = "User unbanned."
        elif action == "xp_adjust":
            try:
                delta_xp = int(data.get("deltaXp"))
            except (TypeError, ValueError) as exc:
                raise APIError("XP adjustment must be a whole number.") from exc
            if delta_xp == 0 or delta_xp < -5000 or delta_xp > 5000:
                raise APIError("XP adjustment must be between -5000 and 5000 and cannot be zero.")
            reason = clean_text(data.get("reason"), min_len=4, max_len=500, field="XP reason")
            before_xp = int(target["xp"])
            before_role = target["role"]
            award_xp(conn, user_id, delta_xp)
            updated_target = conn.execute("SELECT xp, role FROM users WHERE id = ?", (user_id,)).fetchone()
            after_xp = int(updated_target["xp"]) if updated_target else before_xp
            after_role = updated_target["role"] if updated_target else before_role
            log_moderation_action(
                conn,
                user_id=user_id,
                actor_id=viewer["id"],
                action_type="xp_adjust",
                reason=reason,
                delta_xp=delta_xp,
                metadata={
                    "beforeXp": before_xp,
                    "afterXp": after_xp,
                    "beforeRole": before_role,
                    "afterRole": after_role,
                },
                created_at=now,
            )
            notify_staff_action(
                conn,
                target_user_id=user_id,
                actor=viewer,
                action="xp_adjust",
                reason=reason,
                delta_xp=delta_xp,
                metadata={
                    "beforeXp": before_xp,
                    "afterXp": after_xp,
                    "beforeRole": before_role,
                    "afterRole": after_role,
                },
                created_at=now,
            )
            conn.commit()
            message = "XP updated."
        elif action == "set_temp_password":
            if not is_admin(viewer):
                raise APIError(
                    "Only admins and the owner can set temporary passwords.",
                    HTTPStatus.FORBIDDEN,
                )
            if is_banned_user(target):
                raise APIError("Unban the user before issuing a recovery password.")
            temp_password = clean_password(data.get("tempPassword"))
            note = clean_text(data.get("note"), min_len=0, max_len=500, field="Recovery note")
            conn.execute(
                """
                UPDATE users
                SET password_hash = ?, password_reset_required = 1,
                    password_reset_set_by = ?, password_reset_set_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (make_password_hash(temp_password), viewer["id"], now, now, user_id),
            )
            log_moderation_action(
                conn,
                user_id=user_id,
                actor_id=viewer["id"],
                action_type="temp_password",
                note=note,
                created_at=now,
            )
            notify_staff_action(
                conn,
                target_user_id=user_id,
                actor=viewer,
                action="temp_password",
                note=note,
                created_at=now,
            )
            conn.commit()
            delete_sessions_for_user(conn, user_id)
            message = "Temporary password set. The user will be forced to reset it after login."
        else:
            raise APIError("Unknown moderation action.")

        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "user": get_user_profile(conn, user_id, viewer=viewer),
            "message": message,
        }

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
        sort_order = clean_sort_order(
            data.get("sortOrder"),
            default=get_next_section_sort_order(conn, category["id"]),
        )
        try:
            conn.execute(
                """
                INSERT INTO sections (
                    category_id, slug, name, description, icon, icon_bg,
                    required_role, write_role, sort_order
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    sort_order,
                ),
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
        sort_order = clean_sort_order(
            data.get("sortOrder", section["sort_order"]),
            default=section["sort_order"],
        )
        try:
            conn.execute(
                """
                UPDATE sections
                SET category_id = ?, slug = ?, name = ?, description = ?, icon = ?, icon_bg = ?,
                    required_role = ?, write_role = ?, sort_order = ?
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
                    sort_order,
                    section["id"],
                ),
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
            WHERE t.section_id = ?
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
        conn.commit()
        if thread_ids:
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
            WHERE t.section_id = ?
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

    def api_create_thread(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        slug: str,
    ) -> dict[str, Any]:
        ensure_can_post_content(viewer)
        self.enforce_rate_limit("thread_create", viewer)
        section = get_section_by_slug(conn, slug)
        if not section:
            raise APIError("Section not found.", HTTPStatus.NOT_FOUND)
        if not has_required_role(viewer, section["write_role"]):
            raise APIError("You do not have permission to post here.", HTTPStatus.FORBIDDEN)
        enforce_recent_action_limit(
            conn,
            viewer,
            query="SELECT created_at FROM threads WHERE author_id = ? ORDER BY created_at DESC, id DESC LIMIT 1",
            params=(viewer["id"],),
            base_seconds=FLOOD_CONTROL_SECONDS["thread"],
            verb="start another thread",
        )
        data = self.read_json()
        title = clean_text(data.get("title"), min_len=4, max_len=120, field="Title")
        media_uploads = normalize_media_uploads(
            data.get("mediaUploads"),
            max_items=POST_MEDIA_MAX_COUNT,
        )
        content = clean_post_content(data.get("content"), has_media=bool(media_uploads))
        enforce_low_trust_content_limits(viewer, content)
        tags = normalize_tags(data.get("tags"))
        poll = clean_poll_payload(data.get("poll"))
        now = utc_iso()
        cur = conn.execute(
            """
            INSERT INTO threads (
                section_id, author_id, title, tags_json, created_at, updated_at,
                edited_at, view_count, pinned, locked, solved, answer_post_id, shadow_hidden
            )
            VALUES (?, ?, ?, ?, ?, ?, NULL, 1, 0, 0, 0, NULL, ?)
            """,
            (section["id"], viewer["id"], title, json.dumps(tags), now, now, int(is_shadow_muted(viewer))),
        )
        thread_id = cur.lastrowid
        first_post = conn.execute(
            """
            INSERT INTO posts (thread_id, author_id, content, created_at, updated_at, edited_at, shadow_hidden)
            VALUES (?, ?, ?, ?, ?, NULL, ?)
            """,
            (thread_id, viewer["id"], content, now, now, int(is_shadow_muted(viewer))),
        )
        if poll:
            create_thread_poll(conn, thread_id=thread_id, poll=poll, created_at=now)
        save_post_media_entries(
            conn,
            post_id=first_post.lastrowid,
            uploads=media_uploads,
            created_at=now,
        )
        if not is_shadow_muted(viewer):
            notify_mentions_in_thread(
                conn,
                actor=viewer,
                content=content,
                thread_id=thread_id,
                post_id=first_post.lastrowid,
                required_role=section["required_role"],
                created_at=now,
            )
        ensure_thread_subscription(conn, thread_id=thread_id, user_id=viewer["id"], created_at=now)
        conn.commit()
        award_xp(conn, viewer["id"], XP_THREAD)
        return {
            "currentUser": get_user_profile(conn, viewer["id"], viewer=viewer),
            "thread": serialize_thread(get_thread_by_id(conn, thread_id), conn, viewer),
        }

    def api_thread(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        thread_id: int,
        query: dict[str, list[str]],
    ) -> dict[str, Any]:
        thread = get_thread_by_id(conn, thread_id)
        if not thread:
            raise APIError("Thread not found.", HTTPStatus.NOT_FOUND)
        if not has_required_role(viewer, thread["section_required_role"]):
            raise APIError("You do not have access to this thread.", HTTPStatus.FORBIDDEN)
        if is_shadow_hidden_to_viewer(hidden=thread["shadow_hidden"], author_id=thread["author_id"], viewer=viewer):
            raise APIError("Thread not found.", HTTPStatus.NOT_FOUND)
        page, page_size, last_page = parse_pagination_query(
            query,
            default_page_size=DEFAULT_POST_PAGE_SIZE,
        )
        focus_post_id = None
        raw_focus_post = (query.get("postId") or query.get("post") or [""])[0]
        if raw_focus_post:
            try:
                focus_post_id = int(raw_focus_post)
            except (TypeError, ValueError):
                focus_post_id = None
        conn.execute(
            "UPDATE threads SET view_count = view_count + 1 WHERE id = ?",
            (thread_id,),
        )
        if viewer:
            mark_notifications_read(
                conn,
                viewer["id"],
                target_type="thread",
                target_id=thread_id,
            )
        conn.commit()
        updated_thread = get_thread_by_id(conn, thread_id)
        posts, pagination = get_posts_for_thread(
            conn,
            thread_id,
            viewer,
            page=page,
            page_size=page_size,
            last_page=last_page,
            focus_post_id=focus_post_id,
        )
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "topMembers": get_top_members(conn),
            "thread": serialize_thread(updated_thread, conn, viewer),
            "posts": posts,
            "relatedThreads": get_related_threads(conn, updated_thread, viewer),
            "pagination": pagination,
        }

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
                "UPDATE posts SET thread_id = ? WHERE thread_id = ?",
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
            conn.execute(
                "UPDATE threads SET updated_at = ? WHERE id = ?",
                (now, merge_to_thread_id),
            )
            conn.execute("DELETE FROM threads WHERE id = ?", (thread_id,))
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
        tags = normalize_tags(data.get("tags", json.loads(thread["tags_json"] or "[]")))
        pinned = bool(data.get("pinned", thread["pinned"]))
        locked = bool(data.get("locked", thread["locked"]))
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
                    "SELECT id FROM posts WHERE id = ? AND thread_id = ?",
                    (answer_post_id, thread_id),
                ).fetchone()
                if not answer_row:
                    raise APIError("That answer must be a post inside this thread.")
                solved = True
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
        now = utc_iso()
        conn.execute(
            """
            UPDATE threads
            SET section_id = ?, title = ?, tags_json = ?, pinned = ?, locked = ?,
                solved = ?, answer_post_id = ?, edited_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                next_section_id,
                title,
                json.dumps(tags),
                int(pinned),
                int(locked),
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
        conn.commit()
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "thread": serialize_thread(get_thread_by_id(conn, thread_id), conn, viewer),
        }

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
        post_ids = [
            row["id"]
            for row in conn.execute("SELECT id FROM posts WHERE thread_id = ?", (thread_id,)).fetchall()
        ]
        media_paths = collect_post_media_paths(conn, post_ids)
        delete_post_artifact_rows(conn, post_ids)
        conn.execute("DELETE FROM posts WHERE thread_id = ?", (thread_id,))
        conn.execute("DELETE FROM thread_bookmarks WHERE thread_id = ?", (thread_id,))
        conn.execute("DELETE FROM thread_subscriptions WHERE thread_id = ?", (thread_id,))
        conn.execute("DELETE FROM thread_polls WHERE thread_id = ?", (thread_id,))
        conn.execute("DELETE FROM threads WHERE id = ?", (thread_id,))
        conn.commit()
        for storage_path in media_paths:
            delete_media_file(storage_path)
        return {"currentUser": get_current_user_payload(conn, viewer), "deleted": True}

    def api_create_post(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        thread_id: int,
    ) -> dict[str, Any]:
        ensure_can_post_content(viewer)
        self.enforce_rate_limit("post_create", viewer)
        thread = get_thread_by_id(conn, thread_id)
        if not thread:
            raise APIError("Thread not found.", HTTPStatus.NOT_FOUND)
        if thread["locked"]:
            raise APIError("This thread is locked.", HTTPStatus.FORBIDDEN)
        if not has_required_role(viewer, thread["section_write_role"]):
            raise APIError("You do not have permission to reply here.", HTTPStatus.FORBIDDEN)
        enforce_recent_action_limit(
            conn,
            viewer,
            query="SELECT created_at FROM posts WHERE author_id = ? ORDER BY created_at DESC, id DESC LIMIT 1",
            params=(viewer["id"],),
            base_seconds=FLOOD_CONTROL_SECONDS["reply"],
            verb="reply again",
        )
        data = self.read_json()
        media_uploads = normalize_media_uploads(
            data.get("mediaUploads"),
            max_items=POST_MEDIA_MAX_COUNT,
        )
        content = clean_post_content(data.get("content"), has_media=bool(media_uploads))
        enforce_low_trust_content_limits(viewer, content)
        now = utc_iso()
        cur = conn.execute(
            """
            INSERT INTO posts (thread_id, author_id, content, created_at, updated_at, edited_at, shadow_hidden)
            VALUES (?, ?, ?, ?, ?, NULL, ?)
            """,
            (thread_id, viewer["id"], content, now, now, int(is_shadow_muted(viewer))),
        )
        post_id = cur.lastrowid
        save_post_media_entries(
            conn,
            post_id=post_id,
            uploads=media_uploads,
            created_at=now,
        )
        conn.execute(
            "UPDATE threads SET updated_at = ? WHERE id = ?",
            (now, thread_id),
        )
        mentioned_ids: set[int] = set()
        if not is_shadow_muted(viewer):
            mentioned_ids = notify_mentions_in_thread(
                conn,
                actor=viewer,
                content=content,
                thread_id=thread_id,
                post_id=post_id,
                required_role=thread["section_required_role"],
                created_at=now,
            )
            notify_thread_reply(
                conn,
                actor=viewer,
                thread=thread,
                post_id=post_id,
                content=content,
                skip_user_ids=mentioned_ids,
                created_at=now,
            )
        ensure_thread_subscription(conn, thread_id=thread_id, user_id=viewer["id"], created_at=now)
        conn.commit()
        award_xp(conn, viewer["id"], XP_REPLY)
        posts, _ = get_posts_for_thread(
            conn,
            thread_id,
            viewer,
            page=1,
            page_size=DEFAULT_POST_PAGE_SIZE,
            last_page=True,
        )
        new_post = next((post for post in posts if post["id"] == post_id), None)
        return {
            "currentUser": get_user_profile(conn, viewer["id"], viewer=viewer),
            "post": new_post,
            "thread": serialize_thread(get_thread_by_id(conn, thread_id), conn, viewer),
        }

    def api_update_post(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        post_id: int,
    ) -> dict[str, Any]:
        ensure_can_post_content(viewer)
        self.enforce_rate_limit("post_update", viewer)
        row = conn.execute(
            """
            SELECT p.*, t.author_id AS thread_author_id, t.title AS thread_title
            FROM posts p
            JOIN threads t ON t.id = p.thread_id
            WHERE p.id = ?
            """,
            (post_id,),
        ).fetchone()
        if not row:
            raise APIError("Post not found.", HTTPStatus.NOT_FOUND)
        if not (viewer["id"] == row["author_id"] or is_staff(viewer)):
            raise APIError("You cannot edit this post.", HTTPStatus.FORBIDDEN)
        data = self.read_json()
        next_thread_title = None
        if row["id"] == thread_first_post_id(conn, row["thread_id"]) and data.get("title"):
            next_thread_title = clean_text(data.get("title"), min_len=4, max_len=120, field="Title")
        existing_media_rows = list_post_media_rows(conn, [post_id]).get(post_id, [])
        existing_media_ids = [item["id"] for item in existing_media_rows]
        should_update_media = "keepMediaIds" in data or "mediaUploads" in data
        keep_media_ids = (
            clean_id_list(
                data.get("keepMediaIds", existing_media_ids),
                field="Media list",
            )
            if should_update_media
            else existing_media_ids
        )
        if any(media_id not in existing_media_ids for media_id in keep_media_ids):
            raise APIError("One of the selected media items no longer exists.")
        new_uploads = normalize_media_uploads(
            data.get("mediaUploads"),
            max_items=max(0, POST_MEDIA_MAX_COUNT - len(keep_media_ids)),
        )
        content = clean_post_content(
            data.get("content", row["content"]),
            has_media=bool(keep_media_ids or new_uploads),
        )
        enforce_low_trust_content_limits(viewer, content)
        now = utc_iso()
        media_summary = [
            {
                "alt": item["alt_text"] or "Forum image",
                "mimeType": item["mime_type"],
            }
            for item in existing_media_rows
        ]
        conn.execute(
            """
            INSERT INTO post_edits (
                post_id, editor_id, previous_content, previous_title,
                media_summary_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                post_id,
                viewer["id"],
                row["content"],
                row["thread_title"] if row["id"] == thread_first_post_id(conn, row["thread_id"]) else "",
                json.dumps(media_summary),
                now,
            ),
        )
        conn.execute(
            "UPDATE posts SET content = ?, updated_at = ?, edited_at = ? WHERE id = ?",
            (content, now, now, post_id),
        )
        removed_media_paths: list[str] = []
        if should_update_media:
            keep_media_set = set(keep_media_ids)
            removed_media = [
                item for item in existing_media_rows if item["id"] not in keep_media_set
            ]
            if removed_media:
                removed_media_paths = [item["storage_path"] for item in removed_media if item["storage_path"]]
                conn.execute(
                    f"DELETE FROM post_media WHERE id IN ({', '.join('?' for _ in removed_media)})",
                    tuple(item["id"] for item in removed_media),
                )
            for sort_order, media_id in enumerate(keep_media_ids):
                conn.execute(
                    "UPDATE post_media SET sort_order = ? WHERE id = ?",
                    (sort_order, media_id),
                )
            save_post_media_entries(
                conn,
                post_id=post_id,
                uploads=new_uploads,
                created_at=now,
                start_order=len(keep_media_ids),
            )
        if next_thread_title:
            conn.execute(
                "UPDATE threads SET title = ?, updated_at = ?, edited_at = ? WHERE id = ?",
                (
                    next_thread_title,
                    now,
                    now,
                    row["thread_id"],
                ),
            )
        conn.execute("UPDATE threads SET updated_at = ? WHERE id = ?", (now, row["thread_id"]))
        conn.commit()
        for storage_path in removed_media_paths:
            delete_media_file(storage_path)
        posts, _ = get_posts_for_thread(conn, row["thread_id"], viewer)
        post = next((item for item in posts if item["id"] == post_id), None)
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "post": post,
            "thread": serialize_thread(get_thread_by_id(conn, row["thread_id"]), conn, viewer),
        }

    def api_delete_post(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        post_id: int,
    ) -> dict[str, Any]:
        ensure_can_post_content(viewer)
        row = conn.execute(
            "SELECT * FROM posts WHERE id = ?",
            (post_id,),
        ).fetchone()
        if not row:
            raise APIError("Post not found.", HTTPStatus.NOT_FOUND)
        first_post_id = thread_first_post_id(conn, row["thread_id"])
        if row["id"] == first_post_id:
            raise APIError("Delete the thread instead of its first post.")
        if not (viewer["id"] == row["author_id"] or is_staff(viewer)):
            raise APIError("You cannot delete this post.", HTTPStatus.FORBIDDEN)
        now = utc_iso()
        media_paths = collect_post_media_paths(conn, [post_id])
        delete_post_artifact_rows(conn, [post_id])
        conn.execute("DELETE FROM posts WHERE id = ?", (post_id,))
        conn.execute(
            "UPDATE threads SET answer_post_id = NULL, solved = 0 WHERE id = ? AND answer_post_id = ?",
            (row["thread_id"], post_id),
        )
        conn.execute("UPDATE threads SET updated_at = ? WHERE id = ?", (now, row["thread_id"]))
        conn.commit()
        for storage_path in media_paths:
            delete_media_file(storage_path)
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "deleted": True,
            "thread": serialize_thread(get_thread_by_id(conn, row["thread_id"]), conn, viewer),
        }

    def api_toggle_like(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        post_id: int,
    ) -> dict[str, Any]:
        ensure_can_post_content(viewer)
        self.enforce_rate_limit("like_toggle", viewer)
        post = conn.execute(
            """
            SELECT
                p.*,
                t.title AS thread_title,
                s.required_role AS section_required_role
            FROM posts p
            JOIN threads t ON t.id = p.thread_id
            JOIN sections s ON s.id = t.section_id
            WHERE p.id = ?
            """,
            (post_id,),
        ).fetchone()
        if not post:
            raise APIError("Post not found.", HTTPStatus.NOT_FOUND)
        if not has_required_role(viewer, post["section_required_role"]):
            raise APIError("You do not have access to this post.", HTTPStatus.FORBIDDEN)
        if is_shadow_hidden_to_viewer(hidden=post["shadow_hidden"], author_id=post["author_id"], viewer=viewer):
            raise APIError("Post not found.", HTTPStatus.NOT_FOUND)
        existing = conn.execute(
            "SELECT 1 FROM post_likes WHERE post_id = ? AND user_id = ?",
            (post_id, viewer["id"]),
        ).fetchone()
        if existing:
            conn.execute(
                "DELETE FROM post_likes WHERE post_id = ? AND user_id = ?",
                (post_id, viewer["id"]),
            )
            conn.commit()
            if post["author_id"] != viewer["id"]:
                award_xp(conn, post["author_id"], -XP_LIKE)
            liked = False
        else:
            now = utc_iso()
            conn.execute(
                "INSERT INTO post_likes (post_id, user_id, created_at) VALUES (?, ?, ?)",
                (post_id, viewer["id"], now),
            )
            if post["author_id"] != viewer["id"]:
                award_xp(conn, post["author_id"], XP_LIKE)
                notify_post_like(
                    conn,
                    actor=viewer,
                    post=post,
                    thread_title=post["thread_title"],
                    created_at=now,
                )
            conn.commit()
            liked = True
        likes = conn.execute(
            "SELECT COUNT(*) AS count FROM post_likes WHERE post_id = ?",
            (post_id,),
        ).fetchone()["count"]
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "liked": liked,
            "likes": likes,
        }

    def api_toggle_reaction(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        post_id: int,
    ) -> dict[str, Any]:
        ensure_can_post_content(viewer)
        self.enforce_rate_limit("like_toggle", viewer)
        data = self.read_json()
        emoji = clean_reaction_emoji(data.get("emoji"))
        post = conn.execute(
            """
            SELECT
                p.*,
                s.required_role AS section_required_role
            FROM posts p
            JOIN threads t ON t.id = p.thread_id
            JOIN sections s ON s.id = t.section_id
            WHERE p.id = ?
            """,
            (post_id,),
        ).fetchone()
        if not post:
            raise APIError("Post not found.", HTTPStatus.NOT_FOUND)
        if not has_required_role(viewer, post["section_required_role"]):
            raise APIError("You do not have access to this post.", HTTPStatus.FORBIDDEN)
        if is_shadow_hidden_to_viewer(hidden=post["shadow_hidden"], author_id=post["author_id"], viewer=viewer):
            raise APIError("Post not found.", HTTPStatus.NOT_FOUND)
        existing = conn.execute(
            "SELECT 1 FROM post_reactions WHERE post_id = ? AND user_id = ? AND emoji = ?",
            (post_id, viewer["id"], emoji),
        ).fetchone()
        if existing:
            conn.execute(
                "DELETE FROM post_reactions WHERE post_id = ? AND user_id = ? AND emoji = ?",
                (post_id, viewer["id"], emoji),
            )
            active = False
        else:
            conn.execute(
                "INSERT INTO post_reactions (post_id, user_id, emoji, created_at) VALUES (?, ?, ?, ?)",
                (post_id, viewer["id"], emoji, utc_iso()),
            )
            active = True
        conn.commit()
        reaction_summary = list_post_reactions_summary(conn, [post_id], viewer).get(post_id, {"items": [], "viewer": []})
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "active": active,
            "reactions": reaction_summary["items"],
            "viewerReactions": reaction_summary["viewer"],
        }

    def api_post_history(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        post_id: int,
    ) -> dict[str, Any]:
        row = conn.execute(
            """
            SELECT
                p.id,
                p.thread_id,
                s.required_role AS section_required_role
            FROM posts p
            JOIN threads t ON t.id = p.thread_id
            JOIN sections s ON s.id = t.section_id
            WHERE p.id = ?
            """,
            (post_id,),
        ).fetchone()
        if not row:
            raise APIError("Post not found.", HTTPStatus.NOT_FOUND)
        if not has_required_role(viewer, row["section_required_role"]):
            raise APIError("You do not have access to this post history.", HTTPStatus.FORBIDDEN)
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "history": list_post_edit_history(conn, post_id),
        }

    def api_toggle_thread_bookmark(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        thread_id: int,
    ) -> dict[str, Any]:
        ensure_can_participate(viewer)
        thread = get_thread_by_id(conn, thread_id)
        if not thread:
            raise APIError("Thread not found.", HTTPStatus.NOT_FOUND)
        if not has_required_role(viewer, thread["section_required_role"]):
            raise APIError("You do not have access to this thread.", HTTPStatus.FORBIDDEN)
        active = toggle_thread_membership(
            conn,
            table="thread_bookmarks",
            thread_id=thread_id,
            user_id=viewer["id"],
        )
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "thread": serialize_thread(get_thread_by_id(conn, thread_id), conn, viewer),
            "active": active,
            "message": "Thread saved." if active else "Thread removed from saved list.",
        }

    def api_toggle_thread_subscription(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        thread_id: int,
    ) -> dict[str, Any]:
        ensure_can_participate(viewer)
        thread = get_thread_by_id(conn, thread_id)
        if not thread:
            raise APIError("Thread not found.", HTTPStatus.NOT_FOUND)
        if not has_required_role(viewer, thread["section_required_role"]):
            raise APIError("You do not have access to this thread.", HTTPStatus.FORBIDDEN)
        active = toggle_thread_membership(
            conn,
            table="thread_subscriptions",
            thread_id=thread_id,
            user_id=viewer["id"],
        )
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "thread": serialize_thread(get_thread_by_id(conn, thread_id), conn, viewer),
            "active": active,
            "message": "Thread subscription enabled." if active else "Thread subscription removed.",
        }

    def api_vote_thread_poll(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        thread_id: int,
    ) -> dict[str, Any]:
        ensure_can_post_content(viewer)
        thread = get_thread_by_id(conn, thread_id)
        if not thread:
            raise APIError("Thread not found.", HTTPStatus.NOT_FOUND)
        if not has_required_role(viewer, thread["section_required_role"]):
            raise APIError("You do not have access to this poll.", HTTPStatus.FORBIDDEN)
        data = self.read_json()
        option_ids = clean_id_list(data.get("optionIds"), field="Poll options")
        poll = vote_in_thread_poll(conn, thread_id=thread_id, viewer=viewer, option_ids=option_ids)
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "poll": poll,
        }

    def api_admin_health(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not viewer or not is_admin(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "health": get_admin_health(conn),
        }

    def api_admin_backup(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not viewer or not is_admin(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        ensure_can_participate(viewer)
        archive = create_backup_archive()
        append_server_log(f"backup created by {viewer['username']}: {archive.name}")
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "downloadUrl": f"{EXPORT_ROUTE}/backups/{archive.name}",
            "filename": archive.name,
            "message": "Backup archive created.",
        }

    def api_admin_logs(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not viewer or not is_admin(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "logs": read_recent_logs(limit_lines=160),
        }

    def api_admin_media_cleanup(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not viewer or not is_admin(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        ensure_can_participate(viewer)
        result = cleanup_orphan_media(conn)
        append_server_log(
            f"media cleanup by {viewer['username']}: {result['deletedCount']} files, {result['deletedSize']}"
        )
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "cleanup": result,
            "message": "Media cleanup complete.",
        }

    def api_leaderboard(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        query: dict[str, list[str]],
    ) -> dict[str, Any]:
        metric = (query.get("metric") or ["xp"])[0]
        page, page_size, last_page = parse_pagination_query(
            query,
            default_page_size=DEFAULT_LEADERBOARD_PAGE_SIZE,
        )
        members = list_members(conn)
        if metric == "posts":
            members.sort(key=lambda member: (-member["posts"], -member["xp"], member["username"].lower()))
        elif metric == "role":
            members.sort(
                key=lambda member: (
                    -role_level(member["role"]),
                    -member["xp"],
                    member["username"].lower(),
                )
            )
        else:
            metric = "xp"
            members.sort(key=lambda member: (-member["xp"], -member["posts"], member["username"].lower()))
        rank = None
        if viewer:
            for index, member in enumerate(members, start=1):
                if member["id"] == viewer["id"]:
                    rank = index
                    break
        podium = members[:3]
        list_members_only = members[3:]
        pagination = resolve_pagination(
            len(list_members_only),
            page=page,
            page_size=page_size,
            last_page=last_page,
        )
        start = pagination["offset"]
        end = start + pagination["pageSize"]
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "metric": metric,
            "podium": podium,
            "members": list_members_only[start:end],
            "rank": rank,
            "pagination": pagination,
        }


def main() -> None:
    init_db()
    server = ThreadingHTTPServer((HOST, PORT), ForumHandler)
    print(f"OmniForum running at http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
