#!/usr/bin/env python3
"""Show applied OmniForum schema migrations for a runtime data directory."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from omniforum.migrations import SCHEMA_MIGRATIONS, migration_checksum, validate_schema_migrations


def load_applied(audit_db: Path) -> dict[str, sqlite3.Row]:
    if not audit_db.exists():
        return {}
    conn = sqlite3.connect(":memory:", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("ATTACH DATABASE ? AS audit_db", (f"file:{audit_db.resolve()}?mode=ro",))
        table = conn.execute(
            "SELECT name FROM audit_db.sqlite_master WHERE type = 'table' AND name = 'schema_migrations'"
        ).fetchone()
        if not table:
            return {}
        rows = conn.execute("SELECT * FROM audit_db.schema_migrations").fetchall()
        return {str(row["migration_id"]): row for row in rows}
    finally:
        conn.close()


def migration_rows(data_dir: Path) -> list[dict[str, Any]]:
    validate_schema_migrations()
    applied = load_applied(data_dir / "audit.db")
    rows = []
    for migration in SCHEMA_MIGRATIONS:
        row = applied.get(migration.migration_id)
        checksum = migration_checksum(migration)
        recorded_checksum = str(row["checksum"] or "") if row else ""
        rows.append(
            {
                "id": migration.migration_id,
                "description": migration.description,
                "applied": bool(row),
                "appliedAt": str(row["applied_at"]) if row else "",
                "checksum": checksum,
                "recordedChecksum": recorded_checksum,
                "checksumOk": (not row) or (not recorded_checksum) or recorded_checksum == checksum,
            }
        )
    return rows


def render_text(rows: list[dict[str, Any]]) -> str:
    lines = ["OmniForum schema migrations:"]
    for row in rows:
        state = "applied" if row["applied"] else "pending"
        checksum = "checksum ok" if row["checksumOk"] else "checksum changed"
        lines.append(f"- {state}: {row['id']} - {checksum} - {row['description']}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--allow-pending", action="store_true", help="Exit 0 even when migrations are pending")
    args = parser.parse_args()

    rows = migration_rows(args.data_dir)
    all_applied = all(row["applied"] for row in rows)
    checksums_ok = all(row["checksumOk"] for row in rows)
    result = {
        "ok": checksums_ok and (all_applied or args.allow_pending),
        "dataDir": str(args.data_dir.resolve()),
        "allApplied": all_applied,
        "checksumsOk": checksums_ok,
        "migrations": rows,
    }
    print(json.dumps(result, indent=2) if args.json else render_text(rows))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
