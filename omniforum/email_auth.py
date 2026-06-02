"""Opt-in email authentication and password reset helpers."""

from __future__ import annotations

import secrets
import smtplib
import sqlite3
from datetime import timedelta
from email.message import EmailMessage
from typing import Any

from .config import (
    EMAIL_AUTH_ENABLED,
    EMAIL_FROM,
    PUBLIC_URL,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_STARTTLS,
    SMTP_USERNAME,
)
from .core import make_password_hash, parse_iso, utc_iso, utc_now, verify_password
from .errors import APIError
from .runtime_logging import append_structured_log

EMAIL_TOKEN_PURPOSES = {"password_reset"}


def smtp_configured() -> bool:
    return bool(SMTP_HOST and EMAIL_FROM)


def email_auth_ready() -> bool:
    return bool(EMAIL_AUTH_ENABLED and smtp_configured())


def public_email_auth_features() -> dict[str, Any]:
    return {
        "enabled": bool(EMAIL_AUTH_ENABLED),
        "configured": smtp_configured(),
        "passwordReset": email_auth_ready(),
        "accountEmail": bool(EMAIL_AUTH_ENABLED),
    }


def require_email_auth_ready() -> None:
    if not EMAIL_AUTH_ENABLED:
        raise APIError("Email account features are not enabled on this forum.")
    if not smtp_configured():
        raise APIError("Email account features are enabled but SMTP is not configured.")


def email_reset_url(token: str) -> str:
    return f"{PUBLIC_URL}/?emailResetToken={token}"


def create_email_auth_token(
    conn: sqlite3.Connection,
    user_id: int,
    *,
    email: str,
    purpose: str,
    minutes: int = 45,
) -> str:
    if purpose not in EMAIL_TOKEN_PURPOSES:
        raise ValueError(f"Unsupported email auth token purpose: {purpose}")
    token = secrets.token_urlsafe(32)
    now = utc_now()
    expires_at = now + timedelta(minutes=max(5, minutes))
    conn.execute(
        """
        INSERT INTO email_auth_tokens (user_id, purpose, email, token_hash, expires_at, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (user_id, purpose, email, make_password_hash(token), expires_at.isoformat(), now.isoformat()),
    )
    return token


def consume_email_auth_token(
    conn: sqlite3.Connection,
    token: str,
    *,
    purpose: str,
) -> sqlite3.Row | None:
    if purpose not in EMAIL_TOKEN_PURPOSES:
        raise ValueError(f"Unsupported email auth token purpose: {purpose}")
    rows = conn.execute(
        """
        SELECT *
        FROM email_auth_tokens
        WHERE purpose = ? AND used_at IS NULL
        ORDER BY created_at DESC
        LIMIT 24
        """,
        (purpose,),
    ).fetchall()
    now = utc_now()
    for row in rows:
        expires_at = parse_iso(row["expires_at"])
        if expires_at and expires_at <= now:
            continue
        if verify_password(token, row["token_hash"]):
            conn.execute("UPDATE email_auth_tokens SET used_at = ? WHERE id = ?", (utc_iso(), row["id"]))
            return row
    return None


def send_email(to_email: str, *, subject: str, text_body: str) -> None:
    require_email_auth_ready()
    message = EmailMessage()
    message["From"] = EMAIL_FROM
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(text_body)
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as smtp:
            if SMTP_STARTTLS:
                smtp.starttls()
            if SMTP_USERNAME or SMTP_PASSWORD:
                smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
            smtp.send_message(message)
    except Exception as exc:  # noqa: BLE001
        append_structured_log("email_auth", status="error", recipient=to_email, error=str(exc))
        raise APIError("Email could not be sent. Please try again later.") from exc
    append_structured_log("email_auth", status="sent", recipient=to_email)


def send_password_reset_email(username: str, email: str, token: str) -> None:
    send_email(
        email,
        subject="Reset your OmniForum password",
        text_body=(
            f"Hi {username},\n\n"
            "A password reset was requested for your OmniForum account.\n\n"
            f"Open this link to choose a new password:\n{email_reset_url(token)}\n\n"
            "This link expires soon. If you did not request it, you can ignore this email."
        ),
    )
