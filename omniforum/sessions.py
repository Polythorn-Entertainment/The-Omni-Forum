"""Cookie session lookup and lifecycle helpers."""

from __future__ import annotations

import secrets
import sqlite3
from datetime import timedelta
from http.cookies import SimpleCookie
from typing import Any

from .account_state import sync_user_restrictions
from .config import SESSION_COOKIE, SESSION_DAYS
from .core import parse_iso, utc_iso, utc_now
from .text_utils import short_preview
from .validation import is_approved_user


def session_token_from_headers(headers: Any) -> str | None:
    cookie_header = headers.get("Cookie")
    if not cookie_header:
        return None
    cookie = SimpleCookie()
    cookie.load(cookie_header)
    session = cookie.get(SESSION_COOKIE)
    return session.value if session else None


def summarize_user_agent(user_agent: str | None) -> str:
    value = short_preview(user_agent or "", max_len=72)
    return value or "Unknown browser"


def recent_session_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "createdAt": row["created_at"],
        "expiresAt": row["expires_at"],
        "lastSeenAt": row["last_seen_at"] or row["created_at"],
        "ip": row["ip_address"] or row["last_seen_ip"] or "Unknown",
        "lastSeenIp": row["last_seen_ip"] or row["ip_address"] or "",
        "userAgent": summarize_user_agent(row["user_agent"]),
        "active": parse_iso(row["expires_at"]) > utc_now() if row["expires_at"] else False,
    }


def list_recent_sessions(
    conn: sqlite3.Connection,
    user_id: int,
    *,
    limit: int = 8,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT *
        FROM sessions
        WHERE user_id = ?
        ORDER BY COALESCE(last_seen_at, created_at) DESC, created_at DESC
        LIMIT ?
        """,
        (user_id, limit),
    ).fetchall()
    return [recent_session_payload(row) for row in rows]


def revoke_other_sessions(conn: sqlite3.Connection, user_id: int, keep_token: str | None) -> int:
    if keep_token:
        cur = conn.execute(
            "DELETE FROM sessions WHERE user_id = ? AND token != ?",
            (user_id, keep_token),
        )
    else:
        cur = conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    conn.commit()
    return cur.rowcount or 0


def current_user_from_request(
    conn: sqlite3.Connection,
    headers: Any,
    client_ip: str = "",
) -> dict[str, Any] | None:
    token = session_token_from_headers(headers)
    if not token:
        return None
    now_dt = utc_now()
    now = utc_iso(now_dt)
    conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
    row = conn.execute(
        """
        SELECT u.*, s.csrf_token AS session_csrf_token, s.last_seen_at AS session_last_seen_at
        FROM sessions s
        JOIN users u ON u.id = s.user_id
        WHERE s.token = ? AND s.expires_at > ?
        """,
        (token, now),
    ).fetchone()
    if not row:
        return None
    user = sync_user_restrictions(conn, row)
    if not user:
        return None
    if not is_approved_user(user):
        delete_session(conn, token)
        return None
    csrf_token = str(user.get("session_csrf_token") or "")
    if not csrf_token:
        csrf_token = secrets.token_urlsafe(32)
        user["session_csrf_token"] = csrf_token
    session_seen_at = parse_iso(user.get("session_last_seen_at"))
    had_csrf_token = bool(row["session_csrf_token"])
    should_touch_session = (not session_seen_at) or session_seen_at < (now_dt - timedelta(seconds=45)) or not had_csrf_token
    if should_touch_session:
        conn.execute(
            "UPDATE users SET last_seen_at = ?, updated_at = ? WHERE id = ?",
            (now, now, user["id"]),
        )
        conn.execute(
            """
            UPDATE sessions
            SET last_seen_at = ?, last_seen_ip = ?, csrf_token = ?
            WHERE token = ?
            """,
            (now, client_ip or "", csrf_token, token),
        )
        conn.commit()
        user["last_seen_at"] = now
        user["updated_at"] = now
    return user


def create_session(
    conn: sqlite3.Connection,
    user_id: int,
    *,
    ip_address: str = "",
    user_agent: str = "",
) -> tuple[str, str, str]:
    token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    created_at = utc_iso()
    expires_at = utc_iso(utc_now() + timedelta(days=SESSION_DAYS))
    conn.execute(
        """
        INSERT INTO sessions (
            token, user_id, csrf_token, created_at, expires_at,
            ip_address, user_agent, last_seen_at, last_seen_ip
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            token,
            user_id,
            csrf_token,
            created_at,
            expires_at,
            ip_address or "",
            user_agent or "",
            created_at,
            ip_address or "",
        ),
    )
    conn.commit()
    return token, expires_at, csrf_token


def delete_session(conn: sqlite3.Connection, token: str | None) -> None:
    if not token:
        return
    conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
    conn.commit()


def delete_sessions_for_user(conn: sqlite3.Connection, user_id: int) -> None:
    conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    conn.commit()
