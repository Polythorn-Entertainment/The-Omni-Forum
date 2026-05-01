from __future__ import annotations

import http.cookiejar
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def copy_workspace() -> tempfile.TemporaryDirectory[str]:
    temp_dir = tempfile.TemporaryDirectory(prefix="omniforum-tests-")
    target = Path(temp_dir.name)
    shutil.copytree(
        REPO_ROOT,
        target,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__", ".DS_Store", "*.pyc"),
    )
    for path in target.glob("data/*.db"):
        path.unlink(missing_ok=True)
    for folder in ("uploads", "logs", "exports"):
        shutil.rmtree(target / "data" / folder, ignore_errors=True)
    return temp_dir


def install_test_plugin(workspace: Path) -> None:
    plugin_dir = workspace / "plugins" / "smoke-plugin" / "client"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    (plugin_dir / "smoke.css").write_text(".smoke-plugin { color: #00d4ff; }\n", encoding="utf-8")
    (plugin_dir / "smoke.js").write_text("window.__omniforumSmokePlugin = true;\n", encoding="utf-8")
    (plugin_dir / "smoke.txt").write_text("plugin asset\n", encoding="utf-8")
    manifest = {
        "id": "smoke-plugin",
        "name": "Smoke Plugin",
        "version": "1.0.0",
        "description": "Used by the automated smoke tests.",
        "enabled": True,
        "author": "Tests",
        "client": {
            "styles": ["client/smoke.css"],
            "scripts": ["client/smoke.js"],
            "assets": ["client/smoke.txt"],
        },
    }
    (workspace / "plugins" / "smoke-plugin" / "plugin.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )


class HttpClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.csrf_token = ""

    def request(
        self,
        method: str,
        path: str,
        *,
        payload: dict | None = None,
        headers: dict[str, str] | None = None,
        expect_status: int = 200,
        parse_json: bool = True,
    ):
        body = None
        request_headers = {"Accept": "application/json"}
        if headers:
            request_headers.update(headers)
        if method.upper() not in {"GET", "HEAD", "OPTIONS"} and self.csrf_token and "X-CSRF-Token" not in request_headers:
            request_headers["X-CSRF-Token"] = self.csrf_token
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            headers=request_headers,
            method=method,
        )
        try:
            with self.opener.open(request, timeout=20) as response:
                status = response.status
                raw = response.read()
        except urllib.error.HTTPError as exc:
            with exc:
                status = exc.code
                raw = exc.read()
        text = raw.decode("utf-8", errors="replace")
        if status != expect_status:
            raise AssertionError(f"{method} {path} returned {status}, expected {expect_status}: {text}")
        if not parse_json:
            return text
        parsed = json.loads(text or "{}")
        if isinstance(parsed, dict) and "currentUser" in parsed:
            current_user = parsed.get("currentUser")
            self.csrf_token = str((current_user or {}).get("csrfToken") or "")
        return parsed


class OmniForumHarness:
    def __init__(self) -> None:
        self.temp_dir = copy_workspace()
        self.workspace = Path(self.temp_dir.name)
        install_test_plugin(self.workspace)
        self.port = free_port()
        self.base_url = f"http://127.0.0.1:{self.port}"
        self.process: subprocess.Popen[str] | None = None
        self.client = HttpClient(self.base_url)

    def start(self) -> None:
        env = os.environ.copy()
        env.update(
            {
                "OMNIFORUM_HOST": "127.0.0.1",
                "OMNIFORUM_PORT": str(self.port),
                "OMNIFORUM_PUBLIC_URL": self.base_url,
                "PYTHONUNBUFFERED": "1",
            }
        )
        self.process = subprocess.Popen(
            [sys.executable, "app.py"],
            cwd=self.workspace,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        deadline = time.time() + 30
        last_error = ""
        while time.time() < deadline:
            try:
                payload = self.client.request("GET", "/api/health", parse_json=True)
                if payload.get("ok"):
                    return
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
            time.sleep(0.2)
        output = ""
        if self.process and self.process.stdout:
            output = self.process.stdout.read()
        raise RuntimeError(f"Server did not start. Last error: {last_error}\n{output}")

    def stop(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=10)
        if self.process and self.process.stdout:
            self.process.stdout.close()
        self.temp_dir.cleanup()

    def register(
        self,
        username: str,
        password: str,
        *,
        invite_code: str = "",
        expect_status: int = 201,
        headers: dict[str, str] | None = None,
    ) -> dict:
        payload = {"username": username, "password": password}
        if invite_code:
            payload["inviteCode"] = invite_code
        return self.client.request(
            "POST",
            "/api/register",
            payload=payload,
            headers=headers,
            expect_status=expect_status,
        )

    def login(self, username: str, password: str) -> dict:
        return self.client.request("POST", "/api/login", payload={"username": username, "password": password})

    def logout(self) -> dict:
        return self.client.request("POST", "/api/logout")
