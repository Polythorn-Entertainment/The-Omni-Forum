"""Default rows for singleton application tables."""

from __future__ import annotations

import json
import sqlite3

from .config import DEFAULT_SITE_SETTINGS, REPORT_MACROS
from .core import utc_iso


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
