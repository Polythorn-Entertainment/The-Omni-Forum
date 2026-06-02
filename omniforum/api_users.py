from __future__ import annotations

import json
import sqlite3
from datetime import timedelta
from http import HTTPStatus
from typing import Any

from .config import DEFAULT_MEMBER_PAGE_SIZE
from .validation import (
    parse_pagination_query,
    resolve_pagination,
)
from .account_state import ensure_can_participate
from .domain import (
    get_current_user_payload,
    get_role_breakdown,
    get_user_profile,
    list_members,
    upsert_user_relationship,
    viewer_ignored_user_ids,
)
from .errors import APIError


class UsersApiMixin:
    def api_users(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        query: dict[str, list[str]],
    ) -> dict[str, Any]:
        members = list_members(conn)
        ignored_ids = viewer_ignored_user_ids(conn, viewer)
        search = (query.get("q") or [""])[0].strip().lower()
        role_filter = (query.get("role") or ["all"])[0].strip()
        if ignored_ids and viewer and bool(viewer.get("hide_ignored_content", 1)):
            members = [member for member in members if member["id"] not in ignored_ids]
        page, page_size, last_page = parse_pagination_query(
            query,
            default_page_size=DEFAULT_MEMBER_PAGE_SIZE,
        )
        if search:
            members = [m for m in members if search in m["username"].lower()]
        if role_filter and role_filter != "all":
            members = [m for m in members if m["role"] == role_filter]
        pagination = resolve_pagination(
            len(members),
            page=page,
            page_size=page_size,
            last_page=last_page,
        )
        members = members[pagination["offset"] : pagination["offset"] + pagination["pageSize"]]
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "members": members,
            "counts": get_role_breakdown(conn),
            "pagination": pagination,
        }

    def api_user_detail(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        user_id: int,
    ) -> dict[str, Any]:
        profile = get_user_profile(conn, user_id, viewer=viewer)
        if not profile:
            raise APIError("User not found.", HTTPStatus.NOT_FOUND)
        return {"currentUser": get_current_user_payload(conn, viewer), "user": profile}

    def api_update_user_relationship(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        user_id: int,
    ) -> dict[str, Any]:
        ensure_can_participate(viewer)
        if not viewer:
            raise APIError("You must be logged in.", HTTPStatus.UNAUTHORIZED)
        if user_id == int(viewer["id"]):
            raise APIError("You cannot change your relationship with yourself.")
        target = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
        if not target:
            raise APIError("User not found.", HTTPStatus.NOT_FOUND)
        data = self.read_json()
        relationship = upsert_user_relationship(
            conn,
            user_id=viewer["id"],
            target_user_id=user_id,
            ignore_content=bool(data.get("ignoreContent")),
            block_dm=bool(data.get("blockDm")),
        )
        conn.commit()
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "relationship": relationship,
            "user": get_user_profile(conn, user_id, viewer=viewer),
            "message": "Member controls updated.",
        }
