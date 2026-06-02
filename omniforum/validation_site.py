"""Site setting validation and serialization helpers."""

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


def site_setting_value(row: sqlite3.Row | None, key: str) -> Any:
    if not row:
        return DEFAULT_SITE_SETTINGS[key]
    try:
        return json.loads(row["value_json"])
    except (json.JSONDecodeError, TypeError):
        return DEFAULT_SITE_SETTINGS[key]


def get_site_settings(conn: sqlite3.Connection) -> dict[str, Any]:
    ensure_site_settings_defaults(conn)
    rows = {row["key"]: row for row in conn.execute("SELECT * FROM site_settings").fetchall()}
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
    output = {key: bool((current or defaults).get(key, defaults[key])) for key in defaults}
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


def clean_site_theme(value: Any) -> str:
    theme = str(value or "midnight").strip().lower()
    if theme not in SITE_THEME_OPTIONS:
        raise APIError("Choose one of the supported site themes.")
    return theme
