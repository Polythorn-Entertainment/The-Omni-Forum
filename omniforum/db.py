"""SQLite connection and runtime directory helpers."""

from __future__ import annotations

import sqlite3
from typing import Any

from .config import (
    BACKUP_DIR,
    DATA_DIR,
    DATA_FILES,
    EXPORTS_DIR,
    LOG_DIR,
    MEDIA_DIR,
    MEDIA_FOLDERS,
    TABLE_PATTERN,
    TABLE_SCHEMAS,
)


def qualify_sql(sql: str) -> str:
    return TABLE_PATTERN.sub(lambda match: TABLE_SCHEMAS[match.group(1)], sql)


class DataConnection:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    @property
    def raw(self) -> sqlite3.Connection:
        return self._connection

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        return self._connection.execute(qualify_sql(sql), params)

    def executemany(self, sql: str, params: Any) -> sqlite3.Cursor:
        return self._connection.executemany(qualify_sql(sql), params)

    def commit(self) -> None:
        self._connection.commit()

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "DataConnection":
        self._connection.__enter__()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool | None:
        return self._connection.__exit__(exc_type, exc, tb)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._connection, name)


def get_connection() -> DataConnection:
    ensure_runtime_dirs()
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    for schema, path in DATA_FILES.items():
        conn.execute(f"ATTACH DATABASE ? AS {schema}", (str(path),))
    return DataConnection(conn)


def ensure_runtime_dirs() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    MEDIA_DIR.mkdir(exist_ok=True)
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    for directory in MEDIA_FOLDERS.values():
        directory.mkdir(parents=True, exist_ok=True)
