"""External service integrations."""

from __future__ import annotations

import json
from urllib.request import Request, urlopen

from .config import DISCORD_WEBHOOK_URL
from .core import utc_now
from .runtime_logging import append_server_log


def discord_webhook_enabled() -> bool:
    return bool(DISCORD_WEBHOOK_URL)


def send_discord_webhook(
    *,
    title: str,
    lines: list[str],
    color: int = 0x00D4FF,
) -> bool:
    if not DISCORD_WEBHOOK_URL:
        return False
    description = "\n".join(str(line).strip() for line in lines if str(line).strip()).strip()
    payload = {
        "embeds": [
            {
                "title": title[:256],
                "description": description[:4096] or "No additional details.",
                "color": color,
                "timestamp": utc_now().isoformat(),
            }
        ]
    }
    request = Request(
        DISCORD_WEBHOOK_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=4):
            return True
    except Exception as exc:  # pragma: no cover - network best-effort
        append_server_log(f"discord webhook failed: {exc}")
        return False


def send_staff_discord_notice(
    *,
    title: str,
    lines: list[str],
    color: int = 0x00D4FF,
) -> None:
    send_discord_webhook(title=title, lines=lines, color=color)
