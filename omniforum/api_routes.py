"""Declarative API route table for the stdlib HTTP handler."""

from __future__ import annotations

import re
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any

from .core import utc_iso
from .errors import APIError


@dataclass(frozen=True)
class ApiRoute:
    method: str
    pattern: re.Pattern[str]
    endpoint: str
    args: tuple[str, ...] = ("conn", "viewer")

    def match(self, method: str, path: str) -> re.Match[str] | None:
        if method != self.method:
            return None
        return self.pattern.fullmatch(path)


def exact(method: str, path: str, endpoint: str, *args: str) -> ApiRoute:
    return ApiRoute(method, re.compile(re.escape(path)), endpoint, args or ("conn", "viewer"))


def regex(method: str, pattern: str, endpoint: str, *args: str) -> ApiRoute:
    return ApiRoute(method, re.compile(pattern), endpoint, args or ("conn", "viewer"))


API_ROUTES: tuple[ApiRoute, ...] = (
    exact("GET", "/api/site", "api_site"),
    exact("GET", "/api/home", "api_home"),
    exact("GET", "/api/auth/features", "api_auth_features"),
    exact("GET", "/api/me", "api_current_user"),
    exact("GET", "/api/me/export", "api_export_me"),
    exact("POST", "/api/register", "api_register", "conn"),
    exact("POST", "/api/login", "api_login", "conn"),
    exact("POST", "/api/auth/email-reset", "api_request_email_password_reset"),
    exact("POST", "/api/auth/email-reset/complete", "api_complete_email_password_reset"),
    exact("POST", "/api/logout", "api_logout", "conn"),
    exact("PATCH", "/api/me", "api_update_me"),
    exact("PATCH", "/api/me/password", "api_update_password"),
    exact("POST", "/api/me/sessions/revoke-others", "api_revoke_other_sessions"),
    exact("GET", "/api/me/recovery-codes", "api_recovery_codes"),
    exact("POST", "/api/me/recovery-codes", "api_create_recovery_codes"),
    exact("GET", "/api/live", "api_live", "conn", "viewer", "query"),
    exact("GET", "/api/plugins", "api_plugins", "conn", "viewer", "query"),
    exact("GET", "/api/search", "api_search", "conn", "viewer", "query"),
    exact("GET", "/api/notifications", "api_notifications", "conn", "viewer", "query"),
    exact("POST", "/api/notifications/read-all", "api_mark_notifications"),
    exact("GET", "/api/messages", "api_messages"),
    exact("POST", "/api/messages", "api_send_message"),
    exact("POST", "/api/contact", "api_contact"),
    exact("GET", "/api/reports", "api_reports", "conn", "viewer", "query"),
    exact("POST", "/api/reports", "api_create_report"),
    exact("POST", "/api/reports/bulk", "api_bulk_update_reports"),
    exact("GET", "/api/reports/macros", "api_report_macros"),
    exact("POST", "/api/reports/macros", "api_create_report_macro"),
    exact("GET", "/api/appeals", "api_appeals", "conn", "viewer", "query"),
    exact("POST", "/api/appeals", "api_create_appeal"),
    exact("POST", "/api/sections", "api_create_section"),
    exact("GET", "/api/users", "api_users", "conn", "viewer", "query"),
    exact("GET", "/api/leaderboard", "api_leaderboard", "conn", "viewer", "query"),
    exact("GET", "/api/notices", "api_notices", "conn", "viewer", "query"),
    exact("GET", "/api/admin/health", "api_admin_health"),
    exact("GET", "/api/admin/trash", "api_admin_trash", "conn", "viewer", "query"),
    exact("POST", "/api/admin/backup", "api_admin_backup"),
    exact("GET", "/api/admin/backups/guide", "api_admin_backup_guide", "conn", "viewer", "query"),
    exact("GET", "/api/admin/logs", "api_admin_logs"),
    exact("GET", "/api/admin/audit", "api_admin_audit", "conn", "viewer", "query"),
    exact("GET", "/api/admin/site-settings", "api_admin_site_settings"),
    exact("PATCH", "/api/admin/site-settings", "api_update_admin_site_settings"),
    exact("GET", "/api/admin/export", "api_admin_export", "conn", "viewer", "query"),
    exact("POST", "/api/admin/import-preview", "api_admin_import_preview"),
    exact("GET", "/api/admin/registration", "api_admin_registration"),
    exact("PATCH", "/api/admin/registration/settings", "api_update_registration_settings"),
    exact("POST", "/api/admin/invites", "api_create_invite"),
    exact("POST", "/api/admin/media-cleanup", "api_admin_media_cleanup"),
    exact("POST", "/api/admin/trash/restore", "api_restore_trash"),
    regex("PATCH", r"/api/plugins/([A-Za-z0-9_-]+)", "api_update_plugin", "conn", "viewer", "str:1"),
    regex("PATCH", r"/api/admin/invites/(\d+)", "api_update_invite", "conn", "viewer", "int:1"),
    regex("POST", r"/api/admin/registrations/(\d+)/review", "api_review_registration", "conn", "viewer", "int:1"),
    regex("GET", r"/api/users/(\d+)", "api_user_detail", "conn", "viewer", "int:1"),
    regex("PATCH", r"/api/users/(\d+)/role", "api_update_role", "conn", "viewer", "int:1"),
    regex("POST", r"/api/users/(\d+)/relationship", "api_update_user_relationship", "conn", "viewer", "int:1"),
    regex("POST", r"/api/users/(\d+)/moderation", "api_moderate_user", "conn", "viewer", "int:1"),
    regex("GET", r"/api/messages/(\d+)", "api_message_thread", "conn", "viewer", "int:1"),
    regex("POST", r"/api/messages/(\d+)", "api_reply_message", "conn", "viewer", "int:1"),
    regex("PATCH", r"/api/notifications/(\d+)", "api_mark_notifications", "conn", "viewer", "int:1"),
    regex("PATCH", r"/api/reports/(\d+)", "api_update_report", "conn", "viewer", "int:1"),
    regex("POST", r"/api/reports/(\d+)/notes", "api_add_report_note", "conn", "viewer", "int:1"),
    regex("PATCH", r"/api/reports/macros/(\d+)", "api_update_report_macro", "conn", "viewer", "int:1"),
    regex("PATCH", r"/api/appeals/(\d+)", "api_update_appeal", "conn", "viewer", "int:1"),
    regex("GET", r"/api/sections/([A-Za-z0-9_-]+)", "api_section", "conn", "viewer", "str:1", "query"),
    regex("POST", r"/api/sections/([A-Za-z0-9_-]+)", "api_create_thread", "conn", "viewer", "str:1"),
    regex("PATCH", r"/api/sections/([A-Za-z0-9_-]+)", "api_update_section", "conn", "viewer", "str:1"),
    regex("DELETE", r"/api/sections/([A-Za-z0-9_-]+)", "api_delete_section", "conn", "viewer", "str:1"),
    regex("GET", r"/api/threads/(\d+)", "api_thread", "conn", "viewer", "int:1", "query"),
    regex("PATCH", r"/api/threads/(\d+)", "api_update_thread", "conn", "viewer", "int:1"),
    regex("DELETE", r"/api/threads/(\d+)", "api_delete_thread", "conn", "viewer", "int:1"),
    regex("POST", r"/api/threads/(\d+)/bookmark", "api_toggle_thread_bookmark", "conn", "viewer", "int:1"),
    regex("POST", r"/api/threads/(\d+)/subscription", "api_toggle_thread_subscription", "conn", "viewer", "int:1"),
    regex("POST", r"/api/threads/(\d+)/split", "api_split_thread", "conn", "viewer", "int:1"),
    regex("POST", r"/api/threads/(\d+)/posts", "api_create_post", "conn", "viewer", "int:1"),
    regex("GET", r"/api/posts/(\d+)", "api_post_history", "conn", "viewer", "int:1"),
    regex("PATCH", r"/api/posts/(\d+)", "api_update_post", "conn", "viewer", "int:1"),
    regex("DELETE", r"/api/posts/(\d+)", "api_delete_post", "conn", "viewer", "int:1"),
    regex("POST", r"/api/posts/(\d+)/like", "api_toggle_like", "conn", "viewer", "int:1"),
    regex("POST", r"/api/posts/(\d+)/reactions", "api_toggle_reaction", "conn", "viewer", "int:1"),
    regex("PATCH", r"/api/notices/contact/(\d+)", "api_update_contact_notice", "conn", "viewer", "int:1"),
    regex("POST", r"/api/threads/(\d+)/poll", "api_vote_thread_poll", "conn", "viewer", "int:1"),
)


def resolve_arg(
    spec: str, *, conn: Any, viewer: dict[str, Any] | None, query: dict[str, list[str]], match: re.Match[str]
) -> Any:
    if spec == "conn":
        return conn
    if spec == "viewer":
        return viewer
    if spec == "query":
        return query
    if spec.startswith("int:"):
        return int(match.group(int(spec.split(":", 1)[1])))
    if spec.startswith("str:"):
        return match.group(int(spec.split(":", 1)[1]))
    raise RuntimeError(f"Unknown route argument: {spec}")


def dispatch_api_route(
    handler: Any, conn: Any, method: str, path: str, query: dict[str, list[str]], viewer: dict[str, Any] | None
) -> dict[str, Any]:
    if method == "GET" and path == "/api/health":
        return {"ok": True, "time": utc_iso()}
    for route in API_ROUTES:
        match = route.match(method, path)
        if not match:
            continue
        endpoint = getattr(handler, route.endpoint)
        args = [resolve_arg(spec, conn=conn, viewer=viewer, query=query, match=match) for spec in route.args]
        return endpoint(*args)
    raise APIError("Endpoint not found.", HTTPStatus.NOT_FOUND)
