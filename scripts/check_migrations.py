#!/usr/bin/env python3
"""Validate the schema migration registry without touching runtime data."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from omniforum.migrations import SCHEMA_MIGRATIONS, migration_checksum, validate_schema_migrations


def main() -> int:
    validate_schema_migrations()
    for migration in SCHEMA_MIGRATIONS:
        print(f"{migration.migration_id} {migration_checksum(migration)} {migration.description}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
