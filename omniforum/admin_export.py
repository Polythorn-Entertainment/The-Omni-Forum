"""Admin export and import-preview helpers."""

from __future__ import annotations

import csv
import json
import sqlite3
from http import HTTPStatus
from io import StringIO
from typing import Any

from .config import ADMIN_EXPORT_FORMATS, ADMIN_EXPORT_TYPES
from .core import utc_iso, utc_now
from .errors import APIError
from .validation import (
    get_registration_settings,
    get_site_settings,
    serialize_registration_settings,
    serialize_site_settings,
)


def records_to_csv(records: list[dict[str, Any]]) -> str:
    if not records:
        return ""
    columns: list[str] = []
    for record in records:
        for key in record:
            if key not in columns:
                columns.append(key)
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for record in records:
        writer.writerow({
            key: json.dumps(value, ensure_ascii=True) if isinstance(value, (dict, list)) else value
            for key, value in record.items()
        })
    return buffer.getvalue()


def admin_export_records(conn: sqlite3.Connection, export_type: str) -> list[dict[str, Any]] | dict[str, Any]:
    if export_type == "users":
        rows = conn.execute(
            """
            SELECT id, username, role, bio, xp, created_at, updated_at, last_seen_at,
                   approval_status, recovery_discord_username
            FROM users
            ORDER BY id ASC
            """
        ).fetchall()
        return [dict(row) for row in rows]
    if export_type == "threads":
        rows = conn.execute(
            """
            SELECT t.id, t.title, t.prefix, t.tags_json, t.created_at, t.updated_at,
                   t.pinned, t.locked, t.solved, t.featured, t.deleted_at,
                   s.slug AS section_slug, s.name AS section_name,
                   u.username AS author_username
            FROM threads t
            JOIN sections s ON s.id = t.section_id
            JOIN users u ON u.id = t.author_id
            ORDER BY t.id ASC
            """
        ).fetchall()
        return [dict(row) for row in rows]
    if export_type == "posts":
        rows = conn.execute(
            """
            SELECT p.id, p.thread_id, t.title AS thread_title, p.author_id,
                   u.username AS author_username, p.content, p.media_sensitive,
                   p.created_at, p.updated_at, p.edited_at, p.deleted_at
            FROM posts p
            JOIN threads t ON t.id = p.thread_id
            JOIN users u ON u.id = p.author_id
            ORDER BY p.id ASC
            """
        ).fetchall()
        return [dict(row) for row in rows]
    if export_type == "reports":
        rows = conn.execute(
            """
            SELECT r.*, reporter.username AS reporter_username,
                   handler.username AS handled_by_username,
                   assigned.username AS assigned_to_username
            FROM reports r
            JOIN users reporter ON reporter.id = r.reporter_id
            LEFT JOIN users handler ON handler.id = r.handled_by
            LEFT JOIN users assigned ON assigned.id = r.assigned_to
            ORDER BY r.id ASC
            """
        ).fetchall()
        return [dict(row) for row in rows]
    if export_type == "moderation":
        rows = conn.execute(
            """
            SELECT ma.*, target.username AS target_username, actor.username AS actor_username
            FROM moderation_actions ma
            JOIN users target ON target.id = ma.user_id
            JOIN users actor ON actor.id = ma.actor_id
            ORDER BY ma.id ASC
            """
        ).fetchall()
        return [dict(row) for row in rows]
    if export_type == "settings":
        site = serialize_site_settings(get_site_settings(conn))
        registration = serialize_registration_settings(get_registration_settings(conn))
        sections = [
            dict(row)
            for row in conn.execute(
                """
                SELECT c.slug AS category_slug, c.label AS category_label,
                       s.slug, s.name, s.description, s.required_role, s.write_role,
                       s.thread_prefixes_json, s.thread_template, s.thread_state_mode, s.sort_order
                FROM sections s
                JOIN categories c ON c.id = s.category_id
                ORDER BY c.sort_order ASC, s.sort_order ASC, s.id ASC
                """
            ).fetchall()
        ]
        return {"site": site, "registration": registration, "sections": sections}
    if export_type == "all":
        return {
            key: admin_export_records(conn, key)
            for key in ("users", "threads", "posts", "reports", "moderation", "settings")
        }
    raise APIError("Choose a valid export type.", HTTPStatus.BAD_REQUEST)


def build_admin_export(
    conn: sqlite3.Connection,
    *,
    export_type: str,
    export_format: str,
) -> dict[str, Any]:
    if export_type not in ADMIN_EXPORT_TYPES:
        raise APIError("Choose a valid export type.", HTTPStatus.BAD_REQUEST)
    if export_format not in ADMIN_EXPORT_FORMATS:
        raise APIError("Choose JSON or CSV.", HTTPStatus.BAD_REQUEST)
    data = admin_export_records(conn, export_type)
    timestamp = utc_now().strftime("%Y%m%d-%H%M%S")
    if export_format == "csv":
        if isinstance(data, dict):
            if export_type == "settings":
                records = [
                    {"scope": "site", "key": key, "value": json.dumps(value, ensure_ascii=True) if isinstance(value, (dict, list)) else value}
                    for key, value in data["site"].items()
                ] + [
                    {"scope": "registration", "key": key, "value": value}
                    for key, value in data["registration"].items()
                ]
            else:
                raise APIError("CSV export is available for one data type at a time.", HTTPStatus.BAD_REQUEST)
        else:
            records = data
        content = records_to_csv(records)
        extension = "csv"
        content_type = "text/csv; charset=utf-8"
    else:
        content = json.dumps(
            {"exportedAt": utc_iso(), "type": export_type, "data": data},
            indent=2,
            ensure_ascii=True,
            sort_keys=True,
        )
        extension = "json"
        content_type = "application/json; charset=utf-8"
    return {
        "filename": f"omniforum-{export_type}-{timestamp}.{extension}",
        "contentType": content_type,
        "format": export_format,
        "type": export_type,
        "content": content,
        "rowCount": len(data) if isinstance(data, list) else len(data.keys()),
    }


def build_import_preview(raw_content: Any) -> dict[str, Any]:
    raw = str(raw_content or "").strip()
    if not raw:
        raise APIError("Paste JSON content to preview.")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise APIError("Import preview only accepts valid JSON for now.") from exc
    data = parsed.get("data") if isinstance(parsed, dict) and "data" in parsed else parsed
    counts: dict[str, int] = {}
    warnings: list[str] = []
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, list):
                counts[key] = len(value)
            elif isinstance(value, dict):
                counts[key] = len(value)
        if not counts:
            warnings.append("No obvious importable collections were found.")
    elif isinstance(data, list):
        counts["items"] = len(data)
    else:
        warnings.append("The JSON root is not a list or object.")
    warnings.append("Preview only: no live data was changed.")
    return {
        "valid": True,
        "counts": counts,
        "warnings": warnings,
        "detectedType": parsed.get("type", "unknown") if isinstance(parsed, dict) else "list",
        "previewedAt": utc_iso(),
    }
