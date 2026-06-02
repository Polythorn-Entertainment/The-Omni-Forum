#!/usr/bin/env python3
"""OmniForum application server.

This keeps the existing static frontend structure but backs it with a real
SQLite-powered API, cookie sessions, and persistent forum data stored in
separate files under ``data/``.
"""

from __future__ import annotations

import hmac
import json
import math
import mimetypes
import re
import secrets
import sqlite3
import time
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from omniforum.api_routes import dispatch_api_route
from omniforum.config import (
    ACCESS_LOG_FILE,
    BACKUP_DIR,
    BASE_DIR,
    EXPORT_ROUTE,
    HOST,
    LIVE_STREAM_INTERVAL_SECONDS,
    MAX_REQUEST_BYTES,
    MEDIA_FOLDERS,
    MEDIA_ROUTE,
    PORT,
    RATE_LIMIT_RULES,
    SECURE_COOKIES,
    SESSION_COOKIE,
)
from omniforum.core import is_admin, parse_iso, utc_iso
from omniforum.db import ensure_runtime_dirs, get_connection
from omniforum.errors import APIError
from omniforum.api_auth import AuthApiMixin
from omniforum.api_admin import AdminApiMixin
from omniforum.api_content import ContentApiMixin
from omniforum.api_messages import MessagesApiMixin
from omniforum.api_moderation import ModerationApiMixin
from omniforum.api_public import PublicApiMixin
from omniforum.api_users import UsersApiMixin
from omniforum.domain import get_live_snapshot
from omniforum.media import resolve_media_path
from omniforum.plugins import resolve_public_plugin_asset
from omniforum.runtime_logging import append_server_log, append_structured_log
from omniforum.schema import init_db
from omniforum.search import refresh_search_index
from omniforum.seo import render_robots_txt, render_sitemap_xml
from omniforum.sessions import current_user_from_request, session_token_from_headers


class ForumHandler(
    AuthApiMixin,
    PublicApiMixin,
    MessagesApiMixin,
    ModerationApiMixin,
    UsersApiMixin,
    ContentApiMixin,
    AdminApiMixin,
    SimpleHTTPRequestHandler,
):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(BASE_DIR), **kwargs)

    def request_ip(self) -> str:
        forwarded = str(self.headers.get("X-Forwarded-For") or "").split(",", 1)[0].strip()
        return forwarded or (self.client_address[0] if self.client_address else "")

    def request_user_agent(self) -> str:
        return str(self.headers.get("User-Agent") or "").strip()

    def current_session_token(self) -> str | None:
        return session_token_from_headers(self.headers)

    def ensure_request_id(self) -> str:
        existing = str(getattr(self, "_request_id", "") or "")
        if existing:
            return existing
        provided = str(self.headers.get("X-Request-ID") or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9._:-]{8,80}", provided):
            provided = secrets.token_hex(12)
        self._request_id = provided
        return provided

    def enforce_same_origin(self) -> None:
        allowed_hosts = {
            str(self.headers.get("Host") or "").strip(),
            f"{HOST}:{PORT}",
            f"localhost:{PORT}",
            f"127.0.0.1:{PORT}",
        }
        headers_to_check = [self.headers.get("Origin"), self.headers.get("Referer")]
        checked = False
        for raw_value in headers_to_check:
            if not raw_value:
                continue
            checked = True
            parsed = urlparse(raw_value)
            if parsed.netloc in allowed_hosts:
                return
        if checked:
            raise APIError("This request origin is not allowed.", HTTPStatus.FORBIDDEN)

    def enforce_csrf_token(self, viewer: dict[str, Any] | None, path: str) -> None:
        if not viewer or path in {"/api/login", "/api/register"}:
            return
        expected = str(viewer.get("session_csrf_token") or "")
        provided = str(self.headers.get("X-CSRF-Token") or "")
        if not expected or not hmac.compare_digest(expected, provided):
            raise APIError("Security token expired. Refresh the page and try again.", HTTPStatus.FORBIDDEN)

    def enforce_rate_limit(self, action: str, viewer: dict[str, Any] | None = None) -> None:
        # Backwards-compatible wrapper for older plugin code paths.
        with get_connection() as conn:
            self.enforce_persistent_rate_limit(conn.raw, action, viewer)

    def enforce_persistent_rate_limit(
        self,
        conn: sqlite3.Connection,
        action: str,
        viewer: dict[str, Any] | None = None,
    ) -> None:
        rule = RATE_LIMIT_RULES.get(action)
        if not rule:
            return
        limit, window_seconds, label = rule
        identity = f"user:{viewer['id']}" if viewer else f"ip:{self.request_ip() or 'unknown'}"
        now = time.time()
        cutoff = now - float(window_seconds)
        conn.execute(
            "DELETE FROM rate_limit_events WHERE action = ? AND identity = ? AND created_at < ?",
            (action, identity, cutoff),
        )
        rows = conn.execute(
            """
            SELECT created_at
            FROM rate_limit_events
            WHERE action = ? AND identity = ? AND created_at >= ?
            ORDER BY created_at ASC
            """,
            (action, identity, cutoff),
        ).fetchall()
        if len(rows) >= limit:
            retry_after = max(1, math.ceil(window_seconds - (now - float(rows[0]["created_at"]))))
            raise APIError(
                f"Too many {label}. Please wait about {retry_after}s and try again.",
                HTTPStatus.TOO_MANY_REQUESTS,
            )
        conn.execute(
            "INSERT INTO rate_limit_events (action, identity, created_at) VALUES (?, ?, ?)",
            (action, identity, now),
        )
        conn.commit()

    def end_headers(self) -> None:
        self.send_header("X-Request-ID", self.ensure_request_id())
        if not urlparse(self.path).path.startswith(f"{MEDIA_ROUTE}/"):
            self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data: blob:; "
            "style-src 'self'; font-src 'self'; "
            "script-src 'self'; script-src-attr 'none'; connect-src 'self'; frame-ancestors 'none'; "
            "object-src 'none'; base-uri 'self'; form-action 'self'",
        )
        super().end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/live/stream":
            self.serve_live_stream(parse_qs(parsed.query))
            return
        if parsed.path.startswith("/api/"):
            self.handle_api("GET")
            return
        if parsed.path == "/robots.txt":
            self.respond_text(render_robots_txt(), content_type="text/plain; charset=utf-8")
            return
        if parsed.path == "/sitemap.xml":
            with get_connection() as conn:
                self.respond_text(render_sitemap_xml(conn), content_type="application/xml; charset=utf-8")
            return
        if parsed.path == "/data" or parsed.path.startswith("/data/"):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if parsed.path.startswith("/plugins/"):
            self.serve_plugin_asset(parsed.path)
            return
        if parsed.path.startswith(f"{EXPORT_ROUTE}/"):
            self.serve_export(parsed.path)
            return
        if parsed.path.startswith(f"{MEDIA_ROUTE}/"):
            self.serve_media(parsed.path)
            return
        super().do_GET()

    def do_POST(self) -> None:
        if self.path.startswith("/api/"):
            self.handle_api("POST")
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_PATCH(self) -> None:
        if self.path.startswith("/api/"):
            self.handle_api("PATCH")
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_DELETE(self) -> None:
        if self.path.startswith("/api/"):
            self.handle_api("DELETE")
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def log_message(self, fmt: str, *args: Any) -> None:
        message = f"{self.address_string()} request_id={self.ensure_request_id()} {fmt % args}"
        print(f"[{self.log_date_time_string()}] {message}")
        append_server_log(message)
        ensure_runtime_dirs()
        with ACCESS_LOG_FILE.open("a", encoding="utf-8") as handle:
            handle.write(f"[{utc_iso()}] {message}\n")

    def serve_media(self, path: str) -> None:
        relative = unquote(path[len(MEDIA_ROUTE) :]).strip("/")
        parts = [part for part in relative.split("/") if part]
        if len(parts) != 2 or parts[0] not in MEDIA_FOLDERS:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not re.fullmatch(r"[A-Za-z0-9._-]+", parts[1]):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        file_path = resolve_media_path("/".join(parts))
        if not file_path or not file_path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header(
            "Content-Type",
            mimetypes.guess_type(file_path.name)[0] or "application/octet-stream",
        )
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "public, max-age=86400")
        self.end_headers()
        self.wfile.write(body)

    def respond_text(self, payload: str | bytes, *, status: int = HTTPStatus.OK, content_type: str) -> None:
        body = payload.encode("utf-8") if isinstance(payload, str) else payload
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_plugin_asset(self, path: str) -> None:
        relative = unquote(path[len("/plugins/") :]).strip("/")
        parts = [part for part in relative.split("/") if part]
        if len(parts) < 2:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        directory = parts[0]
        asset_path = "/".join(parts[1:])
        resolved = resolve_public_plugin_asset(directory, asset_path)
        if not resolved:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        _plugin_root, _manifest_path, _manifest, file_path = resolved
        body = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header(
            "Content-Type",
            mimetypes.guess_type(file_path.name)[0] or "application/octet-stream",
        )
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "public, max-age=600")
        self.end_headers()
        self.wfile.write(body)

    def serve_export(self, path: str) -> None:
        with get_connection() as conn:
            viewer = current_user_from_request(conn, self.headers, self.request_ip())
            if not viewer or not is_admin(viewer):
                self.send_error(HTTPStatus.FORBIDDEN)
                return
        relative = unquote(path[len(EXPORT_ROUTE) :]).strip("/")
        parts = [part for part in relative.split("/") if part]
        if len(parts) != 2 or parts[0] != "backups":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not re.fullmatch(r"[A-Za-z0-9._-]+", parts[1]):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        file_path = (BACKUP_DIR / parts[1]).resolve()
        if file_path.parent != BACKUP_DIR.resolve() or not file_path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Disposition", f'attachment; filename="{file_path.name}"')
        self.end_headers()
        self.wfile.write(body)

    def serve_live_stream(self, query: dict[str, list[str]]) -> None:
        thread_id = None
        raw_thread_id = (query.get("threadId") or [""])[0].strip()
        if raw_thread_id:
            try:
                thread_id = int(raw_thread_id)
            except (TypeError, ValueError):
                thread_id = None
        section_slug = (query.get("section") or [""])[0].strip()
        stream_once = (query.get("once") or [""])[0].strip().lower() in {"1", "true", "yes"}
        self.close_connection = stream_once
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Connection", "close" if stream_once else "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        last_payload = ""
        try:
            while True:
                with get_connection() as conn:
                    viewer = current_user_from_request(conn, self.headers, self.request_ip())
                    payload = get_live_snapshot(
                        conn,
                        viewer,
                        thread_id=thread_id,
                        section_slug=section_slug,
                    )
                encoded = json.dumps(payload, separators=(",", ":"))
                if encoded != last_payload:
                    message = f"retry: {LIVE_STREAM_INTERVAL_SECONDS * 1000}\nevent: snapshot\ndata: {encoded}\n\n"
                    last_payload = encoded
                else:
                    message = f'retry: {LIVE_STREAM_INTERVAL_SECONDS * 1000}\nevent: ping\ndata: {{"serverTime":"{payload["serverTime"]}"}}\n\n'
                self.wfile.write(message.encode("utf-8"))
                self.wfile.flush()
                if stream_once:
                    break
                time.sleep(LIVE_STREAM_INTERVAL_SECONDS)
        except (BrokenPipeError, ConnectionResetError, ValueError):
            return

    def handle_api(self, method: str) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        conn = get_connection()
        request_id = self.ensure_request_id()
        started = time.monotonic()
        viewer_id = None
        status = HTTPStatus.OK
        try:
            if method != "GET":
                self.enforce_same_origin()
            viewer = current_user_from_request(conn, self.headers, self.request_ip())
            viewer_id = int(viewer["id"]) if viewer else None
            if method != "GET":
                self.enforce_csrf_token(viewer, path)
            payload = self.dispatch_api(conn, method, path, query, viewer)
            status = payload.pop("__status__", HTTPStatus.OK)
            cookie_header = payload.pop("__cookie_header__", None)
            payload["requestId"] = request_id
            self.respond_json(payload, status=status, cookie_header=cookie_header)
        except APIError as exc:
            status = exc.status
            self.respond_json({"error": exc.message, "requestId": request_id}, status=status)
        except Exception as exc:  # pragma: no cover - last-resort guardrail
            status = HTTPStatus.INTERNAL_SERVER_ERROR
            append_structured_log(
                "api_exception",
                requestId=request_id,
                method=method,
                path=path,
                viewerId=viewer_id,
                error=str(exc),
            )
            self.respond_json(
                {"error": "Unexpected server error.", "detail": str(exc), "requestId": request_id},
                status=status,
            )
        finally:
            duration_ms = int((time.monotonic() - started) * 1000)
            append_structured_log(
                "api_request",
                requestId=request_id,
                method=method,
                path=path,
                status=int(status),
                durationMs=duration_ms,
                viewerId=viewer_id,
                ip=self.request_ip(),
                userAgent=self.request_user_agent()[:180],
            )
            conn.close()

    def dispatch_api(
        self,
        conn: sqlite3.Connection,
        method: str,
        path: str,
        query: dict[str, list[str]],
        viewer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        return dispatch_api_route(self, conn, method, path, query, viewer)

    def read_json(self) -> dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length > MAX_REQUEST_BYTES:
            raise APIError("That request body is too large.", HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
        raw = self.rfile.read(content_length) if content_length else b"{}"
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise APIError("Malformed JSON body.") from exc

    def respond_json(
        self,
        payload: dict[str, Any],
        status: int = HTTPStatus.OK,
        cookie_header: str | None = None,
    ) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if cookie_header:
            self.send_header("Set-Cookie", cookie_header)
        self.end_headers()
        self.wfile.write(body)

    def make_session_cookie(self, token: str, expires_at: str) -> str:
        cookie = SimpleCookie()
        cookie[SESSION_COOKIE] = token
        cookie[SESSION_COOKIE]["path"] = "/"
        cookie[SESSION_COOKIE]["httponly"] = True
        cookie[SESSION_COOKIE]["samesite"] = "Lax"
        if SECURE_COOKIES or str(self.headers.get("X-Forwarded-Proto") or "").strip().lower() == "https":
            cookie[SESSION_COOKIE]["secure"] = True
        cookie[SESSION_COOKIE]["expires"] = parse_iso(expires_at).strftime("%a, %d %b %Y %H:%M:%S GMT")
        return cookie.output(header="").strip()

    def clear_session_cookie_header(self) -> str:
        cookie = SimpleCookie()
        cookie[SESSION_COOKIE] = ""
        cookie[SESSION_COOKIE]["path"] = "/"
        cookie[SESSION_COOKIE]["httponly"] = True
        cookie[SESSION_COOKIE]["samesite"] = "Lax"
        if SECURE_COOKIES or str(self.headers.get("X-Forwarded-Proto") or "").strip().lower() == "https":
            cookie[SESSION_COOKIE]["secure"] = True
        cookie[SESSION_COOKIE]["expires"] = "Thu, 01 Jan 1970 00:00:00 GMT"
        cookie[SESSION_COOKIE]["max-age"] = 0
        return cookie.output(header="").strip()


def main() -> None:
    init_db(refresh_search_index)
    server = ThreadingHTTPServer((HOST, PORT), ForumHandler)
    print(f"OmniForum running at http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
