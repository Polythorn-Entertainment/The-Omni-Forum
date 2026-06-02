"""Abuse-limit helper calculations."""

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


def count_links(text: str) -> int:
    return len(URL_PATTERN.findall(str(text or "")))


def user_account_age_days(row: sqlite3.Row | dict[str, Any] | None) -> int:
    if not row:
        return 0
    created_at = parse_iso(dict(row).get("created_at"))
    if not created_at:
        return 0
    return max(0, int((utc_now() - created_at).total_seconds() // 86400))
