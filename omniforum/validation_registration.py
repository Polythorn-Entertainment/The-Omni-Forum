"""Registration, invite, and approval validation helpers."""

from __future__ import annotations

import fnmatch
import json
import math
import re
import secrets
import sqlite3
from http import HTTPStatus
from typing import Any

from .config import (
    ALLOWED_PROFILE_ACCENTS,
    ALLOWED_REACTIONS,
    DEFAULT_SITE_SETTINGS,
    DM_PRIVACY_OPTIONS,
    MAX_PAGE_SIZE,
    REGISTRATION_APPROVAL_STATUSES,
    REPORT_CATEGORIES,
    REPORT_PRIORITIES,
    ROLES,
    SITE_THEME_OPTIONS,
    THREAD_STATE_OPTIONS,
    URL_PATTERN,
)
from .core import parse_iso, utc_iso, utc_now
from .errors import APIError
from .schema import ensure_registration_defaults, ensure_site_settings_defaults
from .validation_text import clean_text


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
    return (
        dict(row)
        if row
        else {
            "id": 1,
            "public_registration_enabled": 1,
            "invite_required": 0,
            "approval_required": 0,
            "blocked_username_patterns": "",
            "updated_by": None,
            "updated_at": utc_iso(),
        }
    )


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
    return [line.strip().lower() for line in raw.splitlines() if line.strip() and not line.strip().startswith("#")]


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
        conn.execute("SELECT COUNT(*) AS count FROM users WHERE approval_status = 'pending'").fetchone()["count"]
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
