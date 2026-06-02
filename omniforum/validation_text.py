"""Shared text and slug validation helpers."""

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


def clean_text(value: Any, *, min_len: int = 0, max_len: int = 10000, field: str = "Value") -> str:
    text = str(value or "").strip()
    if len(text) < min_len:
        raise APIError(f"{field} is too short.")
    if len(text) > max_len:
        raise APIError(f"{field} is too long.")
    return text


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
