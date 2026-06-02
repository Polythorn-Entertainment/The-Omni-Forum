"""Site settings update helpers."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from .audit import log_audit_event
from .core import utc_iso
from .validation import (
    clean_optional_url,
    clean_site_theme,
    clean_text,
    get_site_settings,
    normalize_feature_toggles,
    normalize_footer_links,
    serialize_site_settings,
)


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
