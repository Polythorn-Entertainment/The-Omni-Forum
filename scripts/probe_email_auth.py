#!/usr/bin/env python3
"""Validate optional OmniForum SMTP/email-account configuration."""

from __future__ import annotations

import argparse
import os
import smtplib
import sys
from email.message import EmailMessage
from pathlib import Path


def load_env_file(path: Path) -> None:
    if not path.exists():
        raise RuntimeError(f"env file not found: {path}")
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def enabled(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip() in {"1", "true", "TRUE", "yes", "YES"}


def redacted(value: str) -> str:
    if not value:
        return "(empty)"
    if len(value) <= 4:
        return "****"
    return f"{value[:2]}...{value[-2:]}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, help="Optional .env file to load before probing")
    parser.add_argument("--to", default="", help="Recipient for the probe email")
    parser.add_argument("--subject", default="OmniForum email probe")
    parser.add_argument("--dry-run", action="store_true", help="Validate config without connecting to SMTP")
    parser.add_argument("--timeout", type=float, default=20)
    args = parser.parse_args()

    try:
        if args.env_file:
            load_env_file(args.env_file)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if not enabled("OMNIFORUM_EMAIL_AUTH_ENABLED"):
        print("Email account features are disabled. Set OMNIFORUM_EMAIL_AUTH_ENABLED=1 to probe SMTP.")
        return 2

    host = os.getenv("OMNIFORUM_SMTP_HOST", "").strip()
    port = int(os.getenv("OMNIFORUM_SMTP_PORT", "587"))
    username = os.getenv("OMNIFORUM_SMTP_USERNAME", "").strip()
    password = os.getenv("OMNIFORUM_SMTP_PASSWORD", "")
    starttls = enabled("OMNIFORUM_SMTP_STARTTLS", "1")
    sender = os.getenv("OMNIFORUM_EMAIL_FROM", "").strip()
    recipient = args.to.strip() or os.getenv("OMNIFORUM_EMAIL_PROBE_TO", "").strip()

    missing = [
        name
        for name, value in {
            "OMNIFORUM_SMTP_HOST": host,
            "OMNIFORUM_EMAIL_FROM": sender,
            "OMNIFORUM_EMAIL_PROBE_TO or --to": recipient,
        }.items()
        if not value
    ]
    if missing:
        print(f"Missing required email probe config: {', '.join(missing)}", file=sys.stderr)
        return 2

    print(
        "SMTP config: "
        f"host={host} port={port} starttls={starttls} "
        f"username={redacted(username)} password={'set' if password else 'empty'} sender={sender} recipient={recipient}"
    )
    if args.dry_run:
        print("Dry run passed; no SMTP connection was opened.")
        return 0

    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = args.subject
    message.set_content(
        "OmniForum SMTP probe succeeded.\n\n"
        "Optional email account features should still stay hidden from users unless "
        "OMNIFORUM_EMAIL_AUTH_ENABLED=1 is set in the deployed environment.\n"
    )

    try:
        with smtplib.SMTP(host, port, timeout=args.timeout) as smtp:
            smtp.ehlo()
            if starttls:
                smtp.starttls()
                smtp.ehlo()
            if username or password:
                smtp.login(username, password)
            smtp.send_message(message)
    except Exception as exc:  # noqa: BLE001 - CLI probe should report SMTP provider errors directly.
        print(f"SMTP probe failed: {exc}", file=sys.stderr)
        return 1
    print("SMTP probe email sent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
