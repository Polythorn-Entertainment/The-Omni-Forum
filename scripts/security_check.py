#!/usr/bin/env python3
"""Run local static security checks for an OmniForum source tree."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SECRET_RE = re.compile(
    r"(discord(?:app)?\.com/api/webhooks/|xox[baprs]-|AKIA[0-9A-Z]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)",
    re.IGNORECASE,
)
SCAN_EXTENSIONS = {".py", ".js", ".html", ".css", ".md", ".sh", ".yml", ".yaml", ".toml", ".example", ".conf"}
ALLOWLIST = {
    "deploy/omniforum-healthcheck.env.example",
    "deploy/staging.env.example",
    ".env.example",
}
PILLOW_SAFE_FLOOR = (12, 2, 0)


def add(checks: list[dict[str, str]], status: str, name: str, message: str) -> None:
    checks.append({"status": status, "name": name, "message": message})


def source_files() -> list[Path]:
    ignored_parts = {".git", ".venv", "venv", "data", "__pycache__"}
    files = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in ignored_parts for part in path.relative_to(ROOT).parts):
            continue
        if path.suffix in SCAN_EXTENSIONS or path.name in {".gitignore", ".dockerignore", "Dockerfile"}:
            files.append(path)
    return files


def check_secrets(checks: list[dict[str, str]]) -> None:
    offenders = []
    for path in source_files():
        rel = str(path.relative_to(ROOT))
        if rel in ALLOWLIST:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if SECRET_RE.search(text):
            offenders.append(rel)
    if offenders:
        add(checks, "fail", "hardcoded secrets", f"Possible secrets found in: {', '.join(offenders)}")
    else:
        add(checks, "pass", "hardcoded secrets", "No obvious webhook tokens, cloud keys, or private keys found in source files.")


def check_env_and_package(checks: list[dict[str, str]]) -> None:
    if (ROOT / ".env").exists():
        add(checks, "warn", "env file", ".env exists locally; do not commit or package it.")
    else:
        add(checks, "pass", "env file", ".env is absent.")
    package_script = (ROOT / "scripts/package_release.sh").read_text(encoding="utf-8")
    required_excludes = [
        ".env",
        "deploy/omniforum-healthcheck.env",
        "deploy/omniforum-offsite-backup.env",
        "deploy/omniforum-remote-deploy.env",
        "data/*.db",
        "data/logs/*",
        "data/uploads",
    ]
    missing = [item for item in required_excludes if item not in package_script]
    if missing:
        add(checks, "fail", "package exclusions", f"Release package script is missing exclusions: {', '.join(missing)}")
    else:
        add(checks, "pass", "package exclusions", "Release package excludes env, database, log, upload, and monitor secret files.")


def check_security_defaults(checks: list[dict[str, str]]) -> None:
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    config = (ROOT / "omniforum/config.py").read_text(encoding="utf-8")
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    if "script-src 'self' 'unsafe-inline'" in app or "style-src 'self' 'unsafe-inline'" in app:
        add(checks, "fail", "csp", "CSP still permits unsafe-inline.")
    else:
        add(checks, "pass", "csp", "CSP keeps scripts and styles on self without unsafe-inline.")
    if 'EMAIL_AUTH_ENABLED = os.getenv("OMNIFORUM_EMAIL_AUTH_ENABLED", "0") == "1"' in config:
        add(checks, "pass", "email default", "Email auth is disabled by default.")
    else:
        add(checks, "fail", "email default", "Could not confirm email auth defaults to disabled.")
    if "OMNIFORUM_SECURE_COOKIES=0" in env_example:
        add(checks, "pass", "secure cookie config", ".env.example exposes the secure-cookie production switch.")
    else:
        add(checks, "warn", "secure cookie config", ".env.example should show OMNIFORUM_SECURE_COOKIES.")


def parse_version_tuple(value: str) -> tuple[int, int, int]:
    parts = [int(part) for part in value.split(".")[:3]]
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def check_dependency_floors(checks: list[dict[str, str]]) -> None:
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    match = re.search(r"(?im)^Pillow\s*>=\s*([0-9]+(?:\.[0-9]+){0,2})\s*(?:,|$)", requirements)
    if not match:
        add(checks, "fail", "dependency floors", "requirements.txt must pin Pillow with a safe lower bound.")
        return
    floor = parse_version_tuple(match.group(1))
    if floor < PILLOW_SAFE_FLOOR:
        add(checks, "fail", "dependency floors", "Pillow must be >=12.2.0 to avoid the PDF trailer loop DoS.")
        return
    add(checks, "pass", "dependency floors", "Pillow lower bound is at or above the patched 12.2.0 release.")


def render_text(result: dict[str, Any]) -> str:
    lines = [f"OmniForum security check: {result['status']}"]
    for check in result["checks"]:
        lines.append(f"- {check['status']}: {check['name']} - {check['message']}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures")
    args = parser.parse_args()

    checks: list[dict[str, str]] = []
    check_secrets(checks)
    check_env_and_package(checks)
    check_security_defaults(checks)
    check_dependency_floors(checks)

    has_fail = any(check["status"] == "fail" for check in checks)
    has_warn = any(check["status"] == "warn" for check in checks)
    status = "fail" if has_fail or (args.strict and has_warn) else ("warn" if has_warn else "pass")
    result = {"status": status, "checks": checks}
    print(json.dumps(result, indent=2) if args.json else render_text(result))
    return 0 if status in {"pass", "warn"} and not args.strict else (1 if status != "pass" else 0)


if __name__ == "__main__":
    raise SystemExit(main())
