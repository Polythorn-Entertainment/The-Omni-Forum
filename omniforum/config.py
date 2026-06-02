"""Configuration constants for OmniForum.

This module intentionally contains no application startup side effects.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
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
ACCESS_LOG_FILE = LOG_DIR / "access.log"
APP_LOG_FILE = LOG_DIR / "app.jsonl"
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
MEDIA_SCAN_COMMAND = str(os.getenv("OMNIFORUM_MEDIA_SCAN_COMMAND") or "").strip()
MEDIA_SCAN_REQUIRED = os.getenv("OMNIFORUM_MEDIA_SCAN_REQUIRED", "0") == "1"
MEDIA_SCAN_TIMEOUT_SECONDS = max(1, int(os.getenv("OMNIFORUM_MEDIA_SCAN_TIMEOUT_SECONDS", "20")))
DISCORD_WEBHOOK_URL = str(os.getenv("OMNIFORUM_DISCORD_WEBHOOK_URL") or "").strip()
EMAIL_AUTH_ENABLED = os.getenv("OMNIFORUM_EMAIL_AUTH_ENABLED", "0") == "1"
EMAIL_FROM = str(os.getenv("OMNIFORUM_EMAIL_FROM") or "").strip()
SMTP_HOST = str(os.getenv("OMNIFORUM_SMTP_HOST") or "").strip()
SMTP_PORT = int(os.getenv("OMNIFORUM_SMTP_PORT", "587"))
SMTP_USERNAME = str(os.getenv("OMNIFORUM_SMTP_USERNAME") or "").strip()
SMTP_PASSWORD = str(os.getenv("OMNIFORUM_SMTP_PASSWORD") or "").strip()
SMTP_STARTTLS = os.getenv("OMNIFORUM_SMTP_STARTTLS", "1") == "1"
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
    "email_auth": (5, 900, "email account requests"),
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

TABLE_SCHEMAS = {
    "users": "users_db.users",
    "moderation_actions": "users_db.moderation_actions",
    "registration_settings": "users_db.registration_settings",
    "invite_codes": "users_db.invite_codes",
    "site_settings": "users_db.site_settings",
    "recovery_codes": "users_db.recovery_codes",
    "email_auth_tokens": "users_db.email_auth_tokens",
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
    "rate_limit_events": "audit_db.rate_limit_events",
    "search_fts": "posts_db.search_fts",
    "search_index_meta": "posts_db.search_index_meta",
}
TABLE_PATTERN = re.compile(r"(?<!\.)\b(" + "|".join(sorted(TABLE_SCHEMAS, key=len, reverse=True)) + r")\b")
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
        "icon": "\U0001f451",
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
        "icon": "\U0001f6e1\ufe0f",
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
        "icon": "\U0001f48e",
        "level": 1,
        "color": "#6b7a94",
        "cssClass": "member",
    },
    "new": {
        "label": "New",
        "icon": "\U0001f331",
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
        "label": "\U0001f4e2 Official",
        "sections": [
            {
                "slug": "s-announcements",
                "name": "Announcements",
                "description": "Official news, updates, and announcements from staff",
                "icon": "\U0001f4e3",
                "icon_bg": "rgba(255,107,107,0.15)",
                "required_role": "new",
                "write_role": "admin",
            },
            {
                "slug": "s-rules",
                "name": "Rules & Guidelines",
                "description": "Community rules, conduct guidelines, and policies",
                "icon": "\U0001f4dc",
                "icon_bg": "rgba(255,209,102,0.15)",
                "required_role": "new",
                "write_role": "admin",
            },
        ],
    },
    {
        "slug": "cat-general",
        "label": "\U0001f4ac General",
        "sections": [
            {
                "slug": "s-general",
                "name": "General Discussion",
                "description": "Talk about anything and everything here",
                "icon": "\U0001f4ac",
                "icon_bg": "rgba(0,212,255,0.1)",
                "required_role": "new",
                "write_role": "new",
            },
            {
                "slug": "s-introductions",
                "name": "Introductions",
                "description": "New here? Say hello and introduce yourself",
                "icon": "\U0001f44b",
                "icon_bg": "rgba(6,214,160,0.1)",
                "required_role": "new",
                "write_role": "new",
            },
            {
                "slug": "s-lounge",
                "name": "Member Lounge",
                "description": "Exclusive lounge for members and above",
                "icon": "\U0001f378",
                "icon_bg": "rgba(123,94,167,0.15)",
                "required_role": "member",
                "write_role": "member",
            },
            {
                "slug": "s-veterans",
                "name": "Veterans Den",
                "description": "A private space for veteran members and staff",
                "icon": "\U0001f3db\ufe0f",
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
                "icon": "\U0001f4bb",
                "icon_bg": "rgba(0,212,255,0.12)",
                "required_role": "new",
                "write_role": "new",
            },
            {
                "slug": "s-gaming",
                "name": "Gaming",
                "description": "Video games, reviews, recommendations, and gaming culture",
                "icon": "\U0001f3ae",
                "icon_bg": "rgba(123,94,167,0.12)",
                "required_role": "new",
                "write_role": "new",
            },
            {
                "slug": "s-ai",
                "name": "AI & Machine Learning",
                "description": "Artificial intelligence, ML models, tools, ethics, and the future",
                "icon": "\U0001f916",
                "icon_bg": "rgba(255,107,107,0.1)",
                "required_role": "new",
                "write_role": "new",
            },
            {
                "slug": "s-security",
                "name": "Cybersecurity",
                "description": "InfoSec, CTFs, vulnerability research, and best practices",
                "icon": "\U0001f510",
                "icon_bg": "rgba(255,107,107,0.12)",
                "required_role": "new",
                "write_role": "new",
            },
        ],
    },
    {
        "slug": "cat-creative",
        "label": "\U0001f3a8 Creative",
        "sections": [
            {
                "slug": "s-music",
                "name": "Music",
                "description": "Discover and share music, discuss artists, genres, and production",
                "icon": "\U0001f3b5",
                "icon_bg": "rgba(123,94,167,0.12)",
                "required_role": "new",
                "write_role": "new",
            },
            {
                "slug": "s-art-design",
                "name": "Art & Design",
                "description": "Visual art, UI/UX design, photography, and digital creation",
                "icon": "\U0001f58c\ufe0f",
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
        "label": "\U0001f30d Lifestyle",
        "sections": [
            {
                "slug": "s-health",
                "name": "Health & Fitness",
                "description": "Wellness, fitness routines, nutrition, and mental health",
                "icon": "\U0001f4aa",
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
                "icon": "\U0001f4c8",
                "icon_bg": "rgba(255,209,102,0.1)",
                "required_role": "new",
                "write_role": "new",
            },
        ],
    },
    {
        "slug": "cat-staff",
        "label": "\U0001f512 Staff Only",
        "sections": [
            {
                "slug": "s-staff-room",
                "name": "Staff Room",
                "description": "Private area for moderators and administrators",
                "icon": "\U0001f512",
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
