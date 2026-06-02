from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path


class SchemaMigrationRegistryTests(unittest.TestCase):
    def test_schema_migrations_are_ordered_and_recorded_with_checksums(self) -> None:
        from omniforum.migrations import (
            SCHEMA_MIGRATIONS,
            apply_schema_migrations,
            migration_checksum,
            schema_migration_status,
            validate_schema_migrations,
        )

        validate_schema_migrations()
        self.assertEqual(
            [migration.migration_id for migration in SCHEMA_MIGRATIONS],
            sorted(migration.migration_id for migration in SCHEMA_MIGRATIONS),
        )

        with tempfile.TemporaryDirectory(prefix="omniforum-migrations-") as temp_dir:
            conn = sqlite3.connect(":memory:")
            conn.row_factory = sqlite3.Row
            conn.execute("ATTACH DATABASE ? AS audit_db", (str(Path(temp_dir) / "audit.db"),))
            conn.execute("ATTACH DATABASE ? AS users_db", (str(Path(temp_dir) / "users.db"),))
            conn.execute(
                """
                CREATE TABLE users_db.users (
                    id INTEGER PRIMARY KEY,
                    username TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL,
                    bio TEXT NOT NULL DEFAULT '',
                    xp INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

            apply_schema_migrations(conn)

            rows = conn.execute("SELECT * FROM audit_db.schema_migrations ORDER BY migration_id").fetchall()
            self.assertEqual(
                [migration.migration_id for migration in SCHEMA_MIGRATIONS], [row["migration_id"] for row in rows]
            )
            self.assertEqual(
                [migration_checksum(migration) for migration in SCHEMA_MIGRATIONS],
                [row["checksum"] for row in rows],
            )
            status = schema_migration_status(conn)
            self.assertTrue(all(item["applied"] and item["checksumOk"] for item in status))
            email_columns = {row["name"] for row in conn.execute("PRAGMA users_db.table_info(users)").fetchall()}
            self.assertIn("email", email_columns)
            self.assertTrue(conn.execute("PRAGMA users_db.table_info(email_auth_tokens)").fetchall())


if __name__ == "__main__":
    unittest.main()
