"""Profile, account, and role validation helpers."""

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


def clean_role_name(value: Any, *, field: str = "Role") -> str:
    role = str(value or "").strip()
    if role not in ROLES:
        raise APIError(f"Invalid {field.lower()}.")
    return role


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
