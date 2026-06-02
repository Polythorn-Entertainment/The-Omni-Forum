"""Core time, role, password, and recovery-code helpers."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import sqlite3
from datetime import datetime, timezone
from typing import Any

from .config import PBKDF2_ROUNDS, ROLE_LEVELS


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_iso(value: datetime | None = None) -> str:
    if value is None:
        value = utc_now()
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def role_level(role: str | None) -> int:
    return ROLE_LEVELS.get(role or "new", 0)


def guest_can_view(required_role: str) -> bool:
    return role_level(required_role) <= role_level("new")


def has_required_role(user: dict[str, Any] | None, required_role: str) -> bool:
    if user is None:
        return guest_can_view(required_role)
    return role_level(user["role"]) >= role_level(required_role)


def is_staff(user: dict[str, Any] | None) -> bool:
    return role_level(user["role"]) >= role_level("mod") if user else False


def is_admin(user: dict[str, Any] | None) -> bool:
    return role_level(user["role"]) >= role_level("admin") if user else False


def can_manage_user(actor: dict[str, Any] | None, target_role: str) -> bool:
    if not actor:
        return False
    if actor["role"] == "owner":
        return True
    if actor["role"] == "admin":
        return role_level(target_role) <= role_level("mod")
    return False


def can_moderate_user(
    actor: dict[str, Any] | None,
    target: sqlite3.Row | dict[str, Any] | None,
) -> bool:
    if not actor or not target or not is_staff(actor):
        return False
    target_row = dict(target)
    if actor["id"] == target_row["id"]:
        return False
    return role_level(actor["role"]) > role_level(target_row["role"])


def make_password_hash(password: str, salt_hex: str | None = None) -> str:
    salt_hex = salt_hex or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt_hex),
        PBKDF2_ROUNDS,
    )
    return f"{salt_hex}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt_hex, digest_hex = stored_hash.split("$", 1)
    except ValueError:
        return False
    candidate = make_password_hash(password, salt_hex)
    return hmac.compare_digest(candidate, stored_hash)


def normalize_recovery_code(value: Any) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", str(value or "")).upper()


def generate_recovery_code_plain() -> str:
    raw = secrets.token_hex(6).upper()
    return "-".join(raw[index:index + 4] for index in range(0, len(raw), 4))


def recovery_code_summary(conn: sqlite3.Connection, user_id: int) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN used_at IS NULL THEN 1 ELSE 0 END) AS active,
            MAX(created_at) AS latest_created_at,
            MAX(used_at) AS latest_used_at
        FROM recovery_codes
        WHERE user_id = ?
        """,
        (user_id,),
    ).fetchone()
    return {
        "total": int(row["total"] or 0) if row else 0,
        "active": int(row["active"] or 0) if row else 0,
        "latestCreatedAt": row["latest_created_at"] if row else "",
        "latestUsedAt": row["latest_used_at"] if row else "",
    }


def create_recovery_codes(conn: sqlite3.Connection, user_id: int, *, count: int = 8) -> list[str]:
    now = utc_iso()
    conn.execute("DELETE FROM recovery_codes WHERE user_id = ? AND used_at IS NULL", (user_id,))
    codes: list[str] = []
    for index in range(count):
        code = generate_recovery_code_plain()
        codes.append(code)
        conn.execute(
            """
            INSERT INTO recovery_codes (user_id, code_hash, label, used_at, created_at)
            VALUES (?, ?, ?, NULL, ?)
            """,
            (user_id, make_password_hash(normalize_recovery_code(code)), f"Recovery code {index + 1}", now),
        )
    return codes


def consume_recovery_code(conn: sqlite3.Connection, user_id: int, code: Any) -> bool:
    normalized = normalize_recovery_code(code)
    if len(normalized) < 8 or len(normalized) > 32:
        return False
    rows = conn.execute(
        """
        SELECT id, code_hash
        FROM recovery_codes
        WHERE user_id = ? AND used_at IS NULL
        ORDER BY created_at DESC, id DESC
        LIMIT 40
        """,
        (user_id,),
    ).fetchall()
    for row in rows:
        if verify_password(normalized, row["code_hash"]):
            conn.execute("UPDATE recovery_codes SET used_at = ? WHERE id = ?", (utc_iso(), row["id"]))
            return True
    return False


def human_size(value: int) -> str:
    size = float(max(0, value))
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(size)}{unit}"
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


def human_duration(seconds: int | float) -> str:
    remaining = max(0, int(seconds or 0))
    if remaining < 60:
        return f"{remaining}s"
    minutes = remaining // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    if hours < 48:
        return f"{hours}h"
    days = hours // 24
    return f"{days}d"
