#!/usr/bin/env python3
"""OmniForum application server.

This keeps the existing static frontend structure but backs it with a real
SQLite-powered API, cookie sessions, and persistent forum data stored in
separate files under ``data/``.
"""

from __future__ import annotations

import base64
import binascii
import csv
import fnmatch
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
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse
from urllib.request import Request, urlopen

try:
    from PIL import Image, ImageOps, ImageSequence, UnidentifiedImageError

    PIL_AVAILABLE = True
except Exception:  # pragma: no cover - dependency availability is environment-specific.
    Image = ImageOps = ImageSequence = None
    UnidentifiedImageError = Exception
    PIL_AVAILABLE = False


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
PLUGIN_DIR = BASE_DIR / "plugins"
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
    "audit_db": DATA_DIR / "audit.db",
    "contact_db": DATA_DIR / "contact.db",
}
MEDIA_ROUTE = "/media"
EXPORT_ROUTE = "/exports"
MEDIA_DIR = DATA_DIR / "uploads"
EXPORTS_DIR = DATA_DIR / "exports"
BACKUP_DIR = EXPORTS_DIR / "backups"
LOG_DIR = DATA_DIR / "logs"
LOG_FILE = LOG_DIR / "server.log"
RESTORE_SCRIPT = BASE_DIR / "scripts" / "restore_omniforum.sh"
MEDIA_FOLDERS = {
    "avatars": MEDIA_DIR / "avatars",
    "posts": MEDIA_DIR / "posts",
    "thumbs": MEDIA_DIR / "thumbs",
}
HOST = os.getenv("OMNIFORUM_HOST", "127.0.0.1")
PORT = int(os.getenv("OMNIFORUM_PORT", "8000"))
PUBLIC_URL = os.getenv("OMNIFORUM_PUBLIC_URL", f"http://{HOST}:{PORT}").rstrip("/")
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
AVATAR_IMAGE_MAX_DIMENSION = 512
POST_IMAGE_MAX_DIMENSION = 2_400
POST_THUMBNAIL_MAX_DIMENSION = 720
JPEG_QUALITY = 86
WEBP_QUALITY = 84
MAX_REQUEST_BYTES = int(os.getenv("OMNIFORUM_MAX_REQUEST_BYTES", str(48 * 1024 * 1024)))
DEFAULT_PAGE_SIZE = 20
DEFAULT_POST_PAGE_SIZE = 20
DEFAULT_MEMBER_PAGE_SIZE = 24
DEFAULT_LEADERBOARD_PAGE_SIZE = 18
MAX_PAGE_SIZE = 50
BACKUP_ROTATION_LIMIT = int(os.getenv("OMNIFORUM_BACKUP_ROTATION", "8"))
BACKUP_STALE_HOURS = int(os.getenv("OMNIFORUM_BACKUP_STALE_HOURS", "168"))
LIVE_STREAM_INTERVAL_SECONDS = max(2, int(os.getenv("OMNIFORUM_LIVE_INTERVAL_SECONDS", "5")))
USER_MEDIA_LIMIT_BYTES = int(os.getenv("OMNIFORUM_USER_MEDIA_LIMIT_BYTES", str(64 * 1024 * 1024)))
USER_MEDIA_LIMIT_FILES = int(os.getenv("OMNIFORUM_USER_MEDIA_LIMIT_FILES", "80"))
DISCORD_WEBHOOK_URL = str(os.getenv("OMNIFORUM_DISCORD_WEBHOOK_URL") or "").strip()
DM_PRIVACY_OPTIONS = {"everyone", "members", "staff_only", "disabled"}
THREAD_STATE_OPTIONS = {"discussion", "support"}
REPORT_MACROS = {
    "needs_context": "Requested more context from the reporter before acting.",
    "warned_user": "Reviewed and issued a warning to the reported user.",
    "content_removed": "Reviewed and removed the reported content from public view.",
    "no_action": "Reviewed and documented why no further staff action was needed.",
    "escalated": "Escalated to higher-priority staff follow-up.",
}
ALLOWED_REACTIONS = {"👍", "❤️", "😂", "🎉", "🔥", "👀"}
PLUGIN_ASSET_EXTENSIONS = {
    ".css",
    ".js",
    ".gif",
    ".jpeg",
    ".jpg",
    ".json",
    ".png",
    ".svg",
    ".txt",
    ".webp",
    ".woff",
    ".woff2",
}
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
DEFAULT_SITE_SETTINGS = {
    "site_name": "OmniForum",
    "logo_text": "OmniForum",
    "logo_mark": "◈",
    "hero_eyebrow": "Welcome to",
    "hero_title": "OmniForum",
    "hero_subtitle": "A community built for thinkers, creators, and builders.",
    "homepage_copy": "Browse forum sections, featured threads, and the latest community activity.",
    "footer_copy": "Community Forum · Built with passion",
    "rules_copy": (
        "These rules keep the forum sharp, safe, and worth returning to. Staff may remove "
        "content or accounts that undermine the community even when a situation is not spelled out word-for-word."
    ),
    "privacy_copy": (
        "This forum stores the information needed to run accounts, discussions, messages, "
        "moderation workflows, backups, and account recovery without email support."
    ),
    "contact_copy": (
        "Use the contact form for moderation concerns, account recovery, bug reports, "
        "privacy questions, or anything else that should land directly in the staff inbox."
    ),
    "support_discord": "",
    "support_url": "",
    "footer_links": [
        {"label": "Rules", "url": "/pages/rules.html"},
        {"label": "Privacy", "url": "/pages/privacy.html"},
        {"label": "Contact", "url": "/pages/contact.html"},
    ],
    "seo_title": "OmniForum — Community Hub",
    "seo_description": "OmniForum is a modern community hub for discussion, support, direct messages, moderation, and member discovery.",
    "default_theme": "midnight",
    "upload_policy": "PNG, JPG, GIF, and WEBP uploads are supported. Staff can remove media that violates the forum rules.",
    "feature_toggles": {
        "directMessages": True,
        "uploads": True,
        "polls": True,
        "reactions": True,
        "leaderboard": True,
        "publicMemberList": True,
        "staffInbox": True,
    },
}
SITE_SETTING_KEYS = set(DEFAULT_SITE_SETTINGS)
ADMIN_EXPORT_TYPES = {"users", "threads", "posts", "reports", "moderation", "settings", "all"}
ADMIN_EXPORT_FORMATS = {"json", "csv"}

if PIL_AVAILABLE:
    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
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
AUDIT_CATEGORIES = {
    "moderation",
    "content",
    "sections",
    "operations",
    "signup",
    "plugins",
    "settings",
}
NOTIFICATION_PREFERENCE_COLUMNS = {
    "reply": "notify_replies",
    "like": "notify_likes",
    "mention": "notify_mentions",
    "dm": "notify_dms",
}
SERVER_STARTED_AT = datetime.now(timezone.utc)
RATE_LIMIT_RULES = {
    "register": (4, 3600, "registrations"),
    "register_burst": (2, 300, "registration attempts"),
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
    "registration_settings": "users_db.registration_settings",
    "invite_codes": "users_db.invite_codes",
    "site_settings": "users_db.site_settings",
    "recovery_codes": "users_db.recovery_codes",
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
    "report_internal_notes": "reports_db.report_internal_notes",
    "moderation_macros": "reports_db.moderation_macros",
    "audit_events": "audit_db.audit_events",
    "contact_submissions": "contact_db.contact_submissions",
    "thread_polls": "threads_db.thread_polls",
    "thread_poll_options": "threads_db.thread_poll_options",
    "thread_poll_votes": "threads_db.thread_poll_votes",
    "thread_notes": "threads_db.thread_notes",
    "search_events": "audit_db.search_events",
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
REGISTRATION_APPROVAL_STATUSES = {"approved", "pending", "rejected"}

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


def normalize_recovery_code(value: Any) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", str(value or "")).upper()


def generate_recovery_code_plain() -> str:
    raw = secrets.token_hex(6).upper()
    return "-".join(raw[index:index + 4] for index in range(0, len(raw), 4))


def recovery_code_summary(conn: sqlite3.Connection, user_id: int) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN used_at IS NULL THEN 1 ELSE 0 END) AS active,
            MAX(created_at) AS latest_created_at,
            MAX(used_at) AS latest_used_at
        FROM recovery_codes
        WHERE user_id = ?
        """,
        (user_id,),
    ).fetchone()
    return {
        "total": int(row["total"] or 0) if row else 0,
        "active": int(row["active"] or 0) if row else 0,
        "latestCreatedAt": row["latest_created_at"] if row else "",
        "latestUsedAt": row["latest_used_at"] if row else "",
    }


def create_recovery_codes(conn: sqlite3.Connection, user_id: int, *, count: int = 8) -> list[str]:
    now = utc_iso()
    conn.execute("DELETE FROM recovery_codes WHERE user_id = ? AND used_at IS NULL", (user_id,))
    codes: list[str] = []
    for index in range(count):
        code = generate_recovery_code_plain()
        codes.append(code)
        conn.execute(
            """
            INSERT INTO recovery_codes (user_id, code_hash, label, used_at, created_at)
            VALUES (?, ?, ?, NULL, ?)
            """,
            (user_id, make_password_hash(normalize_recovery_code(code)), f"Recovery code {index + 1}", now),
        )
    return codes


def consume_recovery_code(conn: sqlite3.Connection, user_id: int, code: Any) -> bool:
    normalized = normalize_recovery_code(code)
    if len(normalized) < 8 or len(normalized) > 32:
        return False
    rows = conn.execute(
        """
        SELECT id, code_hash
        FROM recovery_codes
        WHERE user_id = ? AND used_at IS NULL
        ORDER BY created_at DESC, id DESC
        LIMIT 40
        """,
        (user_id,),
    ).fetchall()
    for row in rows:
        if verify_password(normalized, row["code_hash"]):
            conn.execute("UPDATE recovery_codes SET used_at = ? WHERE id = ?", (utc_iso(), row["id"]))
            return True
    return False


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
    conn.execute("PRAGMA busy_timeout = 5000")
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
                CREATE INDEX IF NOT EXISTS users_db.idx_relationships_target ON user_relationships(target_user_id, updated_at DESC);
                CREATE INDEX IF NOT EXISTS users_db.idx_invite_codes_code ON invite_codes(code);
                CREATE INDEX IF NOT EXISTS users_db.idx_invite_codes_enabled ON invite_codes(enabled, expires_at);
                CREATE INDEX IF NOT EXISTS users_db.idx_recovery_codes_user ON recovery_codes(user_id, used_at, created_at DESC);
                CREATE INDEX IF NOT EXISTS sessions_db.idx_sessions_user ON sessions(user_id);
                CREATE INDEX IF NOT EXISTS contact_db.idx_contact_status ON contact_submissions(status, created_at DESC);
                CREATE INDEX IF NOT EXISTS sections_db.idx_sections_category_sort ON sections(category_id, sort_order, id);
                CREATE INDEX IF NOT EXISTS audit_db.idx_search_events_created ON search_events(created_at DESC);
                CREATE INDEX IF NOT EXISTS audit_db.idx_search_events_query ON search_events(query COLLATE NOCASE, created_at DESC);
                CREATE INDEX IF NOT EXISTS threads_db.idx_thread_notes_thread ON thread_notes(thread_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS reports_db.idx_report_notes_report ON report_internal_notes(report_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS reports_db.idx_moderation_macros_enabled ON moderation_macros(enabled, title COLLATE NOCASE);
                """
            )
        ensure_database_schema(conn.raw)
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


def ensure_registration_defaults(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO users_db.registration_settings (
            id, public_registration_enabled, invite_required, approval_required,
            blocked_username_patterns, updated_by, updated_at
        )
        VALUES (1, 1, 0, 0, '', NULL, ?)
        """,
        (utc_iso(),),
    )


def ensure_site_settings_defaults(conn: sqlite3.Connection) -> None:
    now = utc_iso()
    for key, value in DEFAULT_SITE_SETTINGS.items():
        conn.execute(
            """
            INSERT OR IGNORE INTO users_db.site_settings (key, value_json, updated_by, updated_at)
            VALUES (?, ?, NULL, ?)
            """,
            (key, json.dumps(value, ensure_ascii=True, sort_keys=True), now),
        )


def ensure_moderation_macro_defaults(conn: sqlite3.Connection) -> None:
    existing = conn.execute("SELECT COUNT(*) AS count FROM reports_db.moderation_macros").fetchone()["count"]
    if existing:
        return
    now = utc_iso()
    for key, body in REPORT_MACROS.items():
        title = key.replace("_", " ").title()
        conn.execute(
            """
            INSERT INTO reports_db.moderation_macros (
                title, body, category, enabled, created_by, created_at, updated_at
            )
            VALUES (?, ?, ?, 1, NULL, ?, ?)
            """,
            (title, body, key, now, now),
        )


def ensure_database_schema(conn: sqlite3.Connection) -> None:
    ensure_column(conn, "users_db", "users", "avatar_path", "TEXT NOT NULL DEFAULT ''")
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
            CREATE INDEX IF NOT EXISTS threads_db.idx_thread_notes_thread
            ON thread_notes(thread_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS audit_db.idx_search_events_created
            ON search_events(created_at DESC);
            CREATE INDEX IF NOT EXISTS audit_db.idx_search_events_query
            ON search_events(query COLLATE NOCASE, created_at DESC);
            CREATE INDEX IF NOT EXISTS users_db.idx_recovery_codes_user
            ON recovery_codes(user_id, used_at, created_at DESC);
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


def clean_invite_code(value: Any, *, required: bool = True) -> str:
    code = clean_text(value, min_len=4 if required else 0, max_len=40, field="Invite code")
    if not code:
        return ""
    if not re.fullmatch(r"[A-Za-z0-9_-]+", code):
        raise APIError("Invite codes can only contain letters, numbers, _ and -.")
    return code


def registration_status(row: sqlite3.Row | dict[str, Any] | None) -> str:
    if not row:
        return "approved"
    status = str(dict(row).get("approval_status") or "approved").strip().lower()
    return status if status in REGISTRATION_APPROVAL_STATUSES else "approved"


def is_approved_user(row: sqlite3.Row | dict[str, Any] | None) -> bool:
    return registration_status(row) == "approved"


def get_registration_settings(conn: sqlite3.Connection) -> dict[str, Any]:
    row = conn.execute("SELECT * FROM registration_settings WHERE id = 1").fetchone()
    if not row:
        ensure_registration_defaults(conn)
        conn.commit()
        row = conn.execute("SELECT * FROM registration_settings WHERE id = 1").fetchone()
    return dict(row) if row else {
        "id": 1,
        "public_registration_enabled": 1,
        "invite_required": 0,
        "approval_required": 0,
        "blocked_username_patterns": "",
        "updated_by": None,
        "updated_at": utc_iso(),
    }


def serialize_registration_settings(row: dict[str, Any]) -> dict[str, Any]:
    public_enabled = bool(row.get("public_registration_enabled", 1))
    invite_required = bool(row.get("invite_required", 0))
    approval_required = bool(row.get("approval_required", 0))
    if not public_enabled and invite_required:
        mode = "Invite-only"
    elif not public_enabled:
        mode = "Closed"
    elif invite_required:
        mode = "Invite-gated"
    elif approval_required:
        mode = "Approval queue"
    else:
        mode = "Open"
    return {
        "publicRegistrationEnabled": public_enabled,
        "inviteRequired": invite_required,
        "approvalRequired": approval_required,
        "blockedUsernamePatterns": row.get("blocked_username_patterns") or "",
        "updatedBy": row.get("updated_by"),
        "updatedAt": row.get("updated_at"),
        "mode": mode,
        "captchaSupported": False,
        "captchaNote": "Captcha is not enabled yet. Use invite-only mode, approval, throttles, and username blocks for now.",
    }


def blocked_username_patterns(settings: dict[str, Any]) -> list[str]:
    raw = str(settings.get("blocked_username_patterns") or "")
    return [
        line.strip().lower()
        for line in raw.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def username_matches_blocked_pattern(username: str, patterns: list[str]) -> str | None:
    normalized = username.strip().lower()
    for pattern in patterns:
        if any(char in pattern for char in "*?[]"):
            if fnmatch.fnmatchcase(normalized, pattern):
                return pattern
            continue
        if pattern in normalized:
            return pattern
    return None


def ensure_username_allowed_for_registration(username: str, settings: dict[str, Any]) -> None:
    matched = username_matches_blocked_pattern(username, blocked_username_patterns(settings))
    if matched:
        raise APIError("That username is not available.", HTTPStatus.FORBIDDEN)


def generate_invite_code() -> str:
    return secrets.token_urlsafe(12).replace("-", "").replace("_", "")[:16].upper()


def serialize_invite_code(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    data = dict(row)
    expires_at = parse_iso(data.get("expires_at"))
    expired = bool(expires_at and expires_at <= utc_now())
    max_uses = int(data.get("max_uses") or 1)
    uses = int(data.get("uses") or 0)
    return {
        "id": data["id"],
        "code": data["code"],
        "note": data.get("note") or "",
        "maxUses": max_uses,
        "uses": uses,
        "remainingUses": max(0, max_uses - uses),
        "enabled": bool(data.get("enabled")),
        "expired": expired,
        "expiresAt": data.get("expires_at"),
        "createdBy": (
            {"id": data.get("created_by"), "username": data.get("created_by_username")}
            if data.get("created_by") and data.get("created_by_username")
            else None
        ),
        "createdAt": data.get("created_at"),
        "updatedAt": data.get("updated_at"),
    }


def list_invite_codes(conn: sqlite3.Connection, *, limit: int = 80) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT ic.*, creator.username AS created_by_username
        FROM invite_codes ic
        LEFT JOIN users creator ON creator.id = ic.created_by
        ORDER BY ic.created_at DESC, ic.id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [serialize_invite_code(row) for row in rows]


def find_valid_invite_code(conn: sqlite3.Connection, code: str) -> sqlite3.Row | None:
    if not code:
        return None
    row = conn.execute(
        "SELECT * FROM invite_codes WHERE lower(code) = lower(?) LIMIT 1",
        (code,),
    ).fetchone()
    if not row or not bool(row["enabled"]):
        return None
    if int(row["uses"] or 0) >= int(row["max_uses"] or 1):
        return None
    expires_at = parse_iso(row["expires_at"])
    if expires_at and expires_at <= utc_now():
        return None
    return row


def pending_registration_count(conn: sqlite3.Connection) -> int:
    return int(
        conn.execute(
            "SELECT COUNT(*) AS count FROM users WHERE approval_status = 'pending'"
        ).fetchone()["count"]
    )


def serialize_pending_registration(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    data = dict(row)
    return {
        "id": data["id"],
        "username": data["username"],
        "role": data["role"],
        "createdAt": data["created_at"],
        "registrationIp": data.get("registration_ip") or "",
        "inviteCodeUsed": data.get("invite_code_used") or "",
        "approvalNote": data.get("approval_note") or "",
        "approvedBy": (
            {"id": data.get("approved_by"), "username": data.get("approved_by_username")}
            if data.get("approved_by") and data.get("approved_by_username")
            else None
        ),
        "approvedAt": data.get("approved_at"),
    }


def list_pending_registrations(conn: sqlite3.Connection, *, limit: int = 100) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT u.*, reviewer.username AS approved_by_username
        FROM users u
        LEFT JOIN users reviewer ON reviewer.id = u.approved_by
        WHERE u.approval_status = 'pending'
        ORDER BY u.created_at ASC, u.id ASC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [serialize_pending_registration(row) for row in rows]


def registration_controls_payload(conn: sqlite3.Connection) -> dict[str, Any]:
    settings = get_registration_settings(conn)
    return {
        "settings": serialize_registration_settings(settings),
        "pending": list_pending_registrations(conn),
        "pendingCount": pending_registration_count(conn),
        "invites": list_invite_codes(conn),
    }


def site_setting_value(row: sqlite3.Row | None, key: str) -> Any:
    if not row:
        return DEFAULT_SITE_SETTINGS[key]
    try:
        return json.loads(row["value_json"])
    except (json.JSONDecodeError, TypeError):
        return DEFAULT_SITE_SETTINGS[key]


def get_site_settings(conn: sqlite3.Connection) -> dict[str, Any]:
    ensure_site_settings_defaults(conn)
    rows = {
        row["key"]: row
        for row in conn.execute("SELECT * FROM site_settings").fetchall()
    }
    settings: dict[str, Any] = {}
    updated_at = ""
    for key in DEFAULT_SITE_SETTINGS:
        row = rows.get(key)
        settings[key] = site_setting_value(row, key)
        if row and str(row["updated_at"] or "") > updated_at:
            updated_at = row["updated_at"]
    settings["_updated_at"] = updated_at
    return settings


def clean_optional_url(value: Any, *, field: str = "URL", max_len: int = 240) -> str:
    text = clean_text(value, min_len=0, max_len=max_len, field=field)
    if not text:
        return ""
    if text.startswith("/"):
        return text
    if not re.fullmatch(r"https?://[^\s<>'\"]{3,}", text, re.IGNORECASE):
        raise APIError(f"{field} must be a relative path or http(s) URL.")
    return text


def normalize_footer_links(value: Any) -> list[dict[str, str]]:
    if value is None or value == "":
        return list(DEFAULT_SITE_SETTINGS["footer_links"])
    if not isinstance(value, list):
        raise APIError("Footer links must be a list.")
    links: list[dict[str, str]] = []
    for item in value[:8]:
        if not isinstance(item, dict):
            continue
        label = clean_text(item.get("label"), min_len=1, max_len=40, field="Footer link label")
        url = clean_optional_url(item.get("url"), field="Footer link URL")
        if label and url:
            links.append({"label": label, "url": url})
    return links


def normalize_feature_toggles(value: Any, current: dict[str, Any] | None = None) -> dict[str, bool]:
    defaults = DEFAULT_SITE_SETTINGS["feature_toggles"]
    output = {
        key: bool((current or defaults).get(key, defaults[key]))
        for key in defaults
    }
    if isinstance(value, dict):
        for key in defaults:
            if key in value:
                output[key] = bool(value[key])
    return output


def serialize_site_settings(settings: dict[str, Any]) -> dict[str, Any]:
    feature_toggles = normalize_feature_toggles(settings.get("feature_toggles"))
    return {
        "siteName": settings.get("site_name") or DEFAULT_SITE_SETTINGS["site_name"],
        "logoText": settings.get("logo_text") or DEFAULT_SITE_SETTINGS["logo_text"],
        "logoMark": settings.get("logo_mark") or DEFAULT_SITE_SETTINGS["logo_mark"],
        "heroEyebrow": settings.get("hero_eyebrow") or DEFAULT_SITE_SETTINGS["hero_eyebrow"],
        "heroTitle": settings.get("hero_title") or DEFAULT_SITE_SETTINGS["hero_title"],
        "heroSubtitle": settings.get("hero_subtitle") or DEFAULT_SITE_SETTINGS["hero_subtitle"],
        "homepageCopy": settings.get("homepage_copy") or DEFAULT_SITE_SETTINGS["homepage_copy"],
        "footerCopy": settings.get("footer_copy") or DEFAULT_SITE_SETTINGS["footer_copy"],
        "rulesCopy": settings.get("rules_copy") or DEFAULT_SITE_SETTINGS["rules_copy"],
        "privacyCopy": settings.get("privacy_copy") or DEFAULT_SITE_SETTINGS["privacy_copy"],
        "contactCopy": settings.get("contact_copy") or DEFAULT_SITE_SETTINGS["contact_copy"],
        "supportDiscord": settings.get("support_discord") or "",
        "supportUrl": settings.get("support_url") or "",
        "footerLinks": normalize_footer_links(settings.get("footer_links")),
        "seoTitle": settings.get("seo_title") or DEFAULT_SITE_SETTINGS["seo_title"],
        "seoDescription": settings.get("seo_description") or DEFAULT_SITE_SETTINGS["seo_description"],
        "defaultTheme": clean_site_theme(settings.get("default_theme") or DEFAULT_SITE_SETTINGS["default_theme"]),
        "uploadPolicy": settings.get("upload_policy") or DEFAULT_SITE_SETTINGS["upload_policy"],
        "featureToggles": feature_toggles,
        "updatedAt": settings.get("_updated_at") or "",
        "themeOptions": sorted(SITE_THEME_OPTIONS),
    }


def update_site_settings_from_payload(
    conn: sqlite3.Connection,
    data: dict[str, Any],
    viewer: dict[str, Any],
) -> dict[str, Any]:
    current = get_site_settings(conn)
    field_map = {
        "siteName": ("site_name", 2, 80, "Site name"),
        "logoText": ("logo_text", 1, 80, "Logo text"),
        "logoMark": ("logo_mark", 1, 12, "Logo mark"),
        "heroEyebrow": ("hero_eyebrow", 0, 80, "Hero eyebrow"),
        "heroTitle": ("hero_title", 2, 120, "Hero title"),
        "heroSubtitle": ("hero_subtitle", 0, 240, "Hero subtitle"),
        "homepageCopy": ("homepage_copy", 0, 400, "Homepage copy"),
        "footerCopy": ("footer_copy", 0, 160, "Footer copy"),
        "rulesCopy": ("rules_copy", 0, 1200, "Rules copy"),
        "privacyCopy": ("privacy_copy", 0, 1200, "Privacy copy"),
        "contactCopy": ("contact_copy", 0, 1200, "Contact copy"),
        "supportDiscord": ("support_discord", 0, 64, "Support Discord"),
        "seoTitle": ("seo_title", 2, 120, "SEO title"),
        "seoDescription": ("seo_description", 0, 220, "SEO description"),
        "uploadPolicy": ("upload_policy", 0, 500, "Upload policy"),
    }
    updates: dict[str, Any] = {}
    for camel_key, (store_key, min_len, max_len, label) in field_map.items():
        if camel_key in data:
            updates[store_key] = clean_text(data.get(camel_key), min_len=min_len, max_len=max_len, field=label)
    if "supportUrl" in data:
        updates["support_url"] = clean_optional_url(data.get("supportUrl"), field="Support URL")
    if "footerLinks" in data:
        updates["footer_links"] = normalize_footer_links(data.get("footerLinks"))
    if "defaultTheme" in data:
        updates["default_theme"] = clean_site_theme(data.get("defaultTheme"))
    if "featureToggles" in data:
        updates["feature_toggles"] = normalize_feature_toggles(data.get("featureToggles"), current.get("feature_toggles"))
    if not updates:
        return serialize_site_settings(current)
    now = utc_iso()
    for key, value in updates.items():
        conn.execute(
            """
            INSERT INTO site_settings (key, value_json, updated_by, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value_json = excluded.value_json,
                updated_by = excluded.updated_by,
                updated_at = excluded.updated_at
            """,
            (key, json.dumps(value, ensure_ascii=True, sort_keys=True), viewer["id"], now),
        )
    log_audit_event(
        conn,
        actor=viewer,
        action_type="site_settings_update",
        category="settings",
        target_type="settings",
        target_label="Site settings",
        reason="Site configuration updated.",
        metadata={"keys": sorted(updates)},
        created_at=now,
    )
    conn.commit()
    return serialize_site_settings(get_site_settings(conn))


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


def clean_status_text(value: Any) -> str:
    return clean_text(value, min_len=0, max_len=80, field="Status")


def normalize_thread_prefixes(value: Any) -> list[str]:
    if value in {None, ""}:
        return []
    if isinstance(value, str):
        raw_items = [part.strip() for part in value.split(",")]
    elif isinstance(value, list):
        raw_items = [str(part).strip() for part in value]
    else:
        raise APIError("Thread prefixes must be a list or comma-separated string.")
    output: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        if not item:
            continue
        normalized = re.sub(r"\s+", " ", item).strip()
        if len(normalized) > 24:
            raise APIError("Thread prefixes must stay under 24 characters each.")
        dedupe_key = normalized.lower()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        output.append(normalized)
        if len(output) >= 8:
            break
    return output


def clean_thread_prefix(value: Any, allowed_prefixes: list[str]) -> str:
    prefix = clean_text(value, min_len=0, max_len=24, field="Thread prefix")
    if not prefix:
        return ""
    if allowed_prefixes and prefix.lower() not in {item.lower() for item in allowed_prefixes}:
        raise APIError("Choose one of the configured thread prefixes for this section.")
    return re.sub(r"\s+", " ", prefix).strip()


def clean_thread_template(value: Any) -> str:
    return clean_text(value, min_len=0, max_len=2400, field="Thread template")


def clean_thread_state_mode(value: Any) -> str:
    mode = str(value or "discussion").strip().lower()
    if mode not in THREAD_STATE_OPTIONS:
        raise APIError("Thread state mode is invalid.")
    return mode


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
    if not viewer:
        return
    trust = user_trust_summary(viewer)
    if trust["tier"] not in {"new", "restricted"}:
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


def user_account_age_days(row: sqlite3.Row | dict[str, Any] | None) -> int:
    if not row:
        return 0
    created_at = parse_iso(dict(row).get("created_at"))
    if not created_at:
        return 0
    return max(0, int((utc_now() - created_at).total_seconds() // 86400))


def user_trust_summary(row: sqlite3.Row | dict[str, Any] | None) -> dict[str, Any]:
    data = dict(row or {})
    role = data.get("role") or "new"
    xp = int(data.get("xp") or 0)
    posts = int(data.get("posts_count") or data.get("posts") or 0)
    age_days = user_account_age_days(data)
    if is_banned_user(data) or active_timeout_until(data) or active_mute_until(data) or is_shadow_muted(data):
        tier = "restricted"
        label = "Restricted"
        cooldown = "Strict"
        limits = f"{LOW_TRUST_MAX_LINKS} links and {LOW_TRUST_MAX_MENTIONS} mentions per post"
    elif role_level(role) >= role_level("mod"):
        tier = "staff"
        label = "Staff"
        cooldown = "None"
        limits = "Staff permissions"
    elif role_level(role) >= role_level("veteran") or xp >= 600 or (posts >= 25 and age_days >= 14):
        tier = "trusted"
        label = "Trusted"
        cooldown = "Reduced"
        limits = "Normal community limits"
    elif role_level(role) >= role_level("member") or xp >= 100 or (posts >= 5 and age_days >= 2):
        tier = "member"
        label = "Member"
        cooldown = "Reduced"
        limits = "Normal community limits"
    else:
        tier = "new"
        label = "New Account"
        cooldown = "Strict"
        limits = f"{LOW_TRUST_MAX_LINKS} links and {LOW_TRUST_MAX_MENTIONS} mentions per post"
    return {
        "tier": tier,
        "label": label,
        "accountAgeDays": age_days,
        "cooldown": cooldown,
        "limits": limits,
        "nextStep": "Build history with posts, replies, and positive XP." if tier == "new" else "",
    }


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


def media_file_size(storage_path: str | None) -> int:
    path = resolve_media_path(storage_path)
    if not path or not path.is_file():
        return 0
    try:
        return path.stat().st_size
    except OSError:
        return 0


def get_user_media_usage(conn: sqlite3.Connection, user_id: int) -> dict[str, Any]:
    user_row = conn.execute(
        "SELECT avatar_path FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    avatar_path = str(user_row["avatar_path"] or "") if user_row else ""
    media_rows = conn.execute(
        """
        SELECT pm.storage_path, pm.thumbnail_path
        FROM post_media pm
        JOIN posts p ON p.id = pm.post_id
        WHERE p.author_id = ?
        """,
        (user_id,),
    ).fetchall()
    user_file_paths = [avatar_path] if avatar_path else []
    user_file_paths.extend(str(row["storage_path"] or "") for row in media_rows if row["storage_path"])
    byte_paths = list(user_file_paths)
    byte_paths.extend(str(row["thumbnail_path"] or "") for row in media_rows if row["thumbnail_path"])
    unique_user_files = sorted({path for path in user_file_paths if path})
    unique_byte_paths = sorted({path for path in byte_paths if path})
    bytes_used = sum(media_file_size(path) for path in unique_byte_paths)
    avatar_count = 1 if avatar_path else 0
    return {
        "files": len(unique_user_files),
        "bytes": bytes_used,
        "bytesLabel": human_size(bytes_used),
        "avatarCount": avatar_count,
        "postMediaCount": max(0, len(unique_user_files) - avatar_count),
        "limitFiles": USER_MEDIA_LIMIT_FILES,
        "limitBytes": USER_MEDIA_LIMIT_BYTES,
        "limitBytesLabel": human_size(USER_MEDIA_LIMIT_BYTES),
        "remainingFiles": max(0, USER_MEDIA_LIMIT_FILES - len(unique_user_files)),
        "remainingBytes": max(0, USER_MEDIA_LIMIT_BYTES - bytes_used),
        "remainingBytesLabel": human_size(max(0, USER_MEDIA_LIMIT_BYTES - bytes_used)),
    }


def ensure_user_media_quota(
    conn: sqlite3.Connection,
    user_id: int,
    uploads: list[dict[str, Any]],
    *,
    replacing_paths: list[str] | None = None,
) -> dict[str, Any]:
    if not uploads:
        return get_user_media_usage(conn, user_id)
    usage = get_user_media_usage(conn, user_id)
    replacing = sorted({path for path in (replacing_paths or []) if path})
    replaced_bytes = sum(media_file_size(path) for path in replacing)
    replaced_files = len([path for path in replacing if not path.startswith("thumbs/")])
    pending_bytes = sum(
        len(upload.get("bytes") or b"") + len(upload.get("thumbnail_bytes") or b"")
        for upload in uploads
    )
    next_file_total = max(0, int(usage["files"]) - replaced_files) + len(uploads)
    next_byte_total = max(0, int(usage["bytes"]) - replaced_bytes) + pending_bytes
    if next_file_total > USER_MEDIA_LIMIT_FILES:
        raise APIError(
            f"You have reached the media library limit of {USER_MEDIA_LIMIT_FILES} files. "
            "Remove older uploads before adding more.",
        )
    if next_byte_total > USER_MEDIA_LIMIT_BYTES:
        raise APIError(
            f"Your media library is over the {human_size(USER_MEDIA_LIMIT_BYTES)} quota. "
            "Remove older uploads or use smaller files before uploading more.",
        )
    return {
        **usage,
        "nextFiles": next_file_total,
        "nextBytes": next_byte_total,
        "nextBytesLabel": human_size(next_byte_total),
    }


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


def pil_resample_filter():
    return getattr(getattr(Image, "Resampling", Image), "LANCZOS")


def pil_adaptive_palette():
    palette = getattr(Image, "Palette", None)
    return getattr(palette, "ADAPTIVE", getattr(Image, "ADAPTIVE", 1))


def image_has_alpha(image: Any) -> bool:
    if image.mode in {"RGBA", "LA"}:
        return True
    if image.mode == "P" and "transparency" in image.info:
        return True
    return False


def save_pillow_image(image: Any, image_format: str, **kwargs: Any) -> bytes:
    buffer = BytesIO()
    try:
        image.save(buffer, format=image_format, **kwargs)
    except OSError:
        kwargs.pop("optimize", None)
        buffer = BytesIO()
        image.save(buffer, format=image_format, **kwargs)
    return buffer.getvalue()


def encode_static_image(
    image: Any,
    *,
    source_mime_type: str,
    max_dimension: int,
    thumbnail: bool = False,
) -> dict[str, Any]:
    processed = ImageOps.exif_transpose(image.copy())
    processed.load()
    processed.thumbnail((max_dimension, max_dimension), pil_resample_filter())
    has_alpha = image_has_alpha(processed)

    if thumbnail:
        output_format = "PNG" if has_alpha else "JPEG"
    elif source_mime_type == "image/jpeg":
        output_format = "JPEG"
    elif source_mime_type == "image/webp":
        output_format = "WEBP"
    elif source_mime_type == "image/gif":
        output_format = "GIF"
    else:
        output_format = "PNG"

    if output_format == "JPEG":
        encoded = save_pillow_image(
            processed.convert("RGB"),
            "JPEG",
            quality=JPEG_QUALITY if not thumbnail else 78,
            optimize=True,
            progressive=True,
        )
        mime_type, extension = "image/jpeg", "jpg"
    elif output_format == "WEBP":
        encoded = save_pillow_image(
            processed.convert("RGBA" if has_alpha else "RGB"),
            "WEBP",
            quality=WEBP_QUALITY if not thumbnail else 78,
            method=6,
        )
        mime_type, extension = "image/webp", "webp"
    elif output_format == "GIF":
        encoded = save_pillow_image(
            processed.convert("P", palette=pil_adaptive_palette()),
            "GIF",
            optimize=True,
        )
        mime_type, extension = "image/gif", "gif"
    else:
        mode = "RGBA" if has_alpha else "RGB"
        encoded = save_pillow_image(processed.convert(mode), "PNG", optimize=True)
        mime_type, extension = "image/png", "png"

    return {
        "bytes": encoded,
        "mime_type": mime_type,
        "extension": extension,
        "width": processed.width,
        "height": processed.height,
    }


def encode_animated_image(
    image: Any,
    *,
    source_mime_type: str,
    max_dimension: int,
) -> dict[str, Any]:
    output_format = "WEBP" if source_mime_type == "image/webp" else "GIF"
    frames = []
    durations = []
    for frame in ImageSequence.Iterator(image):
        duration = int(frame.info.get("duration", image.info.get("duration", 80)) or 80)
        processed = frame.copy().convert("RGBA")
        processed.thumbnail((max_dimension, max_dimension), pil_resample_filter())
        frames.append(processed)
        durations.append(duration)
    if not frames:
        raise APIError("Could not read that animated image.")

    buffer = BytesIO()
    if output_format == "WEBP":
        first = frames[0]
        first.save(
            buffer,
            format="WEBP",
            save_all=True,
            append_images=frames[1:],
            duration=durations,
            loop=int(image.info.get("loop", 0) or 0),
            quality=WEBP_QUALITY,
            method=6,
        )
        mime_type, extension = "image/webp", "webp"
    else:
        palette_frames = [frame.convert("P", palette=pil_adaptive_palette()) for frame in frames]
        first = palette_frames[0]
        first.save(
            buffer,
            format="GIF",
            save_all=True,
            append_images=palette_frames[1:],
            duration=durations,
            loop=int(image.info.get("loop", 0) or 0),
            disposal=2,
            optimize=True,
        )
        mime_type, extension = "image/gif", "gif"

    return {
        "bytes": buffer.getvalue(),
        "mime_type": mime_type,
        "extension": extension,
        "width": frames[0].width,
        "height": frames[0].height,
    }


def process_image_upload_bytes(
    binary: bytes,
    *,
    mime_type: str,
    extension: str,
    field: str,
    kind: str,
) -> dict[str, Any]:
    if not PIL_AVAILABLE:
        return {
            "bytes": binary,
            "mime_type": mime_type,
            "extension": extension,
            "thumbnail_bytes": b"",
            "thumbnail_mime_type": "",
            "thumbnail_extension": "",
            "processed": False,
        }

    max_dimension = AVATAR_IMAGE_MAX_DIMENSION if kind == "avatar" else POST_IMAGE_MAX_DIMENSION
    try:
        with Image.open(BytesIO(binary)) as image:
            image.load() if not getattr(image, "is_animated", False) else None
            is_animated = bool(getattr(image, "is_animated", False))
            if is_animated:
                full = encode_animated_image(
                    image,
                    source_mime_type=mime_type,
                    max_dimension=max_dimension,
                )
                first_frame = next(ImageSequence.Iterator(image)).copy()
                thumb = encode_static_image(
                    first_frame,
                    source_mime_type="image/png",
                    max_dimension=POST_THUMBNAIL_MAX_DIMENSION,
                    thumbnail=True,
                )
            else:
                full = encode_static_image(
                    image,
                    source_mime_type=mime_type,
                    max_dimension=max_dimension,
                )
                thumb = encode_static_image(
                    image,
                    source_mime_type=mime_type,
                    max_dimension=POST_THUMBNAIL_MAX_DIMENSION,
                    thumbnail=True,
                )
    except (UnidentifiedImageError, OSError, ValueError, EOFError) as exc:
        raise APIError(f"{field} could not be processed as a safe image.") from exc

    result = {
        **full,
        "thumbnail_bytes": b"",
        "thumbnail_mime_type": "",
        "thumbnail_extension": "",
        "processed": True,
    }
    if kind == "post":
        result.update(
            {
                "thumbnail_bytes": thumb["bytes"],
                "thumbnail_mime_type": thumb["mime_type"],
                "thumbnail_extension": thumb["extension"],
            }
        )
    return result


def decode_image_upload(
    payload: Any,
    *,
    field: str,
    max_bytes: int,
    kind: str = "post",
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
    processed = process_image_upload_bytes(
        binary,
        mime_type=mime_type,
        extension=extension,
        field=field,
        kind=kind,
    )
    filename = Path(str(payload.get("name") or payload.get("filename") or "")).name.strip()
    if not filename:
        filename = f"{slugify_text(field, fallback='image')}.{processed['extension']}"
    alt_text = clean_text(
        payload.get("alt") or Path(filename).stem.replace("-", " ").replace("_", " "),
        min_len=0,
        max_len=120,
        field=f"{field} description",
    )
    return {
        "bytes": processed["bytes"],
        "mime_type": processed["mime_type"],
        "extension": processed["extension"],
        "thumbnail_bytes": processed.get("thumbnail_bytes") or b"",
        "thumbnail_mime_type": processed.get("thumbnail_mime_type") or "",
        "thumbnail_extension": processed.get("thumbnail_extension") or "",
        "filename": filename,
        "alt_text": alt_text or "Forum image",
        "width": processed.get("width") or width,
        "height": processed.get("height") or height,
        "original_width": width,
        "original_height": height,
        "processed": bool(processed.get("processed")),
    }


def normalize_media_uploads(
    value: Any,
    *,
    max_items: int,
    field: str = "Images",
    max_bytes: int = POST_MEDIA_MAX_BYTES,
    kind: str = "post",
) -> list[dict[str, Any]]:
    if value is None or value == "":
        return []
    if not isinstance(value, list):
        raise APIError(f"{field} must be sent as a list.")
    if len(value) > max_items:
        raise APIError(f"You can attach up to {max_items} images per post.")
    return [
        decode_image_upload(item, field=f"{field} #{index}", max_bytes=max_bytes, kind=kind)
        for index, item in enumerate(value, start=1)
    ]


def store_image_upload(upload: dict[str, Any], *, bucket: str) -> str:
    return store_image_upload_paths(upload, bucket=bucket)["storage_path"]


def store_image_upload_paths(upload: dict[str, Any], *, bucket: str) -> dict[str, str]:
    if bucket not in MEDIA_FOLDERS:
        raise APIError("Upload destination is invalid.", HTTPStatus.INTERNAL_SERVER_ERROR)
    stem = f"{utc_now().strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(8)}"
    filename = f"{stem}.{upload['extension']}"
    path = MEDIA_FOLDERS[bucket] / filename
    path.write_bytes(upload["bytes"])
    result = {"storage_path": f"{bucket}/{filename}", "thumbnail_path": ""}
    thumbnail_bytes = upload.get("thumbnail_bytes") or b""
    thumbnail_extension = upload.get("thumbnail_extension") or ""
    if thumbnail_bytes and thumbnail_extension:
        thumb_filename = f"{stem}-thumb.{thumbnail_extension}"
        thumb_path = MEDIA_FOLDERS["thumbs"] / thumb_filename
        thumb_path.write_bytes(thumbnail_bytes)
        result["thumbnail_path"] = f"thumbs/{thumb_filename}"
    return result


def serialize_post_media_row(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    payload = dict(row)
    return {
        "id": payload["id"],
        "url": media_url_for_path(payload.get("storage_path")),
        "thumbnailUrl": media_url_for_path(payload.get("thumbnail_path")),
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
        path
        for rows in grouped_rows.values()
        for row in rows
        for path in (row["storage_path"], row["thumbnail_path"])
        if path
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
        media_paths = store_image_upload_paths(upload, bucket="posts")
        conn.execute(
            """
            INSERT INTO post_media (
                post_id, storage_path, thumbnail_path, mime_type, alt_text,
                width, height, sort_order, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                post_id,
                media_paths["storage_path"],
                media_paths["thumbnail_path"],
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
            delete_media_file(row["thumbnail_path"])


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
        SELECT pm.id, pm.storage_path, pm.thumbnail_path
        FROM post_media pm
        LEFT JOIN posts p ON p.id = pm.post_id
        WHERE p.id IS NULL
        """
    ).fetchall()
    orphan_media_ids = [int(row["id"]) for row in orphan_media_rows]
    orphan_media_paths = [
        path
        for row in orphan_media_rows
        for path in (row["storage_path"], row["thumbnail_path"])
        if path
    ]
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


def soft_delete_post(
    conn: sqlite3.Connection,
    *,
    post_id: int,
    actor_id: int,
    reason: str = "",
    deleted_at: str | None = None,
) -> None:
    now = deleted_at or utc_iso()
    conn.execute(
        """
        UPDATE posts
        SET deleted_at = ?, deleted_by = ?, delete_reason = ?, updated_at = ?
        WHERE id = ? AND deleted_at IS NULL
        """,
        (now, actor_id, reason, now, post_id),
    )


def soft_delete_thread(
    conn: sqlite3.Connection,
    *,
    thread_id: int,
    actor_id: int,
    reason: str = "",
    deleted_at: str | None = None,
) -> None:
    now = deleted_at or utc_iso()
    conn.execute(
        """
        UPDATE threads
        SET deleted_at = ?, deleted_by = ?, delete_reason = ?, updated_at = ?
        WHERE id = ? AND deleted_at IS NULL
        """,
        (now, actor_id, reason, now, thread_id),
    )
    conn.execute(
        """
        UPDATE posts
        SET deleted_at = COALESCE(deleted_at, ?),
            deleted_by = COALESCE(deleted_by, ?),
            delete_reason = CASE WHEN delete_reason = '' THEN ? ELSE delete_reason END,
            updated_at = ?
        WHERE thread_id = ? AND deleted_at IS NULL
        """,
        (now, actor_id, reason, now, thread_id),
    )


def restore_deleted_post(conn: sqlite3.Connection, post_id: int) -> None:
    conn.execute(
        """
        UPDATE posts
        SET deleted_at = NULL, deleted_by = NULL, delete_reason = ''
        WHERE id = ?
        """,
        (post_id,),
    )


def restore_deleted_thread(conn: sqlite3.Connection, thread_id: int) -> None:
    conn.execute(
        """
        UPDATE threads
        SET deleted_at = NULL, deleted_by = NULL, delete_reason = ''
        WHERE id = ?
        """,
        (thread_id,),
    )
    conn.execute(
        """
        UPDATE posts
        SET deleted_at = NULL, deleted_by = NULL, delete_reason = ''
        WHERE thread_id = ?
        """,
        (thread_id,),
    )


def serialize_deleted_item(row: sqlite3.Row) -> dict[str, Any]:
    item_type = row["item_type"]
    payload = {
        "type": item_type,
        "id": row["id"],
        "title": row["title"],
        "preview": row["preview"] or "",
        "deletedAt": row["deleted_at"],
        "deleteReason": row["delete_reason"] or "",
        "author": {
            "id": row["author_id"],
            "username": row["author_username"],
            "role": row["author_role"],
        },
        "deletedBy": (
            {
                "id": row["deleted_by"],
                "username": row["deleted_by_username"],
            }
            if row["deleted_by"] and row["deleted_by_username"]
            else None
        ),
    }
    if item_type == "thread":
        payload["threadId"] = row["id"]
        payload["section"] = {
            "id": row["section_slug"],
            "name": row["section_name"],
        }
    else:
        payload["threadId"] = row["thread_id"]
        payload["threadTitle"] = row["thread_title"]
    return payload


def list_deleted_content(conn: sqlite3.Connection, *, limit: int = 120) -> list[dict[str, Any]]:
    thread_rows = conn.execute(
        """
        SELECT
            'thread' AS item_type,
            t.id,
            t.title,
            '' AS preview,
            t.deleted_at,
            t.delete_reason,
            t.author_id,
            author.username AS author_username,
            author.role AS author_role,
            t.deleted_by,
            deleter.username AS deleted_by_username,
            s.slug AS section_slug,
            s.name AS section_name,
            NULL AS thread_id,
            NULL AS thread_title
        FROM threads t
        JOIN users author ON author.id = t.author_id
        JOIN sections s ON s.id = t.section_id
        LEFT JOIN users deleter ON deleter.id = t.deleted_by
        WHERE t.deleted_at IS NOT NULL
        ORDER BY t.deleted_at DESC, t.id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    post_rows = conn.execute(
        """
        SELECT
            'post' AS item_type,
            p.id,
            ('Reply by ' || author.username) AS title,
            substr(trim(replace(replace(p.content, char(10), ' '), char(13), ' ')), 1, 220) AS preview,
            p.deleted_at,
            p.delete_reason,
            p.author_id,
            author.username AS author_username,
            author.role AS author_role,
            p.deleted_by,
            deleter.username AS deleted_by_username,
            NULL AS section_slug,
            NULL AS section_name,
            p.thread_id,
            t.title AS thread_title
        FROM posts p
        JOIN users author ON author.id = p.author_id
        JOIN threads t ON t.id = p.thread_id
        LEFT JOIN users deleter ON deleter.id = p.deleted_by
        WHERE p.deleted_at IS NOT NULL
          AND (t.deleted_at IS NULL OR p.delete_reason != COALESCE(t.delete_reason, ''))
        ORDER BY p.deleted_at DESC, p.id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    combined = [*thread_rows, *post_rows]
    combined.sort(key=lambda item: (item["deleted_at"], item["id"]), reverse=True)
    return [serialize_deleted_item(row) for row in combined[:limit]]


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
    now_dt = utc_now()
    now = utc_iso(now_dt)
    conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
    row = conn.execute(
        """
        SELECT u.*, s.csrf_token AS session_csrf_token, s.last_seen_at AS session_last_seen_at
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
    if not is_approved_user(user):
        delete_session(conn, token)
        return None
    csrf_token = str(user.get("session_csrf_token") or "")
    if not csrf_token:
        csrf_token = secrets.token_urlsafe(32)
        user["session_csrf_token"] = csrf_token
    session_seen_at = parse_iso(user.get("session_last_seen_at"))
    had_csrf_token = bool(row["session_csrf_token"])
    should_touch_session = (not session_seen_at) or session_seen_at < (now_dt - timedelta(seconds=45)) or not had_csrf_token
    if should_touch_session:
        conn.execute(
            "UPDATE users SET last_seen_at = ?, updated_at = ? WHERE id = ?",
            (now, now, user["id"]),
        )
        conn.execute(
            """
            UPDATE sessions
            SET last_seen_at = ?, last_seen_ip = ?, csrf_token = ?
            WHERE token = ?
            """,
            (now, client_ip or "", csrf_token, token),
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
) -> tuple[str, str, str]:
    token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    created_at = utc_iso()
    expires_at = utc_iso(utc_now() + timedelta(days=SESSION_DAYS))
    conn.execute(
        """
        INSERT INTO sessions (
            token, user_id, csrf_token, created_at, expires_at,
            ip_address, user_agent, last_seen_at, last_seen_ip
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            token,
            user_id,
            csrf_token,
            created_at,
            expires_at,
            ip_address or "",
            user_agent or "",
            created_at,
            ip_address or "",
        ),
    )
    conn.commit()
    return token, expires_at, csrf_token


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
    if not is_approved_user(viewer):
        raise APIError("This account is not approved yet.", HTTPStatus.FORBIDDEN)
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
    trust = user_trust_summary(viewer)
    if trust["tier"] in {"trusted", "staff"}:
        return 0
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
    conn: sqlite3.Connection,
    recipient: sqlite3.Row | dict[str, Any] | None,
    sender: dict[str, Any] | None,
) -> bool:
    if not recipient or not sender:
        return False
    if sender["id"] == dict(recipient)["id"]:
        return False
    if has_dm_block_relationship(conn, int(dict(recipient)["id"]), int(sender["id"])):
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


def audit_actor_snapshot(
    conn: sqlite3.Connection,
    actor: dict[str, Any] | sqlite3.Row | None = None,
    actor_id: int | None = None,
) -> dict[str, Any]:
    if actor:
        actor_row = dict(actor)
        return {
            "id": actor_row.get("id"),
            "username": actor_row.get("username") or "",
            "role": actor_row.get("role") or "",
        }
    if actor_id:
        row = conn.execute("SELECT id, username, role FROM users WHERE id = ?", (actor_id,)).fetchone()
        if row:
            return {
                "id": row["id"],
                "username": row["username"],
                "role": row["role"],
            }
    return {
        "id": actor_id,
        "username": "",
        "role": "",
    }


def log_audit_event(
    conn: sqlite3.Connection,
    *,
    actor: dict[str, Any] | sqlite3.Row | None = None,
    actor_id: int | None = None,
    action_type: str,
    category: str,
    target_type: str = "",
    target_id: int | None = None,
    target_label: str = "",
    reason: str = "",
    metadata: dict[str, Any] | None = None,
    ip_address: str = "",
    created_at: str | None = None,
) -> None:
    normalized_category = str(category or "operations").strip().lower()
    if normalized_category not in AUDIT_CATEGORIES:
        normalized_category = "operations"
    actor_snapshot = audit_actor_snapshot(conn, actor=actor, actor_id=actor_id)
    conn.execute(
        """
        INSERT INTO audit_events (
            actor_id, actor_username, actor_role, action_type, category,
            target_type, target_id, target_label, reason, metadata_json,
            ip_address, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            actor_snapshot["id"],
            actor_snapshot["username"],
            actor_snapshot["role"],
            clean_text(action_type, min_len=1, max_len=80, field="Audit action"),
            normalized_category,
            clean_text(target_type, min_len=0, max_len=40, field="Audit target type"),
            target_id,
            clean_text(target_label, min_len=0, max_len=160, field="Audit target"),
            clean_text(reason, min_len=0, max_len=1000, field="Audit reason"),
            json.dumps(metadata or {}, sort_keys=True),
            clean_text(ip_address, min_len=0, max_len=80, field="Audit IP"),
            created_at or utc_iso(),
        ),
    )


def serialize_audit_event(row: sqlite3.Row) -> dict[str, Any]:
    try:
        metadata = json.loads(row["metadata_json"] or "{}")
    except json.JSONDecodeError:
        metadata = {}
    return {
        "id": row["id"],
        "action": row["action_type"],
        "category": row["category"],
        "targetType": row["target_type"] or "",
        "targetId": row["target_id"],
        "targetLabel": row["target_label"] or "",
        "reason": row["reason"] or "",
        "metadata": metadata,
        "ipAddress": row["ip_address"] or "",
        "createdAt": row["created_at"],
        "actor": {
            "id": row["actor_id"],
            "username": row["actor_username"] or "System",
            "role": row["actor_role"] or "",
        },
    }


def audit_filter_value(query: dict[str, list[str]], key: str, *, max_len: int = 80) -> str:
    return clean_text((query.get(key) or [""])[0], min_len=0, max_len=max_len, field=key)


def list_audit_events(
    conn: sqlite3.Connection,
    query: dict[str, list[str]],
) -> dict[str, Any]:
    try:
        limit = int((query.get("limit") or ["80"])[0])
    except (TypeError, ValueError):
        limit = 80
    limit = max(10, min(200, limit))
    category = audit_filter_value(query, "category", max_len=40).lower()
    action = audit_filter_value(query, "action", max_len=80).lower()
    target_type = audit_filter_value(query, "targetType", max_len=40).lower()
    search = audit_filter_value(query, "q", max_len=120)
    actor = audit_filter_value(query, "actor", max_len=80)
    date_from = audit_filter_value(query, "from", max_len=40)
    date_to = audit_filter_value(query, "to", max_len=40)
    params: list[Any] = []
    clauses: list[str] = ["1 = 1"]
    if category in AUDIT_CATEGORIES:
        clauses.append("category = ?")
        params.append(category)
    if action:
        clauses.append("lower(action_type) = ?")
        params.append(action)
    if target_type:
        clauses.append("lower(target_type) = ?")
        params.append(target_type)
    if actor:
        if actor.isdigit():
            clauses.append("actor_id = ?")
            params.append(int(actor))
        else:
            clauses.append("lower(actor_username) LIKE ?")
            params.append(f"%{actor.lower()}%")
    if search:
        like = f"%{search.lower()}%"
        clauses.append(
            """
            (
                lower(action_type) LIKE ?
                OR lower(category) LIKE ?
                OR lower(target_type) LIKE ?
                OR lower(target_label) LIKE ?
                OR lower(actor_username) LIKE ?
                OR lower(reason) LIKE ?
            )
            """
        )
        params.extend([like, like, like, like, like, like])
    if date_from:
        clauses.append("created_at >= ?")
        params.append(date_from if "T" in date_from else f"{date_from}T00:00:00Z")
    if date_to:
        clauses.append("created_at <= ?")
        params.append(date_to if "T" in date_to else f"{date_to}T23:59:59Z")

    where_sql = " AND ".join(clauses)
    rows = conn.execute(
        f"""
        SELECT *
        FROM audit_events
        WHERE {where_sql}
        ORDER BY created_at DESC, id DESC
        LIMIT ?
        """,
        (*params, limit),
    ).fetchall()
    category_rows = conn.execute(
        """
        SELECT category, COUNT(*) AS count
        FROM audit_events
        GROUP BY category
        ORDER BY category ASC
        """
    ).fetchall()
    total = conn.execute("SELECT COUNT(*) AS count FROM audit_events").fetchone()["count"]
    latest = conn.execute(
        "SELECT created_at FROM audit_events ORDER BY created_at DESC, id DESC LIMIT 1"
    ).fetchone()
    return {
        "items": [serialize_audit_event(row) for row in rows],
        "filters": {
            "category": category if category in AUDIT_CATEGORIES else "",
            "action": action,
            "targetType": target_type,
            "actor": actor,
            "q": search,
            "from": date_from,
            "to": date_to,
            "limit": limit,
        },
        "summary": {
            "total": total,
            "latestAt": latest["created_at"] if latest else "",
            "categories": {row["category"]: row["count"] for row in category_rows},
        },
        "categories": sorted(AUDIT_CATEGORIES),
    }


def log_moderation_action(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    actor_id: int,
    action_type: str,
    category: str = "moderation",
    reason: str = "",
    note: str = "",
    delta_xp: int = 0,
    expires_at: str | None = None,
    metadata: dict[str, Any] | None = None,
    created_at: str | None = None,
) -> None:
    timestamp = created_at or utc_iso()
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
            timestamp,
            json.dumps(metadata or {}),
        ),
    )
    target = conn.execute("SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()
    audit_metadata = {
        **(metadata or {}),
        "note": note,
        "deltaXp": delta_xp,
        "expiresAt": expires_at,
        "moderationTargetUserId": user_id,
    }
    log_audit_event(
        conn,
        actor_id=actor_id,
        action_type=action_type,
        category=category,
        target_type="user",
        target_id=user_id,
        target_label=target["username"] if target else f"user {user_id}",
        reason=reason or note,
        metadata={
            key: value
            for key, value in audit_metadata.items()
            if value is not None and value != "" and value != 0
        },
        created_at=timestamp,
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
        "passwordResetExpiresAt": row.get("password_reset_expires_at"),
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
        "SELECT id FROM posts WHERE thread_id = ? AND deleted_at IS NULL ORDER BY id ASC LIMIT 1",
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
            s.thread_prefixes_json AS section_thread_prefixes_json,
            s.thread_template AS section_thread_template,
            s.thread_state_mode AS section_thread_state_mode,
            u.username AS author_name,
            u.role AS author_role,
            u.avatar_path AS author_avatar_path,
            x.created_at AS saved_at
        FROM {table} x
        JOIN threads t ON t.id = x.thread_id
        JOIN sections s ON s.id = t.section_id
        JOIN users u ON u.id = t.author_id
        WHERE x.user_id = ? AND t.deleted_at IS NULL
        ORDER BY x.created_at DESC, x.thread_id DESC
        LIMIT ?
        """,
        (user_id, limit * 3),
    ).fetchall()
    output: list[dict[str, Any]] = []
    for row in rows:
        if not has_required_role(viewer, row["section_required_role"]):
            continue
        if is_ignored_author(conn, viewer, row["author_id"]):
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
            (SELECT COUNT(*) FROM posts p WHERE p.author_id = u.id AND p.deleted_at IS NULL) AS posts_count,
            (SELECT COUNT(*) FROM threads t WHERE t.author_id = u.id AND t.deleted_at IS NULL) AS threads_count,
            (SELECT COUNT(*) FROM post_likes pl
             JOIN posts p2 ON p2.id = pl.post_id
             WHERE p2.author_id = u.id AND p2.deleted_at IS NULL) AS likes_received
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
    if not is_approved_user(resolved) and not (viewer and is_admin(viewer)):
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
    relationship = (
        get_user_relationship(conn, viewer["id"], user_id)
        if viewer and viewer["id"] != user_id
        else {"ignoreContent": False, "blockDm": False}
    )
    profile["relationship"] = relationship
    profile["canMessage"] = bool(
        viewer
        and viewer["id"] != user_id
        and not relationship["blockDm"]
        and not has_dm_block_relationship(conn, viewer["id"], user_id)
    )
    if viewer and viewer["id"] == user_id:
        if viewer.get("session_csrf_token"):
            profile["csrfToken"] = viewer.get("session_csrf_token")
        profile["mustResetPassword"] = bool(resolved.get("password_reset_required"))
        notification_counts = get_notification_counts(conn, user_id, viewer=viewer)
        profile["messageCount"] = notification_counts["dms"]
        profile["notificationCount"] = notification_counts["unread"]
        profile["notificationCounts"] = notification_counts
        profile["registrationCount"] = notification_counts["registrations"]
        profile["appealCount"] = notification_counts["appeals"]
        profile["preferences"] = {
            "siteTheme": resolved.get("site_theme") or "midnight",
            "dmPrivacy": resolved.get("dm_privacy") or "everyone",
            "blurSensitiveMedia": bool(resolved.get("blur_sensitive_media", 1)),
            "compactPostLayout": bool(resolved.get("compact_post_layout", 0)),
            "hideIgnoredContent": bool(resolved.get("hide_ignored_content", 1)),
            "notifyReplies": bool(resolved.get("notify_replies", 1)),
            "notifyLikes": bool(resolved.get("notify_likes", 1)),
            "notifyMentions": bool(resolved.get("notify_mentions", 1)),
            "notifyDms": bool(resolved.get("notify_dms", 1)),
        }
        profile["community"] = {
            "statusText": resolved.get("status_text") or "",
            "signature": resolved.get("signature") or "",
            "profileBadge": resolved.get("profile_badge") or "",
            "profileAccent": resolved.get("profile_accent") or "",
        }
        profile["recovery"] = {
            "discordUsername": resolved.get("recovery_discord_username") or "",
            "codes": recovery_code_summary(conn, user_id),
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
            profile["relationships"] = list_user_relationships(conn, user_id)
            profile["mediaUsage"] = get_user_media_usage(conn, user_id)
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
        "statusText": row.get("status_text") or "",
        "signature": row.get("signature") or "",
        "profileBadge": row.get("profile_badge") or "",
        "profileAccent": row.get("profile_accent") or "",
        "xp": row.get("xp", 0),
        "posts": row.get("posts_count", 0),
        "threads": row.get("threads_count", 0),
        "likesReceived": row.get("likes_received", 0),
        "joined": row["created_at"],
        "online": bool(last_seen and last_seen >= online_threshold),
        "trust": user_trust_summary(row),
    }


def get_user_relationship(
    conn: sqlite3.Connection,
    user_id: int,
    target_user_id: int,
) -> dict[str, bool]:
    if int(user_id or 0) <= 0 or int(target_user_id or 0) <= 0 or int(user_id) == int(target_user_id):
        return {"ignoreContent": False, "blockDm": False}
    row = conn.execute(
        """
        SELECT ignore_content, block_dm
        FROM user_relationships
        WHERE user_id = ? AND target_user_id = ?
        """,
        (user_id, target_user_id),
    ).fetchone()
    return {
        "ignoreContent": bool(row and row["ignore_content"]),
        "blockDm": bool(row and row["block_dm"]),
    }


def list_user_relationships(
    conn: sqlite3.Connection,
    user_id: int,
    *,
    limit: int = 80,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            rel.*,
            u.id AS target_id,
            u.username AS target_username,
            u.role AS target_role,
            u.bio AS target_bio,
            u.avatar_path AS target_avatar_path,
            u.status_text AS target_status_text,
            u.xp AS target_xp,
            u.created_at AS target_created_at,
            u.last_seen_at AS target_last_seen_at
        FROM user_relationships rel
        JOIN users u ON u.id = rel.target_user_id
        WHERE rel.user_id = ? AND (rel.ignore_content = 1 OR rel.block_dm = 1)
        ORDER BY rel.updated_at DESC, rel.target_user_id DESC
        LIMIT ?
        """,
        (user_id, limit),
    ).fetchall()
    output: list[dict[str, Any]] = []
    for row in rows:
        output.append(
            {
                "user": serialize_user(
                    {
                        "id": row["target_id"],
                        "username": row["target_username"],
                        "role": row["target_role"],
                        "bio": row["target_bio"] or "",
                        "avatar_path": row["target_avatar_path"] or "",
                        "status_text": row["target_status_text"] or "",
                        "xp": row["target_xp"] or 0,
                        "created_at": row["target_created_at"],
                        "last_seen_at": row["target_last_seen_at"],
                        "posts_count": 0,
                        "threads_count": 0,
                        "likes_received": 0,
                    }
                ),
                "ignoreContent": bool(row["ignore_content"]),
                "blockDm": bool(row["block_dm"]),
                "updatedAt": row["updated_at"],
            }
        )
    return output


def upsert_user_relationship(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    target_user_id: int,
    ignore_content: bool,
    block_dm: bool,
) -> dict[str, bool]:
    if int(user_id or 0) <= 0 or int(target_user_id or 0) <= 0:
        raise APIError("Relationship target is invalid.")
    if user_id == target_user_id:
        raise APIError("You cannot apply safety controls to your own account.")
    now = utc_iso()
    if not ignore_content and not block_dm:
        conn.execute(
            "DELETE FROM user_relationships WHERE user_id = ? AND target_user_id = ?",
            (user_id, target_user_id),
        )
        conn.commit()
        return {"ignoreContent": False, "blockDm": False}
    conn.execute(
        """
        INSERT INTO user_relationships (
            user_id, target_user_id, ignore_content, block_dm, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, target_user_id)
        DO UPDATE SET
            ignore_content = excluded.ignore_content,
            block_dm = excluded.block_dm,
            updated_at = excluded.updated_at
        """,
        (user_id, target_user_id, int(ignore_content), int(block_dm), now, now),
    )
    conn.commit()
    return {"ignoreContent": bool(ignore_content), "blockDm": bool(block_dm)}


def viewer_ignored_user_ids(
    conn: sqlite3.Connection,
    viewer: dict[str, Any] | None,
) -> set[int]:
    if not viewer or not bool(viewer.get("hide_ignored_content", 1)):
        return set()
    cached = viewer.get("_ignored_user_ids")
    if isinstance(cached, set):
        return cached
    rows = conn.execute(
        """
        SELECT target_user_id
        FROM user_relationships
        WHERE user_id = ? AND ignore_content = 1
        """,
        (viewer["id"],),
    ).fetchall()
    ignored = {int(row["target_user_id"]) for row in rows}
    viewer["_ignored_user_ids"] = ignored
    return ignored


def is_ignored_author(
    conn: sqlite3.Connection,
    viewer: dict[str, Any] | None,
    author_id: int | None,
) -> bool:
    return bool(author_id and int(author_id) in viewer_ignored_user_ids(conn, viewer))


def has_dm_block_relationship(conn: sqlite3.Connection, user_a: int, user_b: int) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM user_relationships
        WHERE ((user_id = ? AND target_user_id = ?) OR (user_id = ? AND target_user_id = ?))
          AND block_dm = 1
        LIMIT 1
        """,
        (user_a, user_b, user_b, user_a),
    ).fetchone()
    return bool(row)


def get_top_members(conn: sqlite3.Connection, limit: int = 5) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            u.*,
            (SELECT COUNT(*) FROM posts p WHERE p.author_id = u.id AND p.deleted_at IS NULL) AS posts_count,
            (SELECT COUNT(*) FROM threads t WHERE t.author_id = u.id AND t.deleted_at IS NULL) AS threads_count,
            (SELECT COUNT(*) FROM post_likes pl
             JOIN posts p2 ON p2.id = pl.post_id
             WHERE p2.author_id = u.id AND p2.deleted_at IS NULL) AS likes_received
            FROM users u
            WHERE u.approval_status = 'approved'
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
            (SELECT COUNT(*) FROM posts p WHERE p.author_id = u.id AND p.deleted_at IS NULL) AS posts_count,
            (SELECT COUNT(*) FROM threads t WHERE t.author_id = u.id AND t.deleted_at IS NULL) AS threads_count,
            (SELECT COUNT(*) FROM post_likes pl
             JOIN posts p2 ON p2.id = pl.post_id
             WHERE p2.author_id = u.id AND p2.deleted_at IS NULL) AS likes_received
            FROM users u
            WHERE u.approval_status = 'approved'
            ORDER BY u.created_at DESC
        """
    ).fetchall()
    return [serialize_user(dict(row)) for row in rows]


def get_role_breakdown(conn: sqlite3.Connection) -> dict[str, int]:
    counts = {role: 0 for role in ROLES}
    rows = conn.execute(
        "SELECT role, COUNT(*) AS count FROM users WHERE approval_status = 'approved' GROUP BY role"
    ).fetchall()
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
    return sum(int(item["unreadCount"] or 0) for item in list_dm_threads(conn, user_id, limit=200))


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
    output: list[dict[str, Any]] = []
    for row in rows:
        other_id = row["user_high_id"] if row["user_low_id"] == viewer_id else row["user_low_id"]
        if has_dm_block_relationship(conn, viewer_id, int(other_id)):
            continue
        output.append(serialize_dm_thread_summary(row, viewer_id))
        if len(output) >= limit:
            break
    return output


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
    other_id = row["user_high_id"] if row["user_low_id"] == viewer_id else row["user_low_id"]
    if has_dm_block_relationship(conn, viewer_id, int(other_id)):
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
            "SELECT * FROM users WHERE lower(username) = ? AND approval_status = 'approved'",
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
        "SELECT id FROM users WHERE role IN ('mod', 'admin', 'owner') AND approval_status = 'approved'"
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
          AND NOT EXISTS (
            SELECT 1
            FROM user_relationships rel
            WHERE rel.user_id = ?
              AND rel.target_user_id = COALESCE(notifications.actor_id, -1)
              AND (rel.ignore_content = 1 OR rel.block_dm = 1)
          )
        """,
        (user_id, user_id),
    ).fetchone()["count"]


def get_notification_counts(
    conn: sqlite3.Connection,
    user_id: int,
    *,
    viewer: dict[str, Any] | None = None,
) -> dict[str, int]:
    rows = conn.execute(
        """
        SELECT kind, target_type, COUNT(*) AS count
        FROM notifications
        WHERE user_id = ? AND read_at IS NULL
          AND NOT EXISTS (
            SELECT 1
            FROM user_relationships rel
            WHERE rel.user_id = ?
              AND rel.target_user_id = COALESCE(notifications.actor_id, -1)
              AND (rel.ignore_content = 1 OR rel.block_dm = 1)
          )
        GROUP BY kind, target_type
        """,
        (user_id, user_id),
    ).fetchall()
    counts = {
        "unread": 0,
        "replies": 0,
        "mentions": 0,
        "likes": 0,
        "dms": get_unread_dm_count(conn, user_id),
        "staff": 0,
        "reports": get_open_report_count(conn) if is_staff(viewer) else 0,
        "appeals": get_open_appeal_count(conn) if is_staff(viewer) else 0,
        "contactNotices": get_open_contact_notice_count(conn) if is_staff(viewer) else 0,
        "registrations": pending_registration_count(conn) if is_admin(viewer) else 0,
        "staffActions": 0,
    }
    for row in rows:
        count = int(row["count"] or 0)
        kind = row["kind"]
        target_type = row["target_type"] or ""
        counts["unread"] += count
        if kind == "reply":
            counts["replies"] += count
        elif kind == "mention":
            counts["mentions"] += count
        elif kind == "like":
            counts["likes"] += count
        elif kind == "dm":
            counts["dms"] = max(counts["dms"], count)
        elif kind == "staff_action":
            counts["staffActions"] += count
        if kind == "staff_alert" or target_type in {"report_queue", "appeal_queue", "contact_notice", "registration_queue"}:
            counts["staff"] += count
    counts["totalAttention"] = (
        counts["unread"]
        + counts["dms"]
        + counts["reports"]
        + counts["appeals"]
        + counts["contactNotices"]
        + counts["registrations"]
    )
    return counts


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
    kind: str = "all",
    limit: int = 60,
) -> list[dict[str, Any]]:
    params: list[Any] = [user_id, user_id]
    where = """
    WHERE n.user_id = ?
      AND NOT EXISTS (
        SELECT 1
        FROM user_relationships rel
        WHERE rel.user_id = ?
          AND rel.target_user_id = COALESCE(n.actor_id, -1)
          AND (rel.ignore_content = 1 OR rel.block_dm = 1)
      )
    """
    if status == "unread":
        where += " AND n.read_at IS NULL"
    if kind == "replies":
        where += " AND n.kind = 'reply'"
    elif kind == "mentions":
        where += " AND n.kind = 'mention'"
    elif kind == "likes":
        where += " AND n.kind = 'like'"
    elif kind == "dms":
        where += " AND n.kind = 'dm'"
    elif kind == "staff":
        where += " AND (n.kind = 'staff_alert' OR n.target_type IN ('report_queue', 'appeal_queue', 'contact_notice', 'registration_queue'))"
    elif kind == "staff_actions":
        where += " AND n.kind = 'staff_action'"
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
            WHERE p.id = ? AND p.deleted_at IS NULL AND t.deleted_at IS NULL
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


def serialize_report_note(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "note": row["note"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "author": {
            "id": row["author_id"],
            "username": row["author_username"],
            "role": row["author_role"],
        },
    }


def list_report_notes(conn: sqlite3.Connection, report_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            rn.*,
            author.username AS author_username,
            author.role AS author_role
        FROM report_internal_notes rn
        JOIN users author ON author.id = rn.author_id
        WHERE rn.report_id = ?
        ORDER BY rn.created_at ASC, rn.id ASC
        """,
        (report_id,),
    ).fetchall()
    return [serialize_report_note(row) for row in rows]


def serialize_moderation_macro(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "body": row["body"],
        "category": row["category"] or "",
        "enabled": bool(row["enabled"]),
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "createdBy": (
            {"id": row["created_by"], "username": row["created_by_username"]}
            if row["created_by"] and row["created_by_username"]
            else None
        ),
    }


def list_moderation_macros(conn: sqlite3.Connection, *, include_disabled: bool = False) -> list[dict[str, Any]]:
    where = "" if include_disabled else "WHERE mm.enabled = 1"
    rows = conn.execute(
        f"""
        SELECT mm.*, creator.username AS created_by_username
        FROM moderation_macros mm
        LEFT JOIN users creator ON creator.id = mm.created_by
        {where}
        ORDER BY mm.enabled DESC, mm.title COLLATE NOCASE ASC, mm.id ASC
        """
    ).fetchall()
    return [serialize_moderation_macro(row) for row in rows]


def serialize_report(row: sqlite3.Row, conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    sla_due_at = parse_iso(row["sla_due_at"] if "sla_due_at" in row.keys() else None)
    sla_state = "none"
    if sla_due_at:
        sla_state = "overdue" if sla_due_at <= utc_now() and row["status"] == "open" else "active"
    return {
        "id": row["id"],
        "reason": row["reason"],
        "details": row["details"] or "",
        "status": row["status"],
        "adminNote": row["admin_note"] or "",
        "priority": row["triage_priority"] or "normal",
        "category": row["triage_category"] or "",
        "resolutionCode": row["resolution_code"] or "",
        "slaDueAt": row["sla_due_at"] if "sla_due_at" in row.keys() else None,
        "slaState": sla_state,
        "escalatedAt": row["escalated_at"] if "escalated_at" in row.keys() else None,
        "escalationNote": row["escalation_note"] if "escalation_note" in row.keys() else "",
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
        "internalNotes": list_report_notes(conn, row["id"]) if conn is not None else [],
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
    return [serialize_report(row, conn) for row in rows]


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
            (SELECT COUNT(*) FROM posts p WHERE p.author_id = u.id AND p.deleted_at IS NULL) AS posts_count,
            (SELECT COUNT(*) FROM threads t WHERE t.author_id = u.id AND t.deleted_at IS NULL) AS threads_count,
            (SELECT COUNT(*) FROM post_likes pl
             JOIN posts p2 ON p2.id = pl.post_id
             WHERE p2.author_id = u.id AND p2.deleted_at IS NULL) AS likes_received
            FROM users u
            WHERE u.approval_status = 'approved'
              AND (lower(u.username) LIKE ? OR lower(u.bio) LIKE ?)
        ORDER BY
            CASE WHEN lower(u.username) = ? THEN 0 ELSE 1 END,
            CASE WHEN lower(u.username) LIKE ? THEN 0 ELSE 1 END,
            u.username COLLATE NOCASE ASC
        LIMIT ?
        """,
        (pattern, pattern, query.lower(), f"{query.lower()}%", limit),
    ).fetchall()
    return [serialize_user(dict(row)) for row in rows]


def search_date_cutoff(date_filter: str) -> datetime | None:
    now = utc_now()
    if date_filter == "today":
        return now - timedelta(days=1)
    if date_filter == "week":
        return now - timedelta(days=7)
    if date_filter == "month":
        return now - timedelta(days=30)
    if date_filter == "year":
        return now - timedelta(days=365)
    return None


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


def search_threads(
    conn: sqlite3.Connection,
    query: str,
    *,
    viewer: dict[str, Any] | None,
    section_slug: str = "",
    author: str = "",
    tag: str = "",
    solved: str = "all",
    media: str = "all",
    replies: str = "all",
    date: str = "all",
    sort: str = "relevance",
    limit: int = 8,
) -> list[dict[str, Any]]:
    normalized_query = query.lower().strip()
    pattern = f"%{normalized_query}%" if normalized_query else "%"
    cutoff = search_date_cutoff(date)
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
          AND (lower(t.title) LIKE ? OR lower(t.tags_json) LIKE ? OR lower(t.prefix) LIKE ?)
        ORDER BY
            CASE WHEN lower(t.title) = ? THEN 0 ELSE 1 END,
            CASE WHEN lower(t.title) LIKE ? THEN 0 ELSE 1 END,
            t.updated_at DESC,
            t.id DESC
        LIMIT ?
        """,
        (pattern, pattern, pattern, normalized_query, f"{normalized_query}%", limit * 5),
    ).fetchall()
    output: list[dict[str, Any]] = []
    for row in rows:
        if not has_required_role(viewer, row["section_required_role"]):
            continue
        if is_ignored_author(conn, viewer, row["author_id"]):
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
        if cutoff and parse_iso(row["created_at"]) and parse_iso(row["created_at"]) < cutoff:
            continue
        if media == "with_media" and not thread_has_media(conn, row["id"]):
            continue
        if row["deleted_at"] is not None:
            continue
        if is_shadow_hidden_to_viewer(hidden=row["shadow_hidden"], author_id=row["author_id"], viewer=viewer):
            continue
        item = serialize_thread(row, conn, viewer)
        if replies == "unanswered" and item["replies"] > 0:
            continue
        if replies == "answered" and item["replies"] <= 0:
            continue
        output.append(item)
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
    media: str = "all",
    date: str = "all",
    limit: int = 8,
) -> list[dict[str, Any]]:
    normalized_query = query.lower().strip()
    pattern = f"%{normalized_query}%" if normalized_query else "%"
    cutoff = search_date_cutoff(date)
    rows = conn.execute(
        """
        SELECT
            p.id,
            p.thread_id,
            p.content,
            p.created_at,
            p.updated_at,
            p.shadow_hidden,
            p.deleted_at,
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
        WHERE p.deleted_at IS NULL
          AND lower(p.content) LIKE ?
          AND (? != 'with_media' OR EXISTS(SELECT 1 FROM post_media pm WHERE pm.post_id = p.id))
        ORDER BY
            CASE WHEN lower(p.content) LIKE ? THEN 0 ELSE 1 END,
            p.created_at DESC,
            p.id DESC
        LIMIT ?
        """,
        (pattern, media, f"{normalized_query}%", limit * 5),
    ).fetchall()
    output: list[dict[str, Any]] = []
    for row in rows:
        if not has_required_role(viewer, row["section_required_role"]):
            continue
        if is_ignored_author(conn, viewer, row["author_id"]):
            continue
        if section_slug and row["section_slug"] != section_slug:
            continue
        if author and row["author_username"].lower() != author.lower():
            continue
        if cutoff and parse_iso(row["created_at"]) and parse_iso(row["created_at"]) < cutoff:
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


def get_latest_activity(
    conn: sqlite3.Connection,
    viewer: dict[str, Any] | None = None,
    limit: int = 8,
) -> list[dict[str, Any]]:
    activities: list[dict[str, Any]] = []

    new_users = conn.execute(
        """
            SELECT username, created_at
            FROM users
            WHERE approval_status = 'approved'
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
        SELECT u.username, s.name AS section_name, t.title, t.created_at, t.author_id
        FROM threads t
        JOIN users u ON u.id = t.author_id
        JOIN sections s ON s.id = t.section_id
        WHERE COALESCE(t.shadow_hidden, 0) = 0
          AND t.deleted_at IS NULL
        ORDER BY t.created_at DESC
        LIMIT 6
        """
    ).fetchall()
    for row in new_threads:
        if is_ignored_author(conn, viewer, row["author_id"]):
            continue
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
        SELECT u.username, t.title, p.created_at, p.author_id
        FROM posts p
        JOIN users u ON u.id = p.author_id
        JOIN threads t ON t.id = p.thread_id
        WHERE COALESCE(p.shadow_hidden, 0) = 0
          AND p.deleted_at IS NULL
          AND p.id NOT IN (
            SELECT MIN(id)
            FROM posts
            WHERE deleted_at IS NULL
            GROUP BY thread_id
        )
        ORDER BY p.created_at DESC
        LIMIT 6
        """
    ).fetchall()
    for row in replies:
        if is_ignored_author(conn, viewer, row["author_id"]):
            continue
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
          AND deleted_at IS NULL
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
    member_count = conn.execute(
        "SELECT COUNT(*) AS count FROM users WHERE approval_status = 'approved'"
    ).fetchone()["count"]
    thread_count = conn.execute(
        "SELECT COUNT(*) AS count FROM threads WHERE COALESCE(shadow_hidden, 0) = 0 AND deleted_at IS NULL"
    ).fetchone()["count"]
    post_count = conn.execute(
        "SELECT COUNT(*) AS count FROM posts WHERE COALESCE(shadow_hidden, 0) = 0 AND deleted_at IS NULL"
    ).fetchone()["count"]
    online_since = utc_iso(utc_now() - timedelta(minutes=ONLINE_WINDOW_MINUTES))
    online_count = conn.execute(
        "SELECT COUNT(*) AS count FROM users WHERE approval_status = 'approved' AND last_seen_at >= ?",
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


def human_duration(seconds: int | float) -> str:
    remaining = max(0, int(seconds or 0))
    if remaining < 60:
        return f"{remaining}s"
    minutes = remaining // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    if hours < 48:
        return f"{hours}h"
    days = hours // 24
    return f"{days}d"


def append_server_log(message: str) -> None:
    ensure_runtime_dirs()
    with LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(f"[{utc_iso()}] {message}\n")


def read_recent_logs(*, limit_lines: int = 120) -> list[str]:
    if not LOG_FILE.exists():
        return []
    lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
    return lines[-limit_lines:]


def parse_log_timestamp(line: str) -> str:
    match = re.match(r"\[([^\]]+)\]", line or "")
    return match.group(1) if match else ""


def parse_log_status(line: str) -> int | None:
    match = re.search(r'"\s+(\d{3})\s+', line or "")
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def find_latest_log_entry(*needles: str) -> dict[str, str] | None:
    lowered_needles = [needle.lower() for needle in needles if needle]
    if not lowered_needles:
        return None
    for line in reversed(read_recent_logs(limit_lines=600)):
        lowered = line.lower()
        if any(needle in lowered for needle in lowered_needles):
            return {
                "time": parse_log_timestamp(line),
                "line": line,
            }
    return None


def recent_error_logs(*, limit: int = 8) -> list[dict[str, Any]]:
    error_terms = (" error", "failed", "exception", "traceback", "bad request")
    entries: list[dict[str, Any]] = []
    for line in reversed(read_recent_logs(limit_lines=500)):
        status = parse_log_status(line)
        lowered = f" {line.lower()}"
        if (status is not None and status >= 400) or any(term in lowered for term in error_terms):
            entries.append(
                {
                    "time": parse_log_timestamp(line),
                    "status": status,
                    "line": line,
                }
            )
        if len(entries) >= limit:
            break
    return entries


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


def list_backup_archives(*, limit: int = 12) -> list[dict[str, Any]]:
    ensure_runtime_dirs()
    archives = sorted(
        BACKUP_DIR.glob("omniforum-backup-*.zip"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    items: list[dict[str, Any]] = []
    for path in archives[:limit]:
        stat = path.stat()
        items.append(
            {
                "filename": path.name,
                "size": stat.st_size,
                "sizeLabel": human_size(stat.st_size),
                "createdAt": utc_iso(datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)),
                "downloadUrl": f"{EXPORT_ROUTE}/backups/{path.name}",
            }
        )
    return items


def resolve_backup_archive(filename: str) -> Path:
    candidate = str(filename or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9._-]+\.zip", candidate):
        raise APIError("Choose a valid backup archive.", HTTPStatus.BAD_REQUEST)
    path = (BACKUP_DIR / candidate).resolve()
    if path.parent != BACKUP_DIR.resolve() or not path.is_file():
        raise APIError("Backup archive not found.", HTTPStatus.NOT_FOUND)
    return path


def inspect_backup_archive(filename: str) -> dict[str, Any]:
    archive_path = resolve_backup_archive(filename)
    try:
        with zipfile.ZipFile(archive_path) as archive:
            names = sorted(name for name in archive.namelist() if not name.endswith("/"))
    except zipfile.BadZipFile as exc:
        raise APIError("That backup archive could not be opened.", HTTPStatus.BAD_REQUEST) from exc
    databases = [name for name in names if name.startswith("data/") and name.endswith(".db")]
    media_files = [name for name in names if name.startswith("data/uploads/")]
    log_files = [name for name in names if name.startswith("data/logs/")]
    missing = [
        path.name
        for path in DATA_FILES.values()
        if f"data/{path.name}" not in names
    ]
    return {
        "filename": archive_path.name,
        "downloadUrl": f"{EXPORT_ROUTE}/backups/{archive_path.name}",
        "size": archive_path.stat().st_size,
        "sizeLabel": human_size(archive_path.stat().st_size),
        "createdAt": utc_iso(datetime.fromtimestamp(archive_path.stat().st_mtime, tz=timezone.utc)),
        "contents": {
            "databaseCount": len(databases),
            "mediaCount": len(media_files),
            "logCount": len(log_files),
            "entriesPreview": names[:12],
            "hasAllDatabases": not missing,
            "missingDatabases": missing,
        },
        "restore": {
            "scriptPath": str(RESTORE_SCRIPT),
            "command": f"{RESTORE_SCRIPT} {archive_path} {BASE_DIR}",
            "steps": [
                "Create a fresh backup before restoring over live data.",
                "Stop OmniForum or your reverse-proxy-managed service first.",
                "Run the restore script with the backup archive path and project directory.",
                "Start OmniForum again and confirm /api/health, the homepage, and an admin login work.",
            ],
            "checks": [
                "Confirm the archive date and filename match the snapshot you want.",
                "Confirm the archive includes the expected database files and upload assets.",
                "Verify your current data/ directory was copied to a pre-restore safety snapshot.",
            ],
        },
    }


def discord_webhook_enabled() -> bool:
    return bool(DISCORD_WEBHOOK_URL)


def send_discord_webhook(
    *,
    title: str,
    lines: list[str],
    color: int = 0x00D4FF,
) -> bool:
    if not DISCORD_WEBHOOK_URL:
        return False
    description = "\n".join(str(line).strip() for line in lines if str(line).strip()).strip()
    payload = {
        "embeds": [
            {
                "title": title[:256],
                "description": description[:4096] or "No additional details.",
                "color": color,
                "timestamp": utc_now().isoformat(),
            }
        ]
    }
    request = Request(
        DISCORD_WEBHOOK_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=4):
            return True
    except Exception as exc:  # pragma: no cover - network best-effort
        append_server_log(f"discord webhook failed: {exc}")
        return False


def send_staff_discord_notice(
    *,
    title: str,
    lines: list[str],
    color: int = 0x00D4FF,
) -> None:
    send_discord_webhook(title=title, lines=lines, color=color)


def referenced_media_paths(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        """
        SELECT storage_path FROM post_media WHERE storage_path != ''
        UNION
        SELECT thumbnail_path AS storage_path FROM post_media WHERE thumbnail_path != ''
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


def get_database_storage() -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    total_bytes = 0
    for key, path in DATA_FILES.items():
        exists = path.exists()
        stat = path.stat() if exists else None
        size = stat.st_size if stat else 0
        total_bytes += size
        files.append(
            {
                "key": key,
                "name": path.name,
                "exists": exists,
                "size": size,
                "sizeLabel": human_size(size),
                "updatedAt": utc_iso(datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)) if stat else "",
            }
        )
    return {
        "totalBytes": total_bytes,
        "totalSize": human_size(total_bytes),
        "fileCount": len(files),
        "missingCount": sum(1 for item in files if not item["exists"]),
        "files": files,
        "labels": {item["name"]: item["sizeLabel"] for item in files},
    }


def get_storage_sizes() -> dict[str, str]:
    return get_database_storage()["labels"]


def get_media_usage(conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    ensure_runtime_dirs()
    referenced = referenced_media_paths(conn) if conn is not None else set()
    buckets: list[dict[str, Any]] = []
    total_files = 0
    total_bytes = 0
    orphaned_files = 0
    orphaned_bytes = 0

    loose_files = [path for path in MEDIA_DIR.glob("*") if path.is_file()]
    for file_path in loose_files:
        size = file_path.stat().st_size
        total_files += 1
        total_bytes += size
        orphaned_files += 1
        orphaned_bytes += size

    if loose_files:
        buckets.append(
            {
                "bucket": "loose",
                "label": "Loose uploads",
                "files": len(loose_files),
                "bytes": sum(path.stat().st_size for path in loose_files),
                "sizeLabel": human_size(sum(path.stat().st_size for path in loose_files)),
                "orphanedFiles": len(loose_files),
                "orphanedBytes": sum(path.stat().st_size for path in loose_files),
                "orphanedSize": human_size(sum(path.stat().st_size for path in loose_files)),
            }
        )

    for bucket, directory in MEDIA_FOLDERS.items():
        files = [path for path in directory.glob("*") if path.is_file()]
        bucket_bytes = 0
        bucket_orphaned_files = 0
        bucket_orphaned_bytes = 0
        for file_path in files:
            size = file_path.stat().st_size
            storage_path = f"{bucket}/{file_path.name}"
            bucket_bytes += size
            total_files += 1
            total_bytes += size
            if conn is not None and storage_path not in referenced:
                bucket_orphaned_files += 1
                bucket_orphaned_bytes += size
                orphaned_files += 1
                orphaned_bytes += size
        buckets.append(
            {
                "bucket": bucket,
                "label": bucket.replace("_", " ").title(),
                "files": len(files),
                "bytes": bucket_bytes,
                "sizeLabel": human_size(bucket_bytes),
                "orphanedFiles": bucket_orphaned_files,
                "orphanedBytes": bucket_orphaned_bytes,
                "orphanedSize": human_size(bucket_orphaned_bytes),
            }
        )

    return {
        "totalFiles": total_files,
        "totalBytes": total_bytes,
        "totalSize": human_size(total_bytes),
        "orphanedFiles": orphaned_files,
        "orphanedBytes": orphaned_bytes,
        "orphanedSize": human_size(orphaned_bytes),
        "buckets": buckets,
    }


def count_media_assets() -> int:
    return get_media_usage()["totalFiles"]


def get_backup_status(backups: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    ensure_runtime_dirs()
    backup_items = backups if backups is not None else list_backup_archives()
    all_archives = list(BACKUP_DIR.glob("omniforum-backup-*.zip"))
    total_bytes = sum(path.stat().st_size for path in all_archives if path.is_file())
    latest = backup_items[0] if backup_items else None
    now = utc_now()
    check = {
        "status": "missing",
        "checkedAt": utc_iso(now),
        "message": "No backup archive has been created yet.",
        "missingDatabases": list(DATA_FILES[path_key].name for path_key in DATA_FILES),
    }
    latest_age_seconds: int | None = None
    latest_age_label = ""
    if latest:
        try:
            created_at = datetime.fromisoformat(str(latest["createdAt"]).replace("Z", "+00:00"))
            latest_age_seconds = int((now - created_at).total_seconds())
            latest_age_label = human_duration(latest_age_seconds)
        except (KeyError, TypeError, ValueError):
            latest_age_seconds = None
        try:
            guide = inspect_backup_archive(str(latest["filename"]))
            missing = guide["contents"].get("missingDatabases", [])
            check = {
                "status": "ok" if not missing else "warning",
                "checkedAt": utc_iso(now),
                "message": "Latest backup includes all database files." if not missing else "Latest backup is missing database files.",
                "missingDatabases": missing,
            }
        except APIError as exc:
            check = {
                "status": "error",
                "checkedAt": utc_iso(now),
                "message": str(exc),
                "missingDatabases": [],
            }
    stale = bool(latest_age_seconds is not None and latest_age_seconds > BACKUP_STALE_HOURS * 3600)
    status = "healthy" if latest and check["status"] == "ok" and not stale else "warning"
    if check["status"] == "error":
        status = "error"
    if not latest:
        status_label = "No backups yet"
    elif stale:
        status_label = f"Latest backup is {latest_age_label} old"
    elif check["status"] == "ok":
        status_label = "Latest backup verified"
    else:
        status_label = check["message"]
    return {
        "count": len(all_archives),
        "listedCount": len(backup_items),
        "totalBytes": total_bytes,
        "totalSize": human_size(total_bytes),
        "latest": latest,
        "latestAgeSeconds": latest_age_seconds,
        "latestAgeLabel": latest_age_label,
        "rotationLimit": BACKUP_ROTATION_LIMIT,
        "staleAfterHours": BACKUP_STALE_HOURS,
        "status": status,
        "statusLabel": status_label,
        "check": check,
        "lastCreatedLog": find_latest_log_entry("backup created"),
    }


def get_plugin_status_summary(plugins: list[dict[str, Any]]) -> dict[str, Any]:
    enabled = sum(1 for plugin in plugins if plugin.get("enabled"))
    disabled = sum(1 for plugin in plugins if not plugin.get("enabled"))
    with_assets = sum(1 for plugin in plugins if plugin.get("hasClientAssets"))
    asset_counts = {
        "styles": sum(int(plugin.get("assetCounts", {}).get("styles") or 0) for plugin in plugins),
        "scripts": sum(int(plugin.get("assetCounts", {}).get("scripts") or 0) for plugin in plugins),
        "assets": sum(int(plugin.get("assetCounts", {}).get("assets") or 0) for plugin in plugins),
    }
    invalid_directories: list[str] = []
    if PLUGIN_DIR.exists():
        for plugin_root in sorted(path for path in PLUGIN_DIR.iterdir() if path.is_dir()):
            if not load_plugin_manifest(plugin_root):
                invalid_directories.append(plugin_root.name)
    return {
        "total": len(plugins),
        "enabled": enabled,
        "disabled": disabled,
        "withClientAssets": with_assets,
        "invalidCount": len(invalid_directories),
        "invalidDirectories": invalid_directories,
        "assetCounts": asset_counts,
        "status": "warning" if invalid_directories else "healthy",
    }


def get_queue_status(conn: sqlite3.Connection) -> dict[str, Any]:
    counts = {
        "reports": get_open_report_count(conn),
        "appeals": get_open_appeal_count(conn),
        "contactNotices": get_open_contact_notice_count(conn),
        "registrations": pending_registration_count(conn),
    }
    total = sum(int(value or 0) for value in counts.values())
    return {
        **counts,
        "totalOpen": total,
        "status": "attention" if total else "clear",
    }


def get_recovery_readiness(backups: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    backup_status = get_backup_status(backups)
    restore_script_exists = RESTORE_SCRIPT.exists()
    restore_script_ready = restore_script_exists and os.access(RESTORE_SCRIPT, os.X_OK)
    if backup_status["status"] == "healthy" and restore_script_ready:
        status = "healthy"
        message = "Latest backup validates and restore tooling is present."
    elif not restore_script_exists:
        status = "error"
        message = "Restore script is missing."
    elif not restore_script_ready:
        status = "warning"
        message = "Restore script exists but is not executable."
    else:
        status = "warning"
        message = backup_status["statusLabel"]
    return {
        "status": status,
        "message": message,
        "checkedAt": backup_status["check"]["checkedAt"],
        "latestBackupCheck": backup_status["check"],
        "lastBackupCreated": backup_status.get("lastCreatedLog"),
        "lastRestoreGuideCheck": find_latest_log_entry("restore guide checked"),
        "restoreScript": {
            "path": str(RESTORE_SCRIPT),
            "exists": restore_script_exists,
            "executable": restore_script_ready,
        },
    }


def resolve_plugin_asset(plugin_root: Path, relative_path: str) -> Path | None:
    relative = str(relative_path or "").strip().replace("\\", "/").strip("/")
    if not relative:
        return None
    candidate = (plugin_root / relative).resolve()
    if plugin_root.resolve() not in {candidate, *candidate.parents}:
        return None
    if not candidate.is_file():
        return None
    return candidate


def load_plugin_manifest(plugin_root: Path) -> tuple[Path, dict[str, Any]] | None:
    manifest_path = plugin_root / "plugin.json"
    if not manifest_path.is_file():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(manifest, dict):
        return None
    return manifest_path, manifest


def plugin_client_assets(
    plugin_root: Path,
    manifest: dict[str, Any],
) -> dict[str, list[dict[str, str]]]:
    client = manifest.get("client") or {}
    assets: dict[str, list[dict[str, str]]] = {
        "styles": [],
        "scripts": [],
        "assets": [],
    }
    for bucket in ("styles", "scripts", "assets"):
        for item in client.get(bucket, []):
            resolved = resolve_plugin_asset(plugin_root, str(item))
            if not resolved:
                continue
            extension = resolved.suffix.lower()
            if extension not in PLUGIN_ASSET_EXTENSIONS:
                continue
            relative = resolved.relative_to(plugin_root).as_posix()
            assets[bucket].append(
                {
                    "path": relative,
                    "url": f"/plugins/{plugin_root.name}/{relative}",
                }
            )
    return assets


def serialize_plugin(plugin_root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    plugin_id = clean_slug(manifest.get("id") or plugin_root.name, fallback=plugin_root.name)
    enabled = bool(manifest.get("enabled", True))
    assets = plugin_client_assets(plugin_root, manifest)
    styles = [item["url"] for item in assets["styles"]]
    scripts = [item["url"] for item in assets["scripts"]]
    public_assets = [item["url"] for item in assets["assets"]]
    return {
        "id": plugin_id,
        "directory": plugin_root.name,
        "name": clean_text(manifest.get("name") or plugin_root.name, min_len=1, max_len=80, field="Plugin name"),
        "version": clean_text(manifest.get("version") or "0.0.0", min_len=1, max_len=32, field="Plugin version"),
        "description": clean_text(manifest.get("description"), min_len=0, max_len=200, field="Plugin description"),
        "enabled": enabled,
        "author": clean_text(manifest.get("author"), min_len=0, max_len=80, field="Plugin author"),
        "styles": styles,
        "scripts": scripts,
        "assets": public_assets,
        "assetCounts": {
            "styles": len(styles),
            "scripts": len(scripts),
            "assets": len(public_assets),
        },
        "hasClientAssets": bool(styles or scripts or public_assets),
        "safeLoadingRules": {
            "enabledOnly": True,
            "manifestDeclaredOnly": True,
            "allowedExtensions": sorted(PLUGIN_ASSET_EXTENSIONS),
        },
    }


def list_plugins(*, include_disabled: bool = True) -> list[dict[str, Any]]:
    if not PLUGIN_DIR.exists():
        return []
    output: list[dict[str, Any]] = []
    for plugin_root in sorted(path for path in PLUGIN_DIR.iterdir() if path.is_dir()):
        loaded = load_plugin_manifest(plugin_root)
        if not loaded:
            continue
        _manifest_path, manifest = loaded
        enabled = bool(manifest.get("enabled", True))
        if not include_disabled and not enabled:
            continue
        output.append(serialize_plugin(plugin_root, manifest))
    return output


def get_plugin_record(plugin_id: str) -> tuple[Path, Path, dict[str, Any]] | None:
    requested = clean_slug(plugin_id or "", fallback="")
    if not requested or not PLUGIN_DIR.exists():
        return None
    for plugin_root in sorted(path for path in PLUGIN_DIR.iterdir() if path.is_dir()):
        loaded = load_plugin_manifest(plugin_root)
        if not loaded:
            continue
        manifest_path, manifest = loaded
        current_id = clean_slug(manifest.get("id") or plugin_root.name, fallback=plugin_root.name)
        if current_id == requested or plugin_root.name == requested:
            return plugin_root, manifest_path, manifest
    return None


def set_plugin_enabled(plugin_id: str, enabled: bool) -> dict[str, Any]:
    record = get_plugin_record(plugin_id)
    if not record:
        raise APIError("Plugin not found.", HTTPStatus.NOT_FOUND)
    plugin_root, manifest_path, manifest = record
    manifest["enabled"] = bool(enabled)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return serialize_plugin(plugin_root, manifest)


def resolve_public_plugin_asset(directory: str, relative_path: str) -> tuple[Path, Path, dict[str, Any], Path] | None:
    plugin_root = (PLUGIN_DIR / directory).resolve()
    if PLUGIN_DIR.resolve() not in {plugin_root, *plugin_root.parents} or not plugin_root.is_dir():
        return None
    loaded = load_plugin_manifest(plugin_root)
    if not loaded:
        return None
    manifest_path, manifest = loaded
    if not bool(manifest.get("enabled", True)):
        return None
    allowed_paths = {
        item["path"]
        for bucket in plugin_client_assets(plugin_root, manifest).values()
        for item in bucket
    }
    normalized = str(relative_path or "").strip().replace("\\", "/").strip("/")
    if normalized not in allowed_paths:
        return None
    resolved = resolve_plugin_asset(plugin_root, normalized)
    if not resolved or resolved.suffix.lower() not in PLUGIN_ASSET_EXTENSIONS:
        return None
    return plugin_root, manifest_path, manifest, resolved


def admin_daily_series(
    conn: sqlite3.Connection,
    query: str,
    *,
    days: int = 7,
) -> list[dict[str, Any]]:
    series: list[dict[str, Any]] = []
    start_date = utc_now().date() - timedelta(days=days - 1)
    for offset in range(days):
        current = start_date + timedelta(days=offset)
        start = datetime.combine(current, datetime.min.time(), tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        row = conn.execute(query, (utc_iso(start), utc_iso(end))).fetchone()
        series.append({"date": current.isoformat(), "count": int(row["count"] if row else 0)})
    return series


def get_admin_analytics(conn: sqlite3.Connection) -> dict[str, Any]:
    top_sections = conn.execute(
        """
        SELECT
            s.slug,
            s.name,
            COUNT(DISTINCT t.id) AS thread_count,
            COUNT(p.id) AS post_count
        FROM sections s
        LEFT JOIN threads t ON t.section_id = s.id AND t.deleted_at IS NULL
        LEFT JOIN posts p ON p.thread_id = t.id AND p.deleted_at IS NULL
        GROUP BY s.id, s.slug, s.name
        ORDER BY post_count DESC, thread_count DESC, s.name COLLATE NOCASE ASC
        LIMIT 6
        """
    ).fetchall()
    tag_counts: dict[str, int] = {}
    tag_rows = conn.execute(
        "SELECT tags_json FROM threads WHERE deleted_at IS NULL ORDER BY updated_at DESC LIMIT 400"
    ).fetchall()
    for row in tag_rows:
        try:
            tags = json.loads(row["tags_json"] or "[]")
        except json.JSONDecodeError:
            tags = []
        for tag in tags:
            normalized = str(tag).strip().lower()
            if normalized:
                tag_counts[normalized] = tag_counts.get(normalized, 0) + 1
    top_tags = [
        {"tag": tag, "count": count}
        for tag, count in sorted(tag_counts.items(), key=lambda item: (-item[1], item[0]))[:10]
    ]
    moderator_rows = conn.execute(
        """
        SELECT actor.username, actor.role, COUNT(*) AS count
        FROM moderation_actions ma
        JOIN users actor ON actor.id = ma.actor_id
        WHERE ma.created_at >= ?
        GROUP BY ma.actor_id, actor.username, actor.role
        ORDER BY count DESC, actor.username COLLATE NOCASE ASC
        LIMIT 6
        """,
        (utc_iso(utc_now() - timedelta(days=30)),),
    ).fetchall()
    action_rows = conn.execute(
        """
        SELECT action_type, COUNT(*) AS count
        FROM moderation_actions
        WHERE created_at >= ?
        GROUP BY action_type
        ORDER BY count DESC, action_type ASC
        LIMIT 12
        """,
        (utc_iso(utc_now() - timedelta(days=30)),),
    ).fetchall()
    report_rows = conn.execute(
        """
        SELECT triage_priority, COUNT(*) AS count
        FROM reports
        WHERE status = 'open'
        GROUP BY triage_priority
        ORDER BY count DESC, triage_priority ASC
        """
    ).fetchall()
    search_rows = conn.execute(
        """
        SELECT query, COUNT(*) AS count, AVG(result_count) AS avg_results, MAX(created_at) AS latest_at
        FROM search_events
        WHERE created_at >= ? AND query != ''
        GROUP BY lower(query)
        ORDER BY count DESC, latest_at DESC
        LIMIT 8
        """,
        (utc_iso(utc_now() - timedelta(days=30)),),
    ).fetchall()
    deleted_counts = {
        "threads": conn.execute(
            "SELECT COUNT(*) AS count FROM threads WHERE deleted_at IS NOT NULL"
        ).fetchone()["count"],
        "posts": conn.execute(
            "SELECT COUNT(*) AS count FROM posts WHERE deleted_at IS NOT NULL"
        ).fetchone()["count"],
    }
    return {
        "registrations7d": admin_daily_series(
            conn,
            query="SELECT COUNT(*) AS count FROM users WHERE created_at >= ? AND created_at < ?",
        ),
        "threads7d": admin_daily_series(
            conn,
            query="SELECT COUNT(*) AS count FROM threads WHERE deleted_at IS NULL AND created_at >= ? AND created_at < ?",
        ),
        "posts7d": admin_daily_series(
            conn,
            query="SELECT COUNT(*) AS count FROM posts WHERE deleted_at IS NULL AND created_at >= ? AND created_at < ?",
        ),
        "activeUsers7d": admin_daily_series(
            conn,
            query="SELECT COUNT(DISTINCT user_id) AS count FROM sessions WHERE last_seen_at >= ? AND last_seen_at < ?",
        ),
        "searches7d": admin_daily_series(
            conn,
            query="SELECT COUNT(*) AS count FROM search_events WHERE created_at >= ? AND created_at < ?",
        ),
        "reports7d": admin_daily_series(
            conn,
            query="SELECT COUNT(*) AS count FROM reports WHERE created_at >= ? AND created_at < ?",
        ),
        "moderation7d": admin_daily_series(
            conn,
            query="SELECT COUNT(*) AS count FROM moderation_actions WHERE created_at >= ? AND created_at < ?",
        ),
        "topSections": [
            {
                "id": row["slug"],
                "name": row["name"],
                "threads": row["thread_count"],
                "posts": row["post_count"],
            }
            for row in top_sections
        ],
        "topTags": top_tags,
        "topModerators30d": [
            {
                "username": row["username"],
                "role": row["role"],
                "count": row["count"],
            }
            for row in moderator_rows
        ],
        "actionTypes30d": [
            {
                "type": row["action_type"],
                "count": row["count"],
            }
            for row in action_rows
        ],
        "activeRestrictions": {
            "banned": conn.execute("SELECT COUNT(*) AS count FROM users WHERE banned_at IS NOT NULL").fetchone()["count"],
            "timedOut": conn.execute(
                "SELECT COUNT(*) AS count FROM users WHERE timeout_until IS NOT NULL AND timeout_until > ?",
                (utc_iso(),),
            ).fetchone()["count"],
            "muted": conn.execute(
                "SELECT COUNT(*) AS count FROM users WHERE mute_until IS NOT NULL AND mute_until > ?",
                (utc_iso(),),
            ).fetchone()["count"],
            "shadowMuted": conn.execute(
                "SELECT COUNT(*) AS count FROM users WHERE shadow_muted = 1"
            ).fetchone()["count"],
        },
        "openReportPriorities": [
            {
                "priority": row["triage_priority"] or "normal",
                "count": row["count"],
            }
            for row in report_rows
        ],
        "topSearchTerms30d": [
            {
                "query": row["query"],
                "count": row["count"],
                "averageResults": round(float(row["avg_results"] or 0), 1),
                "latestAt": row["latest_at"],
            }
            for row in search_rows
        ],
        "storageFootprint": {
            "databases": get_database_storage()["totalSize"],
            "media": get_media_usage(conn)["totalSize"],
        },
        "deletedQueue": deleted_counts,
    }


def checklist_item(key: str, label: str, ok: bool, detail: str) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "ok": bool(ok),
        "status": "ok" if ok else "attention",
        "detail": detail,
    }


def get_admin_onboarding_checklist(conn: sqlite3.Connection) -> dict[str, Any]:
    owner_count = conn.execute(
        "SELECT COUNT(*) AS count FROM users WHERE role = 'owner' AND approval_status = 'approved'"
    ).fetchone()["count"]
    section_count = conn.execute("SELECT COUNT(*) AS count FROM sections").fetchone()["count"]
    public_section_count = conn.execute(
        "SELECT COUNT(*) AS count FROM sections WHERE required_role = 'new'"
    ).fetchone()["count"]
    settings = serialize_registration_settings(get_registration_settings(conn))
    items = [
        checklist_item("owner", "Owner Account", owner_count > 0, "Create and secure the first owner account."),
        checklist_item("sections", "Forum Sections", section_count >= 3, "Create enough sections for launch navigation."),
        checklist_item("public_sections", "Public Visibility", public_section_count > 0, "Keep at least one readable public section unless the forum is private."),
        checklist_item("rules", "Rules Page", (BASE_DIR / "pages" / "rules.html").exists(), "Publish community rules and enforcement expectations."),
        checklist_item("privacy", "Privacy Page", (BASE_DIR / "pages" / "privacy.html").exists(), "Publish privacy and data handling information."),
        checklist_item("contact", "Contact Form", (BASE_DIR / "pages" / "contact.html").exists(), "Keep the contact form available for staff notices."),
        checklist_item(
            "registration",
            "Registration Mode",
            bool(settings.get("publicRegistrationEnabled") or settings.get("inviteRequired")),
            "Choose open, invite-only, or approval-based registration.",
        ),
        checklist_item("backups", "First Backup", bool(list_backup_archives()), "Create at least one backup before public launch."),
        checklist_item("themes", "Theme Options", len(SITE_THEME_OPTIONS) >= 3, "Offer theme choices in user settings."),
    ]
    complete = sum(1 for item in items if item["ok"])
    return {
        "complete": complete,
        "total": len(items),
        "status": "ready" if complete == len(items) else "attention",
        "items": items,
    }


def get_production_install_checks(conn: sqlite3.Connection) -> dict[str, Any]:
    data_writable = DATA_DIR.exists() and os.access(DATA_DIR, os.R_OK | os.W_OK | os.X_OK)
    media_writable = all(path.exists() and os.access(path, os.R_OK | os.W_OK | os.X_OK) for path in MEDIA_FOLDERS.values())
    database_files_ready = all(path.exists() and os.access(path, os.R_OK | os.W_OK) for path in DATA_FILES.values())
    checks = [
        checklist_item("data_dir", "Dedicated Data Folder", data_writable, f"{DATA_DIR} must be readable and writable."),
        checklist_item("database_files", "SQLite Files", database_files_ready, "All required database files should exist in the data folder."),
        checklist_item("media_dirs", "Upload Folders", media_writable, "Avatar, post, and thumbnail folders must be writable."),
        checklist_item("docker", "Docker Files", (BASE_DIR / "Dockerfile").exists() and (BASE_DIR / "docker-compose.yml").exists(), "Dockerfile and docker-compose.yml are present."),
        checklist_item("reverse_proxy", "Reverse Proxy Config", (BASE_DIR / "deploy" / "nginx-omniforum.conf").exists(), "Nginx sample config is present for public hosting."),
        checklist_item("service_file", "Service File", (BASE_DIR / "deploy" / "omniforum.service").exists(), "Systemd service file is present for VPS installs."),
        checklist_item("secure_cookies", "Secure Cookies", SECURE_COOKIES or HOST in {"127.0.0.1", "localhost"}, "Set OMNIFORUM_SECURE_COOKIES=1 behind HTTPS."),
        checklist_item("public_url", "Public URL", bool(os.getenv("OMNIFORUM_PUBLIC_URL")) or HOST in {"127.0.0.1", "localhost"}, "Set OMNIFORUM_PUBLIC_URL for production share links."),
        checklist_item("upload_limit", "Upload Limit", MAX_REQUEST_BYTES >= POST_MEDIA_MAX_BYTES * POST_MEDIA_MAX_COUNT, "Server request limit can handle max post uploads."),
        checklist_item("backup_script", "Restore Script", RESTORE_SCRIPT.exists() and os.access(RESTORE_SCRIPT, os.X_OK), "Restore script should exist and be executable."),
        checklist_item("image_processing", "Image Processing", PIL_AVAILABLE, "Pillow should be installed for resize, compression, and thumbnails."),
    ]
    passing = sum(1 for item in checks if item["ok"])
    return {
        "passing": passing,
        "total": len(checks),
        "status": "ready" if passing == len(checks) else "attention",
        "items": checks,
    }


def get_admin_health(conn: sqlite3.Connection) -> dict[str, Any]:
    database_storage = get_database_storage()
    media_usage = get_media_usage(conn)
    backups = list_backup_archives()
    backup_status = get_backup_status(backups)
    plugins = list_plugins()
    queues = get_queue_status(conn)
    latest_errors = recent_error_logs(limit=8)
    return {
        "uptimeSeconds": int((utc_now() - SERVER_STARTED_AT).total_seconds()),
        "startedAt": utc_iso(SERVER_STARTED_AT),
        "stats": get_site_stats(conn),
        "storage": {
            "databases": database_storage["labels"],
            "databaseFiles": database_storage["files"],
            "databaseTotalBytes": database_storage["totalBytes"],
            "databaseTotalSize": database_storage["totalSize"],
            "databaseMissingCount": database_storage["missingCount"],
            "mediaAssets": media_usage["totalFiles"],
            "mediaUsage": media_usage,
            "backupCount": backup_status["count"],
            "backupTotalBytes": backup_status["totalBytes"],
            "backupTotalSize": backup_status["totalSize"],
            "backupStatus": backup_status,
            "backups": backups,
            "mediaQuotaBytes": USER_MEDIA_LIMIT_BYTES,
            "mediaQuotaBytesLabel": human_size(USER_MEDIA_LIMIT_BYTES),
            "mediaQuotaFiles": USER_MEDIA_LIMIT_FILES,
        },
        "queues": queues,
        "runtime": {
            "host": HOST,
            "port": PORT,
            "maxRequestBytes": MAX_REQUEST_BYTES,
            "secureCookies": SECURE_COOKIES,
            "maxRequestSize": human_size(MAX_REQUEST_BYTES),
            "publicUrl": PUBLIC_URL,
            "discordWebhookConfigured": discord_webhook_enabled(),
            "site": serialize_site_settings(get_site_settings(conn)),
            "registration": serialize_registration_settings(get_registration_settings(conn)),
            "mediaProcessing": {
                "enabled": PIL_AVAILABLE,
                "library": "Pillow" if PIL_AVAILABLE else "Unavailable",
                "avatarMaxDimension": AVATAR_IMAGE_MAX_DIMENSION,
                "postMaxDimension": POST_IMAGE_MAX_DIMENSION,
                "thumbnailMaxDimension": POST_THUMBNAIL_MAX_DIMENSION,
            },
        },
        "analytics": get_admin_analytics(conn),
        "onboarding": get_admin_onboarding_checklist(conn),
        "installChecks": get_production_install_checks(conn),
        "plugins": plugins,
        "pluginStatus": get_plugin_status_summary(plugins),
        "logs": {
            "latestErrors": latest_errors,
            "errorCount": len(latest_errors),
            "lastErrorAt": latest_errors[0]["time"] if latest_errors else "",
        },
        "recovery": get_recovery_readiness(backups),
        "recentLogs": read_recent_logs(limit_lines=40),
    }


def get_live_snapshot(
    conn: sqlite3.Connection,
    viewer: dict[str, Any] | None,
    *,
    thread_id: int | None = None,
    section_slug: str = "",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "serverTime": utc_iso(),
        "stats": get_site_stats(conn),
        "currentUser": get_current_user_payload(conn, viewer),
    }
    if viewer:
        counts = get_notification_counts(conn, viewer["id"], viewer=viewer)
        payload["attention"] = {
            "notifications": counts["unread"],
            "messages": counts["dms"],
            "reports": counts["reports"],
            "appeals": counts["appeals"],
            "notices": counts["contactNotices"],
            "registrations": counts["registrations"],
        }
    if thread_id:
        thread = get_thread_by_id(conn, thread_id)
        if thread and has_required_role(viewer, thread["section_required_role"]) and not is_shadow_hidden_to_viewer(
            hidden=thread["shadow_hidden"],
            author_id=thread["author_id"],
            viewer=viewer,
        ):
            visibility_clause = "thread_id = ? AND deleted_at IS NULL"
            params: list[Any] = [thread_id]
            ignored_ids = viewer_ignored_user_ids(conn, viewer)
            if ignored_ids:
                placeholders = ", ".join("?" for _ in ignored_ids)
                visibility_clause += f" AND author_id NOT IN ({placeholders})"
                params.extend(sorted(ignored_ids))
            if not is_staff(viewer):
                visibility_clause += " AND (COALESCE(shadow_hidden, 0) = 0"
                if viewer:
                    visibility_clause += " OR author_id = ?"
                    params.append(viewer["id"])
                visibility_clause += ")"
            thread_counts = conn.execute(
                f"""
                SELECT COUNT(*) AS post_count, MAX(id) AS last_post_id, MAX(updated_at) AS last_post_at
                FROM posts
                WHERE {visibility_clause}
                """,
                tuple(params),
            ).fetchone()
            payload["thread"] = {
                "id": thread_id,
                "updatedAt": thread["updated_at"],
                "postCount": int(thread_counts["post_count"] or 0),
                "lastPostId": int(thread_counts["last_post_id"] or 0),
                "lastPostAt": thread_counts["last_post_at"],
            }
    if section_slug:
        section = get_section_by_slug(conn, section_slug)
        if section and has_required_role(viewer, section["required_role"]):
            ignored_ids = viewer_ignored_user_ids(conn, viewer)
            clauses = ["t.section_id = ?", "t.deleted_at IS NULL"]
            params: list[Any] = [section["id"]]
            if ignored_ids:
                placeholders = ", ".join("?" for _ in ignored_ids)
                clauses.append(f"t.author_id NOT IN ({placeholders})")
                params.extend(sorted(ignored_ids))
            if not is_staff(viewer):
                clauses.append("COALESCE(t.shadow_hidden, 0) = 0")
            row = conn.execute(
                f"""
                SELECT COUNT(*) AS thread_count, MAX(t.updated_at) AS last_thread_at
                FROM threads t
                WHERE {" AND ".join(clauses)}
                """,
                tuple(params),
            ).fetchone()
            payload["section"] = {
                "id": section_slug,
                "threadCount": int(row["thread_count"] or 0),
                "lastThreadAt": row["last_thread_at"],
            }
    return payload


def public_forum_urls(conn: sqlite3.Connection) -> dict[str, list[dict[str, Any]]]:
    sections = conn.execute(
        """
        SELECT slug, name, updated_at
        FROM (
            SELECT s.slug AS slug, s.name AS name, MAX(t.updated_at) AS updated_at
            FROM sections s
            LEFT JOIN threads t ON t.section_id = s.id AND t.deleted_at IS NULL AND COALESCE(t.shadow_hidden, 0) = 0
            WHERE s.required_role = 'new'
            GROUP BY s.id, s.slug, s.name
        )
        ORDER BY name COLLATE NOCASE ASC
        """
    ).fetchall()
    threads = conn.execute(
        """
        SELECT t.id, t.title, t.updated_at, s.slug AS section_slug
        FROM threads t
        JOIN sections s ON s.id = t.section_id
        WHERE s.required_role = 'new'
          AND t.deleted_at IS NULL
          AND COALESCE(t.shadow_hidden, 0) = 0
        ORDER BY t.updated_at DESC, t.id DESC
        LIMIT 500
        """
    ).fetchall()
    return {
        "sections": [dict(row) for row in sections],
        "threads": [dict(row) for row in threads],
    }


def xml_escape(value: str) -> str:
    return (
        str(value or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def render_robots_txt() -> str:
    return "\n".join(
        [
            "User-agent: *",
            "Allow: /",
            "Disallow: /api/",
            "Disallow: /data/",
            "Disallow: /exports/",
            "Disallow: /pages/settings.html",
            f"Sitemap: {PUBLIC_URL}/sitemap.xml",
            "",
        ]
    )


def render_sitemap_xml(conn: sqlite3.Connection) -> str:
    public_urls = public_forum_urls(conn)
    static_urls = [
        {"loc": f"{PUBLIC_URL}/", "changefreq": "hourly", "priority": "1.0"},
        {"loc": f"{PUBLIC_URL}/pages/members.html", "changefreq": "daily", "priority": "0.7"},
        {"loc": f"{PUBLIC_URL}/pages/leaderboard.html", "changefreq": "daily", "priority": "0.7"},
        {"loc": f"{PUBLIC_URL}/pages/rules.html", "changefreq": "monthly", "priority": "0.4"},
        {"loc": f"{PUBLIC_URL}/pages/privacy.html", "changefreq": "monthly", "priority": "0.4"},
        {"loc": f"{PUBLIC_URL}/pages/contact.html", "changefreq": "monthly", "priority": "0.4"},
    ]
    entries = list(static_urls)
    for section in public_urls["sections"]:
        entries.append(
            {
                "loc": f"{PUBLIC_URL}/pages/section.html?section={section['slug']}",
                "lastmod": section.get("updated_at"),
                "changefreq": "daily",
                "priority": "0.8",
            }
        )
    for thread in public_urls["threads"]:
        entries.append(
            {
                "loc": f"{PUBLIC_URL}/pages/thread.html?thread={thread['id']}",
                "lastmod": thread.get("updated_at"),
                "changefreq": "daily",
                "priority": "0.7",
            }
        )
    parts = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for item in entries:
        parts.append("  <url>")
        parts.append(f"    <loc>{xml_escape(item['loc'])}</loc>")
        if item.get("lastmod"):
            parts.append(f"    <lastmod>{xml_escape(str(item['lastmod']))}</lastmod>")
        if item.get("changefreq"):
            parts.append(f"    <changefreq>{xml_escape(item['changefreq'])}</changefreq>")
        if item.get("priority"):
            parts.append(f"    <priority>{xml_escape(item['priority'])}</priority>")
        parts.append("  </url>")
    parts.append("</urlset>")
    return "\n".join(parts)


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
            s.thread_prefixes_json AS section_thread_prefixes_json,
            s.thread_template AS section_thread_template,
            s.thread_state_mode AS section_thread_state_mode,
            u.username AS author_name,
            u.role AS author_role,
            u.avatar_path AS author_avatar_path
        FROM threads t
        JOIN sections s ON s.id = t.section_id
        JOIN users u ON u.id = t.author_id
        WHERE t.id = ? AND t.deleted_at IS NULL
        """,
        (thread_id,),
    ).fetchone()


def serialize_thread_note(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "note": row["note"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "author": {
            "id": row["author_id"],
            "username": row["author_username"],
            "role": row["author_role"],
        },
    }


def list_thread_notes(
    conn: sqlite3.Connection,
    thread_id: int,
    *,
    limit: int = 12,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT tn.*, u.username AS author_username, u.role AS author_role
        FROM thread_notes tn
        JOIN users u ON u.id = tn.author_id
        WHERE tn.thread_id = ?
        ORDER BY tn.created_at DESC, tn.id DESC
        LIMIT ?
        """,
        (thread_id, limit),
    ).fetchall()
    return [serialize_thread_note(row) for row in rows]


def add_thread_note(
    conn: sqlite3.Connection,
    *,
    thread_id: int,
    author_id: int,
    note: str,
    created_at: str,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO thread_notes (thread_id, author_id, note, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (thread_id, author_id, note, created_at, created_at),
    )
    return int(cur.lastrowid)


def serialize_thread(
    thread_row: sqlite3.Row,
    conn: sqlite3.Connection,
    viewer: dict[str, Any] | None,
) -> dict[str, Any]:
    stats_where = "thread_id = ? AND deleted_at IS NULL"
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
    last_post_where = "p.thread_id = ? AND p.deleted_at IS NULL"
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
        "prefix": thread_row["prefix"] or "",
        "authorId": author_id,
        "authorName": thread_row["author_name"],
        "authorRole": thread_row["author_role"],
        "authorAvatarUrl": media_url_for_path(thread_row["author_avatar_path"]),
        "createdAt": thread_row["created_at"],
        "updatedAt": thread_row["updated_at"],
        "editedAt": thread_row["edited_at"],
        "views": thread_row["view_count"],
        "pinned": bool(thread_row["pinned"]),
        "featured": bool(thread_row["featured"]),
        "hot": stats["post_count"] >= 15,
        "locked": bool(thread_row["locked"]),
        "solved": bool(thread_row["solved"]),
        "answered": bool(thread_row["answer_post_id"]) and not bool(thread_row["solved"]),
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
            "threadPrefixes": json.loads(thread_row["section_thread_prefixes_json"] or "[]"),
            "threadTemplate": thread_row["section_thread_template"] or "",
            "threadStateMode": thread_row["section_thread_state_mode"] or "discussion",
        },
        "canEdit": can_edit,
        "canDelete": can_delete,
        "canModerate": can_moderate,
        "canMarkAnswer": can_mark_answer,
        "bookmarkedByViewer": flags["bookmarked"],
        "subscribedByViewer": flags["subscribed"],
        "staffNotes": list_thread_notes(conn, thread_row["id"]) if can_moderate else [],
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
        row for row in rows
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
    visibility_clause = "p.thread_id = ? AND p.deleted_at IS NULL"
    visibility_params: list[Any] = [thread_id]
    ignored_ids = viewer_ignored_user_ids(conn, viewer)
    if ignored_ids:
        placeholders = ", ".join("?" for _ in ignored_ids)
        visibility_clause += f" AND p.author_id NOT IN ({placeholders})"
        visibility_params.extend(sorted(ignored_ids))
    if not is_staff(viewer):
        visibility_clause += " AND (COALESCE(p.shadow_hidden, 0) = 0"
        if viewer:
            visibility_clause += " OR p.author_id = ?"
            visibility_params.append(viewer["id"])
        visibility_clause += ")"
    total_posts = conn.execute(
        f"SELECT COUNT(*) AS count FROM posts p WHERE {visibility_clause}",
        tuple(visibility_params),
    ).fetchone()["count"]
    if focus_post_id:
        focus_row = conn.execute(
            f"""
            SELECT COUNT(*) AS count
            FROM posts p
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
            (SELECT COUNT(*) FROM posts p2 WHERE p2.author_id = u.id AND p2.deleted_at IS NULL) AS author_posts,
            (SELECT COUNT(*) FROM threads t2 WHERE t2.author_id = u.id AND t2.deleted_at IS NULL) AS author_threads,
            (SELECT COUNT(*) FROM post_likes pl WHERE pl.post_id = p.id) AS likes_count,
            EXISTS(
                SELECT 1
                FROM post_likes pl2
                WHERE pl2.post_id = p.id AND pl2.user_id = ?
            ) AS liked_by_viewer
        FROM posts p
        JOIN threads t ON t.id = p.thread_id
        JOIN users u ON u.id = p.author_id
        WHERE {visibility_clause} AND t.deleted_at IS NULL
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
                "mediaSensitive": bool(row["media_sensitive"]),
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


def build_user_export(conn: sqlite3.Connection, user_id: int) -> dict[str, Any]:
    profile = get_user_profile(conn, user_id, viewer={"id": user_id, "role": "owner"}, include_detail=True)
    if not profile:
        raise APIError("User not found.", HTTPStatus.NOT_FOUND)
    thread_rows = conn.execute(
        """
        SELECT t.id, t.title, t.prefix, t.tags_json, t.created_at, t.updated_at,
               s.slug AS section_slug, s.name AS section_name
        FROM threads t
        JOIN sections s ON s.id = t.section_id
        WHERE t.author_id = ?
        ORDER BY t.created_at DESC, t.id DESC
        """,
        (user_id,),
    ).fetchall()
    post_rows = conn.execute(
        """
        SELECT p.id, p.thread_id, p.content, p.created_at, p.updated_at, p.edited_at,
               p.deleted_at, p.media_sensitive, t.title AS thread_title
        FROM posts p
        JOIN threads t ON t.id = p.thread_id
        WHERE p.author_id = ?
        ORDER BY p.created_at DESC, p.id DESC
        """,
        (user_id,),
    ).fetchall()
    dm_rows = conn.execute(
        """
        SELECT
            dm.id,
            dm.thread_id,
            dm.sender_id,
            dm.recipient_id,
            dm.content,
            dm.created_at,
            dm.updated_at,
            dm.read_at,
            dt.user_low_id,
            dt.user_high_id,
            sender.username AS sender_username,
            recipient.username AS recipient_username
        FROM dm_messages dm
        JOIN dm_threads dt ON dt.id = dm.thread_id
        JOIN users sender ON sender.id = dm.sender_id
        JOIN users recipient ON recipient.id = dm.recipient_id
        WHERE dm.sender_id = ? OR dm.recipient_id = ?
        ORDER BY dm.created_at DESC, dm.id DESC
        """,
        (user_id, user_id),
    ).fetchall()
    notification_rows = conn.execute(
        """
        SELECT id, kind, title, body, target_type, target_id, read_at, created_at
        FROM notifications
        WHERE user_id = ?
        ORDER BY created_at DESC, id DESC
        LIMIT 500
        """,
        (user_id,),
    ).fetchall()
    report_rows = conn.execute(
        """
        SELECT id, target_type, target_label, reason, status, created_at, updated_at
        FROM reports
        WHERE reporter_id = ?
        ORDER BY created_at DESC, id DESC
        """,
        (user_id,),
    ).fetchall()
    appeal_rows = conn.execute(
        """
        SELECT id, message, status, created_at, updated_at, handled_at
        FROM appeals
        WHERE user_id = ?
        ORDER BY created_at DESC, id DESC
        """,
        (user_id,),
    ).fetchall()
    return {
        "exportedAt": utc_iso(),
        "site": "OmniForum",
        "account": profile,
        "user": profile,
        "threads": [
            {
                "id": row["id"],
                "title": row["title"],
                "prefix": row["prefix"] or "",
                "tags": json.loads(row["tags_json"] or "[]"),
                "section": {"id": row["section_slug"], "name": row["section_name"]},
                "createdAt": row["created_at"],
                "updatedAt": row["updated_at"],
            }
            for row in thread_rows
        ],
        "posts": [
            {
                "id": row["id"],
                "threadId": row["thread_id"],
                "threadTitle": row["thread_title"],
                "content": row["content"],
                "mediaSensitive": bool(row["media_sensitive"]),
                "createdAt": row["created_at"],
                "updatedAt": row["updated_at"],
                "editedAt": row["edited_at"],
                "deletedAt": row["deleted_at"],
            }
            for row in post_rows
        ],
        "messages": [
            {
                "id": row["id"],
                "threadId": row["thread_id"],
                "content": row["content"],
                "createdAt": row["created_at"],
                "updatedAt": row["updated_at"],
                "readAt": row["read_at"],
                "sender": {
                    "id": row["sender_id"],
                    "username": row["sender_username"],
                },
                "recipient": {
                    "id": row["recipient_id"],
                    "username": row["recipient_username"],
                },
                "participants": [row["user_low_id"], row["user_high_id"]],
            }
            for row in dm_rows
        ],
        "notifications": [
            {
                "id": row["id"],
                "kind": row["kind"],
                "title": row["title"],
                "body": row["body"],
                "targetType": row["target_type"],
                "targetId": row["target_id"],
                "readAt": row["read_at"],
                "createdAt": row["created_at"],
            }
            for row in notification_rows
        ],
        "reports": [dict(row) for row in report_rows],
        "appeals": [dict(row) for row in appeal_rows],
        "relationships": profile.get("relationships") or [],
        "mediaUsage": get_user_media_usage(conn, user_id),
    }


def records_to_csv(records: list[dict[str, Any]]) -> str:
    if not records:
        return ""
    columns: list[str] = []
    for record in records:
        for key in record:
            if key not in columns:
                columns.append(key)
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for record in records:
        writer.writerow({
            key: json.dumps(value, ensure_ascii=True) if isinstance(value, (dict, list)) else value
            for key, value in record.items()
        })
    return buffer.getvalue()


def admin_export_records(conn: sqlite3.Connection, export_type: str) -> list[dict[str, Any]] | dict[str, Any]:
    if export_type == "users":
        rows = conn.execute(
            """
            SELECT id, username, role, bio, xp, created_at, updated_at, last_seen_at,
                   approval_status, recovery_discord_username
            FROM users
            ORDER BY id ASC
            """
        ).fetchall()
        return [dict(row) for row in rows]
    if export_type == "threads":
        rows = conn.execute(
            """
            SELECT t.id, t.title, t.prefix, t.tags_json, t.created_at, t.updated_at,
                   t.pinned, t.locked, t.solved, t.featured, t.deleted_at,
                   s.slug AS section_slug, s.name AS section_name,
                   u.username AS author_username
            FROM threads t
            JOIN sections s ON s.id = t.section_id
            JOIN users u ON u.id = t.author_id
            ORDER BY t.id ASC
            """
        ).fetchall()
        return [dict(row) for row in rows]
    if export_type == "posts":
        rows = conn.execute(
            """
            SELECT p.id, p.thread_id, t.title AS thread_title, p.author_id,
                   u.username AS author_username, p.content, p.media_sensitive,
                   p.created_at, p.updated_at, p.edited_at, p.deleted_at
            FROM posts p
            JOIN threads t ON t.id = p.thread_id
            JOIN users u ON u.id = p.author_id
            ORDER BY p.id ASC
            """
        ).fetchall()
        return [dict(row) for row in rows]
    if export_type == "reports":
        rows = conn.execute(
            """
            SELECT r.*, reporter.username AS reporter_username,
                   handler.username AS handled_by_username,
                   assigned.username AS assigned_to_username
            FROM reports r
            JOIN users reporter ON reporter.id = r.reporter_id
            LEFT JOIN users handler ON handler.id = r.handled_by
            LEFT JOIN users assigned ON assigned.id = r.assigned_to
            ORDER BY r.id ASC
            """
        ).fetchall()
        return [dict(row) for row in rows]
    if export_type == "moderation":
        rows = conn.execute(
            """
            SELECT ma.*, target.username AS target_username, actor.username AS actor_username
            FROM moderation_actions ma
            JOIN users target ON target.id = ma.user_id
            JOIN users actor ON actor.id = ma.actor_id
            ORDER BY ma.id ASC
            """
        ).fetchall()
        return [dict(row) for row in rows]
    if export_type == "settings":
        site = serialize_site_settings(get_site_settings(conn))
        registration = serialize_registration_settings(get_registration_settings(conn))
        sections = [
            dict(row)
            for row in conn.execute(
                """
                SELECT c.slug AS category_slug, c.label AS category_label,
                       s.slug, s.name, s.description, s.required_role, s.write_role,
                       s.thread_prefixes_json, s.thread_template, s.thread_state_mode, s.sort_order
                FROM sections s
                JOIN categories c ON c.id = s.category_id
                ORDER BY c.sort_order ASC, s.sort_order ASC, s.id ASC
                """
            ).fetchall()
        ]
        return {"site": site, "registration": registration, "sections": sections}
    if export_type == "all":
        return {
            key: admin_export_records(conn, key)
            for key in ("users", "threads", "posts", "reports", "moderation", "settings")
        }
    raise APIError("Choose a valid export type.", HTTPStatus.BAD_REQUEST)


def build_admin_export(
    conn: sqlite3.Connection,
    *,
    export_type: str,
    export_format: str,
) -> dict[str, Any]:
    if export_type not in ADMIN_EXPORT_TYPES:
        raise APIError("Choose a valid export type.", HTTPStatus.BAD_REQUEST)
    if export_format not in ADMIN_EXPORT_FORMATS:
        raise APIError("Choose JSON or CSV.", HTTPStatus.BAD_REQUEST)
    data = admin_export_records(conn, export_type)
    timestamp = utc_now().strftime("%Y%m%d-%H%M%S")
    if export_format == "csv":
        if isinstance(data, dict):
            if export_type == "settings":
                records = [
                    {"scope": "site", "key": key, "value": json.dumps(value, ensure_ascii=True) if isinstance(value, (dict, list)) else value}
                    for key, value in data["site"].items()
                ] + [
                    {"scope": "registration", "key": key, "value": value}
                    for key, value in data["registration"].items()
                ]
            else:
                raise APIError("CSV export is available for one data type at a time.", HTTPStatus.BAD_REQUEST)
        else:
            records = data
        content = records_to_csv(records)
        extension = "csv"
        content_type = "text/csv; charset=utf-8"
    else:
        content = json.dumps(
            {"exportedAt": utc_iso(), "type": export_type, "data": data},
            indent=2,
            ensure_ascii=True,
            sort_keys=True,
        )
        extension = "json"
        content_type = "application/json; charset=utf-8"
    return {
        "filename": f"omniforum-{export_type}-{timestamp}.{extension}",
        "contentType": content_type,
        "format": export_format,
        "type": export_type,
        "content": content,
        "rowCount": len(data) if isinstance(data, list) else len(data.keys()),
    }


def build_import_preview(raw_content: Any) -> dict[str, Any]:
    raw = str(raw_content or "").strip()
    if not raw:
        raise APIError("Paste JSON content to preview.")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise APIError("Import preview only accepts valid JSON for now.") from exc
    data = parsed.get("data") if isinstance(parsed, dict) and "data" in parsed else parsed
    counts: dict[str, int] = {}
    warnings: list[str] = []
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, list):
                counts[key] = len(value)
            elif isinstance(value, dict):
                counts[key] = len(value)
        if not counts:
            warnings.append("No obvious importable collections were found.")
    elif isinstance(data, list):
        counts["items"] = len(data)
    else:
        warnings.append("The JSON root is not a list or object.")
    warnings.append("Preview only: no live data was changed.")
    return {
        "valid": True,
        "counts": counts,
        "warnings": warnings,
        "detectedType": parsed.get("type", "unknown") if isinstance(parsed, dict) else "list",
        "previewedAt": utc_iso(),
    }


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

    def enforce_csrf_token(self, viewer: dict[str, Any] | None, path: str) -> None:
        if not viewer or path in {"/api/login", "/api/register"}:
            return
        expected = str(viewer.get("session_csrf_token") or "")
        provided = str(self.headers.get("X-CSRF-Token") or "")
        if not expected or not hmac.compare_digest(expected, provided):
            raise APIError("Security token expired. Refresh the page and try again.", HTTPStatus.FORBIDDEN)

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
        if parsed.path == "/api/live/stream":
            self.serve_live_stream(parse_qs(parsed.query))
            return
        if parsed.path.startswith("/api/"):
            self.handle_api("GET")
            return
        if parsed.path == "/robots.txt":
            self.respond_text(render_robots_txt(), content_type="text/plain; charset=utf-8")
            return
        if parsed.path == "/sitemap.xml":
            with get_connection() as conn:
                self.respond_text(render_sitemap_xml(conn), content_type="application/xml; charset=utf-8")
            return
        if parsed.path == "/data" or parsed.path.startswith("/data/"):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if parsed.path.startswith("/plugins/"):
            self.serve_plugin_asset(parsed.path)
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

    def respond_text(self, payload: str | bytes, *, status: int = HTTPStatus.OK, content_type: str) -> None:
        body = payload.encode("utf-8") if isinstance(payload, str) else payload
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_plugin_asset(self, path: str) -> None:
        relative = unquote(path[len("/plugins/") :]).strip("/")
        parts = [part for part in relative.split("/") if part]
        if len(parts) < 2:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        directory = parts[0]
        asset_path = "/".join(parts[1:])
        resolved = resolve_public_plugin_asset(directory, asset_path)
        if not resolved:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        _plugin_root, _manifest_path, _manifest, file_path = resolved
        body = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header(
            "Content-Type",
            mimetypes.guess_type(file_path.name)[0] or "application/octet-stream",
        )
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "public, max-age=600")
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

    def serve_live_stream(self, query: dict[str, list[str]]) -> None:
        thread_id = None
        raw_thread_id = (query.get("threadId") or [""])[0].strip()
        if raw_thread_id:
            try:
                thread_id = int(raw_thread_id)
            except (TypeError, ValueError):
                thread_id = None
        section_slug = (query.get("section") or [""])[0].strip()
        stream_once = (query.get("once") or [""])[0].strip().lower() in {"1", "true", "yes"}
        self.close_connection = stream_once
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Connection", "close" if stream_once else "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        last_payload = ""
        try:
            while True:
                with get_connection() as conn:
                    viewer = current_user_from_request(conn, self.headers, self.request_ip())
                    payload = get_live_snapshot(
                        conn,
                        viewer,
                        thread_id=thread_id,
                        section_slug=section_slug,
                    )
                encoded = json.dumps(payload, separators=(",", ":"))
                if encoded != last_payload:
                    message = f"retry: {LIVE_STREAM_INTERVAL_SECONDS * 1000}\nevent: snapshot\ndata: {encoded}\n\n"
                    last_payload = encoded
                else:
                    message = f"retry: {LIVE_STREAM_INTERVAL_SECONDS * 1000}\nevent: ping\ndata: {{\"serverTime\":\"{payload['serverTime']}\"}}\n\n"
                self.wfile.write(message.encode("utf-8"))
                self.wfile.flush()
                if stream_once:
                    break
                time.sleep(LIVE_STREAM_INTERVAL_SECONDS)
        except (BrokenPipeError, ConnectionResetError, ValueError):
            return

    def handle_api(self, method: str) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        conn = get_connection()
        try:
            if method != "GET":
                self.enforce_same_origin()
            viewer = current_user_from_request(conn, self.headers, self.request_ip())
            if method != "GET":
                self.enforce_csrf_token(viewer, path)
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
        if method == "GET" and path == "/api/site":
            return self.api_site(conn, viewer)
        if method == "GET" and path == "/api/home":
            return self.api_home(conn, viewer)
        if method == "GET" and path == "/api/me":
            return {"currentUser": get_current_user_payload(conn, viewer)}
        if method == "GET" and path == "/api/me/export":
            return self.api_export_me(conn, viewer)
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
        if method == "GET" and path == "/api/me/recovery-codes":
            return self.api_recovery_codes(conn, viewer)
        if method == "POST" and path == "/api/me/recovery-codes":
            return self.api_create_recovery_codes(conn, viewer)
        if method == "GET" and path == "/api/live":
            return self.api_live(conn, viewer, query)
        if method == "GET" and path == "/api/plugins":
            return self.api_plugins(conn, viewer, query)
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
        if method == "GET" and path == "/api/reports/macros":
            return self.api_report_macros(conn, viewer)
        if method == "POST" and path == "/api/reports/macros":
            return self.api_create_report_macro(conn, viewer)
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
        if method == "GET" and path == "/api/admin/trash":
            return self.api_admin_trash(conn, viewer, query)
        if method == "POST" and path == "/api/admin/backup":
            return self.api_admin_backup(conn, viewer)
        if method == "GET" and path == "/api/admin/backups/guide":
            return self.api_admin_backup_guide(conn, viewer, query)
        if method == "GET" and path == "/api/admin/logs":
            return self.api_admin_logs(conn, viewer)
        if method == "GET" and path == "/api/admin/audit":
            return self.api_admin_audit(conn, viewer, query)
        if method == "GET" and path == "/api/admin/site-settings":
            return self.api_admin_site_settings(conn, viewer)
        if method == "PATCH" and path == "/api/admin/site-settings":
            return self.api_update_admin_site_settings(conn, viewer)
        if method == "GET" and path == "/api/admin/export":
            return self.api_admin_export(conn, viewer, query)
        if method == "POST" and path == "/api/admin/import-preview":
            return self.api_admin_import_preview(conn, viewer)
        if method == "GET" and path == "/api/admin/registration":
            return self.api_admin_registration(conn, viewer)
        if method == "PATCH" and path == "/api/admin/registration/settings":
            return self.api_update_registration_settings(conn, viewer)
        if method == "POST" and path == "/api/admin/invites":
            return self.api_create_invite(conn, viewer)
        if method == "POST" and path == "/api/admin/media-cleanup":
            return self.api_admin_media_cleanup(conn, viewer)
        if method == "POST" and path == "/api/admin/trash/restore":
            return self.api_restore_trash(conn, viewer)

        plugin_match = re.fullmatch(r"/api/plugins/([A-Za-z0-9_-]+)", path)
        if method == "PATCH" and plugin_match:
            return self.api_update_plugin(conn, viewer, plugin_match.group(1))

        invite_match = re.fullmatch(r"/api/admin/invites/(\d+)", path)
        if method == "PATCH" and invite_match:
            return self.api_update_invite(conn, viewer, int(invite_match.group(1)))

        registration_match = re.fullmatch(r"/api/admin/registrations/(\d+)/review", path)
        if method == "POST" and registration_match:
            return self.api_review_registration(conn, viewer, int(registration_match.group(1)))

        user_match = re.fullmatch(r"/api/users/(\d+)", path)
        if method == "GET" and user_match:
            return self.api_user_detail(conn, viewer, int(user_match.group(1)))

        role_match = re.fullmatch(r"/api/users/(\d+)/role", path)
        if method == "PATCH" and role_match:
            return self.api_update_role(conn, viewer, int(role_match.group(1)))

        relationship_match = re.fullmatch(r"/api/users/(\d+)/relationship", path)
        if method == "POST" and relationship_match:
            return self.api_update_user_relationship(conn, viewer, int(relationship_match.group(1)))

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

        report_note_match = re.fullmatch(r"/api/reports/(\d+)/notes", path)
        if method == "POST" and report_note_match:
            return self.api_add_report_note(conn, viewer, int(report_note_match.group(1)))

        report_macro_match = re.fullmatch(r"/api/reports/macros/(\d+)", path)
        if method == "PATCH" and report_macro_match:
            return self.api_update_report_macro(conn, viewer, int(report_macro_match.group(1)))

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

        thread_split_match = re.fullmatch(r"/api/threads/(\d+)/split", path)
        if method == "POST" and thread_split_match:
            return self.api_split_thread(conn, viewer, int(thread_split_match.group(1)))

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

    def api_site(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "site": serialize_site_settings(get_site_settings(conn)),
        }

    def api_home(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        return {
            "roles": ROLES,
            "site": serialize_site_settings(get_site_settings(conn)),
            "currentUser": get_current_user_payload(conn, viewer),
            "stats": get_site_stats(conn),
            "categories": get_sections_with_stats(conn, viewer),
            "topMembers": get_top_members(conn),
            "trendingThreads": get_trending_threads(conn, viewer),
            "featuredThreads": get_featured_threads(conn, viewer),
            "activity": get_latest_activity(conn, viewer),
            "announcements": get_home_announcements(conn),
        }

    def api_register(self, conn: sqlite3.Connection) -> dict[str, Any]:
        self.enforce_rate_limit("register")
        self.enforce_rate_limit("register_burst")
        data = self.read_json()
        username = clean_username(data.get("username"))
        password = clean_password(data.get("password"))
        now = utc_iso()
        current_count = conn.execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"]
        first_account = current_count == 0
        role = "owner" if first_account else "new"
        settings = get_registration_settings(conn)
        invite_code = ""
        invite_row = None
        approval_status = "approved"
        if not first_account:
            ensure_username_allowed_for_registration(username, settings)
            public_enabled = bool(settings.get("public_registration_enabled", 1))
            invite_required = bool(settings.get("invite_required", 0))
            if not public_enabled and not invite_required:
                raise APIError("Registration is currently closed.", HTTPStatus.FORBIDDEN)
            if invite_required:
                invite_code = clean_invite_code(data.get("inviteCode"))
                invite_row = find_valid_invite_code(conn, invite_code)
                if not invite_row:
                    raise APIError("That invite code is invalid, expired, or already used.", HTTPStatus.FORBIDDEN)
            approval_status = "pending" if bool(settings.get("approval_required", 0)) else "approved"
        bio = "New to OmniForum. Say hello and start the first thread."
        approved_at = now if approval_status == "approved" else None
        last_seen_at = now if approval_status == "approved" else None
        try:
            cur = conn.execute(
                """
                INSERT INTO users (
                    username, password_hash, role, bio, xp, created_at, updated_at, last_seen_at,
                    approval_status, approved_at, registration_ip, invite_code_used
                )
                VALUES (?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    username,
                    make_password_hash(password),
                    role,
                    bio,
                    now,
                    now,
                    last_seen_at,
                    approval_status,
                    approved_at,
                    self.request_ip(),
                    invite_code,
                ),
            )
            if invite_row:
                conn.execute(
                    "UPDATE invite_codes SET uses = uses + 1, updated_at = ? WHERE id = ?",
                    (now, invite_row["id"]),
                )
            if approval_status == "pending":
                create_staff_notifications(
                    conn,
                    actor_id=None,
                    title="Registration pending approval",
                    body=f"{username} is waiting for admin review.",
                    target_type="registration_queue",
                    target_id=cur.lastrowid,
                    created_at=now,
                )
            conn.commit()
        except sqlite3.IntegrityError as exc:
            raise APIError("Username already taken.") from exc

        if approval_status == "pending":
            append_server_log(f"registration pending approval: {username}")
            return {
                "currentUser": None,
                "pendingApproval": True,
                "message": "Account created and pending admin approval.",
                "__status__": HTTPStatus.ACCEPTED,
            }

        token, expires_at, csrf_token = create_session(
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
        if user is not None:
            user["csrfToken"] = csrf_token
        return {
            "currentUser": user,
            "__status__": HTTPStatus.CREATED,
            "__cookie_header__": self.make_session_cookie(token, expires_at),
        }

    def api_login(self, conn: sqlite3.Connection) -> dict[str, Any]:
        self.enforce_rate_limit("login")
        data = self.read_json()
        username = clean_username(data.get("username"))
        password = clean_text(data.get("password"), min_len=0, max_len=128, field="Password")
        recovery_code = normalize_recovery_code(data.get("recoveryCode"))
        if not password and not recovery_code:
            raise APIError("Enter a password or recovery code.", HTTPStatus.UNAUTHORIZED)
        row = conn.execute(
            "SELECT * FROM users WHERE lower(username) = lower(?)",
            (username,),
        ).fetchone()
        if not row:
            raise APIError("Invalid username or password.", HTTPStatus.UNAUTHORIZED)
        status = registration_status(row)
        if status == "pending":
            raise APIError("This account is still pending admin approval.", HTTPStatus.FORBIDDEN)
        if status == "rejected":
            raise APIError("This account registration was rejected.", HTTPStatus.FORBIDDEN)
        password_valid = verify_password(password, row["password_hash"])
        recovery_code_used = False
        now = utc_iso()
        if not password_valid:
            if recovery_code and consume_recovery_code(conn, row["id"], recovery_code):
                recovery_code_used = True
                conn.execute(
                    """
                    UPDATE users
                    SET password_reset_required = 1,
                        password_reset_set_by = NULL,
                        password_reset_set_at = ?,
                        password_reset_expires_at = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        now,
                        utc_iso(utc_now() + timedelta(minutes=30)),
                        now,
                        row["id"],
                    ),
                )
                log_audit_event(
                    conn,
                    actor_id=row["id"],
                    action_type="recovery_code_login",
                    category="settings",
                    target_type="user",
                    target_id=row["id"],
                    target_label=row["username"],
                    reason="Recovery code used to start a forced password reset session.",
                    created_at=now,
                )
                conn.commit()
                row = conn.execute("SELECT * FROM users WHERE id = ?", (row["id"],)).fetchone()
            else:
                raise APIError("Invalid username or password.", HTTPStatus.UNAUTHORIZED)
        reset_expires_at = parse_iso(row["password_reset_expires_at"] if row else None)
        if bool(row["password_reset_required"]) and reset_expires_at and reset_expires_at <= utc_now():
            raise APIError("That temporary password has expired. Ask an admin to issue a new recovery password.", HTTPStatus.FORBIDDEN)
        user_row = sync_user_restrictions(conn, row)
        if not user_row:
            raise APIError("Invalid username or password.", HTTPStatus.UNAUTHORIZED)
        token, expires_at, csrf_token = create_session(
            conn,
            user_row["id"],
            ip_address=self.request_ip(),
            user_agent=self.request_user_agent(),
        )
        conn.execute(
            "UPDATE users SET last_seen_at = ?, updated_at = ? WHERE id = ?",
            (now, now, user_row["id"]),
        )
        conn.commit()
        user = get_user_profile(conn, user_row["id"], viewer=user_row)
        if user is not None:
            user["csrfToken"] = csrf_token
        return {
            "currentUser": user,
            "recoveryCodeUsed": recovery_code_used,
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
        status_text = clean_status_text(data.get("statusText", viewer.get("status_text", "")))
        avatar_upload = data.get("avatarUpload")
        remove_avatar = bool(data.get("removeAvatar"))
        site_theme = clean_site_theme(data.get("siteTheme", viewer.get("site_theme", "midnight")))
        dm_privacy = clean_dm_privacy(data.get("dmPrivacy", viewer.get("dm_privacy", "everyone")))
        blur_sensitive_media = bool(data.get("blurSensitiveMedia", viewer.get("blur_sensitive_media", 1)))
        compact_post_layout = bool(data.get("compactPostLayout", viewer.get("compact_post_layout", 0)))
        hide_ignored_content = bool(data.get("hideIgnoredContent", viewer.get("hide_ignored_content", 1)))
        notify_replies = bool(data.get("notifyReplies", viewer.get("notify_replies", 1)))
        notify_likes = bool(data.get("notifyLikes", viewer.get("notify_likes", 1)))
        notify_mentions = bool(data.get("notifyMentions", viewer.get("notify_mentions", 1)))
        notify_dms = bool(data.get("notifyDms", viewer.get("notify_dms", 1)))
        signature = clean_signature(data.get("signature", viewer.get("signature", "")))
        profile_badge = clean_profile_badge(data.get("profileBadge", viewer.get("profile_badge", "")))
        profile_accent = clean_profile_accent(data.get("profileAccent", viewer.get("profile_accent", "")))
        recovery_discord_username = clean_discord_username(
            data.get("recoveryDiscordUsername", viewer.get("recovery_discord_username", ""))
        )
        current_avatar_path = str(viewer.get("avatar_path") or "")
        next_avatar_path = current_avatar_path
        decoded_avatar_upload = None
        if avatar_upload:
            decoded_avatar_upload = decode_image_upload(
                avatar_upload,
                field="Avatar",
                max_bytes=AVATAR_MAX_BYTES,
                kind="avatar",
            )
            ensure_user_media_quota(
                conn,
                viewer["id"],
                [decoded_avatar_upload],
                replacing_paths=[current_avatar_path] if current_avatar_path else [],
            )
            next_avatar_path = store_image_upload(
                decoded_avatar_upload,
                bucket="avatars",
            )
        elif remove_avatar:
            next_avatar_path = ""
        now = utc_iso()
        try:
            conn.execute(
                """
                UPDATE users
                SET username = ?, bio = ?, status_text = ?, avatar_path = ?, site_theme = ?, dm_privacy = ?,
                    blur_sensitive_media = ?, compact_post_layout = ?, hide_ignored_content = ?,
                    notify_replies = ?, notify_likes = ?, notify_mentions = ?, notify_dms = ?,
                    signature = ?, profile_badge = ?, profile_accent = ?,
                    recovery_discord_username = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    username,
                    bio,
                    status_text,
                    next_avatar_path,
                    site_theme,
                    dm_privacy,
                    int(blur_sensitive_media),
                    int(compact_post_layout),
                    int(hide_ignored_content),
                    int(notify_replies),
                    int(notify_likes),
                    int(notify_mentions),
                    int(notify_dms),
                    signature,
                    profile_badge,
                    profile_accent,
                    recovery_discord_username,
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
        if refreshed is not None and viewer.get("session_csrf_token"):
            refreshed["session_csrf_token"] = viewer.get("session_csrf_token")
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
                password_reset_expires_at = NULL,
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
        if refreshed is not None and viewer.get("session_csrf_token"):
            refreshed["session_csrf_token"] = viewer.get("session_csrf_token")
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

    def api_recovery_codes(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        ensure_can_participate(viewer)
        if not viewer:
            raise APIError("You must be logged in.", HTTPStatus.UNAUTHORIZED)
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "summary": recovery_code_summary(conn, viewer["id"]),
            "discordUsername": viewer.get("recovery_discord_username") or "",
            "message": "Recovery codes can be used once if you forget your password.",
        }

    def api_create_recovery_codes(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        ensure_can_participate(viewer)
        if not viewer:
            raise APIError("You must be logged in.", HTTPStatus.UNAUTHORIZED)
        data = self.read_json()
        if not bool(viewer.get("password_reset_required")):
            current_password = str(data.get("currentPassword") or "")
            if not verify_password(current_password, viewer["password_hash"]):
                raise APIError("Current password is required to regenerate recovery codes.", HTTPStatus.FORBIDDEN)
        codes = create_recovery_codes(conn, viewer["id"])
        log_audit_event(
            conn,
            actor=viewer,
            action_type="recovery_codes_regenerate",
            category="settings",
            target_type="user",
            target_id=viewer["id"],
            target_label=viewer["username"],
            reason="Account recovery codes regenerated.",
        )
        conn.commit()
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "codes": codes,
            "summary": recovery_code_summary(conn, viewer["id"]),
            "message": "Recovery codes regenerated. Store them somewhere safe; they are shown once.",
        }

    def api_export_me(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        ensure_can_participate(viewer)
        if not viewer:
            raise APIError("You must be logged in.", HTTPStatus.UNAUTHORIZED)
        export_payload = build_user_export(conn, viewer["id"])
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "filename": f"omniforum-export-{viewer['username']}-{utc_now().strftime('%Y%m%d-%H%M%S')}.json",
            "export": export_payload,
        }

    def api_live(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        query: dict[str, list[str]],
    ) -> dict[str, Any]:
        thread_id = None
        raw_thread_id = (query.get("threadId") or [""])[0].strip()
        if raw_thread_id:
            try:
                thread_id = int(raw_thread_id)
            except (TypeError, ValueError):
                thread_id = None
        section_slug = (query.get("section") or [""])[0].strip()
        return get_live_snapshot(
            conn,
            viewer,
            thread_id=thread_id,
            section_slug=section_slug,
        )

    def api_plugins(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        query: dict[str, list[str]],
    ) -> dict[str, Any]:
        include_disabled = bool(
            viewer
            and is_admin(viewer)
            and (query.get("includeAll") or [""])[0].strip().lower() in {"1", "true", "yes"}
        )
        plugins = list_plugins(include_disabled=include_disabled)
        if not include_disabled:
            plugins = [plugin for plugin in plugins if plugin["enabled"]]
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "plugins": plugins,
        }

    def api_update_plugin(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        plugin_id: str,
    ) -> dict[str, Any]:
        if not viewer or not is_admin(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        ensure_can_participate(viewer)
        data = self.read_json()
        if "enabled" not in data:
            raise APIError("Choose whether that plugin should be enabled.")
        plugin = set_plugin_enabled(plugin_id, bool(data.get("enabled")))
        state = "enabled" if plugin["enabled"] else "disabled"
        log_audit_event(
            conn,
            actor=viewer,
            action_type="plugin_update",
            category="plugins",
            target_type="plugin",
            target_label=plugin["id"],
            reason=f"Plugin {state}.",
            metadata={
                "pluginName": plugin["name"],
                "enabled": plugin["enabled"],
            },
        )
        conn.commit()
        append_server_log(f"plugin {state} by {viewer['username']}: {plugin['id']}")
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "plugin": plugin,
            "plugins": list_plugins(include_disabled=True),
            "message": f"{plugin['name']} is now {state}.",
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
        media_filter = (query.get("media") or ["all"])[0].strip().lower()
        replies_filter = (query.get("replies") or ["all"])[0].strip().lower()
        date_filter = (query.get("date") or ["all"])[0].strip().lower()
        sort = (query.get("sort") or ["relevance"])[0].strip().lower()
        if solved_filter not in {"all", "solved", "unsolved"}:
            solved_filter = "all"
        if media_filter not in {"all", "with_media"}:
            media_filter = "all"
        if replies_filter not in {"all", "answered", "unanswered"}:
            replies_filter = "all"
        if date_filter not in {"all", "today", "week", "month", "year"}:
            date_filter = "all"
        filters = {
            "section": section_filter,
            "author": author_filter,
            "tag": tag_filter,
            "solved": solved_filter,
            "media": media_filter,
            "replies": replies_filter,
            "date": date_filter,
            "sort": sort,
        }
        has_active_filter = any(value and value != "all" for key, value in filters.items() if key != "sort")
        if len(term) < 2 and not has_active_filter:
            return {
                "currentUser": get_current_user_payload(conn, viewer),
                "query": term,
                "filters": filters,
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
        search_term = term if len(term) >= 2 else ""
        threads = search_threads(
            conn,
            search_term,
            viewer=viewer,
            section_slug=section_filter,
            author=author_filter,
            tag=tag_filter,
            solved=solved_filter,
            media=media_filter,
            replies=replies_filter,
            date=date_filter,
            sort=sort,
            limit=12,
        )
        posts = search_posts(
            conn,
            search_term,
            viewer=viewer,
            section_slug=section_filter,
            author=author_filter,
            media=media_filter,
            date=date_filter,
            limit=12,
        )
        members = search_members(conn, search_term, limit=12) if search_term else []
        log_search_event(
            conn,
            viewer=viewer,
            query=search_term,
            filters=filters,
            result_count=len(threads) + len(posts) + len(members),
        )
        conn.commit()
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "query": term,
            "filters": filters,
            "threads": threads,
            "posts": posts,
            "members": members,
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
        kind = (query.get("kind") or ["all"])[0].strip().lower()
        if kind not in {"all", "replies", "mentions", "likes", "dms", "staff", "staff_actions"}:
            kind = "all"
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "items": list_notifications(conn, viewer["id"], status=status, kind=kind),
            "counts": get_notification_counts(conn, viewer["id"], viewer=viewer),
            "kind": kind,
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
        if not can_receive_direct_message(conn, recipient, viewer):
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
        if not can_receive_direct_message(conn, recipient, viewer):
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
            "macros": list_moderation_macros(conn),
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
        report_lines = [
            f"Reporter: {viewer['username']}",
            f"Target: {target['label']}",
            f"Reason: {reason}",
        ]
        if details:
            report_lines.append(f"Details: {short_preview(details, max_len=240)}")
        if target.get("contextThreadId"):
            report_lines.append(f"Review: {PUBLIC_URL}/pages/thread.html?thread={target['contextThreadId']}")
        send_staff_discord_notice(
            title="New OmniForum report",
            lines=report_lines,
            color=0xFF6B6B,
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
        now = utc_iso()
        sla_due_at = row["sla_due_at"]
        if "slaHours" in data:
            raw_sla_hours = data.get("slaHours")
            if raw_sla_hours in {None, "", 0, "0"}:
                sla_due_at = None
            else:
                try:
                    sla_hours = int(raw_sla_hours)
                except (TypeError, ValueError) as exc:
                    raise APIError("SLA hours must be a whole number.") from exc
                if sla_hours < 1 or sla_hours > 720:
                    raise APIError("SLA hours must be between 1 and 720.")
                sla_due_at = utc_iso(utc_now() + timedelta(hours=sla_hours))
        escalated_at = row["escalated_at"]
        escalation_note = row["escalation_note"] or ""
        if "escalated" in data:
            escalated = bool(data.get("escalated"))
            escalated_at = now if escalated and not escalated_at else (escalated_at if escalated else None)
        if "escalationNote" in data:
            escalation_note = clean_text(
                data.get("escalationNote"),
                min_len=0,
                max_len=500,
                field="Escalation note",
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
        handled_at = now if status == "resolved" else None
        handled_by = viewer["id"] if status == "resolved" else None
        conn.execute(
            """
            UPDATE reports
            SET status = ?, admin_note = ?, triage_priority = ?, triage_category = ?,
                resolution_code = ?, assigned_to = ?, sla_due_at = ?, escalated_at = ?,
                escalation_note = ?, handled_by = ?, handled_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                status,
                admin_note,
                priority,
                category,
                resolution_code,
                assigned_to,
                sla_due_at,
                escalated_at,
                escalation_note,
                handled_by,
                handled_at,
                now,
                report_id,
            ),
        )
        log_audit_event(
            conn,
            actor=viewer,
            action_type="report_update",
            category="moderation",
            target_type="report",
            target_id=report_id,
            target_label=row["target_label"],
            reason=admin_note or f"Report marked {status}.",
            metadata={
                "status": status,
                "priority": priority,
                "category": category,
                "resolutionCode": resolution_code,
                "assignedTo": assigned_to,
                "slaDueAt": sla_due_at,
                "escalatedAt": escalated_at,
            },
            created_at=now,
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
        log_audit_event(
            conn,
            actor=viewer,
            action_type="report_bulk_update",
            category="moderation",
            target_type="report",
            reason=f"Bulk-updated {len(report_ids)} reports.",
            metadata={
                "reportIds": report_ids,
                "updates": {field: value for field, value in updates},
            },
            created_at=now,
        )
        conn.commit()
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "message": "Report queue updated.",
            "items": list_reports(conn, status="all"),
        }

    def api_add_report_note(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        report_id: int,
    ) -> dict[str, Any]:
        if not viewer or not is_staff(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        ensure_can_participate(viewer)
        report = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
        if not report:
            raise APIError("Report not found.", HTTPStatus.NOT_FOUND)
        data = self.read_json()
        note = clean_text(data.get("note"), min_len=2, max_len=1200, field="Internal note")
        now = utc_iso()
        conn.execute(
            """
            INSERT INTO report_internal_notes (report_id, author_id, note, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (report_id, viewer["id"], note, now, now),
        )
        conn.execute("UPDATE reports SET updated_at = ? WHERE id = ?", (now, report_id))
        log_audit_event(
            conn,
            actor=viewer,
            action_type="report_internal_note",
            category="moderation",
            target_type="report",
            target_id=report_id,
            target_label=report["target_label"],
            reason="Internal report discussion note added.",
            metadata={"notePreview": short_preview(note, max_len=120)},
            created_at=now,
        )
        conn.commit()
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "message": "Internal note added.",
            "items": list_reports(conn, status="all"),
        }

    def api_report_macros(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not viewer or not is_staff(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "macros": list_moderation_macros(conn, include_disabled=is_admin(viewer)),
        }

    def api_create_report_macro(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not viewer or not is_staff(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        ensure_can_participate(viewer)
        data = self.read_json()
        title = clean_text(data.get("title"), min_len=2, max_len=80, field="Macro title")
        body = clean_text(data.get("body"), min_len=4, max_len=1200, field="Macro body")
        category = clean_text(data.get("category"), min_len=0, max_len=40, field="Macro category")
        enabled = bool(data.get("enabled", True))
        now = utc_iso()
        cur = conn.execute(
            """
            INSERT INTO moderation_macros (title, body, category, enabled, created_by, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (title, body, category, int(enabled), viewer["id"], now, now),
        )
        log_audit_event(
            conn,
            actor=viewer,
            action_type="moderation_macro_create",
            category="moderation",
            target_type="moderation_macro",
            target_id=cur.lastrowid,
            target_label=title,
            reason="Moderation macro created.",
            created_at=now,
        )
        conn.commit()
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "macro": serialize_moderation_macro(conn.execute(
                """
                SELECT mm.*, creator.username AS created_by_username
                FROM moderation_macros mm
                LEFT JOIN users creator ON creator.id = mm.created_by
                WHERE mm.id = ?
                """,
                (cur.lastrowid,),
            ).fetchone()),
            "macros": list_moderation_macros(conn, include_disabled=is_admin(viewer)),
            "message": "Moderation macro saved.",
        }

    def api_update_report_macro(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        macro_id: int,
    ) -> dict[str, Any]:
        if not viewer or not is_staff(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        ensure_can_participate(viewer)
        row = conn.execute("SELECT * FROM moderation_macros WHERE id = ?", (macro_id,)).fetchone()
        if not row:
            raise APIError("Macro not found.", HTTPStatus.NOT_FOUND)
        data = self.read_json()
        title = clean_text(data.get("title", row["title"]), min_len=2, max_len=80, field="Macro title")
        body = clean_text(data.get("body", row["body"]), min_len=4, max_len=1200, field="Macro body")
        category = clean_text(data.get("category", row["category"]), min_len=0, max_len=40, field="Macro category")
        enabled = bool(data.get("enabled", row["enabled"]))
        now = utc_iso()
        conn.execute(
            """
            UPDATE moderation_macros
            SET title = ?, body = ?, category = ?, enabled = ?, updated_at = ?
            WHERE id = ?
            """,
            (title, body, category, int(enabled), now, macro_id),
        )
        log_audit_event(
            conn,
            actor=viewer,
            action_type="moderation_macro_update",
            category="moderation",
            target_type="moderation_macro",
            target_id=macro_id,
            target_label=title,
            reason="Moderation macro updated.",
            metadata={"enabled": enabled},
            created_at=now,
        )
        conn.commit()
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "macros": list_moderation_macros(conn, include_disabled=is_admin(viewer)),
            "message": "Moderation macro updated.",
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
            if mark_notifications_read(conn, viewer["id"], target_type="appeal_queue"):
                conn.commit()
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
        send_staff_discord_notice(
            title="New OmniForum appeal",
            lines=[
                f"User: {viewer['username']}",
                f"Appeal: {short_preview(message, max_len=240)}",
                f"Review: {PUBLIC_URL}/pages/settings.html",
            ],
            color=0xF4B860,
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
        log_audit_event(
            conn,
            actor=viewer,
            action_type="appeal_update",
            category="moderation",
            target_type="appeal",
            target_id=appeal_id,
            target_label=f"appeal #{appeal_id}",
            reason=staff_note or f"Appeal marked {status}.",
            metadata={
                "status": status,
                "userId": row["user_id"],
            },
            created_at=now,
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
        contact_lines = [
            f"From: {name}",
            f"Subject: {subject}",
            f"Message: {short_preview(message, max_len=240)}",
        ]
        if discord_username:
            contact_lines.append(f"Discord: @{discord_username}")
        if viewer:
            contact_lines.append(f"Member: {viewer['username']}")
        contact_lines.append(f"Review: {PUBLIC_URL}/pages/settings.html")
        send_staff_discord_notice(
            title="New OmniForum contact notice",
            lines=contact_lines,
            color=0x00D4FF,
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
        log_audit_event(
            conn,
            actor=viewer,
            action_type="contact_notice_update",
            category="moderation",
            target_type="contact_notice",
            target_id=submission_id,
            target_label=row["subject"],
            reason=admin_note or f"Contact notice marked {new_status}.",
            metadata={
                "status": new_status,
                "name": row["name"],
                "discordUsername": row["discord_username"],
            },
            created_at=now,
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
        ignored_ids = viewer_ignored_user_ids(conn, viewer)
        search = (query.get("q") or [""])[0].strip().lower()
        role_filter = (query.get("role") or ["all"])[0].strip()
        if ignored_ids and viewer and bool(viewer.get("hide_ignored_content", 1)):
            members = [member for member in members if member["id"] not in ignored_ids]
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

    def api_update_user_relationship(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        user_id: int,
    ) -> dict[str, Any]:
        ensure_can_participate(viewer)
        if not viewer:
            raise APIError("You must be logged in.", HTTPStatus.UNAUTHORIZED)
        if user_id == int(viewer["id"]):
            raise APIError("You cannot change your relationship with yourself.")
        target = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
        if not target:
            raise APIError("User not found.", HTTPStatus.NOT_FOUND)
        data = self.read_json()
        relationship = upsert_user_relationship(
            conn,
            user_id=viewer["id"],
            target_user_id=user_id,
            ignore_content=bool(data.get("ignoreContent")),
            block_dm=bool(data.get("blockDm")),
        )
        conn.commit()
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "relationship": relationship,
            "user": get_user_profile(conn, user_id, viewer=viewer),
            "message": "Member controls updated.",
        }

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
            try:
                expires_in_hours = int(data.get("expiresInHours") or 48)
            except (TypeError, ValueError) as exc:
                raise APIError("Temporary password expiry must be a whole number of hours.") from exc
            if expires_in_hours < 1 or expires_in_hours > 168:
                raise APIError("Temporary passwords must expire between 1 and 168 hours.")
            reset_expires_at = utc_iso(utc_now() + timedelta(hours=expires_in_hours))
            conn.execute(
                """
                UPDATE users
                SET password_hash = ?, password_reset_required = 1,
                    password_reset_set_by = ?, password_reset_set_at = ?,
                    password_reset_expires_at = ?, recovery_note = ?, updated_at = ?
                WHERE id = ?
                """,
                (make_password_hash(temp_password), viewer["id"], now, reset_expires_at, note, now, user_id),
            )
            log_moderation_action(
                conn,
                user_id=user_id,
                actor_id=viewer["id"],
                action_type="temp_password",
                note=note,
                expires_at=reset_expires_at,
                metadata={
                    "expiresInHours": expires_in_hours,
                    "recoveryDiscordUsername": target.get("recovery_discord_username") or "",
                    "checklist": [
                        "Verify the request through the user's saved Discord username or known forum context.",
                        "Record why the account owner is believed to be legitimate.",
                        "Tell the user the temporary password expires and must be changed immediately after login.",
                    ],
                },
                created_at=now,
            )
            notify_staff_action(
                conn,
                target_user_id=user_id,
                actor=viewer,
                action="temp_password",
                note=note,
                metadata={"expiresAt": reset_expires_at},
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
        allowed_prefixes = json.loads(section["thread_prefixes_json"] or "[]")
        prefix = clean_thread_prefix(data.get("prefix"), allowed_prefixes)
        media_sensitive = bool(data.get("mediaSensitive"))
        poll = clean_poll_payload(data.get("poll"))
        ensure_user_media_quota(conn, viewer["id"], media_uploads)
        now = utc_iso()
        cur = conn.execute(
            """
            INSERT INTO threads (
                section_id, author_id, title, prefix, tags_json, created_at, updated_at,
                edited_at, view_count, pinned, locked, solved, answer_post_id, shadow_hidden
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, NULL, 1, 0, 0, 0, NULL, ?)
            """,
            (
                section["id"],
                viewer["id"],
                title,
                prefix,
                json.dumps(tags),
                now,
                now,
                int(is_shadow_muted(viewer)),
            ),
        )
        thread_id = cur.lastrowid
        first_post = conn.execute(
            """
            INSERT INTO posts (
                thread_id, author_id, content, media_sensitive,
                created_at, updated_at, edited_at, shadow_hidden
            )
            VALUES (?, ?, ?, ?, ?, ?, NULL, ?)
            """,
            (
                thread_id,
                viewer["id"],
                content,
                int(media_sensitive),
                now,
                now,
                int(is_shadow_muted(viewer)),
            ),
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
                "UPDATE posts SET thread_id = ? WHERE thread_id = ? AND deleted_at IS NULL",
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
            soft_delete_thread(
                conn,
                thread_id=thread_id,
                actor_id=viewer["id"],
                reason=f"Merged into thread {merge_to_thread_id}.",
                deleted_at=now,
            )
            log_audit_event(
                conn,
                actor=viewer,
                action_type="thread_merge",
                category="content",
                target_type="thread",
                target_id=thread_id,
                target_label=thread["title"],
                reason=f"Merged into thread {merge_to_thread_id}.",
                metadata={
                    "sourceThreadId": thread_id,
                    "destinationThreadId": merge_to_thread_id,
                    "destinationTitle": destination["title"],
                },
                created_at=now,
            )
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
        allowed_prefixes = json.loads(thread["section_thread_prefixes_json"] or "[]")
        prefix = clean_thread_prefix(data.get("prefix", thread["prefix"]), allowed_prefixes)
        tags = normalize_tags(data.get("tags", json.loads(thread["tags_json"] or "[]")))
        pinned = bool(data.get("pinned", thread["pinned"]))
        locked = bool(data.get("locked", thread["locked"]))
        featured = bool(data.get("featured", thread["featured"]))
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
                    "SELECT id FROM posts WHERE id = ? AND thread_id = ? AND deleted_at IS NULL",
                    (answer_post_id, thread_id),
                ).fetchone()
                if not answer_row:
                    raise APIError("That answer must be a post inside this thread.")
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
            featured = bool(thread["featured"])
        staff_note = ""
        if is_staff(viewer) and "staffNote" in data:
            staff_note = clean_text(
                data.get("staffNote"),
                min_len=0,
                max_len=1200,
                field="Staff note",
            )
        now = utc_iso()
        conn.execute(
            """
            UPDATE threads
            SET section_id = ?, title = ?, prefix = ?, tags_json = ?, pinned = ?, locked = ?, featured = ?,
                solved = ?, answer_post_id = ?, edited_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                next_section_id,
                title,
                prefix,
                json.dumps(tags),
                int(pinned),
                int(locked),
                int(featured),
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
        if is_staff(viewer):
            moderation_changes = {
                "fromSectionId": thread["section_id"],
                "toSectionId": next_section_id,
                "fromPinned": bool(thread["pinned"]),
                "toPinned": pinned,
                "fromLocked": bool(thread["locked"]),
                "toLocked": locked,
                "fromFeatured": bool(thread["featured"]),
                "toFeatured": featured,
                "fromSolved": bool(thread["solved"]),
                "toSolved": solved,
                "fromTitle": thread["title"],
                "toTitle": title,
            }
            if (
                next_section_id != thread["section_id"]
                or pinned != bool(thread["pinned"])
                or locked != bool(thread["locked"])
                or featured != bool(thread["featured"])
                or solved != bool(thread["solved"])
                or title != thread["title"]
                or "pollClosed" in data
            ):
                log_audit_event(
                    conn,
                    actor=viewer,
                    action_type="thread_update",
                    category="content",
                    target_type="thread",
                    target_id=thread_id,
                    target_label=title,
                    reason=f"Thread updated: {thread['title']}.",
                    metadata=moderation_changes,
                    created_at=now,
                )
        if staff_note:
            note_id = add_thread_note(
                conn,
                thread_id=thread_id,
                author_id=viewer["id"],
                note=staff_note,
                created_at=now,
            )
            log_audit_event(
                conn,
                actor=viewer,
                action_type="thread_note_create",
                category="content",
                target_type="thread",
                target_id=thread_id,
                target_label=title,
                reason=short_preview(staff_note, max_len=160),
                metadata={"noteId": note_id},
                created_at=now,
            )
        conn.commit()
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "thread": serialize_thread(get_thread_by_id(conn, thread_id), conn, viewer),
        }

    def api_split_thread(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        thread_id: int,
    ) -> dict[str, Any]:
        if not viewer or not is_staff(viewer):
            raise APIError("Only staff can split threads.", HTTPStatus.FORBIDDEN)
        ensure_can_participate(viewer)
        thread = get_thread_by_id(conn, thread_id)
        if not thread:
            raise APIError("Thread not found.", HTTPStatus.NOT_FOUND)
        data = self.read_json()
        try:
            post_id = int(data.get("postId"))
        except (TypeError, ValueError) as exc:
            raise APIError("Choose the reply where the split should begin.") from exc
        first_post_id = thread_first_post_id(conn, thread_id)
        if post_id == first_post_id:
            raise APIError("Use thread edit instead of splitting from the opening post.")
        split_post = conn.execute(
            """
            SELECT *
            FROM posts
            WHERE id = ? AND thread_id = ? AND deleted_at IS NULL
            """,
            (post_id, thread_id),
        ).fetchone()
        if not split_post:
            raise APIError("Split point not found.", HTTPStatus.NOT_FOUND)
        title = clean_text(
            data.get("title") or f"Split from: {thread['title']}",
            min_len=4,
            max_len=120,
            field="New thread title",
        )
        section_slug = str(data.get("sectionId") or thread["section_slug"]).strip()
        target_section = get_section_by_slug(conn, section_slug)
        if not target_section:
            raise APIError("Destination section not found.", HTTPStatus.NOT_FOUND)
        tags = normalize_tags(data.get("tags", json.loads(thread["tags_json"] or "[]")))
        split_rows = conn.execute(
            """
            SELECT id
            FROM posts
            WHERE thread_id = ? AND deleted_at IS NULL
              AND (created_at > ? OR (created_at = ? AND id >= ?))
            ORDER BY created_at ASC, id ASC
            """,
            (thread_id, split_post["created_at"], split_post["created_at"], post_id),
        ).fetchall()
        split_post_ids = [int(row["id"]) for row in split_rows]
        if not split_post_ids:
            raise APIError("There are no posts to split from that point.")
        now = utc_iso()
        cur = conn.execute(
            """
            INSERT INTO threads (
                section_id, author_id, title, prefix, tags_json, created_at, updated_at,
                edited_at, view_count, pinned, locked, solved, answer_post_id, featured, shadow_hidden
            )
            VALUES (?, ?, ?, '', ?, ?, ?, NULL, 0, 0, 0, 0, NULL, 0, ?)
            """,
            (
                target_section["id"],
                split_post["author_id"],
                title,
                json.dumps(tags),
                now,
                now,
                int(split_post["shadow_hidden"]),
            ),
        )
        new_thread_id = int(cur.lastrowid)
        placeholders = ", ".join("?" for _ in split_post_ids)
        conn.execute(
            f"UPDATE posts SET thread_id = ?, updated_at = ? WHERE id IN ({placeholders})",
            (new_thread_id, now, *split_post_ids),
        )
        if thread["answer_post_id"] in split_post_ids:
            conn.execute(
                "UPDATE threads SET solved = 0, answer_post_id = NULL WHERE id = ?",
                (thread_id,),
            )
        conn.execute("UPDATE threads SET updated_at = ? WHERE id = ?", (now, thread_id))
        ensure_thread_subscription(conn, thread_id=new_thread_id, user_id=viewer["id"], created_at=now)
        ensure_thread_subscription(conn, thread_id=new_thread_id, user_id=split_post["author_id"], created_at=now)
        log_audit_event(
            conn,
            actor=viewer,
            action_type="thread_split",
            category="content",
            target_type="thread",
            target_id=thread_id,
            target_label=thread["title"],
            reason=f"Split {len(split_post_ids)} posts into thread {new_thread_id}.",
            metadata={
                "sourceThreadId": thread_id,
                "newThreadId": new_thread_id,
                "postIds": split_post_ids,
                "destinationSection": target_section["slug"],
            },
            created_at=now,
        )
        conn.commit()
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "thread": serialize_thread(get_thread_by_id(conn, new_thread_id), conn, viewer),
            "sourceThread": serialize_thread(get_thread_by_id(conn, thread_id), conn, viewer),
            "message": "Thread split created.",
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
        media_sensitive = bool(data.get("mediaSensitive"))
        ensure_user_media_quota(conn, viewer["id"], media_uploads)
        now = utc_iso()
        cur = conn.execute(
            """
            INSERT INTO posts (
                thread_id, author_id, content, media_sensitive,
                created_at, updated_at, edited_at, shadow_hidden
            )
            VALUES (?, ?, ?, ?, ?, ?, NULL, ?)
            """,
            (
                thread_id,
                viewer["id"],
                content,
                int(media_sensitive),
                now,
                now,
                int(is_shadow_muted(viewer)),
            ),
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
        if row["deleted_at"]:
            raise APIError("Deleted posts cannot be edited.")
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
        media_sensitive = bool(data.get("mediaSensitive", row["media_sensitive"]))
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
            "UPDATE posts SET content = ?, media_sensitive = ?, updated_at = ?, edited_at = ? WHERE id = ?",
            (content, int(media_sensitive), now, now, post_id),
        )
        removed_media_paths: list[str] = []
        if should_update_media:
            keep_media_set = set(keep_media_ids)
            removed_media = [
                item for item in existing_media_rows if item["id"] not in keep_media_set
            ]
            if removed_media:
                removed_media_paths = [
                    path
                    for item in removed_media
                    for path in (item["storage_path"], item["thumbnail_path"])
                    if path
                ]
            ensure_user_media_quota(
                conn,
                viewer["id"],
                new_uploads,
                replacing_paths=removed_media_paths,
            )
            if removed_media:
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
        if is_staff(viewer) and viewer["id"] != row["author_id"]:
            log_audit_event(
                conn,
                actor=viewer,
                action_type="post_edit",
                category="content",
                target_type="post",
                target_id=post_id,
                target_label=f"post #{post_id}",
                reason="Staff edited another user's post.",
                metadata={
                    "threadId": row["thread_id"],
                    "authorId": row["author_id"],
                    "removedMedia": len(removed_media_paths),
                    "addedMedia": len(new_uploads),
                },
                created_at=now,
            )
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
        if row["deleted_at"]:
            raise APIError("This reply is already deleted.")
        first_post_id = thread_first_post_id(conn, row["thread_id"])
        if row["id"] == first_post_id:
            raise APIError("Delete the thread instead of its first post.")
        if not (viewer["id"] == row["author_id"] or is_staff(viewer)):
            raise APIError("You cannot delete this post.", HTTPStatus.FORBIDDEN)
        now = utc_iso()
        soft_delete_post(conn, post_id=post_id, actor_id=viewer["id"], deleted_at=now)
        conn.execute(
            "UPDATE threads SET answer_post_id = NULL, solved = 0 WHERE id = ? AND answer_post_id = ?",
            (row["thread_id"], post_id),
        )
        conn.execute("UPDATE threads SET updated_at = ? WHERE id = ?", (now, row["thread_id"]))
        if is_staff(viewer) or viewer["id"] != row["author_id"]:
            log_audit_event(
                conn,
                actor=viewer,
                action_type="post_delete",
                category="content",
                target_type="post",
                target_id=post_id,
                target_label=f"post #{post_id}",
                reason="Post soft-deleted.",
                metadata={"threadId": row["thread_id"]},
                created_at=now,
            )
        conn.commit()
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "deleted": True,
            "softDeleted": True,
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
            WHERE p.id = ? AND p.deleted_at IS NULL AND t.deleted_at IS NULL
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
            WHERE p.id = ? AND p.deleted_at IS NULL AND t.deleted_at IS NULL
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
            WHERE p.id = ? AND p.deleted_at IS NULL AND t.deleted_at IS NULL
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

    def api_admin_trash(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        query: dict[str, list[str]],
    ) -> dict[str, Any]:
        if not viewer or not is_admin(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        try:
            limit = int((query.get("limit") or ["60"])[0])
        except (TypeError, ValueError):
            limit = 60
        limit = max(1, min(120, limit))
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "items": list_deleted_content(conn, limit=limit),
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
        log_audit_event(
            conn,
            actor=viewer,
            action_type="backup_create",
            category="operations",
            target_type="backup",
            target_label=archive.name,
            reason="Backup archive created.",
            metadata={
                "filename": archive.name,
                "size": archive.stat().st_size if archive.exists() else 0,
            },
        )
        conn.commit()
        append_server_log(f"backup created by {viewer['username']}: {archive.name}")
        send_staff_discord_notice(
            title="OmniForum backup created",
            lines=[
                f"Admin: {viewer['username']}",
                f"Archive: {archive.name}",
                f"Download: {PUBLIC_URL}{EXPORT_ROUTE}/backups/{archive.name}",
            ],
            color=0x06D6A0,
        )
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "downloadUrl": f"{EXPORT_ROUTE}/backups/{archive.name}",
            "filename": archive.name,
            "message": "Backup archive created.",
        }

    def api_admin_backup_guide(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        query: dict[str, list[str]],
    ) -> dict[str, Any]:
        if not viewer or not is_admin(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        filename = (query.get("file") or [""])[0].strip()
        guide = inspect_backup_archive(filename)
        log_audit_event(
            conn,
            actor=viewer,
            action_type="restore_guide_view",
            category="operations",
            target_type="backup",
            target_label=guide["filename"],
            reason="Restore guide opened.",
            metadata={
                "hasAllDatabases": guide["contents"].get("hasAllDatabases"),
                "databaseCount": guide["contents"].get("databaseCount"),
                "mediaCount": guide["contents"].get("mediaCount"),
            },
        )
        conn.commit()
        append_server_log(f"restore guide checked by {viewer['username']}: {guide['filename']}")
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "guide": guide,
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

    def api_admin_audit(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        query: dict[str, list[str]],
    ) -> dict[str, Any]:
        if not viewer or not is_admin(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "audit": list_audit_events(conn, query),
        }

    def api_admin_site_settings(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not viewer or not is_admin(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "site": serialize_site_settings(get_site_settings(conn)),
            "registration": serialize_registration_settings(get_registration_settings(conn)),
            "onboarding": get_admin_onboarding_checklist(conn),
            "backups": list_backup_archives(limit=6),
        }

    def api_update_admin_site_settings(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not viewer or not is_admin(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        ensure_can_participate(viewer)
        site = update_site_settings_from_payload(conn, self.read_json(), viewer)
        append_server_log(f"site settings updated by {viewer['username']}")
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "site": site,
            "message": "Site settings saved.",
        }

    def api_admin_export(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        query: dict[str, list[str]],
    ) -> dict[str, Any]:
        if not viewer or not is_admin(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        export_type = (query.get("type") or ["all"])[0].strip().lower()
        export_format = (query.get("format") or ["json"])[0].strip().lower()
        export = build_admin_export(conn, export_type=export_type, export_format=export_format)
        log_audit_event(
            conn,
            actor=viewer,
            action_type="admin_export",
            category="operations",
            target_type="export",
            target_label=export["filename"],
            reason=f"Admin {export_type} export generated.",
            metadata={"type": export_type, "format": export_format, "rowCount": export["rowCount"]},
        )
        conn.commit()
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "export": export,
        }

    def api_admin_import_preview(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not viewer or not is_admin(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        preview = build_import_preview(self.read_json().get("content"))
        log_audit_event(
            conn,
            actor=viewer,
            action_type="admin_import_preview",
            category="operations",
            target_type="import_preview",
            target_label=preview.get("detectedType", "unknown"),
            reason="Admin import preview generated without writing data.",
            metadata={"counts": preview.get("counts", {})},
        )
        conn.commit()
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "preview": preview,
            "message": "Import preview complete. No data was changed.",
        }

    def api_admin_registration(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not viewer or not is_admin(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        ensure_can_participate(viewer)
        mark_notifications_read(conn, viewer["id"], target_type="registration_queue")
        conn.commit()
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "controls": registration_controls_payload(conn),
        }

    def api_update_registration_settings(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not viewer or not is_admin(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        ensure_can_participate(viewer)
        current = get_registration_settings(conn)
        data = self.read_json()
        public_enabled = bool(data.get("publicRegistrationEnabled", current["public_registration_enabled"]))
        invite_required = bool(data.get("inviteRequired", current["invite_required"]))
        approval_required = bool(data.get("approvalRequired", current["approval_required"]))
        patterns = clean_text(
            data.get("blockedUsernamePatterns", current.get("blocked_username_patterns") or ""),
            min_len=0,
            max_len=4000,
            field="Blocked username patterns",
        )
        pattern_lines = blocked_username_patterns({"blocked_username_patterns": patterns})
        if len(pattern_lines) > 100:
            raise APIError("Keep the blocked username list to 100 patterns or fewer.")
        if any(len(pattern) > 80 for pattern in pattern_lines):
            raise APIError("Blocked username patterns must be 80 characters or shorter.")
        now = utc_iso()
        conn.execute(
            """
            UPDATE registration_settings
            SET public_registration_enabled = ?,
                invite_required = ?,
                approval_required = ?,
                blocked_username_patterns = ?,
                updated_by = ?,
                updated_at = ?
            WHERE id = 1
            """,
            (
                1 if public_enabled else 0,
                1 if invite_required else 0,
                1 if approval_required else 0,
                patterns,
                viewer["id"],
                now,
            ),
        )
        log_audit_event(
            conn,
            actor=viewer,
            action_type="registration_settings_update",
            category="signup",
            target_type="settings",
            target_label="Signup controls",
            reason="Signup controls updated.",
            metadata={
                "publicRegistrationEnabled": public_enabled,
                "inviteRequired": invite_required,
                "approvalRequired": approval_required,
                "blockedPatternCount": len(pattern_lines),
            },
        )
        conn.commit()
        append_server_log(f"registration settings updated by {viewer['username']}")
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "controls": registration_controls_payload(conn),
            "message": "Signup controls updated.",
        }

    def api_create_invite(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not viewer or not is_admin(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        ensure_can_participate(viewer)
        data = self.read_json()
        note = clean_text(data.get("note"), min_len=0, max_len=160, field="Invite note")
        try:
            max_uses = int(data.get("maxUses") or 1)
        except (TypeError, ValueError) as exc:
            raise APIError("Invite uses must be a whole number.") from exc
        if max_uses < 1 or max_uses > 500:
            raise APIError("Invite uses must be between 1 and 500.")
        expires_at = None
        if data.get("expiresInDays") not in {None, ""}:
            try:
                expires_in_days = int(data.get("expiresInDays"))
            except (TypeError, ValueError) as exc:
                raise APIError("Invite expiration must be a whole number of days.") from exc
            if expires_in_days < 1 or expires_in_days > 365:
                raise APIError("Invite expiration must be between 1 and 365 days.")
            expires_at = utc_iso(utc_now() + timedelta(days=expires_in_days))
        custom_code = clean_invite_code(data.get("code"), required=False)
        now = utc_iso()
        for attempt in range(6):
            code = custom_code or generate_invite_code()
            try:
                cur = conn.execute(
                    """
                    INSERT INTO invite_codes (
                        code, note, max_uses, uses, enabled, expires_at,
                        created_by, created_at, updated_at
                    )
                    VALUES (?, ?, ?, 0, 1, ?, ?, ?, ?)
                    """,
                    (code, note, max_uses, expires_at, viewer["id"], now, now),
                )
                log_audit_event(
                    conn,
                    actor=viewer,
                    action_type="invite_create",
                    category="signup",
                    target_type="invite",
                    target_id=cur.lastrowid,
                    target_label=code,
                    reason=note,
                    metadata={
                        "maxUses": max_uses,
                        "expiresAt": expires_at,
                    },
                    created_at=now,
                )
                conn.commit()
                append_server_log(f"invite code created by {viewer['username']}: {code}")
                return {
                    "currentUser": get_current_user_payload(conn, viewer),
                    "controls": registration_controls_payload(conn),
                    "invite": next(
                        (item for item in list_invite_codes(conn) if item["code"].lower() == code.lower()),
                        None,
                    ),
                    "message": "Invite code created.",
                }
            except sqlite3.IntegrityError as exc:
                if custom_code or attempt == 5:
                    raise APIError("That invite code already exists.") from exc
        raise APIError("Could not create an invite code.")

    def api_update_invite(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        invite_id: int,
    ) -> dict[str, Any]:
        if not viewer or not is_admin(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        ensure_can_participate(viewer)
        row = conn.execute("SELECT * FROM invite_codes WHERE id = ?", (invite_id,)).fetchone()
        if not row:
            raise APIError("Invite code not found.", HTTPStatus.NOT_FOUND)
        data = self.read_json()
        note = clean_text(data.get("note", row["note"]), min_len=0, max_len=160, field="Invite note")
        enabled = bool(data.get("enabled", row["enabled"]))
        try:
            max_uses = int(data.get("maxUses", row["max_uses"]))
        except (TypeError, ValueError) as exc:
            raise APIError("Invite uses must be a whole number.") from exc
        if max_uses < max(1, int(row["uses"] or 0)) or max_uses > 500:
            raise APIError("Invite uses cannot be lower than current uses, below 1, or above 500.")
        expires_at = row["expires_at"]
        if bool(data.get("clearExpires")):
            expires_at = None
        elif data.get("expiresInDays") not in {None, ""}:
            try:
                expires_in_days = int(data.get("expiresInDays"))
            except (TypeError, ValueError) as exc:
                raise APIError("Invite expiration must be a whole number of days.") from exc
            if expires_in_days < 1 or expires_in_days > 365:
                raise APIError("Invite expiration must be between 1 and 365 days.")
            expires_at = utc_iso(utc_now() + timedelta(days=expires_in_days))
        now = utc_iso()
        conn.execute(
            """
            UPDATE invite_codes
            SET note = ?, max_uses = ?, enabled = ?, expires_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (note, max_uses, 1 if enabled else 0, expires_at, now, invite_id),
        )
        log_audit_event(
            conn,
            actor=viewer,
            action_type="invite_update",
            category="signup",
            target_type="invite",
            target_id=invite_id,
            target_label=row["code"],
            reason=note,
            metadata={
                "enabled": enabled,
                "maxUses": max_uses,
                "expiresAt": expires_at,
                "previousEnabled": bool(row["enabled"]),
            },
            created_at=now,
        )
        conn.commit()
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "controls": registration_controls_payload(conn),
            "message": "Invite code updated.",
        }

    def api_review_registration(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        user_id: int,
    ) -> dict[str, Any]:
        if not viewer or not is_admin(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        ensure_can_participate(viewer)
        target = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not target or registration_status(target) != "pending":
            raise APIError("Pending registration not found.", HTTPStatus.NOT_FOUND)
        data = self.read_json()
        action = str(data.get("action") or "").strip().lower()
        if action not in {"approve", "reject"}:
            raise APIError("Choose approve or reject.")
        note = clean_text(data.get("note"), min_len=0, max_len=500, field="Review note")
        now = utc_iso()
        new_status = "approved" if action == "approve" else "rejected"
        conn.execute(
            """
            UPDATE users
            SET approval_status = ?,
                approval_note = ?,
                approved_by = ?,
                approved_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (new_status, note, viewer["id"], now, now, user_id),
        )
        log_moderation_action(
            conn,
            user_id=user_id,
            actor_id=viewer["id"],
            action_type=f"registration_{action}",
            category="signup",
            reason=note,
            created_at=now,
        )
        if action == "approve":
            create_notification(
                conn,
                user_id=user_id,
                actor_id=viewer["id"],
                kind="staff_action",
                title="Registration approved",
                body=note or "Your account is approved. You can now log in.",
                target_type="user",
                target_id=user_id,
                created_at=now,
            )
        conn.commit()
        if action == "reject":
            delete_sessions_for_user(conn, user_id)
        append_server_log(f"registration {action} by {viewer['username']}: user {user_id}")
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "controls": registration_controls_payload(conn),
            "message": f"Registration {new_status}.",
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
        log_audit_event(
            conn,
            actor=viewer,
            action_type="media_cleanup",
            category="operations",
            target_type="media",
            reason=f"Removed {result['deletedCount']} files ({result['deletedSize']}).",
            metadata=result,
        )
        conn.commit()
        append_server_log(
            f"media cleanup by {viewer['username']}: {result['deletedCount']} files, {result['deletedSize']}"
        )
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "cleanup": result,
            "message": "Media cleanup complete.",
        }

    def api_restore_trash(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not viewer or not is_admin(viewer):
            raise APIError("You do not have permission.", HTTPStatus.FORBIDDEN)
        ensure_can_participate(viewer)
        data = self.read_json()
        item_type = str(data.get("type") or "").strip().lower()
        try:
            item_id = int(data.get("id"))
        except (TypeError, ValueError) as exc:
            raise APIError("Choose a valid item to restore.") from exc
        if item_type == "thread":
            row = conn.execute(
                "SELECT id, title FROM threads WHERE id = ? AND deleted_at IS NOT NULL",
                (item_id,),
            ).fetchone()
            if not row:
                raise APIError("That deleted thread could not be found.", HTTPStatus.NOT_FOUND)
            restore_deleted_thread(conn, item_id)
            label = row["title"]
        elif item_type == "post":
            row = conn.execute(
                """
                SELECT p.id, p.thread_id, t.deleted_at AS thread_deleted_at
                FROM posts p
                JOIN threads t ON t.id = p.thread_id
                WHERE p.id = ? AND p.deleted_at IS NOT NULL
                """,
                (item_id,),
            ).fetchone()
            if not row:
                raise APIError("That deleted post could not be found.", HTTPStatus.NOT_FOUND)
            if row["thread_deleted_at"]:
                raise APIError("Restore the parent thread before restoring this reply.")
            restore_deleted_post(conn, item_id)
            label = f"post #{item_id}"
        else:
            raise APIError("Unsupported restore type.")
        log_audit_event(
            conn,
            actor=viewer,
            action_type="trash_restore",
            category="content",
            target_type=item_type,
            target_id=item_id,
            target_label=label,
            reason=f"Restored {label}.",
        )
        conn.commit()
        append_server_log(f"trash restore by {viewer['username']}: {item_type} {item_id}")
        send_staff_discord_notice(
            title="OmniForum trash restore",
            lines=[
                f"Admin: {viewer['username']}",
                f"Restored: {label}",
                f"Type: {item_type}",
            ],
            color=0x7B5EA7,
        )
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "items": list_deleted_content(conn, limit=60),
            "message": f"Restored {label}.",
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
