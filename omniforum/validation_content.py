"""Content, moderation, thread, poll, and ID validation helpers."""

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
