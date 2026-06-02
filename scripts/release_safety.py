"""Shared release/runtime privacy checks for OmniForum helper scripts."""

from __future__ import annotations

import re
import tarfile
from pathlib import Path


PRIVATE_RUNTIME_PATTERNS = [
    "data/*.db",
    "data/*.db-*",
    "data/logs/*",
    "data/exports/backups/*",
    "data/uploads/avatars/*",
    "data/uploads/posts/*",
    "data/uploads/thumbs/*",
    ".env",
    "deploy/omniforum-healthcheck.env",
    "deploy/omniforum-offsite-backup.env",
    "deploy/omniforum-remote-deploy.env",
]

ARCHIVE_LEAK_RE = re.compile(
    r"(^\./data/.*\.db|server\.log|access\.log|app\.jsonl|uploads/avatars/.*gif|"
    r"(^|/)\.env$|deploy/omniforum-healthcheck\.env$|deploy/omniforum-offsite-backup\.env$|"
    r"deploy/omniforum-remote-deploy\.env$|data/exports/backups|__pycache__|\.DS_Store|\.pyc$)"
)


def scan_runtime_private_files(root: Path) -> list[str]:
    files: list[str] = []
    for pattern in PRIVATE_RUNTIME_PATTERNS:
        for path in root.glob(pattern):
            if path.name == ".gitkeep":
                continue
            if path.is_file():
                files.append(str(path.relative_to(root)))
    return sorted(files)


def scan_release_archive(archive: Path) -> list[str]:
    leaks: list[str] = []
    with tarfile.open(archive, "r:gz") as package:
        for member in package.getmembers():
            if ARCHIVE_LEAK_RE.search(member.name):
                leaks.append(member.name)
    return leaks
