#!/usr/bin/env python3
"""Run local OmniForum production-readiness checks."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from omniforum.migrations import validate_schema_migrations
from release_safety import scan_runtime_private_files


INLINE_STYLE_ALLOWED = "root.style.setProperty"
DEPLOY_FILES = [
    ".env.example",
    ".dockerignore",
    "Dockerfile",
    "docker-compose.yml",
    "requirements.txt",
    "requirements-dev.txt",
    "assets/manifest.json",
    "data/README.md",
    "plugins/README.md",
    "deploy/nginx-omniforum.conf",
    "deploy/caddy-omniforum.conf",
    "deploy/omniforum.service",
    "deploy/logrotate-omniforum.conf",
    "deploy/staging.env.example",
    "deploy/omniforum-healthcheck.env.example",
    "deploy/omniforum-healthcheck.service",
    "deploy/omniforum-healthcheck.timer",
    "deploy/omniforum-offsite-backup.env.example",
    "deploy/omniforum-offsite-backup.service",
    "deploy/omniforum-offsite-backup.timer",
    "deploy/omniforum-remote-deploy.env.example",
    "docs/SETUP_GUIDE.md",
    "docs/STAGING_DEPLOY.md",
    "docs/DATA_POLICY.md",
    "docs/LOCAL_SETUP.md",
    "docs/ENVIRONMENT.md",
    "docs/DEPLOYMENT.md",
    "docs/RESOURCES.md",
    "docs/TESTING.md",
    "docs/FEATURES.md",
    "docs/ARCHITECTURE.md",
    "deploy/assistant/index.html",
    "deploy/assistant/style.css",
    "deploy/assistant/app.js",
    "scripts/deploy_assistant.py",
    "scripts/release_safety.py",
    "scripts/check_release_archive.py",
    "scripts/deploy_remote.sh",
    "scripts/staging_smoke.py",
    "scripts/verify_restore.sh",
    "scripts/verify_offsite_restore.sh",
    "scripts/package_release.sh",
    "scripts/scrub_private_data.sh",
    "scripts/container_healthcheck.py",
    "scripts/healthcheck.py",
    "scripts/load_test.py",
    "scripts/probe_email_auth.py",
    "scripts/migration_status.py",
    "scripts/offsite_backup.sh",
    "scripts/security_check.py",
    "scripts/release_check.sh",
]


def add(checks: list[dict[str, str]], status: str, name: str, message: str) -> None:
    checks.append({"status": status, "name": name, "message": message})


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def check_required_files(checks: list[dict[str, str]]) -> None:
    missing = [path for path in DEPLOY_FILES if not (ROOT / path).is_file()]
    if missing:
        add(checks, "fail", "deploy files", f"Missing required production helper files: {', '.join(missing)}")
    else:
        add(checks, "pass", "deploy files", "Deploy, backup, restore, staging, and operator helper files are present.")


def check_csp_and_inline_styles(checks: list[dict[str, str]]) -> None:
    app_source = source("app.py")
    unsafe_csp = [
        token
        for token in ("script-src 'self' 'unsafe-inline'", "style-src 'self' 'unsafe-inline'")
        if token in app_source
    ]
    if unsafe_csp:
        add(checks, "fail", "csp", f"Unsafe inline CSP tokens remain: {', '.join(unsafe_csp)}")
    else:
        add(checks, "pass", "csp", "Script and style CSP no longer allow unsafe-inline.")

    offenders = []
    for folder in ("js", "pages"):
        for path in sorted((ROOT / folder).glob("*.js" if folder == "js" else "*.html")):
            text = path.read_text(encoding="utf-8").replace(INLINE_STYLE_ALLOWED, "")
            if 'style="' in text or ".style." in text:
                offenders.append(str(path.relative_to(ROOT)))
    if offenders:
        add(checks, "fail", "inline styles", f"Inline style usage remains in: {', '.join(offenders)}")
    else:
        add(checks, "pass", "inline styles", "Static inline style attributes/direct mutations are absent.")


def check_migrations(checks: list[dict[str, str]]) -> None:
    try:
        validate_schema_migrations()
    except Exception as exc:  # noqa: BLE001 - readiness report should surface registry problems plainly.
        add(checks, "fail", "migrations", f"Migration registry is invalid: {exc}")
        return
    add(checks, "pass", "migrations", "Migration registry ordering and IDs validate.")


def check_runtime_state(checks: list[dict[str, str]]) -> None:
    files = scan_runtime_private_files(ROOT)
    if files:
        preview = ", ".join(files[:8])
        suffix = f" and {len(files) - 8} more" if len(files) > 8 else ""
        add(
            checks,
            "warn",
            "runtime data",
            f"Private runtime files are present locally ({preview}{suffix}). Use the clean package or scrub script before sharing.",
        )
    else:
        add(checks, "pass", "runtime data", "No private runtime DB/log/upload/backup files were found in the source tree.")


def check_env_posture(checks: list[dict[str, str]]) -> None:
    env_path = ROOT / ".env"
    env_values = parse_env(env_path) if env_path.exists() else dict(os.environ)
    if env_path.exists():
        add(checks, "warn", "env file", ".env exists locally; review and rotate secrets before handoff.")
    else:
        add(checks, "pass", "env file", ".env is not present in the source tree.")

    public_url = env_values.get("OMNIFORUM_PUBLIC_URL", "")
    secure_cookies = env_values.get("OMNIFORUM_SECURE_COOKIES", "0")
    if public_url.startswith("https://") and secure_cookies != "1":
        add(checks, "fail", "secure cookies", "HTTPS PUBLIC_URL is configured but OMNIFORUM_SECURE_COOKIES is not 1.")
    elif public_url:
        add(checks, "pass", "secure cookies", "Cookie posture is consistent with the configured PUBLIC_URL.")
    else:
        add(checks, "warn", "secure cookies", "Set OMNIFORUM_PUBLIC_URL and OMNIFORUM_SECURE_COOKIES in production.")

    email_enabled = env_values.get("OMNIFORUM_EMAIL_AUTH_ENABLED", "0") == "1"
    smtp_ready = bool(env_values.get("OMNIFORUM_SMTP_HOST") and env_values.get("OMNIFORUM_EMAIL_FROM"))
    if email_enabled and not smtp_ready:
        add(checks, "fail", "email auth", "Email auth is enabled but SMTP host/from config is incomplete.")
    elif email_enabled:
        add(checks, "pass", "email auth", "Email auth is enabled and core SMTP config is present.")
    else:
        add(checks, "pass", "email auth", "Email auth is disabled by default, so recovery email UI remains hidden.")


def check_url(checks: list[dict[str, str]], url: str) -> None:
    if not url:
        add(checks, "warn", "remote health", "No --url provided; external HTTPS health was not probed.")
        return
    try:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "healthcheck.py"), url, "--json"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=30,
        )
    except (subprocess.SubprocessError, urllib.error.URLError) as exc:
        add(checks, "fail", "remote health", f"Healthcheck could not run: {exc}")
        return
    if result.returncode:
        add(checks, "fail", "remote health", result.stdout.strip()[:600])
    else:
        add(checks, "pass", "remote health", f"{url.rstrip('/')} passed /api/health and /api/home checks.")


def render_text(result: dict[str, Any]) -> str:
    lines = [f"OmniForum production readiness: {result['status']}"]
    for check in result["checks"]:
        lines.append(f"- {check['status']}: {check['name']} - {check['message']}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=os.getenv("OMNIFORUM_READINESS_URL", ""), help="Optional deployed base URL to probe")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures")
    args = parser.parse_args()

    checks: list[dict[str, str]] = []
    check_required_files(checks)
    check_csp_and_inline_styles(checks)
    check_migrations(checks)
    check_runtime_state(checks)
    check_env_posture(checks)
    check_url(checks, args.url)

    has_fail = any(check["status"] == "fail" for check in checks)
    has_warn = any(check["status"] == "warn" for check in checks)
    status = "fail" if has_fail or (args.strict and has_warn) else ("warn" if has_warn else "pass")
    result = {"status": status, "checks": checks}
    print(json.dumps(result, indent=2) if args.json else render_text(result))
    return 0 if status in {"pass", "warn"} and not args.strict else (1 if status != "pass" else 0)


if __name__ == "__main__":
    raise SystemExit(main())
