#!/usr/bin/env python3
"""Disposable staging smoke check for a deployed OmniForum URL.

This creates test accounts/content. Run only against a staging instance.
"""

from __future__ import annotations

import base64
import http.cookiejar
import json
import os
import sys
import time
import urllib.error
import urllib.request


PNG_DATA_URL = "data:image/png;base64," + base64.b64encode(
    base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=")
).decode("ascii")


class Client:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.csrf_token = ""

    def request(self, method: str, path: str, payload: dict | None = None, expect: int = 200) -> dict:
        headers = {"Accept": "application/json"}
        body = None
        if method.upper() not in {"GET", "HEAD", "OPTIONS"} and self.csrf_token:
            headers["X-CSRF-Token"] = self.csrf_token
        if payload is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(f"{self.base_url}{path}", data=body, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=30) as response:
                status = response.status
                text = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            status = exc.code
            text = exc.read().decode("utf-8", errors="replace")
        if status != expect:
            raise RuntimeError(f"{method} {path} returned {status}, expected {expect}: {text}")
        payload = json.loads(text or "{}")
        current_user = payload.get("currentUser") if isinstance(payload, dict) else None
        if current_user:
            self.csrf_token = str(current_user.get("csrfToken") or self.csrf_token)
        return payload


def register(client: Client, username: str, password: str) -> dict:
    return client.request("POST", "/api/register", {"username": username, "password": password}, expect=201)


def login(client: Client, username: str, password: str) -> dict:
    return client.request("POST", "/api/login", {"username": username, "password": password})


def main() -> int:
    if os.getenv("OMNIFORUM_STAGING_CONFIRM") != "yes":
        print("Refusing to create staging data without OMNIFORUM_STAGING_CONFIRM=yes.", file=sys.stderr)
        return 2
    base_url = (sys.argv[1] if len(sys.argv) > 1 else os.getenv("OMNIFORUM_STAGING_URL", "")).strip()
    if not base_url:
        print(
            "Usage: OMNIFORUM_STAGING_CONFIRM=yes scripts/staging_smoke.py https://staging.example.com", file=sys.stderr
        )
        return 2

    suffix = str(int(time.time()))
    owner_user = os.getenv("OMNIFORUM_STAGING_ADMIN_USER", f"stage_owner_{suffix}")
    owner_password = os.getenv("OMNIFORUM_STAGING_ADMIN_PASSWORD", "stage-password-123")
    member_user = f"stage_member_{suffix}"
    member_password = "stage-password-123"

    owner = Client(base_url)
    health = owner.request("GET", "/api/health")
    if not health.get("ok"):
        raise RuntimeError("Health check did not return ok=true.")
    owner.request("GET", "/api/home")

    if os.getenv("OMNIFORUM_STAGING_ADMIN_USER"):
        login(owner, owner_user, owner_password)
    else:
        registered = register(owner, owner_user, owner_password)
        if registered.get("currentUser", {}).get("role") != "owner":
            raise RuntimeError(
                "No admin credentials were provided and the staging instance was not clean enough to create the first owner."
            )

    thread = owner.request(
        "POST",
        "/api/sections/s-general",
        {
            "title": f"Staging Smoke Thread {suffix}",
            "content": "Staging smoke test with an uploaded image.",
            "mediaUploads": [{"name": "staging-smoke.png", "alt": "Staging smoke pixel", "dataUrl": PNG_DATA_URL}],
        },
    )
    thread_id = int(thread["thread"]["id"])

    member = Client(base_url)
    register(member, member_user, member_password)
    member.request(
        "POST",
        f"/api/threads/{thread_id}/posts",
        {"content": "Staging reply from a second account."},
    )
    member.request(
        "POST",
        "/api/reports",
        {
            "targetType": "thread",
            "targetId": thread_id,
            "reason": "Staging smoke",
            "details": "Report created by the staging smoke script.",
        },
    )

    reports = owner.request("GET", "/api/reports")
    report_id = int(reports["items"][0]["id"])
    owner.request(
        "PATCH", f"/api/reports/{report_id}", {"status": "resolved", "adminNote": "Resolved by staging smoke."}
    )
    backup = owner.request("POST", "/api/admin/backup")
    owner.request("GET", f"/api/admin/backups/guide?file={backup['filename']}")
    owner.request("GET", "/api/admin/health")
    print(f"Staging smoke passed for {base_url}")
    print(f"Thread: {base_url}/pages/thread.html?thread={thread_id}")
    print(f"Backup: {backup['filename']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
