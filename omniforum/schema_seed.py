"""Initial forum category and section seed data."""

from __future__ import annotations

import sqlite3

from .config import SECTION_SEEDS


def seed_sections(conn: sqlite3.Connection) -> None:
    existing = conn.execute("SELECT COUNT(*) AS count FROM sections").fetchone()["count"]
    if existing:
        return
    for category_index, category in enumerate(SECTION_SEEDS):
        cur = conn.execute(
            "INSERT INTO categories (slug, label, sort_order) VALUES (?, ?, ?)",
            (category["slug"], category["label"], category_index),
        )
        category_id = cur.lastrowid
        for section_index, section in enumerate(category["sections"]):
            conn.execute(
                """
                INSERT INTO sections (
                    category_id, slug, name, description, icon, icon_bg,
                    required_role, write_role, sort_order
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    category_id,
                    section["slug"],
                    section["name"],
                    section["description"],
                    section["icon"],
                    section["icon_bg"],
                    section["required_role"],
                    section["write_role"],
                    section_index,
                ),
            )
    conn.commit()
