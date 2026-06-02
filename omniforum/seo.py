"""Public robots.txt and sitemap helpers."""

from __future__ import annotations

import sqlite3
from typing import Any

from .config import PUBLIC_URL


def public_forum_urls(conn: sqlite3.Connection) -> dict[str, list[dict[str, Any]]]:
    sections = conn.execute(
        """
        SELECT slug, name, updated_at
        FROM (
            SELECT s.slug AS slug, s.name AS name, MAX(t.updated_at) AS updated_at
            FROM sections s
            LEFT JOIN threads t ON t.section_id = s.id AND t.deleted_at IS NULL AND COALESCE(t.shadow_hidden, 0) = 0
            WHERE s.required_role = 'new'
            GROUP BY s.id, s.slug, s.name
        )
        ORDER BY name COLLATE NOCASE ASC
        """
    ).fetchall()
    threads = conn.execute(
        """
        SELECT t.id, t.title, t.updated_at, s.slug AS section_slug
        FROM threads t
        JOIN sections s ON s.id = t.section_id
        WHERE s.required_role = 'new'
          AND t.deleted_at IS NULL
          AND COALESCE(t.shadow_hidden, 0) = 0
        ORDER BY t.updated_at DESC, t.id DESC
        LIMIT 500
        """
    ).fetchall()
    return {
        "sections": [dict(row) for row in sections],
        "threads": [dict(row) for row in threads],
    }


def xml_escape(value: str) -> str:
    return (
        str(value or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def render_robots_txt() -> str:
    return "\n".join(
        [
            "User-agent: *",
            "Allow: /",
            "Disallow: /api/",
            "Disallow: /data/",
            "Disallow: /exports/",
            "Disallow: /pages/settings.html",
            f"Sitemap: {PUBLIC_URL}/sitemap.xml",
            "",
        ]
    )


def render_sitemap_xml(conn: sqlite3.Connection) -> str:
    public_urls = public_forum_urls(conn)
    static_urls = [
        {"loc": f"{PUBLIC_URL}/", "changefreq": "hourly", "priority": "1.0"},
        {"loc": f"{PUBLIC_URL}/pages/members.html", "changefreq": "daily", "priority": "0.7"},
        {"loc": f"{PUBLIC_URL}/pages/leaderboard.html", "changefreq": "daily", "priority": "0.7"},
        {"loc": f"{PUBLIC_URL}/pages/rules.html", "changefreq": "monthly", "priority": "0.4"},
        {"loc": f"{PUBLIC_URL}/pages/privacy.html", "changefreq": "monthly", "priority": "0.4"},
        {"loc": f"{PUBLIC_URL}/pages/contact.html", "changefreq": "monthly", "priority": "0.4"},
    ]
    entries = list(static_urls)
    for section in public_urls["sections"]:
        entries.append(
            {
                "loc": f"{PUBLIC_URL}/pages/section.html?section={section['slug']}",
                "lastmod": section.get("updated_at"),
                "changefreq": "daily",
                "priority": "0.8",
            }
        )
    for thread in public_urls["threads"]:
        entries.append(
            {
                "loc": f"{PUBLIC_URL}/pages/thread.html?thread={thread['id']}",
                "lastmod": thread.get("updated_at"),
                "changefreq": "daily",
                "priority": "0.7",
            }
        )
    parts = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for item in entries:
        parts.append("  <url>")
        parts.append(f"    <loc>{xml_escape(item['loc'])}</loc>")
        if item.get("lastmod"):
            parts.append(f"    <lastmod>{xml_escape(str(item['lastmod']))}</lastmod>")
        if item.get("changefreq"):
            parts.append(f"    <changefreq>{xml_escape(item['changefreq'])}</changefreq>")
        if item.get("priority"):
            parts.append(f"    <priority>{xml_escape(item['priority'])}</priority>")
        parts.append("  </url>")
    parts.append("</urlset>")
    return "\n".join(parts)
