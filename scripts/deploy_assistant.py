#!/usr/bin/env python3
"""Local browser app for preparing and checking OmniForum deployments."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import time
import urllib.parse
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from release_safety import scan_release_archive, scan_runtime_private_files


ASSISTANT_OUT_DIR = Path(os.getenv("OMNIFORUM_DEPLOY_ASSISTANT_OUT", "/tmp/omniforum-deploy-assistant"))
SECRET_ENV_FILES = {
    "runtime": ROOT / ".env",
    "remote": ROOT / "deploy" / "omniforum-remote-deploy.env",
    "healthcheck": ROOT / "deploy" / "omniforum-healthcheck.env",
    "offsite": ROOT / "deploy" / "omniforum-offsite-backup.env",
}
SAFE_ACTIONS = {"readiness", "security", "package", "healthcheck", "load"}
LONG_ACTIONS = {"release_check"}


def bool_env(value: Any) -> str:
    return "1" if str(value).lower() in {"1", "true", "yes", "on"} else "0"


def clean_value(value: Any) -> str:
    text = str(value or "").strip()
    return text.replace("\r", "").replace("\n", "")


def env_line(key: str, value: Any) -> str:
    text = clean_value(value)
    if not text or re.fullmatch(r"[A-Za-z0-9_./:@%+=,-]+", text):
        return f"{key}={text}"
    return f"{key}={shlex.quote(text)}"


def build_env_content(kind: str, payload: dict[str, Any]) -> str:
    if kind == "runtime":
        lines = [
            env_line("OMNIFORUM_HOST", payload.get("host") or "127.0.0.1"),
            env_line("OMNIFORUM_PORT", payload.get("port") or "8000"),
            env_line("OMNIFORUM_PUBLIC_URL", payload.get("publicUrl") or "http://127.0.0.1:8000"),
            env_line("OMNIFORUM_SECURE_COOKIES", bool_env(payload.get("secureCookies"))),
            "",
            env_line("OMNIFORUM_MAX_REQUEST_BYTES", payload.get("maxRequestBytes") or "50331648"),
            env_line("OMNIFORUM_BACKUP_ROTATION", payload.get("backupRotation") or "8"),
            env_line("OMNIFORUM_BACKUP_STALE_HOURS", payload.get("backupStaleHours") or "168"),
            env_line("OMNIFORUM_LIVE_INTERVAL_SECONDS", payload.get("liveIntervalSeconds") or "5"),
            env_line("OMNIFORUM_USER_MEDIA_LIMIT_BYTES", payload.get("userMediaLimitBytes") or "67108864"),
            env_line("OMNIFORUM_USER_MEDIA_LIMIT_FILES", payload.get("userMediaLimitFiles") or "80"),
            "",
            env_line("OMNIFORUM_MEDIA_SCAN_COMMAND", payload.get("mediaScanCommand") or ""),
            env_line("OMNIFORUM_MEDIA_SCAN_REQUIRED", bool_env(payload.get("mediaScanRequired"))),
            env_line("OMNIFORUM_MEDIA_SCAN_TIMEOUT_SECONDS", payload.get("mediaScanTimeoutSeconds") or "20"),
            "",
            "# Email account features are hidden unless this is 1 and SMTP is configured.",
            env_line("OMNIFORUM_EMAIL_AUTH_ENABLED", bool_env(payload.get("emailAuthEnabled"))),
            env_line("OMNIFORUM_EMAIL_FROM", payload.get("emailFrom") or ""),
            env_line("OMNIFORUM_SMTP_HOST", payload.get("smtpHost") or ""),
            env_line("OMNIFORUM_SMTP_PORT", payload.get("smtpPort") or "587"),
            env_line("OMNIFORUM_SMTP_USERNAME", payload.get("smtpUsername") or ""),
            env_line("OMNIFORUM_SMTP_PASSWORD", payload.get("smtpPassword") or ""),
            env_line("OMNIFORUM_SMTP_STARTTLS", bool_env(payload.get("smtpStarttls", "1"))),
            "",
            env_line("OMNIFORUM_DISCORD_WEBHOOK_URL", payload.get("discordWebhookUrl") or ""),
        ]
    elif kind == "remote":
        lines = [
            "# Source this file locally before running scripts/deploy_remote.sh.",
            env_line("OMNIFORUM_DEPLOY_HOST", payload.get("deployHost") or "forum.example.com"),
            env_line("OMNIFORUM_DEPLOY_USER", payload.get("deployUser") or "deploy"),
            env_line("OMNIFORUM_DEPLOY_PATH", payload.get("deployPath") or "/var/www/omniforum"),
            env_line("OMNIFORUM_DEPLOY_SERVICE", payload.get("deployService") or "omniforum"),
            env_line("OMNIFORUM_DEPLOY_PUBLIC_URL", payload.get("deployPublicUrl") or "https://forum.example.com"),
            env_line("OMNIFORUM_DEPLOY_SSH_OPTS", payload.get("deploySshOpts") or ""),
            env_line("OMNIFORUM_DEPLOY_SSH_BIN", payload.get("deploySshBin") or "ssh"),
            env_line("OMNIFORUM_DEPLOY_SCP_BIN", payload.get("deployScpBin") or "scp"),
            env_line("OMNIFORUM_DEPLOY_INSTALL_DEPS", bool_env(payload.get("deployInstallDeps", "1"))),
            env_line("OMNIFORUM_DEPLOY_RESTART_SERVICE", bool_env(payload.get("deployRestartService", "1"))),
            env_line("OMNIFORUM_DEPLOY_RUN_READINESS", bool_env(payload.get("deployRunReadiness", "1"))),
        ]
    elif kind == "healthcheck":
        lines = [
            env_line("OMNIFORUM_HEALTHCHECK_URL", payload.get("healthcheckUrl") or "https://forum.example.com"),
            env_line("OMNIFORUM_HEALTHCHECK_WEBHOOK_URL", payload.get("healthcheckWebhookUrl") or ""),
            env_line("OMNIFORUM_HEALTHCHECK_TIMEOUT", payload.get("healthcheckTimeout") or "10"),
        ]
    elif kind == "offsite":
        lines = [
            "# Examples: local:/srv/omniforum-offsite, rclone:remote:path, s3://bucket/prefix, rsync:user@host:/path",
            env_line("OMNIFORUM_OFFSITE_BACKUP_TARGET", payload.get("offsiteTarget") or ""),
            env_line("OMNIFORUM_BACKUP_ENCRYPTION_PASSWORD_FILE", payload.get("backupPasswordFile") or ""),
            env_line("OMNIFORUM_BACKUP_ENCRYPTION_PASSWORD", payload.get("backupPassword") or ""),
            env_line("OMNIFORUM_BACKUP_ROTATION", payload.get("backupRotation") or "8"),
        ]
    else:
        raise ValueError(f"Unknown env kind: {kind}")
    return "\n".join(lines).rstrip() + "\n"


def write_env_file(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    path = SECRET_ENV_FILES.get(kind)
    if not path:
        raise ValueError(f"Unknown env kind: {kind}")
    path.parent.mkdir(parents=True, exist_ok=True)
    content = build_env_content(kind, payload)
    path.write_text(content, encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return {"ok": True, "path": str(path), "message": f"Wrote {path.relative_to(ROOT)}"}


def runtime_private_files() -> list[str]:
    return scan_runtime_private_files(ROOT)


def latest_package(directory: Path = ASSISTANT_OUT_DIR) -> str:
    packages = sorted(directory.glob("omniforum-source-*.tar.gz")) if directory.exists() else []
    return str(packages[-1]) if packages else ""


def command_available(name: str) -> bool:
    return subprocess.run(["/usr/bin/env", "sh", "-lc", f"command -v {shlex.quote(name)} >/dev/null 2>&1"]).returncode == 0


def collect_status() -> dict[str, Any]:
    return {
        "root": str(ROOT),
        "runtimePrivateFiles": runtime_private_files(),
        "latestPackage": latest_package(),
        "envFiles": {kind: path.exists() for kind, path in SECRET_ENV_FILES.items()},
        "dockerAvailable": command_available("docker"),
        "hasDockerfile": (ROOT / "Dockerfile").is_file(),
        "hasCompose": (ROOT / "docker-compose.yml").is_file(),
        "deployCommand": deploy_command(),
    }


def run_command(command: list[str], timeout: int = 120) -> dict[str, Any]:
    started = time.monotonic()
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        timeout=timeout,
    )
    return {
        "ok": result.returncode == 0,
        "returnCode": result.returncode,
        "elapsedMs": round((time.monotonic() - started) * 1000, 1),
        "command": " ".join(shlex.quote(part) for part in command),
        "output": result.stdout,
    }


def build_package() -> dict[str, Any]:
    ASSISTANT_OUT_DIR.mkdir(parents=True, exist_ok=True)
    result = run_command([str(ROOT / "scripts" / "package_release.sh"), str(ROOT), str(ASSISTANT_OUT_DIR)], timeout=120)
    archive = Path(latest_package())
    leaks = scan_release_archive(archive) if archive.exists() else ["package was not created"]
    result["archive"] = str(archive) if archive.exists() else ""
    result["leaks"] = leaks
    result["ok"] = bool(result["ok"] and archive.exists() and not leaks)
    if leaks:
        result["output"] += "\nPackage leak scan failed:\n" + "\n".join(leaks)
    else:
        result["output"] += f"\nPackage leak scan passed: {archive}\n"
    return result


def deploy_command() -> str:
    return (
        "set -a; . deploy/omniforum-remote-deploy.env; set +a\n"
        "OMNIFORUM_DEPLOY_CONFIRM=yes scripts/deploy_remote.sh"
    )


def run_action(action: str, payload: dict[str, Any]) -> dict[str, Any]:
    if action == "readiness":
        command = [sys.executable, str(ROOT / "scripts" / "production_readiness.py"), "--json"]
        url = clean_value(payload.get("url"))
        if url:
            command.extend(["--url", url])
        return run_command(command, timeout=90)
    if action == "security":
        return run_command([sys.executable, str(ROOT / "scripts" / "security_check.py"), "--json"], timeout=90)
    if action == "package":
        return build_package()
    if action == "healthcheck":
        url = clean_value(payload.get("url"))
        if not url:
            return {"ok": False, "output": "Provide a deployed URL before running healthcheck."}
        return run_command([sys.executable, str(ROOT / "scripts" / "healthcheck.py"), url, "--json"], timeout=45)
    if action == "load":
        url = clean_value(payload.get("url"))
        if not url:
            return {"ok": False, "output": "Provide a deployed URL before running load test."}
        return run_command(
            [
                sys.executable,
                str(ROOT / "scripts" / "load_test.py"),
                url,
                "--requests",
                clean_value(payload.get("requests")) or "40",
                "--concurrency",
                clean_value(payload.get("concurrency")) or "8",
                "--json",
            ],
            timeout=90,
        )
    if action == "release_check":
        return run_command([str(ROOT / "scripts" / "release_check.sh")], timeout=900)
    if action == "scrub":
        if clean_value(payload.get("confirm")) != "SCRUB":
            return {"ok": False, "output": "Type SCRUB to confirm runtime data deletion."}
        env = os.environ.copy()
        env["OMNIFORUM_CONFIRM_SCRUB"] = "yes"
        started = time.monotonic()
        result = subprocess.run(
            [str(ROOT / "scripts" / "scrub_private_data.sh"), str(ROOT)],
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=120,
        )
        return {
            "ok": result.returncode == 0,
            "returnCode": result.returncode,
            "elapsedMs": round((time.monotonic() - started) * 1000, 1),
            "command": "OMNIFORUM_CONFIRM_SCRUB=yes scripts/scrub_private_data.sh",
            "output": result.stdout,
        }
    raise ValueError(f"Unknown action: {action}")


ASSISTANT_ASSET_DIR = ROOT / "deploy" / "assistant"


def read_assistant_asset(name: str) -> bytes:
    path = (ASSISTANT_ASSET_DIR / name).resolve()
    if ASSISTANT_ASSET_DIR.resolve() not in path.parents and path != ASSISTANT_ASSET_DIR.resolve():
        raise FileNotFoundError(name)
    if not path.is_file():
        raise FileNotFoundError(name)
    return path.read_bytes()


class DeployAssistantHandler(BaseHTTPRequestHandler):
    server_version = "OmniForumDeployAssistant/1.0"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        print(f"[deploy-assistant] {self.address_string()} - {format % args}")

    def json_response(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or "0")
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        payload = json.loads(raw or "{}")
        if not isinstance(payload, dict):
            raise ValueError("Expected JSON object.")
        return payload

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/":
            raw = read_assistant_asset("index.html")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)
            return
        if parsed.path.startswith("/assistant/"):
            name = parsed.path.removeprefix("/assistant/")
            content_type = {
                ".css": "text/css; charset=utf-8",
                ".js": "application/javascript; charset=utf-8",
                ".html": "text/html; charset=utf-8",
            }.get(Path(name).suffix, "application/octet-stream")
            try:
                raw = read_assistant_asset(name)
            except FileNotFoundError:
                self.json_response({"error": "Not found"}, HTTPStatus.NOT_FOUND)
                return
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)
            return
        if parsed.path == "/api/status":
            self.json_response(collect_status())
            return
        self.json_response({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        try:
            payload = self.read_json()
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path == "/api/write-env":
                kind = clean_value(payload.get("kind"))
                env_payload = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
                self.json_response(write_env_file(kind, env_payload))
                return
            if parsed.path == "/api/run":
                action = clean_value(payload.get("action"))
                action_payload = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
                self.json_response(run_action(action, action_payload))
                return
            self.json_response({"error": "Not found"}, HTTPStatus.NOT_FOUND)
        except Exception as exc:  # noqa: BLE001 - show local operator errors in the assistant UI.
            self.json_response({"error": str(exc)}, HTTPStatus.BAD_REQUEST)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--allow-remote", action="store_true", help="Allow binding to non-loopback hosts")
    parser.add_argument("--open", action="store_true", help="Open the assistant in the default browser")
    args = parser.parse_args()

    if args.host not in {"127.0.0.1", "localhost", "::1"} and not args.allow_remote:
        print("Refusing to bind outside localhost without --allow-remote.", file=sys.stderr)
        return 2

    server = ThreadingHTTPServer((args.host, args.port), DeployAssistantHandler)
    url = f"http://{args.host}:{args.port}/"
    print(f"OmniForum Deployment Assistant running at {url}")
    print("Press Ctrl+C to stop.")
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
