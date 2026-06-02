"""Pagination parsing and resolution helpers."""

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
