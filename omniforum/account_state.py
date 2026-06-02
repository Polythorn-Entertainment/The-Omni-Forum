"""Account trust, restrictions, and participation guards."""

from __future__ import annotations

import math
import sqlite3
from datetime import datetime, timedelta
from http import HTTPStatus
from typing import Any

from .config import (
    AUTO_ROLES,
    LOW_TRUST_MAX_LINKS,
    LOW_TRUST_MAX_MENTIONS,
    MENTION_PATTERN,
)
from .core import parse_iso, role_level, utc_iso, utc_now
from .errors import APIError
from .validation import count_links, is_approved_user, user_account_age_days


def enforce_low_trust_content_limits(viewer: dict[str, Any] | None, text: str) -> None:
    if not viewer:
        return
    trust = user_trust_summary(viewer)
    if trust["tier"] not in {"new", "restricted"}:
        return
    if count_links(text) > LOW_TRUST_MAX_LINKS:
        raise APIError(
            f"New accounts can only include up to {LOW_TRUST_MAX_LINKS} links in one post.",
            HTTPStatus.TOO_MANY_REQUESTS,
        )
    if len(MENTION_PATTERN.findall(text)) > LOW_TRUST_MAX_MENTIONS:
        raise APIError(
            f"New accounts can only mention up to {LOW_TRUST_MAX_MENTIONS} people at once.",
            HTTPStatus.TOO_MANY_REQUESTS,
        )


def user_trust_summary(row: sqlite3.Row | dict[str, Any] | None) -> dict[str, Any]:
    data = dict(row or {})
    role = data.get("role") or "new"
    xp = int(data.get("xp") or 0)
    posts = int(data.get("posts_count") or data.get("posts") or 0)
    age_days = user_account_age_days(data)
    if is_banned_user(data) or active_timeout_until(data) or active_mute_until(data) or is_shadow_muted(data):
        tier = "restricted"
        label = "Restricted"
        cooldown = "Strict"
        limits = f"{LOW_TRUST_MAX_LINKS} links and {LOW_TRUST_MAX_MENTIONS} mentions per post"
    elif role_level(role) >= role_level("mod"):
        tier = "staff"
        label = "Staff"
        cooldown = "None"
        limits = "Staff permissions"
    elif role_level(role) >= role_level("veteran") or xp >= 600 or (posts >= 25 and age_days >= 14):
        tier = "trusted"
        label = "Trusted"
        cooldown = "Reduced"
        limits = "Normal community limits"
    elif role_level(role) >= role_level("member") or xp >= 100 or (posts >= 5 and age_days >= 2):
        tier = "member"
        label = "Member"
        cooldown = "Reduced"
        limits = "Normal community limits"
    else:
        tier = "new"
        label = "New Account"
        cooldown = "Strict"
        limits = f"{LOW_TRUST_MAX_LINKS} links and {LOW_TRUST_MAX_MENTIONS} mentions per post"
    return {
        "tier": tier,
        "label": label,
        "accountAgeDays": age_days,
        "cooldown": cooldown,
        "limits": limits,
        "nextStep": "Build history with posts, replies, and positive XP." if tier == "new" else "",
    }


def set_auto_role(conn: sqlite3.Connection, user_id: int) -> None:
    row = conn.execute("SELECT role, xp FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row or row["role"] in {"mod", "admin", "owner"}:
        return
    new_role = "new"
    for role_name, threshold in AUTO_ROLES:
        if row["xp"] >= threshold:
            new_role = role_name
            break
    if new_role != row["role"]:
        now = utc_iso()
        conn.execute(
            "UPDATE users SET role = ?, updated_at = ? WHERE id = ?",
            (new_role, now, user_id),
        )
        conn.commit()


def award_xp(conn: sqlite3.Connection, user_id: int, delta: int) -> None:
    if delta == 0:
        return
    now = utc_iso()
    conn.execute(
        "UPDATE users SET xp = MAX(0, xp + ?), updated_at = ? WHERE id = ?",
        (delta, now, user_id),
    )
    conn.commit()
    set_auto_role(conn, user_id)


def clear_timeout_state(conn: sqlite3.Connection, user_id: int) -> None:
    conn.execute(
        """
        UPDATE users
        SET timeout_until = NULL, timeout_reason = '', timeout_set_by = NULL, updated_at = ?
        WHERE id = ?
        """,
        (utc_iso(), user_id),
    )
    conn.commit()


def sync_user_restrictions(
    conn: sqlite3.Connection,
    row: sqlite3.Row | dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not row:
        return None
    payload = dict(row)
    timeout_until = parse_iso(payload.get("timeout_until"))
    if timeout_until and timeout_until <= utc_now():
        clear_timeout_state(conn, payload["id"])
        payload["timeout_until"] = None
        payload["timeout_reason"] = ""
        payload["timeout_set_by"] = None
    mute_until = parse_iso(payload.get("mute_until"))
    if mute_until and mute_until <= utc_now():
        conn.execute(
            """
            UPDATE users
            SET mute_until = NULL, mute_reason = '', mute_set_by = NULL, updated_at = ?
            WHERE id = ?
            """,
            (utc_iso(), payload["id"]),
        )
        conn.commit()
        payload["mute_until"] = None
        payload["mute_reason"] = ""
        payload["mute_set_by"] = None
    return payload


def is_banned_user(row: sqlite3.Row | dict[str, Any] | None) -> bool:
    return bool(row and dict(row).get("banned_at"))


def active_timeout_until(row: sqlite3.Row | dict[str, Any] | None) -> datetime | None:
    if not row:
        return None
    timeout_until = parse_iso(dict(row).get("timeout_until"))
    if not timeout_until or timeout_until <= utc_now():
        return None
    return timeout_until


def active_mute_until(row: sqlite3.Row | dict[str, Any] | None) -> datetime | None:
    if not row:
        return None
    mute_until = parse_iso(dict(row).get("mute_until"))
    if not mute_until or mute_until <= utc_now():
        return None
    return mute_until


def is_shadow_muted(row: sqlite3.Row | dict[str, Any] | None) -> bool:
    return bool(row and dict(row).get("shadow_muted"))


def ensure_can_participate(viewer: dict[str, Any] | None) -> None:
    if not viewer:
        raise APIError("You must be logged in.", HTTPStatus.UNAUTHORIZED)
    if not is_approved_user(viewer):
        raise APIError("This account is not approved yet.", HTTPStatus.FORBIDDEN)
    if is_banned_user(viewer):
        reason = str(viewer.get("ban_reason") or "").strip()
        detail = f" Reason: {reason.rstrip('.!?')}" if reason else ""
        raise APIError(f"This account is banned.{detail}", HTTPStatus.FORBIDDEN)
    if bool(viewer.get("password_reset_required")):
        raise APIError(
            "You need to reset your password before using the forum.",
            HTTPStatus.FORBIDDEN,
        )
    timeout_until = active_timeout_until(viewer)
    if timeout_until:
        detail = f" until {utc_iso(timeout_until)}"
        reason = str(viewer.get("timeout_reason") or "").strip()
        if reason:
            detail += f". Reason: {reason.rstrip('.!?')}"
        raise APIError(f"Your account is timed out{detail}.", HTTPStatus.FORBIDDEN)


def ensure_can_post_content(viewer: dict[str, Any] | None) -> None:
    ensure_can_participate(viewer)
    mute_until = active_mute_until(viewer)
    if mute_until:
        detail = f" until {utc_iso(mute_until)}"
        reason = str(viewer.get("mute_reason") or "").strip()
        if reason:
            detail += f". Reason: {reason.rstrip('.!?')}"
        raise APIError(f"Your account is muted from posting{detail}.", HTTPStatus.FORBIDDEN)


def ensure_can_send_message(viewer: dict[str, Any] | None) -> None:
    ensure_can_participate(viewer)
    mute_until = active_mute_until(viewer)
    if mute_until:
        raise APIError("Your account is currently muted from sending messages.", HTTPStatus.FORBIDDEN)


def scaled_cooldown_seconds(viewer: dict[str, Any] | None, base_seconds: int) -> int:
    if not viewer:
        return base_seconds
    trust = user_trust_summary(viewer)
    if trust["tier"] in {"trusted", "staff"}:
        return 0
    level = role_level(viewer["role"])
    if level >= role_level("veteran"):
        return 0
    if level >= role_level("member"):
        return max(2, base_seconds // 2)
    return base_seconds


def enforce_recent_action_limit(
    conn: sqlite3.Connection,
    viewer: dict[str, Any] | None,
    *,
    query: str,
    params: tuple[Any, ...],
    base_seconds: int,
    verb: str,
) -> None:
    cooldown = scaled_cooldown_seconds(viewer, base_seconds)
    if cooldown <= 0:
        return
    row = conn.execute(query, params).fetchone()
    last_at = parse_iso(row["created_at"]) if row and row["created_at"] else None
    if not last_at:
        return
    wait_until = last_at + timedelta(seconds=cooldown)
    if wait_until <= utc_now():
        return
    remaining = max(1, math.ceil((wait_until - utc_now()).total_seconds()))
    raise APIError(
        f"Slow down a little. You can {verb} again in about {remaining}s.",
        HTTPStatus.TOO_MANY_REQUESTS,
    )
