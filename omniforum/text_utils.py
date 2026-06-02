"""Text formatting helpers."""

from __future__ import annotations

import re
from typing import Any


def short_preview(text: Any, *, max_len: int = 180) -> str:
    preview = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(preview) <= max_len:
        return preview
    return f"{preview[: max_len - 3].rstrip()}..."
