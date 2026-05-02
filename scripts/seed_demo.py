#!/usr/bin/env python3
"""Seed a local OmniForum instance with non-private demo content.

Run OmniForum first, ideally after `scripts/reset_runtime_data.sh`, then run:

    python3 scripts/seed_demo.py http://127.0.0.1:8000
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from urllib.request import HTTPCookieProcessor, build_opener


BASE_URL = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
PASSWORD = "demo-password-123"


class Client:
    def __init__(self) -> None:
        self.csrf_token = ""
        self.opener = build_opener(HTTPCookieProcessor(CookieJar()))

    def request(self, method: str, path: str, payload: dict | None = None, expect: int | None = None) -> dict:
        body = json.dumps(payload or {}).encode("utf-8") if payload is not None else None
        headers = {"Accept": "application/json"}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        if method not in {"GET", "HEAD", "OPTIONS"} and self.csrf_token:
            headers["X-CSRF-Token"] = self.csrf_token
        request = urllib.request.Request(BASE_URL + path, data=body, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=15) as response:
                status = response.status
                raw = response.read()
        except urllib.error.HTTPError as exc:
            status = exc.code
            raw = exc.read()
        if expect is not None and status != expect:
            raise RuntimeError(f"{method} {path} returned {status}: {raw.decode('utf-8', errors='replace')}")
        parsed = json.loads(raw.decode("utf-8") or "{}")
        user = parsed.get("currentUser") if isinstance(parsed, dict) else None
        if user:
            self.csrf_token = str(user.get("csrfToken") or self.csrf_token)
        return parsed


def register(client: Client, username: str) -> dict:
    return client.request("POST", "/api/register", {"username": username, "password": PASSWORD}, expect=201)


def login(client: Client, username: str) -> dict:
    return client.request("POST", "/api/login", {"username": username, "password": PASSWORD}, expect=200)


def logout(client: Client) -> None:
    client.request("POST", "/api/logout", {}, expect=200)
    client.csrf_token = ""


def main() -> None:
    owner = Client()
    register(owner, "demo_owner")
    owner.request(
        "PATCH",
        "/api/admin/site-settings",
        {
            "siteName": "OmniForum Demo",
            "logoText": "OmniForum Demo",
            "heroTitle": "OmniForum Demo",
            "heroSubtitle": "A seeded local forum for screenshots, QA, and onboarding.",
            "defaultTheme": "seaglass",
        },
        expect=200,
    )
    thread_ids: list[int] = []
    demo_threads = [
        ("Welcome to the demo forum", "Use this space to test posting, replies, search, and moderation workflows.", "welcome, demo"),
        ("Share your current project", "What are you building, learning, or trying to improve this week?", "projects, community"),
        ("Support desk sample", "This thread is marked as a support-style discussion for staff workflow testing.", "support, qa"),
    ]
    for title, content, tags in demo_threads:
        created = owner.request(
            "POST",
            "/api/sections/s-general",
            {"title": title, "content": content, "tags": tags},
            expect=200,
        )
        thread_ids.append(int(created["thread"]["id"]))

    logout(owner)
    member = Client()
    register(member, "demo_member")
    member.request(
        "POST",
        f"/api/threads/{thread_ids[0]}/posts",
        {"content": "This is a seeded reply from a regular member account."},
        expect=200,
    )
    member.request(
        "POST",
        "/api/reports",
        {
            "targetType": "thread",
            "targetId": thread_ids[1],
            "reason": "Demo moderation report",
            "details": "Seeded report for staff queue screenshots.",
        },
        expect=200,
    )
    logout(member)

    login(owner, "demo_owner")
    owner.request("POST", "/api/admin/backup", {}, expect=200)
    print(f"Seeded demo content at {BASE_URL}")
    print("Demo users:")
    print(f"  demo_owner / {PASSWORD}")
    print(f"  demo_member / {PASSWORD}")


if __name__ == "__main__":
    main()
