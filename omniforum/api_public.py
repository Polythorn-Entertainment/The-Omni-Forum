from __future__ import annotations

import json
import sqlite3
from datetime import timedelta
from http import HTTPStatus
from typing import Any

from .config import (
    DEFAULT_LEADERBOARD_PAGE_SIZE,
    ROLES,
)
from .email_auth import public_email_auth_features
from .core import (
    is_admin,
    role_level,
)
from .plugins import list_plugins
from .search import log_search_event
from .validation import (
    get_site_settings,
    parse_pagination_query,
    resolve_pagination,
    serialize_site_settings,
)
from .admin_health import (
    get_home_announcements,
    get_site_stats,
)
from .domain import (
    get_current_user_payload,
    get_featured_threads,
    get_latest_activity,
    get_live_snapshot,
    get_sections_with_stats,
    get_top_members,
    get_trending_threads,
    list_members,
    search_members,
    search_posts,
    search_threads,
)
from .errors import APIError


class PublicApiMixin:
    def api_site(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        return {
            "authFeatures": {"email": public_email_auth_features()},
            "currentUser": get_current_user_payload(conn, viewer),
            "site": serialize_site_settings(get_site_settings(conn)),
        }

    def api_home(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        return {
            "authFeatures": {"email": public_email_auth_features()},
            "roles": ROLES,
            "site": serialize_site_settings(get_site_settings(conn)),
            "currentUser": get_current_user_payload(conn, viewer),
            "stats": get_site_stats(conn),
            "categories": get_sections_with_stats(conn, viewer),
            "topMembers": get_top_members(conn),
            "trendingThreads": get_trending_threads(conn, viewer),
            "featuredThreads": get_featured_threads(conn, viewer),
            "activity": get_latest_activity(conn, viewer),
            "announcements": get_home_announcements(conn),
        }

    def api_live(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        query: dict[str, list[str]],
    ) -> dict[str, Any]:
        thread_id = None
        raw_thread_id = (query.get("threadId") or [""])[0].strip()
        if raw_thread_id:
            try:
                thread_id = int(raw_thread_id)
            except (TypeError, ValueError):
                thread_id = None
        section_slug = (query.get("section") or [""])[0].strip()
        return get_live_snapshot(
            conn,
            viewer,
            thread_id=thread_id,
            section_slug=section_slug,
        )

    def api_plugins(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        query: dict[str, list[str]],
    ) -> dict[str, Any]:
        include_disabled = bool(
            viewer and is_admin(viewer) and (query.get("includeAll") or [""])[0].strip().lower() in {"1", "true", "yes"}
        )
        plugins = list_plugins(include_disabled=include_disabled)
        if not include_disabled:
            plugins = [plugin for plugin in plugins if plugin["enabled"]]
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "plugins": plugins,
        }

    def api_search(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        query: dict[str, list[str]],
    ) -> dict[str, Any]:
        term = (query.get("q") or [""])[0].strip()
        section_filter = (query.get("section") or [""])[0].strip()
        author_filter = (query.get("author") or [""])[0].strip()
        tag_filter = (query.get("tag") or [""])[0].strip().lower()
        solved_filter = (query.get("solved") or ["all"])[0].strip().lower()
        media_filter = (query.get("media") or ["all"])[0].strip().lower()
        replies_filter = (query.get("replies") or ["all"])[0].strip().lower()
        date_filter = (query.get("date") or ["all"])[0].strip().lower()
        sort = (query.get("sort") or ["relevance"])[0].strip().lower()
        if solved_filter not in {"all", "solved", "unsolved"}:
            solved_filter = "all"
        if media_filter not in {"all", "with_media"}:
            media_filter = "all"
        if replies_filter not in {"all", "answered", "unanswered"}:
            replies_filter = "all"
        if date_filter not in {"all", "today", "week", "month", "year"}:
            date_filter = "all"
        filters = {
            "section": section_filter,
            "author": author_filter,
            "tag": tag_filter,
            "solved": solved_filter,
            "media": media_filter,
            "replies": replies_filter,
            "date": date_filter,
            "sort": sort,
        }
        has_active_filter = any(value and value != "all" for key, value in filters.items() if key != "sort")
        if len(term) < 2 and not has_active_filter:
            return {
                "currentUser": get_current_user_payload(conn, viewer),
                "query": term,
                "filters": filters,
                "threads": [],
                "posts": [],
                "members": [],
                "sections": [
                    {"id": item["id"], "name": item["name"]}
                    for category in get_sections_with_stats(conn, viewer)
                    for item in category["sections"]
                ],
            }
        self.enforce_rate_limit("search", viewer)
        search_term = term if len(term) >= 2 else ""
        threads = search_threads(
            conn,
            search_term,
            viewer=viewer,
            section_slug=section_filter,
            author=author_filter,
            tag=tag_filter,
            solved=solved_filter,
            media=media_filter,
            replies=replies_filter,
            date=date_filter,
            sort=sort,
            limit=12,
        )
        posts = search_posts(
            conn,
            search_term,
            viewer=viewer,
            section_slug=section_filter,
            author=author_filter,
            media=media_filter,
            date=date_filter,
            limit=12,
        )
        members = search_members(conn, search_term, limit=12) if search_term else []
        log_search_event(
            conn,
            viewer=viewer,
            query=search_term,
            filters=filters,
            result_count=len(threads) + len(posts) + len(members),
        )
        conn.commit()
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "query": term,
            "filters": filters,
            "threads": threads,
            "posts": posts,
            "members": members,
            "sections": [
                {"id": item["id"], "name": item["name"]}
                for category in get_sections_with_stats(conn, viewer)
                for item in category["sections"]
            ],
        }

    def api_leaderboard(
        self,
        conn: sqlite3.Connection,
        viewer: dict[str, Any] | None,
        query: dict[str, list[str]],
    ) -> dict[str, Any]:
        metric = (query.get("metric") or ["xp"])[0]
        page, page_size, last_page = parse_pagination_query(
            query,
            default_page_size=DEFAULT_LEADERBOARD_PAGE_SIZE,
        )
        members = list_members(conn)
        if metric == "posts":
            members.sort(key=lambda member: (-member["posts"], -member["xp"], member["username"].lower()))
        elif metric == "role":
            members.sort(
                key=lambda member: (
                    -role_level(member["role"]),
                    -member["xp"],
                    member["username"].lower(),
                )
            )
        else:
            metric = "xp"
            members.sort(key=lambda member: (-member["xp"], -member["posts"], member["username"].lower()))
        rank = None
        if viewer:
            for index, member in enumerate(members, start=1):
                if member["id"] == viewer["id"]:
                    rank = index
                    break
        podium = members[:3]
        list_members_only = members[3:]
        pagination = resolve_pagination(
            len(list_members_only),
            page=page,
            page_size=page_size,
            last_page=last_page,
        )
        start = pagination["offset"]
        end = start + pagination["pageSize"]
        return {
            "currentUser": get_current_user_payload(conn, viewer),
            "metric": metric,
            "podium": podium,
            "members": list_members_only[start:end],
            "rank": rank,
            "pagination": pagination,
        }
