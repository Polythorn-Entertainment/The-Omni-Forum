"""Migration helpers for legacy and future schema upgrades."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from hashlib import sha256
from typing import Callable

from .config import LEGACY_DB_PATH
from .core import utc_iso
from .db import DataConnection


@dataclass(frozen=True)
class SchemaMigration:
    migration_id: str
    description: str
    apply: Callable[[sqlite3.Connection], None]


def noop_migration(conn: sqlite3.Connection) -> None:
    return None


def ensure_column(
    conn: sqlite3.Connection,
    schema: str,
    table: str,
    column_name: str,
    definition: str,
) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA {schema}.table_info({table})").fetchall()}
    if column_name not in columns:
        conn.execute(f"ALTER TABLE {schema}.{table} ADD COLUMN {column_name} {definition}")


def migrate_email_auth_opt_in(conn: sqlite3.Connection) -> None:
    ensure_column(conn, "users_db", "users", "email", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "users_db", "users", "email_verified_at", "TEXT")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users_db.email_auth_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            purpose TEXT NOT NULL,
            email TEXT NOT NULL DEFAULT '',
            token_hash TEXT NOT NULL,
            used_at TEXT,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS users_db.idx_email_auth_tokens_lookup
        ON email_auth_tokens(purpose, used_at, created_at DESC)
        """
    )


SCHEMA_MIGRATIONS: tuple[SchemaMigration, ...] = (
    SchemaMigration(
        "20260503_0001_baseline",
        "Baseline schema managed by split schema and migration modules.",
        noop_migration,
    ),
    SchemaMigration(
        "20260509_0002_email_auth_opt_in",
        "Add optional account email and email password-reset token storage.",
        migrate_email_auth_opt_in,
    ),
)


def migration_checksum(migration: SchemaMigration) -> str:
    payload = (
        f"{migration.migration_id}\n{migration.description}\n{migration.apply.__module__}.{migration.apply.__name__}"
    )
    return sha256(payload.encode("utf-8")).hexdigest()


def validate_schema_migrations(migrations: Iterable[SchemaMigration] = SCHEMA_MIGRATIONS) -> None:
    migration_list = list(migrations)
    ids = [migration.migration_id for migration in migration_list]
    if ids != sorted(ids):
        raise RuntimeError("Schema migrations must be sorted by migration id.")
    if len(ids) != len(set(ids)):
        raise RuntimeError("Schema migration ids must be unique.")


def ensure_schema_migration_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_db.schema_migrations (
            migration_id TEXT PRIMARY KEY,
            description TEXT NOT NULL DEFAULT '',
            checksum TEXT NOT NULL DEFAULT '',
            applied_at TEXT NOT NULL
        )
        """
    )
    columns = {row["name"] for row in conn.execute("PRAGMA audit_db.table_info(schema_migrations)").fetchall()}
    if "checksum" not in columns:
        conn.execute("ALTER TABLE audit_db.schema_migrations ADD COLUMN checksum TEXT NOT NULL DEFAULT ''")


def applied_schema_migrations(conn: sqlite3.Connection) -> dict[str, sqlite3.Row]:
    ensure_schema_migration_table(conn)
    return {
        str(row["migration_id"]): row for row in conn.execute("SELECT * FROM audit_db.schema_migrations").fetchall()
    }


def apply_schema_migrations(conn: sqlite3.Connection) -> None:
    validate_schema_migrations()
    ensure_schema_migration_table(conn)
    applied = applied_schema_migrations(conn)
    for migration in SCHEMA_MIGRATIONS:
        checksum = migration_checksum(migration)
        applied_row = applied.get(migration.migration_id)
        if applied_row:
            recorded_checksum = str(applied_row["checksum"] or "")
            if recorded_checksum and recorded_checksum != checksum:
                raise RuntimeError(f"Schema migration checksum changed: {migration.migration_id}")
            continue
        migration.apply(conn)
        conn.execute(
            """
            INSERT INTO audit_db.schema_migrations (migration_id, description, checksum, applied_at)
            VALUES (?, ?, ?, ?)
            """,
            (migration.migration_id, migration.description, checksum, utc_iso()),
        )
        applied[migration.migration_id] = conn.execute(
            "SELECT * FROM audit_db.schema_migrations WHERE migration_id = ?",
            (migration.migration_id,),
        ).fetchone()


def schema_migration_status(conn: sqlite3.Connection) -> list[dict[str, str | bool]]:
    applied = applied_schema_migrations(conn)
    output: list[dict[str, str | bool]] = []
    for migration in SCHEMA_MIGRATIONS:
        row = applied.get(migration.migration_id)
        checksum = migration_checksum(migration)
        recorded_checksum = str(row["checksum"] or "") if row else ""
        output.append(
            {
                "id": migration.migration_id,
                "description": migration.description,
                "applied": bool(row),
                "appliedAt": str(row["applied_at"] or "") if row else "",
                "checksum": checksum,
                "checksumOk": (not row) or (not recorded_checksum) or recorded_checksum == checksum,
            }
        )
    return output


def maybe_migrate_legacy_db(conn: DataConnection) -> None:
    if not LEGACY_DB_PATH.exists():
        return

    counts = {
        "users": conn.execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"],
        "threads": conn.execute("SELECT COUNT(*) AS count FROM threads").fetchone()["count"],
        "posts": conn.execute("SELECT COUNT(*) AS count FROM posts").fetchone()["count"],
        "sessions": conn.execute("SELECT COUNT(*) AS count FROM sessions").fetchone()["count"],
        "contacts": conn.execute("SELECT COUNT(*) AS count FROM contact_submissions").fetchone()["count"],
    }
    if any(counts.values()):
        return

    raw = conn.raw
    raw.execute("ATTACH DATABASE ? AS legacy_db", (str(LEGACY_DB_PATH),))
    try:
        legacy_tables = {
            row["name"]
            for row in raw.execute("SELECT name FROM legacy_db.sqlite_master WHERE type = 'table'").fetchall()
        }
        required_tables = {"users", "categories", "sections", "threads", "posts"}
        if not required_tables.issubset(legacy_tables):
            return

        raw.execute("DELETE FROM sections_db.sections")
        raw.execute("DELETE FROM sections_db.categories")

        raw.execute(
            """
            INSERT INTO users_db.users (
                id, username, password_hash, role, bio, xp, created_at, updated_at, last_seen_at
            )
            SELECT
                id, username, password_hash, role, bio, xp, created_at, updated_at, last_seen_at
            FROM legacy_db.users
            """
        )
        if "sessions" in legacy_tables:
            raw.execute("INSERT INTO sessions_db.sessions SELECT * FROM legacy_db.sessions")
        raw.execute("INSERT INTO sections_db.categories SELECT * FROM legacy_db.categories")
        raw.execute("INSERT INTO sections_db.sections SELECT * FROM legacy_db.sections")
        raw.execute("INSERT INTO threads_db.threads SELECT * FROM legacy_db.threads")
        raw.execute("INSERT INTO posts_db.posts SELECT * FROM legacy_db.posts")
        if "post_likes" in legacy_tables:
            raw.execute("INSERT INTO posts_db.post_likes SELECT * FROM legacy_db.post_likes")
        if "contact_submissions" in legacy_tables:
            raw.execute(
                """
                INSERT INTO contact_db.contact_submissions (
                    id, user_id, name, email, discord_username, subject, message,
                    status, admin_note, handled_by, created_at, updated_at, handled_at
                )
                SELECT
                    id, user_id, name, COALESCE(email, ''), '', subject, message,
                    status, admin_note, handled_by, created_at, updated_at, handled_at
                FROM legacy_db.contact_submissions
                """
            )
        raw.commit()
    finally:
        raw.execute("DETACH DATABASE legacy_db")
